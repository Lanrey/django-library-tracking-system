"""
Tests to verify query optimization in ViewSets.
Demonstrates that select_related and prefetch_related reduce N+1 query problems.
"""
import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
@pytest.mark.unit
class TestBookViewSetQueryOptimization:
    """Test query optimization for BookViewSet."""

    @override_settings(DEBUG=True)
    def test_book_list_uses_select_related(self, book_factory, author_factory):
        """
        Test that BookViewSet.list uses select_related to fetch authors.
        Should execute a constant number of queries regardless of book count.
        """
        from django.db import connection
        from django.test.utils import override_settings

        # Create test data: 10 books with different authors
        for i in range(10):
            author = author_factory(
                first_name=f"Author{i}",
                last_name=f"LastName{i}"
            )
            book_factory(
                title=f"Book {i}",
                author=author,
                isbn=f"978000000000{i}"
            )

        client = APIClient()

        # Clear existing queries
        connection.queries_log.clear()

        # Fetch books list
        response = client.get(reverse('book-list'))

        assert response.status_code == 200
        assert len(response.data['results']) == 10

        # Count queries executed
        query_count = len(connection.queries)

        # Without optimization: 1 (fetch books) + 10 (fetch each author) = 11 queries
        # With select_related: 1 query (fetch books with authors joined)
        # Allow some extra queries for pagination/counting
        assert query_count <= 3, (
            f"Expected <= 3 queries, but got {query_count}. "
            f"Queries: {connection.queries}"
        )

    @override_settings(DEBUG=True)
    def test_book_retrieve_uses_select_related(self, sample_book):
        """
        Test that BookViewSet.retrieve uses select_related for single book.
        """
        from django.db import connection

        client = APIClient()
        connection.queries_log.clear()

        response = client.get(reverse('book-detail', args=[sample_book.id]))

        assert response.status_code == 200
        assert response.data['title'] == sample_book.title

        query_count = len(connection.queries)

        # Should be 1 query with JOIN
        assert query_count <= 2, f"Expected <= 2 queries, got {query_count}"


@pytest.mark.django_db
@pytest.mark.unit
class TestLoanViewSetQueryOptimization:
    """Test query optimization for LoanViewSet."""

    @override_settings(DEBUG=True)
    def test_loan_list_uses_select_related(
        self, book_factory, member_factory, user_factory, author_factory
    ):
        """
        Test that LoanViewSet.list uses select_related for related objects.
        Loan -> Book -> Author, Loan -> Member -> User
        """
        from django.db import connection
        from library.models import Loan

        # Create 5 loans with different books, authors, members
        for i in range(5):
            author = author_factory(first_name=f"Author{i}")
            book = book_factory(
                title=f"Book{i}",
                author=author,
                isbn=f"111111111111{i}"
            )
            user = user_factory(
                username=f"user{i}",
                email=f"user{i}@test.com"
            )
            member = member_factory(user=user)

            Loan.objects.create(book=book, member=member)

        client = APIClient()
        connection.queries_log.clear()

        response = client.get(reverse('loan-list'))

        assert response.status_code == 200
        assert len(response.data['results']) == 5

        query_count = len(connection.queries)

        # Without optimization: 1 + (3 * 5) = 16 queries
        # book, book__author, member, member__user for each loan
        # With select_related: 1 query with multiple JOINs
        assert query_count <= 3, (
            f"Expected <= 3 queries, but got {query_count}"
        )


@pytest.mark.django_db
@pytest.mark.unit
class TestMemberViewSetQueryOptimization:
    """Test query optimization for MemberViewSet."""

    @override_settings(DEBUG=True)
    def test_member_list_uses_select_related_and_prefetch(
        self, member_factory, book_factory, user_factory
    ):
        """
        Test that MemberViewSet uses select_related for user
        and prefetch_related for loans.
        """
        from django.db import connection
        from library.models import Loan

        # Create 3 members, each with 2 loans
        for i in range(3):
            user = user_factory(
                username=f"member{i}",
                email=f"member{i}@test.com"
            )
            member = member_factory(user=user)

            # Create 2 loans for this member
            for j in range(2):
                book = book_factory(isbn=f"22222222222{i}{j}")
                Loan.objects.create(book=book, member=member)

        client = APIClient()
        connection.queries_log.clear()

        response = client.get(reverse('member-list'))

        assert response.status_code == 200
        assert len(response.data['results']) == 3

        query_count = len(connection.queries)

        # Without optimization: Many queries for users and loans
        # With optimization: Minimal queries
        assert query_count <= 4, (
            f"Expected <= 4 queries, but got {query_count}"
        )


