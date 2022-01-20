from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_serializer_method
from rest_framework import serializers
from rest_framework_jwt.settings import api_settings
from .models import Post, Comment
from user.serializers import UserSerializer
from user.models import User
from .utils import format_time
from pytz import timezone


class PostSerializer(serializers.ModelSerializer):

    subposts = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()
    shared_post = serializers.SerializerMethodField()
    shared_counts = serializers.SerializerMethodField()
    posted_at = serializers.SerializerMethodField()
    is_noticed = serializers.SerializerMethodField()
    tagged_users = serializers.SerializerMethodField()

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
            "is_noticed",
            "tagged_users",
        )
        extra_kwargs = {"content": {"help_text": "무슨 생각을 하고 계신가요?"}}

    def create(self, validated_data):

        mainpost = validated_data.get("mainpost", None)
        author = self.context["request"].user
        content = validated_data.get("content", "")
        scope = validated_data["scope"]
        shared_post = self.context["request"].data.get("shared_post")

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
            return None

        user = self.context["request"].user
        if user == shared_post.author:
            pass
        elif user in shared_post.author.friends.all():
            if shared_post.scope == 1:
                return None
        else:
            if shared_post.scope != 3:
                return None

        return PostSerializer(shared_post, context=self.context).data

    def get_shared_counts(self, post):
        return post.sharing_posts.count()

    def get_is_noticed(self, post):
        user = self.context["request"].user
        if post.notice_off_users.filter(id=user.id).exists():
            return False
        else:
            return True

    def get_tagged_users(self, post):
        return TagUserSerializer(post.tagged_users, many=True).data


class SubPostSerializer(serializers.ModelSerializer):

    posted_at = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    is_noticed = serializers.SerializerMethodField()
    shared_counts = serializers.SerializerMethodField()
    tagged_users = serializers.SerializerMethodField()

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
            "is_noticed",
            "shared_counts",
            "tagged_users",
        )

    def get_posted_at(self, post):
        return format_time(post.created)

    def get_comments(self, post):
        return post.comments.count()

    def get_shared_counts(self, post):
        return post.sharing_posts.count()

    def get_is_liked(self, post):
        request = self.context.get("request")
        if not request:
            return None

        if post.likeusers.filter(pk=request.user.id).exists():
            return True

        return False

    def get_is_noticed(self, post):
        user = self.context["request"].user
        if post.notice_off_users.filter(id=user.id).exists():
            return False
        else:
            return True

    def get_tagged_users(self, post):
        return TagUserSerializer(post.tagged_users, many=True).data


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


class CommentCreateSerializer(serializers.ModelSerializer):
    class Meta:

        model = Comment

        fields = (
            "id",
            "post",
            "author",
            "content",
            "parent",
        )

    def create(self, validated_data):
        comment = Comment.objects.create(
            post=validated_data["post"],
            author=validated_data["author"],
            content=validated_data["content"],
            parent=validated_data.get("parent"),
            depth=validated_data.get("depth"),
        )

        return comment

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


class CommentSerializer(serializers.ModelSerializer):
    is_liked = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()
    tagged_users = serializers.SerializerMethodField()

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
            "tagged_users",
        )

    def get_is_liked(self, comment):
        request = self.context.get("request")
        if not request:
            return None

        if comment.likeusers.filter(pk=request.user.id).exists():
            return True

        return False

    def get_author(self, comment):
        return UserSerializer(comment.author).data

    def get_tagged_users(self, post):
        return TagUserSerializer(post.tagged_users, many=True).data


class CommentListSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    posted_at = serializers.SerializerMethodField()
    children_count = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    tagged_users = serializers.SerializerMethodField()

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
            "tagged_users",
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

    def get_tagged_users(self, post):
        return TagUserSerializer(post.tagged_users, many=True).data


class TagUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "username",
        )
