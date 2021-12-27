from django.urls import path, include
from .views import PostListView, PostLikeViewSet, CommentListView
from rest_framework.routers import SimpleRouter
from django.conf import settings
from django.conf.urls.static import static

# Router = SimpleRouter()
# Router.register("newsfeed/<post_id>/like", PostLikeViewSet, basename="LikeList")  # /api/v1/like/


urlpatterns = [
    # path("", include(Router.urls), name="NewsFeedList"),
    path("newsfeed/", PostListView.as_view()),
    path("newsfeed/<int:post_id>/comment/", CommentListView.as_view()),
    path("newsfeed/<int:post_id>/like/", PostLikeViewSet.as_view())
]

# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
