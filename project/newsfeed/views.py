from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .serializers import PostListSerializer, PostSerializer
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