@pytest.mark.django_db
@pytest.mark.unit
class TestAuthorViewSetQueryOptimization:
    """Test query optimization for AuthorViewSet."""

    @override_settings(DEBUG=True)
    def test_author_list_uses_prefetch_related(
        self, author_factory, book_factory
    ):
        """
        Test that AuthorViewSet uses prefetch_related for books.
        """
        from django.db import connection

        # Create 3 authors, each with 3 books
        for i in range(3):
            author = author_factory(
                first_name=f"Author{i}",
                last_name="Smith"
            )
            for j in range(3):
                book_factory(
                    author=author,
                    isbn=f"33333333333{i}{j}"
                )

        client = APIClient()
        connection.queries_log.clear()

        response = client.get(reverse('author-list'))

        assert response.status_code == 200
        assert len(response.data['results']) == 3

        query_count = len(connection.queries)

        # Without prefetch: 1 + N queries for books
        # With prefetch: 1 + 1 = 2 queries
        assert query_count <= 4, (
            f"Expected <= 4 queries, but got {query_count}"
        )


@pytest.mark.django_db
@pytest.mark.integration
class TestQueryOptimizationIntegration:
    """Integration tests to verify overall query performance."""

    @override_settings(DEBUG=True)
    def test_complete_workflow_query_count(
        self, author_factory, book_factory, member_factory, user_factory
    ):
        """
        Test a complete workflow and verify total query count is reasonable.
        """
        from django.db import connection
        from library.models import Loan

        # Setup: Create realistic test data
        authors = [author_factory(first_name=f"Author{i}") for i in range(5)]
        books = []
        for i, author in enumerate(authors):
            books.append(
                book_factory(
                    author=author,
                    isbn=f"44444444444{i}"
                )
            )

        users = [
            user_factory(
                username=f"testuser{i}",
                email=f"user{i}@test.com"
            )
            for i in range(3)
        ]
        members = [member_factory(user=user) for user in users]

        # Create loans
        for i in range(5):
            Loan.objects.create(
                book=books[i],
                member=members[i % 3]
            )

        client = APIClient()

        # Test 1: List all books
        connection.queries_log.clear()
        response = client.get(reverse('book-list'))
        assert response.status_code == 200
        book_queries = len(connection.queries)
        assert book_queries <= 3

        # Test 2: List all loans
        connection.queries_log.clear()
        response = client.get(reverse('loan-list'))
        assert response.status_code == 200
        loan_queries = len(connection.queries)
        assert loan_queries <= 3

        # Test 3: List all members
        connection.queries_log.clear()
        response = client.get(reverse('member-list'))
        assert response.status_code == 200
        member_queries = len(connection.queries)
        assert member_queries <= 4

        # Test 4: List all authors
        connection.queries_log.clear()
        response = client.get(reverse('author-list'))
        assert response.status_code == 200
        author_queries = len(connection.queries)
        assert author_queries <= 4


@pytest.mark.django_db
class TestQueryLogging:
    """Test that query logging is working correctly."""

    def test_book_viewset_logs_query_count(
        self, book_factory, author_factory, caplog
    ):
        """Test that BookViewSet logs query count."""
        import logging

        # Create test data
        for i in range(3):
            author = author_factory(first_name=f"TestAuthor{i}")
            book_factory(
                title=f"TestBook{i}",
                author=author,
                isbn=f"55555555555{i}"
            )

        client = APIClient()

        with caplog.at_level(logging.INFO, logger='library'):
            response = client.get(reverse('book-list'))

        assert response.status_code == 200

        # Check that query logging occurred
        log_messages = [record.message for record in caplog.records]
        query_logs = [msg for msg in log_messages if 'queries' in msg.lower()]

        # Should have at least one query log
        assert len(query_logs) > 0
