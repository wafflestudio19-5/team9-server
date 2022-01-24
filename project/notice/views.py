from .pagination import NoticePagination
from .serializers import NoticeSerializer, NoticelistSerializer
from .models import NoticeSender, Notice
from newsfeed.serializers import PostSerializer
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView, ListAPIView
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, permissions
from newsfeed.models import Post
from datetime import datetime


def NoticeCreate(**context):
    content = context["content"]
    sender = context["sender"]
    post = context.get("post")
    parent_comment = context.get("parent_comment")
    receiver = context["receiver"]

    if post:
        if post.notice_off_users.filter(id=receiver.id).exists():
            return None

    if parent_comment:
        notice = receiver.notices.filter(
            post=post, parent_comment=parent_comment, content=content
        )

    elif "Friend" in content:

        if content == "FriendAccept":
            notice = sender.notices.filter(
                content="FriendRequest", senders__user=receiver
            )
            if notice.exists():
                notice = notice[0]
                notice.is_accepted = True
                notice.is_checked = True
                notice.save()

        data = {
            "user": receiver,
            "content": content,
            "url": f"api/v1/user/{sender.id}/newsfeed/",
        }
        serializer = NoticeSerializer(
            data=data,
            context={"sender": sender},
        )
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    else:
        notice = receiver.notices.filter(post=post, content=content)

    if notice:
        notice = notice[0]
        notice.created = datetime.now()
        notice.save()
        notice_sender = notice.senders.filter(user=sender)
        if notice_sender.exists():
            notice_sender = notice_sender[0]
            notice_sender.count += 1
            notice_sender.save()
        else:
            NoticeSender.objects.create(notice=notice, user=sender, count=1)

    else:

        data = {
            "user": receiver.id,
            "content": content,
            "post": post.id,
            "url": f"api/v1/newsfeed/{post.id}/",
        }
        context = {"sender": sender}
        if parent_comment:
            data["parent_comment"] = parent_comment.id

        if content == "CommentComment" or content == "CommentTag":
            if parent_comment:
                data["url"] = f"api/v1/newsfeed/{post.id}/{parent_comment.id}/"

        serializer = NoticeSerializer(
            data=data,
            context=context,
        )
        serializer.is_valid(raise_exception=True)
        return serializer.save()


def NoticeCancel(**context):

    receiver = context["receiver"]
    sender = context["sender"]
    content = context["content"]
    post = context.get("post")
    parent_comment = context.get("parent_comment")

    if post:
        if post.notice_off_users.filter(id=receiver.id).exists():
            return False

    if content == "FriendRequest":
        notice = receiver.notices.filter(senders__user=sender, content=content)
        if notice.exists():
            notice = notice[0]
            notice.delete()
            return True
        return False

    else:
        if parent_comment:
            notice = receiver.notices.filter(
                post=post, parent_comment=parent_comment, content=content
            )
        else:
            notice = receiver.notices.filter(post=post, content=content)

        if notice.exists():
            notice = notice[0]

            notice_sender = notice.senders.filter(user=sender)

            if notice_sender.exists():
                notice_sender = notice_sender[0]
                if notice_sender.count > 1:
                    notice_sender.count -= 1
                    notice_sender.save()
                else:
                    notice_sender.delete()

            if notice.senders.count() == 0:
                notice.delete()

        return True


class NoticeView(GenericAPIView):
    serializer_class = NoticelistSerializer

    @swagger_auto_schema(
        operation_description="알림 읽기",
        responses={200: NoticelistSerializer()},
    )
    def get(self, request, notice_id=None):
        notice = get_object_or_404(request.user.notices, id=notice_id)
        notice.is_checked = True
        notice.save()
        return Response(
            self.get_serializer(notice).data,
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        operation_description="알림 삭제하기",
    )
    def delete(self, request, notice_id=None):

        notice = get_object_or_404(request.user.notices, id=notice_id)

        return Response(notice.delete(), status=status.HTTP_204_NO_CONTENT)


class NoticeListView(ListAPIView):
    serializer_class = NoticelistSerializer
    queryset = Notice.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = NoticePagination

    @swagger_auto_schema(
        operation_description="알림 목록 불러오기",
        responses={200: NoticelistSerializer(many=True)},
    )
    def get(self, request):
        self.queryset = request.user.notices.all()
        return super().list(request)

    def put(self, request):
        notices = request.user.notices.all()
        for notice in notices:
            notice.is_checked = False
            notice.save()
        self.queryset = request.user.notices.all()
        return super().list(request)


class NoticeOnOffView(GenericAPIView):
    serializer_class = PostSerializer

    def put(self, request, post_id=None):
        post = get_object_or_404(Post, id=post_id)

        user = request.user

        if post.notice_off_users.filter(id=user.id).exists():
            post.notice_off_users.remove(user)
        else:
            post.notice_off_users.add(user)
        post.save()

        return Response(
            self.get_serializer(post).data,
            status=status.HTTP_200_OK,
        )
