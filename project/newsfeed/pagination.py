from rest_framework.pagination import CursorPagination


class NoticePagination(CursorPagination):
    page_size = 10
    ordering = "-created"
    cursor_query_param = "c"
