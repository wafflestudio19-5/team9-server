from rest_framework.pagination import CursorPagination


class CommentPagination(CursorPagination):
    page_size = 20
    ordering = "created"
