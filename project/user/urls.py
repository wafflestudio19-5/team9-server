from django.urls import path, include
from rest_framework.routers import SimpleRouter
from rest_framework_jwt.views import refresh_jwt_token

from .views import (
    UserLoginView,
    UserSignUpView,
    UserLogoutView,
    KakaoLoginView,
    KakaoConnectView,
    UserNewsfeedView,
    UserFriendRequestView,
    UserFriendDeleteView,
    UserFriendListView,
    UserSearchListView,
    UserProfileView,
    UserProfileImageView,
    CompanyCreateView,
    CompanyView,
    UniversityCreateView,
    UniversityView,
    UserFriendRequestListView,
    UserDeleteView,
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path(
        "account/signup/", UserSignUpView.as_view(), name="account_signup"
    ),  # /api/v1/account/signup/
    path(
        "account/login/", UserLoginView.as_view(), name="account_login"
    ),  # /api/v1/account/login/
    path(
        "account/logout/", UserLogoutView.as_view(), name="account_logout"
    ),  # /api/v1/account/logout/
    path(
        "account/delete/", UserDeleteView.as_view(), name="account_delete"
    ),  # /api/v1/account/delete/
    path(
        "account/kakao/login/", KakaoLoginView.as_view(), name="kakao_login"
    ),  # /api/v1/account/kakao/login/
    path(
        "account/kakao/connect/", KakaoConnectView.as_view(), name="kakao_connect"
    ),  # /api/v1/account/kakao/connect/
    path(
        "user/<int:user_id>/newsfeed/", UserNewsfeedView.as_view(), name="user_newsfeed"
    ),  # /api/v1/user/{user_id}/newsfeed/
    path(
        "user/<int:user_id>/friend/", UserFriendListView.as_view(), name="user_friend"
    ),  # /api/v1/user/{user_id}/friend/
    path(
        "user/<int:pk>/profile/", UserProfileView.as_view(), name="user_profile"
    ),  # /api/v1/user/{user_id}/profile/
    path(
        "user/<int:pk>/image/",
        UserProfileImageView.as_view(),
        name="user_profile_image",
    ),  # /api/v1/user/{user_id}/image/
    path(
        "user/company/", CompanyCreateView.as_view(), name="company_create"
    ),  # /api/v1/user/company/
    path(
        "user/company/<int:pk>/", CompanyView.as_view(), name="company"
    ),  # /api/v1/user/company/{company_id}/
    path(
        "user/university/", UniversityCreateView.as_view(), name="university_create"
    ),  # /api/v1/user/university/
    path(
        "user/university/<int:pk>/", UniversityView.as_view(), name="university"
    ),  # /api/v1/user/university/{university_id}/
    path(
        "friend/request/",
        UserFriendRequestListView.as_view(),
        name="friend_request_list",
    ),  # /api/v1/friend/request/
    path(
        "friend/request/<int:pk>/",
        UserFriendRequestView.as_view(),
        name="friend_request",
    ),
    path("friend/", UserFriendDeleteView.as_view(), name="friend"),  # /api/v1/friend/
    path("search/", UserSearchListView.as_view(), name="search"),  # /api/v1/search/
    path("token/refresh/", refresh_jwt_token),  # /api/v1/token/refresh/
]

# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
