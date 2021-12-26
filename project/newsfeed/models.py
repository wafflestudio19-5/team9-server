from django.db import models
from django.db.models.deletion import CASCADE
from django.db.models.fields.related import ForeignKey
from user.models import User


class Post(models.Model):

    id = models.AutoField(primary_key=True)
    author = models.ForeignKey(User, on_delete=CASCADE, related_name="posts")
    content = models.CharField(max_length=1000, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    likes = models.PositiveIntegerField(default=0)
    likeusers = models.ManyToManyField(User)

    mainpost = models.ForeignKey(
        "self",
        related_name="subposts",
        null=True,
        blank=True,
        on_delete=CASCADE,
    )

    file = models.FileField(
        upload_to=f"user/{author}/{mainpost}/%Y/%m/%d/{id}/", blank=True
    )

    def get_user_url(self):
        # 게시글에서 유저를 누르면 유저 프로필로 갈 수 있게 하기 위함
        return f"/api/v1/user/{self.author}/"
