from django.urls import path, include
from .views import PostViewSet
from rest_framework.routers import SimpleRouter
from django.conf import settings
from django.conf.urls.static import static

router = SimpleRouter()
router.register('newsfeed', PostViewSet, basename='PostList')  # /api/v1/newsfeed/

urlpatterns = [
    path('', include(router.urls), name='PostList'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)