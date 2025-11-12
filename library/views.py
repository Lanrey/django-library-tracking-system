import logging

from django.db import connection
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from .models import Author, Book, Member, Loan
from .serializers import (
    AuthorSerializer,
    BookSerializer,
    MemberSerializer,
    LoanSerializer,
)
from .tasks import (
    send_loan_notification,
    check_overdue_loans,
)

logger = logging.getLogger(__name__)


class AuthorViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Author model with optimized query.
    """

    serializer_class = AuthorSerializer

    def get_queryset(self):
        """
        Optimize queryset with prefetch_related for books.
        """
        queryset = Author.objects.prefetch_related("books")

        # Log query count for monitoring
        logger.debug(f"Author queryset queries: {len(connection.queries)}")

        return queryset


class BookViewSet(viewsets.ModelViewSet):
    """
    Optimized ViewSet for Book model.
    """

    serializer_class = BookSerializer

    def get_queryset(self):
        """
        Optimize queryset using select_related for author (ForeignKey).
        """
        queryset = Book.objects.select_related("author")

        # Log query count for debugging
        initial_queries = len(connection.queries)
        logger.debug(f"BookViewSet initial queries: {initial_queries}")

        return queryset

    def list(self, request, *args, **kwargs):
        """
        Override list to log query performance.
        """
        initial_query_count = len(connection.queries)
        response = super().list(request, *args, **kwargs)
        final_query_count = len(connection.queries)

        queries_executed = final_query_count - initial_query_count
        logger.info(
            f"BookViewSet.list executed {queries_executed} queries "
            f"for {len(response.data.get('results', []))} books"
        )

        return response

    @action(detail=True, methods=["post"])
    def loan(self, request, pk=None):
        book = self.get_object()
        if book.available_copies < 1:
            return Response(
                {"error": "No available copies."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        member_id = request.data.get("member_id")
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            return Response(
                {"error": "Member does not exist."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        loan = Loan.objects.create(book=book, member=member)
        book.available_copies -= 1
        book.save()
        send_loan_notification.delay(loan.id)
        return Response(
            {"status": "Book loaned successfully."}, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def return_book(self, request, pk=None):
        book = self.get_object()
        member_id = request.data.get("member_id")
        try:
            loan = Loan.objects.get(book=book, member__id=member_id, is_returned=False)
        except Loan.DoesNotExist:
            return Response(
                {"error": "Active loan does not exist."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        loan.is_returned = True
        loan.return_date = timezone.now().date()
        loan.save()
        book.available_copies += 1
        book.save()
        return Response(
            {"status": "Book returned successfully."}, status=status.HTTP_200_OK
        )


class MemberViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Member model with optimized query.
    Uses select_related for user and prefetch_related for loans.
    """

    serializer_class = MemberSerializer

    def get_queryset(self):
        """
        Optimize queryset with select_related for user (OneToOne)
        and prefetch_related for loans (reverse ForeignKey).
        """
        queryset = Member.objects.select_related("user").prefetch_related(
            Prefetch(
                "loans", queryset=Loan.objects.select_related("book", "book__author")
            )
        )

        logger.debug(f"MemberViewSet queries: {len(connection.queries)}")

        return queryset


class LoanViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Loan model with optimized query.
    Uses select_related for book, member, and author relationships.
    """

    serializer_class = LoanSerializer

    def get_queryset(self):
        """
        Optimize queryset using select_related for all ForeignKey relationships.
        Fetches book, book.author, member, and member.user in a single query.
        """
        queryset = Loan.objects.select_related(
            "book", "book__author", "member", "member__user"
        )

        # Add filtering options
        if self.request and self.request.content_params:
            is_returned = self.request.content_params.get("is_returned")
            if is_returned is not None:
                queryset = queryset.filter(is_returned=is_returned.lower() == "true")

        logger.debug(f"LoanViewSet queries: {len(connection.queries)}")

        return queryset

    def list(self, request, *args, **kwargs):
        """
        Override list to log query performance.
        """
        initial_query_count = len(connection.queries)
        response = super().list(request, *args, **kwargs)
        final_query_count = len(connection.queries)

        queries_executed = final_query_count - initial_query_count
        logger.info(
            f"LoanViewSet.list executed {queries_executed} queries "
            f"for {len(response.data.get('results', []))} loans"
        )

        return response

    @action(detail=True, methods=["post"])
    def extend_due_date(self, request):
        """
        Extend the due date of a loan by a specified number of days.
        POST /api/loans/{loan_id}/extend_due_date/
        """
        loan = self.get_object()

        if loan.is_overdue:
            return Response(
                {"error": "Cannot extend due date for an overdue loan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if loan.is_returned:
            return Response(
                {"error": "Cannot extend due date for a returned loan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        additional_days = request.data.get("additional_days")

        if additional_days is None:
            return Response(
                {"error": "additional_days is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            additional_days = int(additional_days)
        except (ValueError, TypeError):
            return Response(
                {"error": "additional_days must be a valid integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if additional_days <= 0:
            return Response(
                {"error": "additional_days must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        loan.extension_days += additional_days
        loan.save()

        check_overdue_loans.delay()

        serializer = self.get_serializer(loan)

        logger.info(
            f"Loan {loan.id} due date extended by {additional_days} days. "
            f"New due date: {loan.due_date}"
        )

        return Response(
            {
                "status": "Due date extended successfully.",
                "loan": serializer.data,
                "new_due_date": loan.due_date,
            },
            status=status.HTTP_200_OK,
        )
