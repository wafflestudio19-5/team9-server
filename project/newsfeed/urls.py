from django.urls import path, include
from .views import PostViewSet, LikeViewSet
from rest_framework.routers import SimpleRouter
from django.conf import settings
from django.conf.urls.static import static

Router = SimpleRouter()
Router.register("newsfeed", PostViewSet, basename="PostList")  # /api/v1/newsfeed/
Router.register("like", LikeViewSet, basename="LikeList")  # /api/v1/like/

# Router = SimpleRouter()
# Router.register("newsfeed", PostViewSet, basename="PostList")  # /api/v1/newsfeed/
# Router.register("like", LikeViewSet, basename="LikeList")  # /api/v1/like/

urlpatterns = [
    path("", include(Router.urls), name="NewsFeedList"),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
