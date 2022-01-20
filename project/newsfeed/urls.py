from django.urls import path
from .views import (
    PostListView,
    PostUpdateView,
    PostLikeView,
    CommentListView,
    CommentLikeView,
    CommentUpdateDeleteView,
    TestView,
)
from notice.views import NoticeOnOffView

urlpatterns = [
    path("newsfeed/", PostListView.as_view()),
    path("newsfeed/<int:pk>/", PostUpdateView.as_view()),
    path("newsfeed/<int:post_id>/notice/", NoticeOnOffView.as_view()),
    path("newsfeed/<int:post_id>/comment/", CommentListView.as_view()),
    path("newsfeed/<int:post_id>/<int:comment_id>/", CommentUpdateDeleteView.as_view()),
    path("newsfeed/<int:post_id>/like/", PostLikeView.as_view()),
    path("newsfeed/<int:post_id>/<int:comment_id>/like/", CommentLikeView.as_view()),
    path("test/", TestView.as_view()),
]
