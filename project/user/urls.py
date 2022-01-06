from django.urls import path, include
from rest_framework.routers import SimpleRouter

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
    CompanyCreateView,
    CompanyView,
    UniversityCreateView,
    UniversityView,
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("signup/", UserSignUpView.as_view(), name="signup"),  # /api/v1/signup/
    path("login/", UserLoginView.as_view(), name="login"),  # /api/v1/login/
    path("logout/", UserLogoutView.as_view(), name="logout"),  # /api/v1/logout/
    path("kakao/login/", KakaoLoginView.as_view(), name="kakao_login"),  # /api/v1/kakao/login/
    path("kakao/connect/", KakaoConnectView.as_view(), name="kakao_connect"),  # /api/v1/kakao/connect/
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
        "friend/request/", UserFriendRequestView.as_view(), name="friend_request"
    ),  # /api/v1/friend/request/
    path("friend/", UserFriendDeleteView.as_view(), name="friend"),  # /api/v1/friend/
    path("search/", UserSearchListView.as_view(), name="search"),  # /api/v1/search/
]

# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
