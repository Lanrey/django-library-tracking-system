"""
Comprehensive test suite for Celery tasks.
Demonstrates TDD practices, mocking, and coverage.
"""
from datetime import date, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from django.contrib.auth.models import User
from django.core import mail

from library.models import Author, Book, Loan, Member
from library.tasks import (
    send_loan_notification,
    send_overdue_reminders,
)


@pytest.mark.django_db
@pytest.mark.unit
class TestSendLoanNotification:
    """Test suite for send_loan_notification task."""

    def test_send_notification_success(self, sample_loan):
        """Test successful loan notification sending."""
        result = send_loan_notification(sample_loan.id)

        assert result["status"] == "success"
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "Book Loaned Successfully"
        assert sample_loan.member.user.email in mail.outbox[0].to

    def test_send_notification_loan_not_found(self):
        """Test notification when loan doesn't exist."""
        result = send_loan_notification(999999)

        assert result["status"] == "error"
        assert result["message"] == "Loan not found"
        assert len(mail.outbox) == 0

    @patch("library.tasks.send_mail")
    def test_send_notification_email_failure_retry(self, mock_send_mail, sample_loan):
        """Test that task retries on email failure."""
        mock_send_mail.side_effect = Exception("SMTP Error")

        # Mock the retry method to prevent actual retry
        with patch.object(send_loan_notification, "retry") as mock_retry:
            mock_retry.side_effect = Exception("Max retries exceeded")

            with pytest.raises(Exception):
                send_loan_notification(sample_loan.id)

            mock_retry.assert_called_once()


@pytest.mark.django_db
@pytest.mark.unit
class TestSendOverdueReminders:
    """Test suite for send_overdue_reminders task."""

    def test_send_overdue_reminders_no_overdue_loans(self):
        """Test when there are no overdue loans."""
        result = send_overdue_reminders()

        assert result["reminders_sent"] == 0
        assert result["total_overdue"] == 0
        assert len(mail.outbox) == 0

    def test_send_overdue_reminders_with_overdue_loans(
        self, book_factory, member_factory
    ):
        """Test sending reminders for overdue loans."""
        # Create overdue loan (20 days old)
        book = book_factory()
        member = member_factory()
        overdue_loan = Loan.objects.create(book=book, member=member)
        overdue_loan.loan_date = date.today() - timedelta(days=20)
        overdue_loan.save()

        result = send_overdue_reminders()

        assert result["reminders_sent"] == 1
        assert result["total_overdue"] == 1
        assert len(mail.outbox) == 1
        assert "Overdue Book Reminder" in mail.outbox[0].subject

    def test_send_overdue_reminders_within_grace_period(
        self, book_factory, member_factory
    ):
        """Test that loans within grace period don't get reminders."""
        # Create loan that's 10 days old (within 14-day grace period)
        book = book_factory()
        member = member_factory()
        recent_loan = Loan.objects.create(book=book, member=member)
        recent_loan.loan_date = date.today() - timedelta(days=10)
        recent_loan.save()

        result = send_overdue_reminders()

        assert result["reminders_sent"] == 0
        assert len(mail.outbox) == 0

    def test_send_overdue_reminders_excludes_returned_books(
        self, book_factory, member_factory
    ):
        """Test that returned books don't get overdue reminders."""
        book = book_factory()
        member = member_factory()
        returned_loan = Loan.objects.create(
            book=book,
            member=member,
            is_returned=True
        )
        returned_loan.loan_date = date.today() - timedelta(days=20)
        returned_loan.save()

        result = send_overdue_reminders()

        assert result["reminders_sent"] == 0
        assert len(mail.outbox) == 0

