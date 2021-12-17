from abc import ABC
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import update_last_login
from drf_yasg.utils import swagger_serializer_method
from rest_framework import serializers
from rest_framework_jwt.settings import api_settings
from .models import Post, PostImage
from user.serializers import UserSerializer
from datetime import datetime, timedelta
from pytz import timezone


class PostSerializer(serializers.ModelSerializer):

    images = serializers.SerializerMethodField()

    class Meta:

        model = Post

        fields = (
            "id",
            "author",
            "content",
            "images",
            "created_at",
            "updated_at",
            "likes",
        )
        extra_kwargs = {"content": {"help_text": "무슨 생각을 하고 계신가요?"}}

    def create(self, validated_data):
        return Post.objects.create(
            author=validated_data["author"], content=validated_data["content"]
        )

    def validate(self, data):
        content = data.get("content", None)

        if not content:
            raise serializers.ValidationError("내용을 입력해주세요.")

        return data

    def get_images(self, post):
        return PostImageSerializer(post.images, many=True, context=self.context).data


class PostListSerializer(serializers.ModelSerializer):

    posted_at = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    author = serializers.CharField(source="author.username")

    class Meta:
        model = Post
        fields = ("id", "author", "content", "images", "likes", "posted_at")

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
        fields = ("post", "image", "author_email")

    def create(self, validated_data):
        return super().create(validated_data)


class PostLikeSerializer(serializers.ModelSerializer):
    likeusers = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ("likes", "likeusers")

    @swagger_serializer_method(serializer_or_field=UserSerializer)
    def get_likeusers(self, post):
        return UserSerializer(post.likeusers, many=True).data
