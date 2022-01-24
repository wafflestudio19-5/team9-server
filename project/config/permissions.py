from rest_framework.permissions import BasePermission


class IsValidAccount(BasePermission):
    # is_valid가 참인 유저만 접근
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.is_valid
