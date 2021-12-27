from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_serializer_method
from rest_framework import serializers
from rest_framework_jwt.settings import api_settings
from .models import Post, Comment, NewsfeedObject
from user.serializers import UserSerializer
from datetime import datetime, timedelta
from pytz import timezone

# TODO comment_count 추가하기
class PostSerializer(serializers.ModelSerializer):

    subposts = serializers.SerializerMethodField()

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
        )
        extra_kwargs = {"content": {"help_text": "무슨 생각을 하고 계신가요?"}}

    def create(self, validated_data):

        author = validated_data["author"]
        mainpost = Post.objects.create(
            author=validated_data["author"], content=validated_data["content"]
        )
        files = validated_data.get("files", None)
        if files:
            for file_content in files:
                if file_content:
                    content = file_content.get("content", "")
                    file = file_content.get("file", None)
                    subpost = Post.objects.create(
                        author=author, content=content, mainpost=mainpost, file=file
                    )

        return mainpost

    def validate(self, data):

        content = data.get("content", None)
        files = self.context.get("files", None)

        if not content:
            raise serializers.ValidationError("내용을 입력해주세요.")

        if files:
            if len(files) == 0:
                pass
            else:
                for f in files:
                    file = f.get("file", None)
                    if not file:
                        raise serializers.ValidationError("'file'이 비었습니다.")
                data["files"] = files

        return data

    def get_subposts(self, post):
        return PostSerializer(post.subposts, many=True).data


class PostListSerializer(serializers.ModelSerializer):

    posted_at = serializers.SerializerMethodField()
    subposts = serializers.SerializerMethodField()
    author = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ("id", "author", "content", "subposts", "file", "likes", "posted_at")

    def get_posted_at(self, post):

        created_at = post.created
        now = datetime.now()
        duration = str(now - created_at).split(".")[0]
        return duration

    @swagger_serializer_method(serializer_or_field=PostSerializer)
    def get_subposts(self, post):
        return PostSerializer(post.subposts, many=True).data

    @swagger_serializer_method(serializer_or_field=UserSerializer)
    def get_author(self, post):
        return UserSerializer(post.author).data


class NewsfeedObjectLikeSerializer(serializers.ModelSerializer):
    likeusers = serializers.SerializerMethodField()

    class Meta:
        model = NewsfeedObject
        fields = ("likes", "likeusers")

    @swagger_serializer_method(serializer_or_field=UserSerializer)
    def get_likeusers(self, newsfeed_object):
        return UserSerializer(newsfeed_object.likeusers, many=True).data


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
        )

    def create(self, validated_data):
        return Comment.objects.create(
            post=validated_data["post"],
            author=validated_data["author"],
            content=validated_data["content"],
            file=validated_data.get("file"),
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
                raise serializers.ValidationError("'parent'가 해당 'Post'의 'comment'가 아닙니다.")

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
        created_at = comment.created
        now = datetime.now()
        duration = str(now - created_at).split(".")[0]
        return duration

    def get_children_count(self, comment):
        return comment.children.count()

    def get_children(self, comment):
        children = comment.children.order_by("created")
        # child comment 3개만 노출시키기
        # if children.count() > 2:
        #     children = children[children.count()-4:]
        return CommentListSerializer(children, many=True, context=self.context).data

