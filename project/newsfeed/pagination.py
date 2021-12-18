from rest_framework.pagination import CursorPagination


class CustomPagination(CursorPagination):
    page_size = 20
    ordering = "-created_at"
    cursor_query_param = "c"
