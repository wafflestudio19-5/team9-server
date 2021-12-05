from django.urls import path, include
from .views import PostViewSet, LikeViewSet
from rest_framework.routers import SimpleRouter
from django.conf import settings
from django.conf.urls.static import static

postRouter = SimpleRouter()
postRouter.register("newsfeed", PostViewSet, basename="PostList")  # /api/v1/newsfeed/
likeRouter = SimpleRouter()
likeRouter.register("like", LikeViewSet, basename="LikeList")  # /api/v1/like/

urlpatterns = [
    path("", include(postRouter.urls), name="PostList"),
    path("", include(likeRouter.urls), name="Likelist"),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
