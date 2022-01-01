from django.urls import path, include
from rest_framework.routers import SimpleRouter

from .views import (
    UserLoginView,
    UserSignUpView,
    UserLogoutView,
    KakaoView,
    KakaoCallbackView, UserFriendRequestView, UserFriendView, UserSearchListView,
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("signup/", UserSignUpView.as_view(), name="signup"),  # /api/v1/signup/
    path("login/", UserLoginView.as_view(), name="login"),  # /api/v1/login/
    path("logout/", UserLogoutView.as_view(), name="logout"),  # /api/v1/logout/
    path("kakao/", KakaoView.as_view(), name="kakao_login"),  # /api/v1/kakao/
    path(
        "kakao/callback/", KakaoCallbackView.as_view(), name="kakao_callback"
    ),  # /api/v1/kakao/callback/
    path("friend/request/", UserFriendRequestView.as_view(), name="friend_request"),  # /api/v1/friend/request/
    path("friend/", UserFriendView.as_view(), name="friend"),  # /api/v1/friend/
    path("search/", UserSearchListView.as_view(), name="search"),  # /api/v1/search/
]

# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
