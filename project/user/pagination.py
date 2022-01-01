from rest_framework.pagination import CursorPagination


class UserPagination(CursorPagination):
    page_size = 20
    ordering = "date_joined"
