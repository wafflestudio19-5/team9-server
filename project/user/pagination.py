from rest_framework.pagination import CursorPagination, LimitOffsetPagination


class UserPagination(CursorPagination):
    ordering = "date_joined"


class FriendPagination(LimitOffsetPagination):
    offset_query_param = "cursor"
