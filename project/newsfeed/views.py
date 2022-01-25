from drf_yasg import openapi
from rest_framework import status, permissions, parsers
from rest_framework.generics import (
    ListCreateAPIView,
    GenericAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.response import Response
from django.db.models import Q
from django.db import transaction
from rest_framework.views import APIView
from ast import literal_eval

from .serializers import (
    PostSerializer,
    PostLikeSerializer,
    CommentListSerializer,
    CommentCreateSerializer,
    CommentSerializer,
    CommentLikeSerializer,
)
from .swagger import (
    CommentCreateSwaggerSerializer,
    CommentUpdateSwaggerSerializer,
    PostCreateSwaggerSerializer,
    PostUpdateSwaggerSerializer,
)
from .models import Post, Comment
from user.models import User
from datetime import datetime
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema, no_body
from rest_framework.parsers import DataAndFiles, MultiPartParser, FormParser, JSONParser
from notice.views import NoticeCancel, NoticeCreate
from config.permissions import IsValidAccount


class PostListView(ListCreateAPIView):

    serializer_class = PostSerializer
    queryset = Post.objects.all()
    permission_classes = (permissions.IsAuthenticated & IsValidAccount,)
    parser_classes = (MultiPartParser,)

    @swagger_auto_schema(
        operation_description="로그인된 유저의 friend들의 post들을 최신순으로 가져오기(현재는 모든 유저 가져오도록 설정되어 있음)",
        responses={200: PostSerializer()},
    )
    def get(self, request):

        user = request.user

        self.queryset = Post.objects.filter(
            (Q(author__in=user.friends.all(), scope__gt=1) | Q(author=user)),
            mainpost=None,
        )

        return super().list(request)

    @swagger_auto_schema(
        operation_description="Post 작성하기",
        request_body=PostCreateSwaggerSerializer(),
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
            subposts = request.data.getlist("subposts", [])

            if len(files) != len(subposts):
                return Response(
                    status=status.HTTP_400_BAD_REQUEST,
                    data="files와 subposts의 개수를 맞춰주세요.",
                )

            for i in range(len(files)):
                subpost = subposts[i]
                subpost = literal_eval(subpost)
                content = subpost.get("content", "")
                tagged_users = subpost.get("tagged_users", [])
                serializer = PostSerializer(
                    data={
                        "content": content,
                        "mainpost": mainpost.id,
                        "scope": scope,
                    },
                    context=context,
                )
                serializer.is_valid(raise_exception=True)
                subpost = serializer.save()
                subpost.file.save(files[i].name, files[i], save=True)

                for tagged_user in tagged_users:
                    tagged_user = User.objects.get(id=tagged_user)
                    subpost.tagged_users.add(tagged_user)
                    subpost.save()
                    if user != tagged_user:
                        NoticeCreate(
                            sender=user,
                            receiver=tagged_user,
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
    permission_classes = (permissions.IsAuthenticated & IsValidAccount,)
    parser_classes = (
        MultiPartParser,
        FormParser,
    )

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
        request_body=PostUpdateSwaggerSerializer(),
        responses={200: PostSerializer()},
    )
    @transaction.atomic
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

        content = request.data.get("content")
        files = request.FILES.getlist("file", [])
        subposts = request.data.getlist("subposts")
        scope = request.data.get("scope")
        removed_subposts = request.data.getlist("removed_subposts")
        tagged_users = request.data.getlist("tagged_users")
        new_subposts = request.data.getlist("new_subposts", [])

        if scope:

            if (not scope.isdigit()) or int(scope) > 3 or int(scope) < 1:
                return Response(
                    status=status.HTTP_400_BAD_REQUEST, data="공개범위는 1, 2, 3 중에 선택해주세요."
                )

            scope = int(scope)
            post.scope = scope

        if len(files) != len(new_subposts):
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data="new_subposts와 files의 개수를 맞춰주세요.",
            )

        # mainpost 수정
        if not post.subposts.exclude(id__in=removed_subposts).exists():

            if not content:
                return Response(status=status.HTTP_400_BAD_REQUEST, data="내용을 입력해주세요.")

        post.content = content

        canceled_users = post.tagged_users.exclude(id__in=tagged_users)
        for canceled_user in canceled_users:
            post.tagged_users.remove(canceled_user)
            if user != canceled_user:
                NoticeCancel(
                    sender=user,
                    receiver=canceled_user,
                    content="PostTag",
                    post=post,
                )

        for tagged_user in tagged_users:

            if not post.tagged_users.filter(id=tagged_user).exists():
                tagged_user = get_object_or_404(User, id=tagged_user)
                post.tagged_users.add(tagged_user)
                if user != tagged_user:
                    NoticeCreate(
                        sender=user,
                        receiver=tagged_user,
                        content="PostTag",
                        post=post,
                    )
        post.save()

        # subposts 삭제
        if removed_subposts:
            subposts = post.subposts.filter(id__in=removed_subposts)
            subposts.delete()

        # 기존의 subposts content 수정
        if subposts:
            for subpost in subposts:
                subpost = literal_eval(subpost)
                subpost_content = subpost.get("content", "")
                subpost_id = subpost["id"]
                subpost_tagged_users = subpost.get("tagged_users", [])

                subpost = get_object_or_404(post.subposts, id=subpost_id)
                subpost.content = subpost_content
                if scope:
                    subpost.scope = scope

                canceled_users = subpost.tagged_users.exclude(
                    id__in=subpost_tagged_users
                )
                for canceled_user in canceled_users:
                    subpost.tagged_users.remove(canceled_user)
                    if user != canceled_user:
                        NoticeCancel(
                            sender=user,
                            receiver=canceled_user,
                            content="PostTag",
                            post=subpost,
                        )

                for subpost_tagged_user in subpost_tagged_users:

                    if not subpost.tagged_users.filter(id=subpost_tagged_user).exists():
                        subpost_tagged_user = get_object_or_404(
                            User, id=subpost_tagged_user
                        )
                        subpost.tagged_users.add(subpost_tagged_user)
                        if user != subpost_tagged_user:
                            NoticeCreate(
                                sender=user,
                                receiver=subpost_tagged_user,
                                content="PostTag",
                                post=subpost,
                            )

                subpost.save()

        # 파일 추가하는 경우 subpost 추가
        if files:

            for i in range(len(files)):
                new_subpost = new_subposts[i]
                new_subpost = literal_eval(new_subpost)
                serializer = PostSerializer(
                    data={
                        "content": new_subpost.get("content", ""),
                        "mainpost": post.id,
                        "scope": post.scope,
                    },
                    context={"isFile": True, "request": request},
                )
                serializer.is_valid(raise_exception=True)
                subpost = serializer.save()
                subpost.file.save(files[i].name, files[i], save=True)

                subpost_tagged_users = new_subpost.get("tagged_users", [])

                for subpost_tagged_user in subpost_tagged_users:
                    subpost_tagged_user = User.objects.get(id=subpost_tagged_user)
                    subpost.tagged_users.add(subpost_tagged_user)
                    subpost.save()
                    if user != subpost_tagged_user:
                        NoticeCreate(
                            sender=user,
                            receiver=subpost_tagged_user,
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
    permission_classes = (permissions.IsAuthenticated & IsValidAccount,)

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
    permission_classes = (permissions.IsAuthenticated & IsValidAccount,)
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
        request_body=CommentCreateSwaggerSerializer(),
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


class CommentUpdateDeleteView(GenericAPIView):
    serializer_class = CommentSerializer
    permission_classes = (permissions.IsAuthenticated & IsValidAccount,)
    queryset = Comment.objects.all()
    parser_classes = (parsers.MultiPartParser,)

    @swagger_auto_schema(
        operation_description="comment 수정하기",
        responses={200: CommentSerializer()},
        request_body=CommentUpdateSwaggerSerializer(),
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
        return Response(
            status=status.HTTP_200_OK, data=self.get_serializer(comment).data
        )

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

        return Response(
            status=status.HTTP_200_OK, data=self.get_serializer(comment).data
        )


class CommentLikeView(GenericAPIView):
    serializer_class = CommentSerializer
    queryset = Comment.objects.all()
    permission_classes = (permissions.IsAuthenticated & IsValidAccount,)

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
