import logging
from datetime import date, timedelta
from typing import Dict, List

import requests
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.utils import timezone

from .models import Author, Book, Loan, Member

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_loan_notification(self, loan_id: int) -> Dict[str, str]:
    """
    Send email notification when a book is loaned.

    Args:
        loan_id: The ID of the loan

    Returns:
        Dictionary with status and message

    Raises:
        Exception: If email sending fails after retries
    """
    try:
        loan = Loan.objects.get(id=loan_id)
        member_email = loan.member.user.email
        book_title = loan.book.title

        send_mail(
            subject="Book Loaned Successfully",
            message=(
                f"Hello {loan.member.user.username},\n\n"
                f'You have successfully loaned "{book_title}".\n'
                f"Please return it by the due date."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member_email],
            fail_silently=False,
        )

        logger.info(f"Loan notification sent for loan_id={loan_id}")
        return {"status": "success", "message": f"Email sent to {member_email}"}

    except Loan.DoesNotExist:
        logger.error(f"Loan with id={loan_id} does not exist")
        return {"status": "error", "message": "Loan not found"}

    except Exception as exc:
        logger.error(f"Failed to send loan notification: {exc}")
        raise self.retry(exc=exc)
    
@shared_task
def check_overdue_loans() -> Dict[str, int]:
    """
    Check for overdue loans and log them.
    Scheduled to run daily via Celery Beat.

    Returns:
        Dictionary with count of overdue loans
        And also sends email notifications to members with overdue loans
    """
    today = date.today()
    overdue_loans = Loan.objects.filter(
        is_returned=False, due_date__lt=today
    ).select_related("book", "member__user")

    for loan in overdue_loans:
        send_mail(
            subject="Overdue Loans Reminder",
            message=(
                f"The following loans are overdue:\n\n"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[loan.member_email],
            fail_silently=False,

        )

    count = overdue_loans.count()
    logger.info(f"Total overdue loans found: {count}")
    return {"overdue_loans_count": count}


@shared_task
def send_overdue_reminders() -> Dict[str, int]:
    """
    Send reminders for overdue books.
    Scheduled to run daily via Celery Beat.

    Returns:
        Dictionary with count of reminders sent
    """
    today = date.today()
    grace_period = 14  # days

    overdue_loans = Loan.objects.filter(
        is_returned=False, loan_date__lt=today - timedelta(days=grace_period)
    ).select_related("book", "member__user")

    reminders_sent = 0

    for loan in overdue_loans:
        days_overdue = (today - loan.loan_date).days - grace_period

        try:
            send_mail(
                subject="Overdue Book Reminder",
                message=(
                    f"Hello {loan.member.user.username},\n\n"
                    f'Your loaned book "{loan.book.title}" is {days_overdue} days overdue.\n'
                    f"Please return it as soon as possible to avoid late fees.\n\n"
                    f"Loaned on: {loan.loan_date}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[loan.member.user.email],
                fail_silently=False,
            )
            reminders_sent += 1
            logger.info(f"Overdue reminder sent for loan_id={loan.id}")

        except Exception as exc:
            logger.error(f"Failed to send overdue reminder for loan_id={loan.id}: {exc}")

    logger.info(f"Sent {reminders_sent} overdue reminders")
    return {"reminders_sent": reminders_sent, "total_overdue": overdue_loans.count()}

