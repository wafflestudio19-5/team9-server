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
        if notice.parent_comment:
            return NoticeCommentSerializer(notice.parent_comment).data
        return None

    def get_count(self, notice):
        return notice.senders.count() - 1


class NoticeSenderSerializer(serializers.ModelSerializer):

    user = serializers.SerializerMethodField()

    class Meta:
        model = NoticeSender
        fields = ("user",)

    def get_user(self, notice):
        return UserSerializer(notice.user).data


class NoticeCommentSerializer(serializers.ModelSerializer):

    user = serializers.SerializerMethodField()
    comment_id = serializers.IntegerField(source="id")
    is_file = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ("user", "comment_id", "content", "is_file")

    def get_user(self, comment):
        return UserSerializer(comment.author).data

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
