from django.db import models
from django.db.models.deletion import CASCADE
from user.models import User

class Post(models.Model):
    
    author = models.ForeignKey(User, on_delete=CASCADE)
    content = models.CharField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    likes = models.PositiveIntegerField(default=0)

