from rest_framework.pagination import CursorPagination


class CommentPagination(CursorPagination):
    page_size = 20
    ordering = "created"
    cursor_query_param = "c"


class NoticePagination(CursorPagination):
    page_size = 10
    ordering = "-created"
    cursor_query_param = "c"

