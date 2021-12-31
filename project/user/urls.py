from django.urls import path, include
from .views import (
    UserLoginView,
    UserSignUpView,
    UserLogoutView,
    KakaoView,
    KakaoCallbackView,
    UserNewsfeedView,
    UserFriendView,
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
    path(
        "user/<int:user_id>/newsfeed/", UserNewsfeedView.as_view(), name="user_newsfeed"
    ),  # /api/v1/user/{user_id}/newsfeed/
    path(
        "user/<int:user_id>/friend/", UserFriendView.as_view(), name="user_friend"
    ),  # /api/v1/user/{user_id}/friend/
]

# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
