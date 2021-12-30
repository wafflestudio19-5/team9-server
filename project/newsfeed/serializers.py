from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_serializer_method
from rest_framework import serializers
from rest_framework_jwt.settings import api_settings
from .models import Notification, Post, Comment, NewsfeedObject
from user.serializers import UserSerializer
from user.models import User
from datetime import datetime, timedelta
from pytz import timezone


class PostSerializer(serializers.ModelSerializer):

    subposts = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()

    class Meta:

        model = Post

        fields = (
            "id",
            "author",
            "content",
            "mainpost",
            "subposts",
            "file",
            "created",
            "updated",
            "likes",
            "comment_count",
        )
        extra_kwargs = {"content": {"help_text": "무슨 생각을 하고 계신가요?"}}

    def create(self, validated_data):

        mainpost = validated_data.get("mainpost", None)
        author = validated_data["author"]
        content = validated_data["content"]

        if mainpost:
            post = Post.objects.create(
                author=author, content=content, mainpost=mainpost
            )
        else:
            post = Post.objects.create(author=author, content=content)

        return post

    def validate(self, data):

        content = data.get("content", None)

        if not content:
            raise serializers.ValidationError("내용을 입력해주세요.")

        return data

    def get_subposts(self, post):
        return PostSerializer(post.subposts, many=True).data

    def get_comment_count(self, post):
        return Comment.objects.filter(post=post).count()


def format_time(time):
    now = datetime.now()
    time_elapsed = now - time
    if time_elapsed < timedelta(minutes=1):
        return "방금"
    elif time_elapsed < timedelta(hours=1):
        return f"{int(time_elapsed.seconds / 60)}분"
    elif time_elapsed < timedelta(days=1):
        return f"{int(time_elapsed.seconds / (60 * 60))}시간"
    elif time_elapsed < timedelta(days=7):
        return f"{time_elapsed.days}일"
    elif time.year == now.year:
        return f"{time.month}월 {time.day}일"
    else:
        return f"{time.year}년 {time.month}월 {time.day}일"


class PostListSerializer(serializers.ModelSerializer):

    posted_at = serializers.SerializerMethodField()
    subposts = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id",
            "author",
            "content",
            "subposts",
            "file",
            "likes",
            "posted_at",
            "comment_count",
        )

    def get_posted_at(self, post):
        return format_time(post.created)

    @swagger_serializer_method(serializer_or_field=PostSerializer)
    def get_subposts(self, post):
        return PostSerializer(post.subposts, many=True).data

    @swagger_serializer_method(serializer_or_field=UserSerializer)
    def get_author(self, post):
        return UserSerializer(post.author).data

    def get_comment_count(self, post):
        return Comment.objects.filter(post=post).count()


class PostLikeSerializer(serializers.ModelSerializer):
    likeusers = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ("likes", "likeusers")

    @swagger_serializer_method(serializer_or_field=UserSerializer)
    def get_likeusers(self, post):
        return UserSerializer(post.likeusers, many=True).data


class CommentLikeSerializer(serializers.ModelSerializer):
    likeusers = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ("likes", "likeusers")

    @swagger_serializer_method(serializer_or_field=UserSerializer)
    def get_likeusers(self, comment):
        return UserSerializer(comment.likeusers, many=True).data


class CommentSerializer(serializers.ModelSerializer):
    class Meta:

        model = Comment

        fields = (
            "id",
            "post",
            "author",
            "content",
            "file",
            "parent",
            "depth",
            "created",
            "likes",
        )

    def create(self, validated_data):
        return Comment.objects.create(
            post=validated_data["post"],
            author=validated_data["author"],
            content=validated_data["content"],
            parent=validated_data.get("parent"),
            depth=validated_data.get("depth"),
        )

    def validate(self, data):
        post = data.get("post", None)
        parent = data.get("parent", None)
        content = data.get("content", None)

        if not content:
            raise serializers.ValidationError("내용을 입력해주세요.")

        if parent:
            if parent.depth > 1:
                raise serializers.ValidationError("depth 2까지만 가능합니다.")

            if not parent.post == post:
                raise serializers.ValidationError(
                    "'parent'가 해당 'Post'의 'comment'가 아닙니다."
                )

            depth = parent.depth + 1
            data["depth"] = depth
        else:
            data["depth"] = 0

        return data


class CommentListSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    posted_at = serializers.SerializerMethodField()
    children_count = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = (
            "id",
            "author",
            "content",
            "file",
            "depth",
            "likes",
            "posted_at",
            "parent",
            "children_count",
            "children",
        )

    @swagger_serializer_method(serializer_or_field=UserSerializer)
    def get_author(self, comment):
        return UserSerializer(comment.author).data

    def get_posted_at(self, comment):
        return format_time(comment.created)

    def get_children_count(self, comment):
        return comment.children.count()

    def get_children(self, comment):
        children = comment.children.order_by("created")
        # child comment 3개만 노출시키기
        # if children.count() > 2:
        #     children = children[children.count()-4:]
        return CommentListSerializer(children, many=True, context=self.context).data


class NotificationSerializer(serializers.ModelSerializer):

    posted_at = serializers.SerializerMethodField()
    post = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            "id",
            "user",
            "post",
            "comment",
            "content",
            "posted_at",
            "isChecked",
            "url",
        )

    def create(self, validated_data):

        subject = self.context["request"].user.username
        object = self.context["object"]
        url = self.context["url"]
        post = self.context.get("post")
        comment = self.context.get("comment")

        if self.context.get("isPostLike"):
            content = f"{subject}님이 내 게시물에 좋아요를 눌렀습니다."
        elif self.context.get("isCommentLike"):
            content = f"{subject}님이 내 댓글에 좋아요를 눌렀습니다."
        elif self.context.get("isComment"):
            content = f"{subject}님이 내 게시물에 댓글을 달았습니다."
        elif self.context.get("isFriend"):
            content = f"{subject}님이 친구요청을 보냈습니다."
        
        return Notification.objects.create(
            user=object,
            content=content,
            post = post,
            comment = comment,
            url=url,
            post=validated_data.get("post"),
        )

    def get_posted_at(self, notification):
        return format_time(notification.created)

    def get_post(self, notification):
        return PostSerializer(notification.post).data

    def get_comment(self, notification):
        return CommentSerializer(notification.post).data
