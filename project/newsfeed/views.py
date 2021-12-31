from drf_yasg import openapi
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.generics import ListCreateAPIView, GenericAPIView
from rest_framework.response import Response
from typing import Type
from django.db.models import Q
from django.db import transaction

from .pagination import CommentPagination
from .serializers import (
    PostListSerializer,
    PostSerializer,
    PostLikeSerializer,
    CommentListSerializer,
    CommentSerializer,
    CommentLikeSerializer,
)
from .models import Post, Comment
from user.models import User
from datetime import datetime
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema, no_body

jwt_header = openapi.Parameter(
    "Authorization",
    openapi.IN_HEADER,
    type=openapi.TYPE_STRING,
    default="JWT [put token here]",
)


class PostListView(ListCreateAPIView):

    serializer_class = PostListSerializer
    queryset = Post.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        operation_description="로그인된 유저의 friend들의 post들을 최신순으로 가져오기",
        manual_parameters=[jwt_header],
        responses={200: PostListSerializer()},
    )
    def get(self, request):

        user = request.user
        self.queryset = Post.objects.filter(
            (Q(author__in=user.friends.all()) | Q(author=user)), mainpost=None
        )
        return super().list(request)

    @swagger_auto_schema(
        operation_description="Post 작성하기",
        manual_parameters=[jwt_header],
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
            },
        ),
        responses={201: PostSerializer()},
    )
    @transaction.atomic
    def post(self, request):

        user = request.user

        request.data["author"] = user.id

        files = request.FILES.getlist("file")

        serializer = PostSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        mainpost = serializer.save()
        if files:
            for i in range(len(files)):

                serializer = PostSerializer(
                    data={
                        "author": user.id,
                        "content": request.data.getlist("subposts", [""])[i],
                        "mainpost": mainpost.id,
                    }
                )
                serializer.is_valid(raise_exception=True)
                subpost = serializer.save()
                subpost.file.save(files[i].name, files[i], save=True)

        return Response(PostSerializer(mainpost).data, status=status.HTTP_201_CREATED)


class PostLikeView(GenericAPIView):
    serializer_class = PostSerializer
    queryset = Post.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        operation_description="게시물 좋아요하기",
        request_body=no_body,
        manual_parameters=[jwt_header],
    )
    def put(self, request, post_id=None):
        user = request.user
        post = get_object_or_404(self.queryset, pk=post_id)
        if post.likeusers.filter(id=user.id).exists():
            return Response(status=status.HTTP_400_BAD_REQUEST, data="이미 좋아요 한 게시글입니다.")
        if (
            not user.friends.filter(id=post.author.id).exists()
            and post.author.id != user.id
        ):
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data="친구 혹은 자신의 게시글이 아닙니다."
            )
        post.likeusers.add(user)
        post.likes = post.likes + 1
        post.save()
        return Response(self.serializer_class(post).data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="게시물 좋아요 취소하기",
        responses={200: PostSerializer()},
        manual_parameters=[jwt_header],
    )
    def delete(self, request, post_id=None):
        user = request.user
        post = get_object_or_404(self.queryset, pk=post_id)
        if not post.likeusers.filter(id=user.id).exists():
            return Response(status=status.HTTP_400_BAD_REQUEST, data="좋아요하지 않은 게시글입니다.")
        if (
            not user.friends.filter(id=post.author.id).exists()
            and post.author.id != user.id
        ):
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data="친구 혹은 자신의 게시글이 아닙니다."
            )
        post.likeusers.remove(user)
        post.likes = post.likes - 1
        post.save()
        return Response(self.serializer_class(post).data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="해당 post의 좋아요 개수, 좋아요 한 유저 가져오기",
        responses={200: PostLikeSerializer()},
        manual_parameters=[jwt_header],
    )
    def get(self, request, post_id=None):
        post = get_object_or_404(self.queryset, pk=post_id)
        return Response(PostLikeSerializer(post).data, status=status.HTTP_200_OK)


class CommentListView(ListCreateAPIView):
    serializer_class = CommentListSerializer
    queryset = Post.objects.all()
    pagination_class = CommentPagination
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        operation_description="해당 post의 comment들 가져오기",
        responses={200: CommentListSerializer()},
        manual_parameters=[jwt_header],
    )
    def get(self, request, post_id=None):
        self.queryset = Comment.objects.filter(post=post_id, depth=0).order_by("-id")
        return super().list(request)

    @swagger_auto_schema(
        operation_description="comment 생성하기",
        responses={201: CommentSerializer()},
        manual_parameters=[jwt_header],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "content": openapi.Schema(type=openapi.TYPE_STRING),
                "file": openapi.Schema(type=openapi.TYPE_STRING),
                "parent": openapi.Schema(
                    type=openapi.TYPE_NUMBER,
                    description="parent comment ID",
                    default=None,
                ),
            },
        ),
    )
    @transaction.atomic
    def post(self, request, post_id=None):
        user = request.user

        request.data["author"] = user.id
        post = get_object_or_404(self.queryset, pk=post_id)
        request.data["post"] = post.id

        if (
            not user.friends.filter(id=post.author.id).exists()
            and post.author.id != user.id
        ):
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data="친구 혹은 자신의 게시글이 아닙니다."
            )
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = serializer.save()
        file = request.FILES.get("file")
        if file:
            comment.file.save(file.name, file, save=True)
        return Response(
            CommentListSerializer(comment).data, status=status.HTTP_201_CREATED
        )


class CommentLikeView(GenericAPIView):
    serializer_class = CommentSerializer
    queryset = Comment.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        operation_description="comment 좋아요하기",
        request_body=no_body,
        manual_parameters=[jwt_header],
    )
    def put(self, request, post_id=None, comment_id=None):
        user = request.user
        comment = get_object_or_404(self.queryset, pk=comment_id, post=post_id)
        if comment.likeusers.filter(id=user.id).exists():
            return Response(status=status.HTTP_400_BAD_REQUEST, data="이미 좋아요 한 댓글입니다.")
        comment.likeusers.add(user)
        comment.likes = comment.likes + 1
        comment.save()
        return Response(self.serializer_class(comment).data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="comment 좋아요 취소하기",
        responses={200: CommentSerializer()},
        manual_parameters=[jwt_header],
    )
    def delete(self, request, post_id=None, comment_id=None):
        user = request.user
        comment = get_object_or_404(self.queryset, pk=comment_id, post=post_id)
        if not comment.likeusers.filter(id=user.id).exists():
            return Response(status=status.HTTP_400_BAD_REQUEST, data="좋아요하지 않은 댓글입니다.")
        comment.likeusers.remove(user)
        comment.likes = comment.likes - 1
        comment.save()
        return Response(self.serializer_class(comment).data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="해당 comment의 좋아요 개수, 좋아요 한 유저 가져오기",
        responses={200: CommentLikeSerializer()},
        manual_parameters=[jwt_header],
    )
    def get(self, request, post_id=None, comment_id=None):
        comment = get_object_or_404(self.queryset, pk=comment_id, post=post_id)
        return Response(CommentLikeSerializer(comment).data, status=status.HTTP_200_OK)
