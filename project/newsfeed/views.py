from drf_yasg import openapi
from rest_framework import status, viewsets, permissions, parsers
from rest_framework.decorators import action
from rest_framework.generics import (
    ListCreateAPIView,
    GenericAPIView,
    ListAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.response import Response
from typing import Type
from django.db.models import Q
from django.db import transaction
from rest_framework.views import APIView

from .pagination import NoticePagination
from .serializers import (
    NoticeSerializer,
    NoticelistSerializer,
    PostSerializer,
    PostLikeSerializer,
    CommentListSerializer,
    CommentCreateSerializer,
    CommentSerializer,
    CommentLikeSerializer,
    CommentPostSwaggerSerializer,
)
from .models import Notice, Post, Comment, NoticeSender
from user.models import User
from datetime import datetime
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema, no_body
from rest_framework.parsers import DataAndFiles, MultiPartParser, FormParser, JSONParser


class PostListView(ListCreateAPIView):

    serializer_class = PostSerializer
    queryset = Post.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        operation_description="로그인된 유저의 friend들의 post들을 최신순으로 가져오기(현재는 모든 유저 가져오도록 설정되어 있음)",
        responses={200: PostSerializer()},
    )
    def get(self, request):

        user = request.user

        self.queryset = Post.objects.filter(
            (Q(author__in=user.friends.all()) | Q(author=user)),
            mainpost=None,
            scope__gt=1,
        )

        return super().list(request)

    @swagger_auto_schema(
        operation_description="Post 작성하기",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "content": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Post Content"
                ),
                "scope": openapi.Schema(
                    type=openapi.TYPE_NUMBER,
                    description="공개범위 설정: 1(자기 자신), 2(친구), 3(전체 공개)",
                    default=3,
                ),
            },
        ),
        responses={201: PostSerializer()},
    )
    @transaction.atomic
    def post(self, request):

        user = request.user

        shared_post = request.data.get("shared_post")

        files = request.FILES.getlist("file")

        tagged_users = request.data.getlist("tagged_users", [])

        context = {"isFile": False, "request": request}

        if files or shared_post:
            context["isFile"] = True

        scope = request.data.get("scope", 3)
        data = request.data.copy()
        data["scope"] = scope
        serializer = PostSerializer(data=data, context=context)

        serializer.is_valid(raise_exception=True)
        mainpost = serializer.save()
        for tagged_user in tagged_users:
            tagged_user = int(tagged_user)
            mainpost.tagged_users.add(tagged_user)
            mainpost.save()
            if user.id != tagged_user:
                NoticeCreate(
                    sender=user,
                    receiver=User.objects.get(id=tagged_user),
                    content="PostTag",
                    post=mainpost,
                )

        if files:
            contents = request.data.getlist("subposts", [])
            subposts_tagged_users = request.data.getlist("subposts_tagged_users", [])

            for i in range(len(files)):

                if len(contents) > i:
                    serializer = PostSerializer(
                        data={
                            "content": contents[i],
                            "mainpost": mainpost.id,
                            "scope": scope,
                        },
                        context=context,
                    )
                else:
                    serializer = PostSerializer(
                        data={"mainpost": mainpost.id, "scope": scope},
                        context=context,
                    )
                serializer.is_valid(raise_exception=True)
                subpost = serializer.save()
                subpost.file.save(files[i].name, files[i], save=True)

                if len(subposts_tagged_users) > i:
                    subpost_tagged_users = list(
                        subposts_tagged_users[i][1:-1].split(",")
                    )

                else:
                    subpost_tagged_users = []

                for subpost_tagged_user in subpost_tagged_users:
                    subpost_tagged_user = int(subpost_tagged_user)
                    subpost.tagged_users.add(subpost_tagged_user)
                    subpost.save()
                    if user.id != subpost_tagged_user:
                        NoticeCreate(
                            sender=user,
                            receiver=User.objects.get(id=subpost_tagged_user),
                            content="PostTag",
                            post=subpost,
                        )

        return Response(
            PostSerializer(mainpost, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class PostUpdateView(RetrieveUpdateDestroyAPIView):
    serializer_class = PostSerializer
    queryset = Post.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    @swagger_auto_schema(
        operation_description="Post 조회하기", responses={200: PostSerializer()}
    )
    def get(self, request, pk=None):

        post = get_object_or_404(Post, pk=pk)
        user = request.user

        if post.author == user:
            pass

        elif user in post.author.friends.all():
            if post.scope == 1:
                return Response(
                    status=status.HTTP_404_NOT_FOUND, data="해당 게시글이 존재하지 않습니다."
                )

        else:
            if post.scope < 3:
                return Response(
                    status=status.HTTP_404_NOT_FOUND, data="해당 게시글이 존재하지 않습니다."
                )
        return Response(
            PostSerializer(post, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        operation_description="게시글 수정하기",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "content": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="main post의 content",
                ),
                "subposts": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    description="subpost들의 content의 array",
                    items=openapi.TYPE_STRING,
                ),
                "subposts_id": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    description="기존 subpost들의 id의 array",
                    items=openapi.TYPE_NUMBER,
                ),
                "removed_subposts_id": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    description="삭제될 subpost들의 id의 array",
                    items=openapi.TYPE_NUMBER,
                ),
                "scope": openapi.Schema(
                    type=openapi.TYPE_NUMBER,
                    description="공개범위 설정: 1(자기 자신), 2(친구), 3(전체 공개)",
                    default=3,
                ),
            },
        ),
        responses={200: PostSerializer()},
    )
    def put(self, request, pk=None):

        post = get_object_or_404(Post, pk=pk)
        user = request.user

        if post.mainpost:
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data="MainPost만 수정 가능합니다."
            )

        if user != post.author:
            return Response(
                status=status.HTTP_403_FORBIDDEN, data="다른 유저의 게시글을 수정할 수 없습니다."
            )

        files = request.FILES.getlist("file")
        contents = request.data.getlist("subposts", [])
        subposts = request.data.getlist("subposts_id")
        cnt = post.subposts.count()
        scope = request.data.get("scope")
        removed = request.data.getlist("removed_subposts_id")
        tagged_users = request.data.getlist("tagged_users")

        if cnt != len(set(subposts)):
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data="subposts_id에 기존 subpost들의 id를 넣어주세요.",
            )

        if scope:

            if (not scope.isdigit()) or int(scope) > 3 or int(scope) < 1:
                return Response(
                    status=status.HTTP_400_BAD_REQUEST, data="공개범위는 1, 2, 3 중에 선택해주세요."
                )

            scope = int(scope)

        # mainpost 수정
        content = request.data.get("content")
        if (set(subposts) == set(removed)) and not files:

            if not content:
                return Response(status=status.HTTP_400_BAD_REQUEST, data="내용을 입력해주세요.")

        post.content = request.data.get("content")

        if scope:
            post.scope = scope

        for before_tagged_user in post.tagged_users.all():
            NoticeCancel(
                sender=user,
                receiver=before_tagged_user,
                content="PostTag",
                post=post,
            )
        post.tagged_users.clear()
        for tagged_user in tagged_users:
            tagged_user = int(tagged_user)
            post.tagged_users.add(tagged_user)
            if user.id != tagged_user:
                NoticeCreate(
                    sender=user,
                    receiver=User.objects.get(id=tagged_user),
                    content="PostTag",
                    post=post,
                )
        post.save()

        # 기존의 subposts content 수정 및 subpost 삭제
        subposts_tagged_users = request.data.getlist("subposts_tagged_users")
        for i in range(len(subposts)):
            subpost = get_object_or_404(post.subposts, id=subposts[i])

            if str(subpost.id) in removed:
                subpost.delete()
            else:
                subpost.content = contents[i]
                if scope:
                    subpost.scope = scope

                if len(subposts_tagged_users) > i:
                    subpost_tagged_users = list(
                        subposts_tagged_users[i][1:-1].split(",")
                    )
                else:
                    subpost_tagged_users = []

                for before_tagged_user in subpost.tagged_users.all():
                    NoticeCancel(
                        sender=user,
                        receiver=before_tagged_user,
                        content="PostTag",
                        post=subpost,
                    )
                subpost.tagged_users.clear()

                for subpost_tagged_user in subpost_tagged_users:
                    subpost_tagged_user = int(subpost_tagged_user)
                    subpost.tagged_users.add(subpost_tagged_user)
                    if user.id != subpost_tagged_user:
                        NoticeCreate(
                            sender=user,
                            receiver=User.objects.get(id=subpost_tagged_user),
                            content="PostTag",
                            post=subpost,
                        )
                subpost.save()

        # 파일 추가하는 경우 subpost 추가
        if files:
            for i in range(len(files)):
                idx = i + len(subposts)
                serializer = PostSerializer(
                    data={
                        "content": contents[idx],
                        "mainpost": post.id,
                        "scope": post.scope,
                    },
                    context={"isFile": True, "request": request},
                )
                serializer.is_valid(raise_exception=True)
                subpost = serializer.save()
                subpost.file.save(files[i].name, files[i], save=True)

                if len(subposts_tagged_users) > idx:
                    subpost_tagged_users = list(
                        subposts_tagged_users[idx][1:-1].split(",")
                    )

                else:
                    subpost_tagged_users = []

                for subpost_tagged_user in subpost_tagged_users:
                    subpost_tagged_user = int(subpost_tagged_user)
                    subpost.tagged_users.add(subpost_tagged_user)
                    subpost.save()
                    if user.id != subpost_tagged_user:
                        NoticeCreate(
                            sender=user,
                            receiver=User.objects.get(id=subpost_tagged_user),
                            content="PostTag",
                            post=subpost,
                        )

        return Response(
            self.get_serializer(post).data,
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        operation_description="게시글 삭제하기",
    )
    def delete(self, request, pk=None):

        post = get_object_or_404(Post, pk=pk)
        if request.user != post.author:
            return Response(
                status=status.HTTP_403_FORBIDDEN, data="다른 유저의 게시글을 삭제할 수 없습니다."
            )

        if post.tagged_users.all().exists():
            for tagged_user in post.tagged_users.all():
                if request.user != tagged_user:
                    NoticeCancel(
                        sender=request.user,
                        receiver=tagged_user,
                        content="PostTag",
                        post=post,
                    )
        if post.subposts.all().exists():
            for subpost in post.subposts.all():
                if subpost.tagged_users.all().exists():
                    for tagged_user in subpost.tagged_users.all():
                        if request.user != tagged_user:
                            NoticeCancel(
                                sender=request.user,
                                receiver=tagged_user,
                                content="PostTag",
                                post=post,
                            )

        return super().destroy(request, pk=pk)

    # 부모의 patch 메서드를 drf-yasg가 읽지 않게 오버리이딩
    @swagger_auto_schema(auto_schema=None)
    def patch(self, request, *args, **kwargs):
        return Response(status.HTTP_204_NO_CONTENT)


