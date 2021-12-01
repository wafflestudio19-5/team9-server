from django.urls import path, include
from .views import PostViewSet
from rest_framework.routers import SimpleRouter

router = SimpleRouter()
router.register('newsfeed', PostViewSet, basename='PostList')  # /api/v1/newsfeed/

urlpatterns = [
    path('', include(router.urls), name='PostList'),
]