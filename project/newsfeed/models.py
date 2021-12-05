from django.db import models
from django.db.models.deletion import CASCADE
from django.db.models.fields.related import ForeignKey
from user.models import User


class Post(models.Model):

    id = models.AutoField(primary_key=True)
    author = models.ForeignKey(User, on_delete=CASCADE, related_name="posts")
    content = models.CharField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    likes = models.PositiveIntegerField(default=0)

    def get_user_url(self):
        # 게시글에서 유저를 누르면 유저 프로필로 갈 수 있게 하기 위함
        return f"/api/v1/user/{self.author}/"


class PostImage(models.Model):
    # 게시글에 사진을 여러장 업로드하려면 별도의 image모델을 파서 다대일 관계를 맺어줘야함
    # Post가 삭제되면 image가 저장된 경로에 해당 이미지도 삭제되는가?
    # https://dheldh77.tistory.com/entry/Django-%EC%9D%B4%EB%AF%B8%EC%A7%80-%EC%97%85%EB%A1%9C%EB%93%9C
    # https://donis-note.medium.com/django-rest-framework-%EB%8B%A4%EC%A4%91-%EC%9D%B4%EB%AF%B8%EC%A7%80-%EC%97%85%EB%A1%9C%EB%93%9C-%EB%B0%A9%EB%B2%95-38c99d26258
    post = models.ForeignKey(Post, on_delete=CASCADE, related_name="images")
    author_email = models.CharField(max_length=30, blank=True)
    image = models.ImageField(
        upload_to=f"user/{author_email}/posts/%Y/%m/%d/{post}/", blank=True
    )
