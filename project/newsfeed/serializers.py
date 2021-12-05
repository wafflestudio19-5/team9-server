from abc import ABC
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import update_last_login
from rest_framework import serializers
from rest_framework_jwt.settings import api_settings
from .models import Post, PostImage
from user.serializers import UserSerializer
from datetime import datetime, timedelta
from pytz import timezone


class PostSerializer(serializers.ModelSerializer):
    class Meta:

        model = Post
        fields = ("id", "author", "content", "likes")

    def create(self, validated_data):

        return None

    def validate(self, attrs):
        return super().validate(attrs)


class PostListSerializer(serializers.ModelSerializer):

    posted_at = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ("author", "content", "images", "likes", "posted_at")

    def get_posted_at(self, post):

        created_at = post.created_at
        now = datetime.now()
        duration = str(now - created_at).split(".")[0]
        return duration

    def get_images(self, post):
        return PostImageSerializer(post.images, many=True, context=self.context).data


class PostImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostImage
        fields = ("image", "author_email")

    def create(self, validated_data):
        return super().create(validated_data)


class PostLikeSerializer(serializers.ModelSerializer):
    likeusers = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ("likes", "likeusers")

    def get_likeusers(self, post):
        return UserSerializer(post.likeusers, many=True).data
