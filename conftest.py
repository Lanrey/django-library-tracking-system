"""
Pytest configuration and fixtures for the library tracking system.
"""
import pytest
from django.contrib.auth.models import User
from library.models import Author, Book, Member, Loan


@pytest.fixture
def author_factory():
    """Factory fixture for creating Author instances."""
    def create_author(first_name="John", last_name="Doe", biography="Test bio"):
        return Author.objects.create(
            first_name=first_name,
            last_name=last_name,
            biography=biography
        )
    return create_author


@pytest.fixture
def book_factory(author_factory):
    """Factory fixture for creating Book instances."""
    def create_book(
        title="Test Book",
        author=None,
        isbn="1234567890123",
        genre="fiction",
        available_copies=5
    ):
        if author is None:
            author = author_factory()
        return Book.objects.create(
            title=title,
            author=author,
            isbn=isbn,
            genre=genre,
            available_copies=available_copies
        )
    return create_book


@pytest.fixture
def user_factory():
    """Factory fixture for creating User instances."""
    def create_user(username="testuser", email="test@example.com", password="testpass123"):
        return User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
    return create_user


@pytest.fixture
def member_factory(user_factory):
    """Factory fixture for creating Member instances."""
    def create_member(user=None):
        if user is None:
            user = user_factory()
        return Member.objects.create(user=user)
    return create_member


@pytest.fixture
def loan_factory(book_factory, member_factory):
    """Factory fixture for creating Loan instances."""
    def create_loan(book=None, member=None, is_returned=False):
        if book is None:
            book = book_factory()
        if member is None:
            member = member_factory()
        return Loan.objects.create(
            book=book,
            member=member,
            is_returned=is_returned
        )
    return create_loan


@pytest.fixture
def sample_author(author_factory):
    """Create a sample author for tests."""
    return author_factory(first_name="Jane", last_name="Austen")


@pytest.fixture
def sample_book(book_factory, sample_author):
    """Create a sample book for tests."""
    return book_factory(
        title="Pride and Prejudice",
        author=sample_author,
        isbn="9780141439518"
    )


@pytest.fixture
def sample_member(member_factory, user_factory):
    """Create a sample member for tests."""
    user = user_factory(username="reader1", email="reader@example.com")
    return member_factory(user=user)


@pytest.fixture
def sample_loan(sample_book, sample_member):
    """Create a sample loan for tests."""
    return Loan.objects.create(
        book=sample_book,
        member=sample_member
    )