class PostLikeView(GenericAPIView):
    serializer_class = PostSerializer
    queryset = Post.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        operation_description="게시물 좋아요하기",
        request_body=no_body,
    )
    def put(self, request, post_id=None):
        user = request.user
        post = get_object_or_404(self.queryset, pk=post_id)
        """
        if (
            not user.friends.filter(id=post.author.id).exists()
            and post.author.id != user.id
        ):
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data="친구 혹은 자신의 게시글이 아닙니다."
            )
        """
        # 친구만 좋아요 할 수 있도록 하는 기능 해제
        # 이미 좋아요 한 게시물 -> 좋아요 취소, 관련 알림 삭제
        if post.likeusers.filter(id=user.id).exists():
            post.likeusers.remove(user)
            post.likes = post.likes - 1
            post.save()
            if user.id != post.author.id:
                NoticeCancel(
                    sender=user,
                    receiver=post.author,
                    content="PostLike",
                    post=post,
                )

        # 좋아요 하지 않은 게시물 -> 좋아요 하기, 알림 생성
        else:
            post.likeusers.add(user)
            post.likes = post.likes + 1
            post.save()

            if user.id != post.author.id:
                NoticeCreate(
                    sender=user, receiver=post.author, content="PostLike", post=post
                )

        return Response(self.get_serializer(post).data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="해당 post의 좋아요 개수, 좋아요 한 유저 가져오기",
        responses={200: PostLikeSerializer()},
    )
    def get(self, request, post_id=None):
        post = get_object_or_404(self.queryset, pk=post_id)
        return Response(PostLikeSerializer(post).data, status=status.HTTP_200_OK)


