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
import boto3
from .serializers import (
    NoticeSerializer,
    NoticelistSerializer,
    MainPostSerializer,
    PostSerializer,
    PostLikeSerializer,
    CommentListSerializer,
    CommentSerializer,
    CommentLikeSerializer,
    CommentPostSwaggerSerializer,
)
from .models import Notice, Post, Comment
from user.models import User
from datetime import datetime
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema, no_body
from rest_framework.parsers import DataAndFiles, MultiPartParser, FormParser, JSONParser


class PostListView(ListCreateAPIView):

    serializer_class = MainPostSerializer
    queryset = Post.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        operation_description="로그인된 유저의 friend들의 post들을 최신순으로 가져오기(현재는 모든 유저 가져오도록 설정되어 있음)",
        responses={200: MainPostSerializer()},
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
                "files": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    description='"content", "file"을 key로 가지는 Dictionary들의 Array',
                    default=[],
                    items=openapi.TYPE_OBJECT,
                ),
                "scope": openapi.Schema(
                    type=openapi.TYPE_NUMBER, description="공개범위 설정: 1(자기 자신), 2(친구), 3(전체 공개)", default=3
                )
            },
        ),
        responses={201: PostSerializer()},
    )
    @transaction.atomic
    def post(self, request):

        user = request.user

        files = request.FILES.getlist("file")
        context = {"isFile": False}
        if files:
            context["isFile"] = True

        context["author"] = user
        scope = request.data.get("scope", 3)
        data = request.data.copy()
        data["scope"] = scope

        serializer = PostSerializer(data=data, context=context)

        serializer.is_valid(raise_exception=True)
        mainpost = serializer.save()
        if files:
            contents = request.data.getlist("subposts", [])

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
        operation_description="Post 조회하기",
        responses={200: PostSerializer()}
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
            self.get_serializer(post).data,
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(
        operation_description="게시글 수정하기",
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
        removed = request.data.getlist("removed_subposts")

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

        if (set(subposts) == set(removed)) and not files:
            content = request.data.get("content")
            if not content:
                return Response(status=status.HTTP_400_BAD_REQUEST, data="내용을 입력해주세요.")
            post.content = content
            if scope:
                post.scope = scope
            post.save()
        else:
            post.content = request.data.get("content")
            if scope:
                post.scope = scope
            post.save()

        for i in range(len(subposts)):
            subpost = get_object_or_404(post.subposts, id=subposts[i])

            if str(subpost.id) in removed:
                subpost.delete()
            else:
                subpost.content = contents[i]
                if scope:
                    subpost.scope = scope
                subpost.save()

        if files:
            for i in range(len(files)):
                idx = i + len(subposts)
                serializer = PostSerializer(
                    data={
                        "content": contents[idx],
                        "mainpost": post.id,
                        "scope": post.scope,
                    },
                    context={"isFile": True, "author": user},
                )
                serializer.is_valid(raise_exception=True)
                subpost = serializer.save()
                subpost.file.save(files[i].name, files[i], save=True)

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

            notice = Notice.objects.filter(post=post, comment=None)
            if notice.exists():
                notice = notice[0]

                if user in notice.senders.all():
                    if notice.senders.count() > 1:
                        notice.senders.remove(user)
                        notice.count -= 1
                        notice.save()
                    else:
                        notice.delete()

        # 좋아요 하지 않은 게시물 -> 좋아요 하기, 알림 생성
        else:
            post.likeusers.add(user)
            post.likes = post.likes + 1
            post.save()

            if user.id != post.author.id:
                NoticeCreate(user=user, content="PostLike", post=post)

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
        serializer = CommentSerializer(data=data, context={"user": user, "post": post})
        serializer.is_valid(raise_exception=True)
        comment = serializer.save()

        file = request.FILES.get("file")
        if file:
            comment.file.save(file.name, file, save=True)

        if user.id != post.author.id:
            NoticeCreate(user=user, content="PostComment", post=post, comment=comment)

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
            }
        )
    )
    def put(self, request, post_id=None, comment_id=None):
        comment = get_object_or_404(self.queryset, pk=comment_id, post=post_id)
        if comment.author != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN, data="다른 유저의 댓글을 수정할 수 없습니다.")

        content = request.data.get("content")

        if not content:
            return Response(status=status.HTTP_400_BAD_REQUEST, data="content를 입력해주세요")

        comment.content = content
        comment.save()
        return Response(status=status.HTTP_200_OK, data=CommentSerializer(comment).data)

    @swagger_auto_schema(
        operation_description="comment 삭제하기",
    )
    def delete(self, request, post_id=None, comment_id=None):
        comment = get_object_or_404(self.queryset, pk=comment_id, post=post_id)

        if comment.author != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN, data="다른 유저의 댓글을 삭제할 수 없습니다.")
        comment.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


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

        # 이미 좋아요 한 댓글 -> 좋아요 취소, 관련 알림 삭제
        if comment.likeusers.filter(id=user.id).exists():
            comment.likeusers.remove(user)
            comment.likes = comment.likes - 1
            comment.save()

            notice = Notice.objects.filter(comment=comment)
            if notice.exists():
                notice = notice[0]
                if user in notice.senders.all():
                    if notice.senders.count() > 1:
                        notice.senders.remove(user)
                        notice.count -= 1
                        notice.save()
                    else:
                        notice.delete()

        # 좋아요 하지 않은 댓글 -> 좋아요 하기, 알림 생성
        else:
            comment.likeusers.add(user)
            comment.likes = comment.likes + 1
            comment.save()

            post = comment.post
            if user.id != comment.author.id:
                NoticeCreate(
                    user=user, content="CommentLike", post=post, comment=comment
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
    user = context["user"]
    post = context.get("post")
    comment = context.get("comment")

    if content == "CommentLike":
        target = comment.author
        notice = target.notices.filter(comment=comment.id, content__contains=content)

    elif "Friend" in content:
        target = context["receiver"]
        data = {
            "user": target,
            "content": content,
            "url": f"api/v1/user/{user.id}/newsfeed/",
        }
        serializer = NoticeSerializer(
            data=data,
            context={"sender": user},
        )
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    else:
        target = post.author
        notice = target.notices.filter(post=post.id, content__contains=content)

    if notice:
        notice = notice[0]
        if user not in notice.senders.all():
            notice.count += 1
            notice.senders.add(user)

        if comment:
            notice.comment = comment
        notice.save()

    else:

        data = {
            "user": target.id,
            "content": content,
            "post": post.id,
            "url": f"api/v1/newsfeed/{post.id}/",
        }
        if comment:
            data["comment"] = comment.id
        if content == "CommentLike":
            data["url"] = f"api/v1/newsfeed/{post.id}/{comment.id}/"

        serializer = NoticeSerializer(
            data=data,
            context={"sender": user},
        )
        serializer.is_valid(raise_exception=True)
        return serializer.save()


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
        notices = request.user.notices.all()
        return super().list(notices)
