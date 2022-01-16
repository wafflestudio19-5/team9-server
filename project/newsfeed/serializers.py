from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_serializer_method
from rest_framework import serializers
from rest_framework_jwt.settings import api_settings
from .models import Notice, Post, Comment, NewsfeedObject, NoticeSender
from user.serializers import UserSerializer
from user.models import User
from datetime import datetime, timedelta
from pytz import timezone


class PostSerializer(serializers.ModelSerializer):

    subposts = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()
    shared_post = serializers.SerializerMethodField()
    shared_counts = serializers.SerializerMethodField()
    posted_at = serializers.SerializerMethodField()

    class Meta:

        model = Post

        fields = (
            "id",
            "author",
            "content",
            "posted_at",
            "mainpost",
            "subposts",
            "comments",
            "likes",
            "is_liked",
            "scope",
            "shared_post",
            "is_sharing",
            "shared_counts",
        )
        extra_kwargs = {"content": {"help_text": "무슨 생각을 하고 계신가요?"}}

    def create(self, validated_data):

        mainpost = validated_data.get("mainpost", None)
        author = self.context["author"]
        content = validated_data.get("content", "")
        scope = validated_data["scope"]
        shared_post = self.context.get("shared_post")

        post = Post.objects.create(
            author=author,
            content=content,
            mainpost=mainpost,
            scope=scope,
        )

        if shared_post:
            shared_post = Post.objects.get(id=shared_post)
            post.shared_post = shared_post
            post.is_sharing = True
            post.save()

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

    def get_posted_at(self, post):
        return format_time(post.created)

    def get_subposts(self, post):

        return SubPostSerializer(post.subposts, many=True, context=self.context).data

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
        return post.comments.count()

    def get_shared_post(self, post):

        if not post.is_sharing:
            return None

        shared_post = post.shared_post

        if not post.shared_post:
            return "AccessDenied"

        user = self.context["request"].user
        if user == shared_post.author:
            pass
        elif user in shared_post.author.friends.all():
            if shared_post.scope == 1:
                return "AccessDenied"
        else:
            if shared_post.scope != 3:
                return "AccessDenied"

        return PostSerializer(shared_post).data

    def get_shared_counts(self, post):
        return post.sharing_posts.count()


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
    shared_post = serializers.SerializerMethodField()
    shared_counts = serializers.SerializerMethodField()

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
            "shared_post",
            "shared_counts",
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

    def get_shared_post(self, post):
        user = self.context["request"].user

        shared_post = post.shared_post

        if not post.shared_post:
            return None

        if user == shared_post.author:
            pass
        elif user in shared_post.author.friends.all():
            if shared_post.scope == 1:
                return "AccessDenied"
        else:
            if shared_post.scope != 3:
                return "AccessDenied"

        return PostSerializer(shared_post).data

    def get_shared_counts(self, post):
        return post.sharing_posts.count()


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


class CommentPostSwaggerSerializer(serializers.Serializer):
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
            "parent_comment",
            "content",
            "url",
        )

    def create(self, validated_data):

        user = validated_data["user"]
        url = validated_data["url"]
        content = validated_data["content"]
        post = validated_data.get("post")
        parent_comment = validated_data.get("parent_comment")
        sender = self.context["sender"]
        # comment = self.context.get("comment")

        notice = Notice.objects.create(
            user=user,
            content=content,
            post=post,
            parent_comment=parent_comment,
            url=url,
        )
        NoticeSender.objects.create(user=sender, notice=notice, count=1)
        # notice.senders.add(sender)

        # if comment:
        #     notice.comments.add(comment)

        return notice


class NoticelistSerializer(serializers.ModelSerializer):

    posted_at = serializers.SerializerMethodField()
    post = serializers.SerializerMethodField()
    parent_comment = serializers.SerializerMethodField()
    senders = serializers.SerializerMethodField()
    count = serializers.SerializerMethodField()
    sender_preview = serializers.SerializerMethodField()

    class Meta:
        model = Notice
        fields = (
            "id",
            "user",
            "post",
            "parent_comment",
            "sender_preview",
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
        return PostSerializer(notice.post, context=self.context).data

    def get_sender_preview(self, notice):

        if notice.content == "PostComment":
            return NoticeCommentSerializer(
                notice.post.comments.exclude(author=notice.user).last()
            ).data
        elif notice.content == "CommentComment":
            return NoticeCommentSerializer(
                notice.parent_comment.children.exclude(author=notice.user).last()
            ).data
        else:
            return NoticeSenderSerializer(notice.senders.last()).data

    def get_senders(self, notice):
        if notice.content == "PostComment":
            recent_user = notice.post.comments.exclude(author=notice.user).last().author
        elif notice.content == "CommentComment":
            recent_user = (
                notice.parent_comment.children.exclude(author=notice.user).last().author
            )
        else:
            recent_user = notice.senders.last().user

        return NoticeSenderSerializer(
            notice.senders.exclude(user=recent_user), many=True
        ).data

    def get_parent_comment(self, notice):

        return NoticeCommentSerializer(notice.parent_comment).data

    def get_count(self, notice):
        return notice.senders.count() - 1


class NoticeSenderSerializer(serializers.ModelSerializer):

    user_id = serializers.IntegerField(source="user.id")
    username = serializers.CharField(source="user.username")

    class Meta:
        model = NoticeSender
        fields = (
            "user_id",
            "username",
        )


class NoticeCommentSerializer(serializers.ModelSerializer):

    user_id = serializers.IntegerField(source="author.id")
    username = serializers.CharField(source="author.username")
    comment_id = serializers.IntegerField(source="id")

    class Meta:
        model = Comment
        fields = ("user_id", "username", "comment_id", "content", "file")
