from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from typing import Type

from .serializers import (
    PostListSerializer,
    PostSerializer,
    PostLikeSerializer,
    PostImageSerializer,
)
from .models import Post, PostImage
from user.models import User
from datetime import datetime
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema, no_body


class PostViewSet(viewsets.GenericViewSet):

    serializer_class = PostSerializer
    queryset = Post.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(operation_description="로그인된 유저의 friend들의 post들을 최신순으로 가져오기")
    def list(self, request):

        # 쿼리셋을 효율적으로 쓰는법 http://raccoonyy.github.io/using-django-querysets-effectively-translate/

        user = request.user
        friends = user.friends.all()
        posts = user.posts.all()
        if friends:
            for f in friends.iterator():
                posts = posts.union(f.posts.all())

        posts = posts.order_by("-created_at")

        serializer = PostListSerializer(posts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(operation_description="Post 작성하기")
    def create(self, request):

        user = request.user
        images = request.data.get("images", None)

        if images:
            request.data.pop("images")

        request.data["author"] = request.user.id
        serializer = PostSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        post = serializer.save()

        if images:

            author_email = user.email

            for image in images:
                PostImage.objects.create(
                    post=post, image=image, author_email=author_email
                )

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class LikeViewSet(viewsets.GenericViewSet):

    serializer_class = PostSerializer
    queryset = Post.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(operation_description="좋아요하기", request_body=no_body)
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
        operation_description="좋아요 취소하기", responses={200: PostSerializer()}
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
    )
    def retrieve(self, request, pk=None):
        post = get_object_or_404(self.queryset, pk=pk)
        return Response(PostLikeSerializer(post).data, status=status.HTTP_200_OK)
