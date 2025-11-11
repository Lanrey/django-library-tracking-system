from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django.utils import timezone
from rest_framework.pagination import Paginator

from .models import Author, Book, Member, Loan
from .serializers import AuthorSerializer, BookSerializer, MemberSerializer, LoanSerializer
from .tasks import (
 
    generate_monthly_report,
    send_loan_notification,
    send_overdue_reminders,
)

class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer

class LargeResultsSetPagination(Paginator.PageNumberPagination):
    page_size = 1000
    page_size_query_param = 'page_size'
    max_page_size = 10000

class BookViewSet(viewsets.ModelViewSet):

    queryset = Book.objects.all()
     # 10 books per page
    serializer_class = BookSerializer
    pagination_class = LargeResultsSetPagination

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
    queryset = Member.objects.all()
    serializer_class = MemberSerializer

class LoanViewSet(viewsets.ModelViewSet):
    queryset = Loan.objects.all()
    serializer_class = LoanSerializer

    @action(detail=False, methods= ['post'])
    def extend_due_date(self, request):
        """
        Extend due date for a loan.
        POST /api/loans/{loans_id}/extend_due_date
        Body: {"loan_id": 1, "extra_days": 7}
        """
        loan_id = request.data.get('loan_id')
        additional_days = request.data.get('additional_days', 7)

        try:
            loan = Loan.objects.get(id=loan_id)
        except Loan.DoesNotExist:
            return Response(
                {'error': 'Loan does not exist'},
                status=status.HTTP_400_BAD_REQUEST
            )

        loan.due_date += timezone.timedelta(days=additional_days)
        loan.save()

        send_overdue_reminders.delay()

        return Response(
            {
                'status': 'Due date extended',
                'new_due_date': loan.due_date
            },
            status=status.HTTP_200_OK
        )

    