from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .serializers import PostListSerializer
from .models import Post
from datetime import datetime
from django.shortcuts import get_object_or_404

class PostViewSet(viewsets.GenericViewSet):

    serializer_class = PostListSerializer
    queryset = Post.objects.all()
    permission_classes = (permissions.AllowAny,)

    def list(self, request):

        posts = Post.objects.all().order_by('-created_at')
        serializer = PostListSerializer(posts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)