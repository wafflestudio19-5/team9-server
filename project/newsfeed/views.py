from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .serializers import PostListSerializer, PostSerializer, PostLikeSerializer
from .models import Post
from user.models import User
from datetime import datetime
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema


class PostViewSet(viewsets.GenericViewSet):

    serializer_class = PostSerializer
    queryset = Post.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

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


class LikeViewSet(viewsets.GenericViewSet):

    serializer_class = PostSerializer
    queryset = Post.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def update(self, request, pk=None):
        user = request.user
        post = get_object_or_404(self.queryset, pk=pk)
        if post.likeusers.filter(user=user).count() == 1:
            return Response(status=status.HTTP_400_BAD_REQUEST, data="이미 좋아요 한 게시글입니다.")
        post.likeusers.add(user)
        post.likes = post.likes + 1
        post.save()
        return Response(self.serializer_class(post), status=status.HTTP_200_OK)

    def delete(self, request, pk=None):
        user = request.user
        post = get_object_or_404(self.queryset, pk=pk)
        if post.likeusers.filter(user=user).count() != 1:
            return Response(status=status.HTTP_400_BAD_REQUEST, data="좋아요하지 않은 게시글입니다.")
        post.likeusers.remove(user)
        post.likes = post.likes - 1
        post.save()
        return Response(self.serializer_class(post), status=status.HTTP_200_OK)

    def retrieve(self, request, pk=None):
        post = get_object_or_404(self.queryset, pk=pk)
        return Response(PostLikeSerializer(post), status=status.HTTP_200_OK)