class CommentListView(ListCreateAPIView):
    serializer_class = CommentListSerializer
    queryset = Post.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (parsers.MultiPartParser, parsers.FileUploadParser)

    # ListModelMixin의 list() 메소드 오버라이딩
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        # 하나의 페이지 안에서 댓글들의 순서 역전
        page = reversed(self.paginate_queryset(queryset))
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="해당 post의 comment들 가져오기",
        responses={200: CommentListSerializer()},
    )
    def get(self, request, post_id=None):
        self.queryset = Comment.objects.filter(post=post_id, depth=0).order_by("-id")
        return self.list(request)

    @swagger_auto_schema(
        operation_description="comment 생성하기",
        responses={201: CommentSerializer()},
        manual_parameters=[
            openapi.Parameter(
                name="file",
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=False,
            ),
        ],
        request_body=CommentPostSwaggerSerializer(),
    )
    @transaction.atomic
    def post(self, request, post_id=None):
        user = request.user
        data = request.data.copy()
        data["author"] = user.id

        post = get_object_or_404(self.queryset, pk=post_id)
        data["post"] = post.id

        tagged_users = request.data.getlist("tagged_users")

        """
        if (
            not user.friends.filter(id=post.author.id).exists()
            and post.author.id != user.id
        ):
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data="친구 혹은 자신의 게시글이 아닙니다."
            )
        """
        # 친구만 댓글 달 수 있도록 하는 기능 해제
        serializer = CommentCreateSerializer(
            data=data, context={"user": user, "post": post}
        )
        serializer.is_valid(raise_exception=True)
        comment = serializer.save()

        file = request.FILES.get("file")
        if file:
            comment.file.save(file.name, file, save=True)

        if data.get("parent"):
            if user.id != comment.parent.author.id:
                NoticeCreate(
                    sender=user,
                    receiver=comment.parent.author,
                    content="CommentComment",
                    post=post,
                    parent_comment=comment.parent,
                )
        else:
            if user.id != post.author.id:
                NoticeCreate(
                    sender=user,
                    receiver=post.author,
                    content="PostComment",
                    post=post,
                )

        for tagged_user in tagged_users:
            tagged_user = int(tagged_user)
            comment.tagged_users.add(tagged_user)
            comment.save()
            if user.id != tagged_user:
                NoticeCreate(
                    sender=user,
                    receiver=User.objects.get(id=tagged_user),
                    content="CommentTag",
                    post=post,
                    parent_comment=comment.parent,
                )

        return Response(
            self.get_serializer(comment).data, status=status.HTTP_201_CREATED
        )


