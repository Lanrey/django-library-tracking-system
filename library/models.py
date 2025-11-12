from datetime import timedelta

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Author(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    biography = models.TextField(blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Book(models.Model):
    GENRE_CHOICES = [
        ('fiction', 'Fiction'),
        ('nonfiction', 'Non-Fiction'),
        ('sci-fi', 'Sci-Fi'),
        ('biography', 'Biography'),
        # Add more genres as needed
    ]

    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, related_name='books', on_delete=models.CASCADE)
    isbn = models.CharField(max_length=13, unique=True)
    genre = models.CharField(max_length=50, choices=GENRE_CHOICES)
    available_copies = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.title

class Member(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    membership_date = models.DateField(auto_now_add=True)
    # Add more fields if necessary

    def __str__(self):
        return self.user.username

class Loan(models.Model):
    """
    Model representing a book loan to a member.
    """
    book = models.ForeignKey(Book, related_name='loans', on_delete=models.CASCADE)
    member = models.ForeignKey(Member, related_name='loans', on_delete=models.CASCADE)
    loan_date = models.DateField(auto_now_add=True)
    return_date = models.DateField(null=True, blank=True)
    is_returned = models.BooleanField(default=False)
    extension_days = models.PositiveIntegerField(default=0)

    # Constants
    LOAN_DURATION_DAYS = 14

    @property
    def due_date(self):
        """
        Calculate due date as loan_date + LOAN_DURATION_DAYS + extension_days.

        Returns:
            date: The due date (loan_date + 14 days + extension days)
        """
        if self.loan_date:
            return self.loan_date + timedelta(days=self.LOAN_DURATION_DAYS + self.extension_days)
        return timezone.now().date() + timedelta(days=self.LOAN_DURATION_DAYS + self.extension_days)

    @property
    def is_overdue(self):
        """
        Check if the loan is overdue.

        Returns:
            bool: True if loan is overdue, False otherwise
        """
        if self.is_returned:
            return False
        return timezone.now().date() > self.due_date

    @property
    def days_until_due(self):
        """
        Calculate days remaining until due date.

        Returns:
            int or None: Days until due (negative if overdue), None if returned
        """
        if self.is_returned:
            return None
        delta = self.due_date - timezone.now().date()
        return delta.days

    def __str__(self):
        return f"{self.book.title} loaned to {self.member.user.username}"
