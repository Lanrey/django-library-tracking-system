import logging

from django.db import connection
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .models import Author, Book, Member, Loan
from .serializers import AuthorSerializer, BookSerializer, MemberSerializer, LoanSerializer
from .tasks import (
    batch_process_loan_returns,
    check_low_inventory,
    fetch_book_metadata,
    generate_monthly_report,
    send_loan_notification,
    send_overdue_reminders,
)

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination class for API endpoints.
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

logger = logging.getLogger(__name__)


class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination class for API endpoints.
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AuthorViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Author model with optimized query.
    Uses prefetch_related to optimize reverse ForeignKey lookups for books.
    """
    serializer_class = AuthorSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """
        Optimize queryset with prefetch_related for books.
        Reduces N+1 queries when accessing author.books.all()
        """
        queryset = Author.objects.prefetch_related('books')

        # Log query count for monitoring
        logger.debug(f"Author queryset queries: {len(connection.queries)}")

        return queryset


class BookViewSet(viewsets.ModelViewSet):
    """
    Optimized ViewSet for Book model.
    Uses select_related to fetch related Author data in a single query,
    preventing N+1 query problems.
    """
    serializer_class = BookSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """
        Optimize queryset using select_related for author (ForeignKey).
        This performs a SQL JOIN and includes author data in the initial query,
        reducing database hits from O(n) to O(1) for author access.

        Before optimization:
        - 1 query to fetch books
        - N queries to fetch each book's author (N+1 problem)

        After optimization:
        - 1 query with JOIN to fetch books and authors together
        """
        queryset = Book.objects.select_related('author')

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

    @action(detail=True, methods=['post'])
    def loan(self, request, pk=None):
        book = self.get_object()
        if book.available_copies < 1:
            return Response({'error': 'No available copies.'}, status=status.HTTP_400_BAD_REQUEST)
        member_id = request.data.get('member_id')
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            return Response({'error': 'Member does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan = Loan.objects.create(book=book, member=member)
        book.available_copies -= 1
        book.save()
        send_loan_notification.delay(loan.id)
        return Response({'status': 'Book loaned successfully.'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def return_book(self, request, pk=None):
        book = self.get_object()
        member_id = request.data.get('member_id')
        try:
            loan = Loan.objects.get(book=book, member__id=member_id, is_returned=False)
        except Loan.DoesNotExist:
            return Response({'error': 'Active loan does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan.is_returned = True
        loan.return_date = timezone.now().date()
        loan.save()
        book.available_copies += 1
        book.save()
        return Response({'status': 'Book returned successfully.'}, status=status.HTTP_200_OK)

class MemberViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Member model with optimized query.
    Uses select_related for user and prefetch_related for loans.
    """
    serializer_class = MemberSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """
        Optimize queryset with select_related for user (OneToOne)
        and prefetch_related for loans (reverse ForeignKey).
        """
        queryset = Member.objects.select_related('user').prefetch_related(
            Prefetch(
                'loans',
                queryset=Loan.objects.select_related('book', 'book__author')
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
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """
        Optimize queryset using select_related for all ForeignKey relationships.
        Fetches book, book.author, member, and member.user in a single query.

        This is crucial for loan listings where you typically want to display:
        - Book title
        - Author name
        - Member name
        - User email

        Without optimization: 1 + (3 * N) queries
        With optimization: 1 query with multiple JOINs
        """
        queryset = Loan.objects.select_related(
            'book',
            'book__author',
            'member',
            'member__user'
        )

        # Add filtering options
        if self.request and self.request.query_params:
            is_returned = self.request.query_params.get('is_returned')
            if is_returned is not None:
                queryset = queryset.filter(
                    is_returned=is_returned.lower() == 'true'
                )

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

    @action(detail=False, methods=['post'])
    def batch_return(self, request):
        """
        Batch process loan returns.
        POST /api/loans/batch_return/
        Body: {"loan_ids": [1, 2, 3]}
        """
        loan_ids = request.data.get('loan_ids', [])
        if not loan_ids:
            return Response(
                {'error': 'loan_ids is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        task = batch_process_loan_returns.delay(loan_ids)
        return Response(
            {
                'status': 'Task queued',
                'task_id': task.id,
                'message': f'Processing {len(loan_ids)} loan returns'
            },
            status=status.HTTP_202_ACCEPTED
        )


@api_view(['POST'])
def trigger_overdue_reminders(request):
    """
    Manually trigger overdue reminders task.
    POST /api/tasks/overdue-reminders/
    """
    task = send_overdue_reminders.delay()
    return Response(
        {
            'status': 'Task queued',
            'task_id': task.id,
            'message': 'Overdue reminders task triggered'
        },
        status=status.HTTP_202_ACCEPTED
    )


@api_view(['POST'])
def trigger_monthly_report(request):
    """
    Manually trigger monthly report generation.
    POST /api/tasks/monthly-report/
    """
    task = generate_monthly_report.delay()
    return Response(
        {
            'status': 'Task queued',
            'task_id': task.id,
            'message': 'Monthly report generation triggered'
        },
        status=status.HTTP_202_ACCEPTED
    )


@api_view(['POST'])
def trigger_inventory_check(request):
    """
    Manually trigger low inventory check.
    POST /api/tasks/inventory-check/
    """
    task = check_low_inventory.delay()
    return Response(
        {
            'status': 'Task queued',
            'task_id': task.id,
            'message': 'Inventory check triggered'
        },
        status=status.HTTP_202_ACCEPTED
    )


@api_view(['POST'])
def fetch_metadata(request):
    """
    Fetch book metadata from external API.
    POST /api/tasks/fetch-metadata/
    Body: {"isbn": "1234567890123", "book_id": 1}
    """
    isbn = request.data.get('isbn')
    book_id = request.data.get('book_id')

    if not isbn or not book_id:
        return Response(
            {'error': 'isbn and book_id are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    task = fetch_book_metadata.delay(isbn, book_id)
    return Response(
        {
            'status': 'Task queued',
            'task_id': task.id,
            'message': f'Fetching metadata for ISBN: {isbn}'
        },
        status=status.HTTP_202_ACCEPTED
    )