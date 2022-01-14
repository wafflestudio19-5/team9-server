from django.db import models
from django.db.models.deletion import CASCADE
from django.db.models.fields.related import ForeignKey
from user.models import User


class NewsfeedObject(models.Model):

    content = models.CharField(max_length=1000, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    likes = models.PositiveIntegerField(default=0)
    likeusers = models.ManyToManyField(User)

    class Meta:
        abstract = True


def get_directory_path(instance, filename):
    return (
        f"user/{instance.author}/posts/{instance.mainpost.id}/{instance.id}/{filename}"
    )


def comment_directory_path(instance, filename):
    return f"user/{instance.author}/comments/{instance.id}/{filename}"


class Post(NewsfeedObject):
    id = models.AutoField(primary_key=True)
    author = models.ForeignKey(User, on_delete=CASCADE, related_name="posts")
    scope = models.PositiveSmallIntegerField(default=3)

    mainpost = models.ForeignKey(
        "self",
        related_name="subposts",
        null=True,
        blank=True,
        on_delete=CASCADE,
    )

    file = models.FileField(
        upload_to=get_directory_path,
        blank=True,
    )

    shared_post = models.ForeignKey(
        "self",
        related_name="sharing_posts",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    is_sharing = models.BooleanField(default=False)

    def get_user_url(self):
        # 게시글에서 유저를 누르면 유저 프로필로 갈 수 있게 하기 위함
        return f"/api/v1/user/{self.author}/"


class Comment(NewsfeedObject):

    id = models.AutoField(primary_key=True)
    author = models.ForeignKey(User, on_delete=CASCADE, related_name="comments")
    post = models.ForeignKey(Post, on_delete=CASCADE, related_name="comments")
    parent = models.ForeignKey(
        "self", on_delete=CASCADE, blank=True, null=True, related_name="children"
    )
    depth = models.PositiveIntegerField(default=0)

    file = models.FileField(upload_to=comment_directory_path, blank=True)

    def get_user_url(self):
        return f"/api/v1/user/{self.author}/"


class Notice(models.Model):

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=CASCADE, related_name="notices")
    senders = models.ManyToManyField(User, null=True, related_name="sent_notices")
    post = models.ForeignKey(Post, on_delete=CASCADE, null=True, related_name="notices")
    parent_comment = models.ForeignKey(
        Comment, on_delete=CASCADE, null=True, related_name="notices"
    )
    content = models.CharField(max_length=30, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    is_checked = models.BooleanField(default=False)
    url = models.CharField(max_length=1000)

    comments = models.ManyToManyField(Comment, null=True)
