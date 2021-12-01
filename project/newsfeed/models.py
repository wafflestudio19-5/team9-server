from django.db import models
from django.db.models.deletion import CASCADE
from user.models import User

class Post(models.Model):
    
    author = models.ForeignKey(User, on_delete=CASCADE)
    content = models.CharField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    likes = models.PositiveIntegerField(default=0)

    def get_user_url(self):
        #게시글에서 유저를 누르면 유저 프로필로 갈 수 있게 하기 위함
        return f'/api/v1/user/{self.author}/'

