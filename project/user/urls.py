from django.urls import path, include
from .views import UserLoginView, UserSignUpView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("signup/", UserSignUpView.as_view(), name="signup"),  # /api/v1/signup/
    path("login/", UserLoginView.as_view(), name="login"),  # /api/v1/login/
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