class CommentUpdateDeleteView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    queryset = Comment.objects.all()

    @swagger_auto_schema(
        operation_description="comment 수정하기",
        responses={200: CommentSerializer()},
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "content": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Comment Content"
                ),
            },
        ),
    )
    def put(self, request, post_id=None, comment_id=None):
        comment = get_object_or_404(self.queryset, pk=comment_id, post=post_id)
        if comment.author != request.user:
            return Response(
                status=status.HTTP_403_FORBIDDEN, data="다른 유저의 댓글을 수정할 수 없습니다."
            )

        content = request.data.get("content")

        if not content:
            return Response(status=status.HTTP_400_BAD_REQUEST, data="content를 입력해주세요")

        comment.content = content

        tagged_users = request.data.getlist("tagged_users")
        for before_tagged_user in comment.tagged_users.all():
            NoticeCancel(
                sender=request.user,
                receiver=before_tagged_user,
                content="CommentTag",
                post=comment.post,
                parent_comment=comment.parent,
            )
        comment.tagged_users.clear()
        for tagged_user in tagged_users:
            tagged_user = int(tagged_user)
            comment.tagged_users.add(tagged_user)
            if request.user.id != tagged_user:
                NoticeCreate(
                    sender=request.user,
                    receiver=User.objects.get(id=tagged_user),
                    content="CommentTag",
                    post=comment.post,
                    parent_comment=comment.parent,
                )
        comment.save()
        return Response(status=status.HTTP_200_OK, data=CommentSerializer(comment).data)

    @swagger_auto_schema(
        operation_description="comment 삭제하기",
    )
    def delete(self, request, post_id=None, comment_id=None):
        comment = get_object_or_404(self.queryset, pk=comment_id, post=post_id)
        user = request.user
        if comment.author != user:
            return Response(
                status=status.HTTP_403_FORBIDDEN, data="다른 유저의 댓글을 삭제할 수 없습니다."
            )
        parent = comment.parent
        post = comment.post
        if parent:
            if user.id != parent.author.id:
                NoticeCancel(
                    sender=user,
                    receiver=parent.author,
                    content="CommentComment",
                    post=post,
                    parent_comment=parent,
                )

        else:
            if user.id != post.author.id:
                NoticeCancel(
                    sender=user,
                    receiver=post.author,
                    content="PostComment",
                    post=post,
                )
        if comment.tagged_users.all().exists():
            for tagged_user in comment.tagged_users.all():
                if user != tagged_user:
                    NoticeCancel(
                        sender=user,
                        receiver=tagged_user,
                        content="CommentTag",
                        post=post,
                        parent_comment=parent,
                    )

        comment.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @swagger_auto_schema(
        operation_description="특정 comment 가져오기",
        responses={200: CommentSerializer()},
    )
    def get(self, request, post_id=None, comment_id=None):

        comment = get_object_or_404(self.queryset, pk=comment_id, post=post_id)
        post = comment.post
        user = request.user

        if post.author == user:
            pass

        elif user in post.author.friends.all():
            if post.scope == 1:
                return Response(
                    status=status.HTTP_404_NOT_FOUND, data="해당 게시글이 존재하지 않습니다."
                )

        else:
            if post.scope < 3:
                return Response(
                    status=status.HTTP_404_NOT_FOUND, data="해당 게시글이 존재하지 않습니다."
                )

        return Response(status=status.HTTP_200_OK, data=CommentSerializer(comment).data)


