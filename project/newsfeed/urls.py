from django.urls import path, include
from .views import (
    PostListView,
    PostUpdateView,
    PostLikeView,
    CommentListView,
    CommentLikeView,
    NoticeView,
    NoticeListView,
    CommentUpdateDeleteView,
    NoticeOnOffView,
)
from rest_framework.routers import SimpleRouter
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("newsfeed/", PostListView.as_view()),
    path("newsfeed/<int:pk>/", PostUpdateView.as_view()),
    path("newsfeed/<int:post_id>/notice/", NoticeOnOffView.as_view()),
    path("newsfeed/<int:post_id>/comment/", CommentListView.as_view()),
    path("newsfeed/<int:post_id>/<int:comment_id>/", CommentUpdateDeleteView.as_view()),
    path("newsfeed/<int:post_id>/like/", PostLikeView.as_view()),
    path("newsfeed/<int:post_id>/<int:comment_id>/like/", CommentLikeView.as_view()),
    path("newsfeed/notices/", NoticeListView.as_view()),
    path("newsfeed/notices/<int:notice_id>/", NoticeView.as_view()),
]
