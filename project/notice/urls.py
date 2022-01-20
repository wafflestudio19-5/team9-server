from django.urls import path
from .views import (
    NoticeView,
    NoticeListView,
)

urlpatterns = [
    path("notices/", NoticeListView.as_view()),
    path("notices/<int:notice_id>/", NoticeView.as_view()),
]