class CommentLikeView(GenericAPIView):
    serializer_class = CommentSerializer
    queryset = Comment.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        operation_description="comment 좋아요하기",
        request_body=no_body,
    )
    def put(self, request, post_id=None, comment_id=None):
        user = request.user
        comment = get_object_or_404(self.queryset, pk=comment_id, post=post_id)
        post = comment.post

        # 이미 좋아요 한 댓글 -> 좋아요 취소, 관련 알림 삭제
        if comment.likeusers.filter(id=user.id).exists():
            comment.likeusers.remove(user)
            comment.likes = comment.likes - 1
            comment.save()

            if user.id != comment.author.id:
                NoticeCancel(
                    sender=user,
                    receiver=comment.author,
                    content="CommentLike",
                    post=post,
                    parent_comment=comment,
                )

        # 좋아요 하지 않은 댓글 -> 좋아요 하기, 알림 생성
        else:
            comment.likeusers.add(user)
            comment.likes = comment.likes + 1
            comment.save()

            if user.id != comment.author.id:
                NoticeCreate(
                    sender=user,
                    receiver=comment.author,
                    content="CommentLike",
                    post=post,
                    parent_comment=comment,
                )

        return Response(self.get_serializer(comment).data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="해당 comment의 좋아요 개수, 좋아요 한 유저 가져오기",
        responses={200: CommentLikeSerializer()},
    )
    def get(self, request, post_id=None, comment_id=None):
        comment = get_object_or_404(self.queryset, pk=comment_id, post=post_id)
        return Response(CommentLikeSerializer(comment).data, status=status.HTTP_200_OK)


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
                notice.content = "isFriend"
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
        notice_sender = notice.senders.filter(user=sender)
        if notice_sender.exists():
            notice_sender = notice_sender[0]
            count = notice_sender.count + 1
            notice_sender.delete()
            NoticeSender.objects.create(notice=notice, user=sender, count=count)
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


class TestView(GenericAPIView):
    def put(self, request):
        print(request.data["email"]["data"])
        return Response(
            status=status.HTTP_200_OK,
        )
