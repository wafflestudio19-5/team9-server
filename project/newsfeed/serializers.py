from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_serializer_method
from rest_framework import serializers
from rest_framework_jwt.settings import api_settings
from .models import Notice, Post, Comment, NewsfeedObject
from user.serializers import UserSerializer
from user.models import User
from datetime import datetime, timedelta
from pytz import timezone


class PostSerializer(serializers.ModelSerializer):

    subposts = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()

    class Meta:

        model = Post

        fields = (
            "id",
            "author",
            "content",
            "mainpost",
            "subposts",
            "comments",
            "likes",
            "is_liked",
            "scope",
        )
        extra_kwargs = {"content": {"help_text": "무슨 생각을 하고 계신가요?"}}

    def create(self, validated_data):

        mainpost = validated_data.get("mainpost", None)
        author = self.context["author"]
        content = validated_data.get("content", "")
        scope = validated_data["scope"]

        if mainpost:
            post = Post.objects.create(
                author=author, content=content, mainpost=mainpost, scope=scope
            )
        else:
            post = Post.objects.create(author=author, content=content, scope=scope)

        return post

    def validate(self, data):

        content = data.get("content", None)
        isFile = self.context["isFile"]
        scope = data["scope"]

        if not isFile:
            if not content:
                raise serializers.ValidationError("내용을 입력해주세요.")

        if scope > 3 or scope < 1:
            raise serializers.ValidationError("공개범위는 1, 2, 3 중에 선택해주세요.")

        return data

    def get_subposts(self, post):

        return SubPostSerializer(post.subposts, many=True).data

    def get_is_liked(self, post):
        request = self.context.get("request")
        if not request:
            return None

        if post.likeusers.filter(pk=request.user.id).exists():
            return True

        return False

    def get_author(self, post):
        return UserSerializer(post.author).data

    def get_comments(self, post):
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


def notice_format_time(time):
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
    else:
        if time_elapsed.days > 60:
            return False
        week = time_elapsed.days // 7
        return f"{week}주"


class MainPostSerializer(serializers.ModelSerializer):

    posted_at = serializers.SerializerMethodField()
    subposts = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id",
            "author",
            "content",
            "subposts",
            "likes",
            "posted_at",
            "comments",
            "is_liked",
            "scope",
        )

    def get_posted_at(self, post):
        return format_time(post.created)

    def get_subposts(self, post):
        return SubPostSerializer(post.subposts, many=True, context=self.context).data

    @swagger_serializer_method(serializer_or_field=UserSerializer)
    def get_author(self, post):
        return UserSerializer(post.author).data

    def get_comments(self, post):
        return Comment.objects.filter(post=post).count()

    def get_is_liked(self, post):
        request = self.context.get("request")
        if not request:
            return None

        if post.likeusers.filter(pk=request.user.id).exists():
            return True

        return False


class SubPostSerializer(serializers.ModelSerializer):

    posted_at = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id",
            "content",
            "mainpost",
            "file",
            "likes",
            "posted_at",
            "comments",
            "is_liked",
            "scope",
        )

    def get_posted_at(self, post):
        return format_time(post.created)

    def get_comments(self, post):
        return Comment.objects.filter(post=post).count()

    def get_is_liked(self, post):
        request = self.context.get("request")
        if not request:
            return None

        if post.likeusers.filter(pk=request.user.id).exists():
            return True

        return False


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


class CommentSwaggerSerializer(serializers.Serializer):
    content = serializers.CharField(required=True)
    parent = serializers.IntegerField(
        required=False, help_text="부모 댓글의 id. Depth가 0인 경우 해당 필드를 비워두세요."
    )


class CommentSerializer(serializers.ModelSerializer):
    is_liked = serializers.SerializerMethodField()

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
            "is_liked",
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

    def get_is_liked(self, comment):
        request = self.context.get("request")
        if not request:
            return None

        if comment.likeusers.filter(pk=request.user.id).exists():
            return True

        return False


class CommentListSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    posted_at = serializers.SerializerMethodField()
    children_count = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()

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
            "is_liked",
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

    def get_is_liked(self, comment):
        request = self.context.get("request")
        if not request:
            return None

        if comment.likeusers.filter(pk=request.user.id).exists():
            return True

        return False


class NoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notice
        fields = (
            "id",
            "user",
            "post",
            "comment",
            "content",
            "url",
        )

    def create(self, validated_data):

        user = validated_data["user"]
        url = validated_data["url"]
        content = validated_data["content"]
        post = validated_data.get("post")
        comment = validated_data.get("comment")
        sender = self.context["sender"]

        notice = Notice.objects.create(
            user=user,
            content=content,
            post=post,
            comment=comment,
            url=url,
        )
        notice.senders.add(sender)

        return notice


class NoticelistSerializer(serializers.ModelSerializer):

    posted_at = serializers.SerializerMethodField()
    post = serializers.SerializerMethodField()
    comment = serializers.SerializerMethodField()
    senders = serializers.SerializerMethodField()

    class Meta:
        model = Notice
        fields = (
            "id",
            "user",
            "post",
            "comment",
            "content",
            "posted_at",
            "is_checked",
            "url",
            "senders",
            "count",
        )

    def get_posted_at(self, notice):
        posted_at = notice_format_time(notice.created)
        if posted_at == False:
            notice.delete()
        return posted_at

    def get_post(self, notice):
        return PostSerializer(notice.post).data

    def get_comment(self, notice):
        return CommentSerializer(notice.comment).data

    def get_senders(self, notice):
        return UserSerializer(notice.senders, many=True).data
