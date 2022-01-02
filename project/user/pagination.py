from rest_framework.pagination import CursorPagination


class UserPagination(CursorPagination):
    ordering = "joined_at"
