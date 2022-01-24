from rest_framework import serializers
from newsfeed.models import Post, Comment
from .models import Notice, NoticeSender
from user.serializers import UserSerializer
from newsfeed.serializers import PostSerializer
from .utils import notice_format_time


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

        notice = Notice.objects.create(
            user=user,
            content=content,
            post=post,
            parent_comment=parent_comment,
            url=url,
        )
        NoticeSender.objects.create(user=sender, notice=notice, count=1)

        return notice


class NoticelistSerializer(serializers.ModelSerializer):

    posted_at = serializers.SerializerMethodField()
    post = serializers.SerializerMethodField()
    parent_comment = serializers.SerializerMethodField()
    comment_preview = serializers.SerializerMethodField()
    senders = serializers.SerializerMethodField()
    count = serializers.SerializerMethodField()
    sender_preview = serializers.SerializerMethodField()

    class Meta:
        model = Notice
        fields = (
            "id",
            "user",
            "content",
            "sender_preview",
            "senders",
            "count",
            "post",
            "parent_comment",
            "comment_preview",
            "posted_at",
            "is_checked",
            "is_accepted",
            "url",
        )

    def get_posted_at(self, notice):
        posted_at = notice_format_time(notice.created)
        if posted_at == False:
            notice.delete()
        return posted_at

    def get_post(self, notice):
        if notice.post:
            return PostSerializer(notice.post, context=self.context).data
        return None

    def get_sender_preview(self, notice):

        if notice.content == "PostComment":
            return UserSerializer(
                notice.post.comments.exclude(author=notice.user).last().author
            ).data
        elif notice.content == "CommentComment":
            return UserSerializer(
                notice.parent_comment.children.exclude(author=notice.user).last().author
            ).data

        elif notice.content == "CommentTag":
            if notice.parent_comment:
                return UserSerializer(
                    notice.parent_comment.children.filter(tagged_users=notice.user)
                    .exclude(author=notice.user)
                    .last()
                    .author
                ).data
            else:
                return UserSerializer(
                    notice.post.comments.filter(tagged_users=notice.user)
                    .exclude(author=notice.user)
                    .last()
                    .author
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
        if notice.parent_comment:
            return NoticeCommentSerializer(notice.parent_comment).data
        return None

    def get_comment_preview(self, notice):
        if notice.content == "PostComment":
            recent_comment = notice.post.comments.exclude(author=notice.user).last()
        elif notice.content == "CommentComment":
            recent_comment = notice.parent_comment.children.exclude(
                author=notice.user
            ).last()

        else:
            return None

        return NoticeCommentSerializer(recent_comment).data

    def get_count(self, notice):
        return notice.senders.count() - 1


class NoticeSenderSerializer(serializers.ModelSerializer):

    id = serializers.IntegerField(source="user.id")
    email = serializers.EmailField(source="user.email")
    username = serializers.CharField(source="user.username")
    profile_image = serializers.FileField(source="user.profile_image")
    is_valid = serializers.BooleanField(source="user.is_valid")

    class Meta:
        model = NoticeSender
        fields = ("id", "email", "username", "profile_image", "is_valid")


class NoticeCommentSerializer(serializers.ModelSerializer):

    is_file = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ("id", "content", "is_file")

    def get_is_file(self, comment):
        if comment.file:
            extension = comment.file.name.split(".")[-1]
            if extension == "jpg" or extension == "png" or extension == "jpeg":
                return "photo"
            elif extension == "gif":
                return "sticker"
            else:
                return "else"
        else:
            return None
