"""Project-wide pagination defaults."""

from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """
    Page-number pagination with a client-selectable, bounded page size.

    ``?page_size=`` lets a client ask for more rows per page, capped at
    ``max_page_size`` so a single request cannot pull an entire table.
    """

    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
