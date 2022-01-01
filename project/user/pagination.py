from rest_framework.pagination import CursorPagination


class UserPagination(CursorPagination):
    ordering = "date_joined"
