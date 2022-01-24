from django.db import models
from django.db.models.deletion import CASCADE
from django.db.models.fields.related import ForeignKey
from user.models import User
from newsfeed.models import Post, Comment


class Notice(models.Model):

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=CASCADE, related_name="notices")
    post = models.ForeignKey(Post, on_delete=CASCADE, null=True, related_name="notices")
    parent_comment = models.ForeignKey(
        Comment, on_delete=CASCADE, null=True, related_name="notices"
    )
    content = models.CharField(max_length=30, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    is_checked = models.BooleanField(default=False)
    is_accepted = models.BooleanField(default=False)
    url = models.CharField(max_length=1000)


class NoticeSender(models.Model):
    notice = models.ForeignKey(
        Notice, on_delete=CASCADE, null=True, related_name="senders"
    )
    user = models.ForeignKey(
        User, on_delete=CASCADE, null=True, related_name="noticesenders"
    )
    count = models.PositiveIntegerField(default=0)
