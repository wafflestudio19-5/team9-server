from abc import ABC
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import update_last_login
from rest_framework import serializers
from rest_framework_jwt.settings import api_settings
from .models import Post
from datetime import datetime, timedelta
from pytz import timezone

class PostListSerializer(serializers.ModelSerializer):

    posted_at = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            'author',
            'content',
            'likes',
            'posted_at'
        )

    def get_posted_at(self, post):
        
        created_at = post.created_at
        now = datetime.now()
        duration = str(now-created_at).split(".")[0]
        return duration
