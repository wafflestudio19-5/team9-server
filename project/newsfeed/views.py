from drf_yasg import openapi
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from typing import Type
from django.db.models import Q

from .serializers import PostListSerializer, PostSerializer, PostLikeSerializer, CommentListSerializer, \
    CommentSerializer
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
                "images": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    description="Array of Image URLs",
                    default=[],
                    items=openapi.TYPE_STRING,
                ),
            },
        ),
        responses={201: PostSerializer()},
    )
    def post(self, request):

        user = request.user
        request.data["author"] = request.user.id
        serializer = PostSerializer(
            data=request.data, context={"files": request.data["files"]}
        )
        serializer.is_valid(raise_exception=True)
        post = serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class LikeViewSet(viewsets.GenericViewSet):
    serializer_class = PostSerializer
    queryset = Post.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        operation_description="좋아요하기",
        request_body=no_body,
        manual_parameters=[jwt_header],
    )
    def update(self, request, pk=None):
        user = request.user
        post = get_object_or_404(self.queryset, pk=pk)
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
        operation_description="좋아요 취소하기",
        responses={200: PostSerializer()},
        manual_parameters=[jwt_header],
    )
    def destroy(self, request, pk=None):
        user = request.user
        post = get_object_or_404(self.queryset, pk=pk)
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
    def retrieve(self, request, pk=None):
        post = get_object_or_404(self.queryset, pk=pk)
        return Response(PostLikeSerializer(post).data, status=status.HTTP_200_OK)


class CommentListView(ListCreateAPIView):

    serializer_class = CommentListSerializer
    queryset = Comment.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        post = request.data["post"]
        self.queryset = Comment.objects.filter(post=post)
        return super().list(request)

    def post(self, request):

        request.data["author"] = request.user.id
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)



