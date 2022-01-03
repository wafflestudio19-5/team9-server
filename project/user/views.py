import requests
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Model, Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.db import IntegrityError
from drf_yasg import openapi
from rest_framework import status, viewsets, permissions
from rest_framework.generics import (
    ListAPIView,
    ListCreateAPIView,
    RetrieveUpdateAPIView,
    CreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.views import APIView
from rest_framework.decorators import action, api_view
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from drf_yasg import openapi
from config.settings import get_secret
from user.models import KakaoId, Company, University, FriendRequest
from rest_framework.viewsets import GenericViewSet
from newsfeed.views import jwt_header
from user.models import KakaoId, FriendRequest
from user.pagination import UserPagination
from user.serializers import (
    UserSerializer,
    UserLoginSerializer,
    UserCreateSerializer,
    CompanySerializer,
    UniversitySerializer,
    UserProfileSerializer,
    jwt_token_of,
    FriendRequestCreateSerializer,
    FriendRequestAcceptDeleteSerializer,
    UserMutualFriendsSerializer,
)
from newsfeed.serializers import PostListSerializer
from newsfeed.models import Post
from drf_yasg.utils import swagger_auto_schema
import uuid

User = get_user_model()


class UserSignUpView(APIView):
    permission_classes = (permissions.AllowAny,)

    @swagger_auto_schema(request_body=UserCreateSerializer)
    def post(self, request, *args, **kwargs):

        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user, jwt_token = serializer.save()
        except IntegrityError:
            return Response(status=status.HTTP_409_CONFLICT, data="이미 존재하는 유저 이메일입니다.")

        return Response(
            {"user": user.email, "username": user.username, "token": jwt_token},
            status=status.HTTP_201_CREATED,
        )


class UserLoginView(APIView):
    permission_classes = (permissions.AllowAny,)

    @swagger_auto_schema(request_body=UserLoginSerializer)
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]

        return Response({"success": True, "token": token}, status=status.HTTP_200_OK)


class UserLogoutView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        request.user.jwt_secret = uuid.uuid4()
        request.user.save()

        return Response("로그아웃 되었습니다.", status=status.HTTP_200_OK)


class UserFriendRequestView(ListCreateAPIView):
    serializer_class = FriendRequestCreateSerializer
    queryset = FriendRequest.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        operation_description="친구 요청 목록 불러오기",
        responses={200: FriendRequestCreateSerializer(many=True)},
        manual_parameters=[jwt_header],
    )
    def get(self, request):
        self.queryset = self.queryset.filter(receiver=request.user)
        return super().list(request)

    @swagger_auto_schema(
        operation_description="친구 요청 보내기",
        responses={201: FriendRequestCreateSerializer()},
        manual_parameters=[jwt_header],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={"receiver": openapi.Schema(type=openapi.TYPE_NUMBER)},
        ),
    )
    def post(self, request):
        request.data["sender"] = request.user.id
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_201_CREATED, data=serializer.data)

    @swagger_auto_schema(
        operation_description="친구 요청 수락하기",
        manual_parameters=[jwt_header],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "sender": openapi.Schema(type=openapi.TYPE_NUMBER),
            },
        ),
        responses={200: "수락 완료되었습니다."},
    )
    def put(self, request):
        request.data["receiver"] = request.user.id
        serializer = FriendRequestAcceptDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.accept(serializer.validated_data)

        return Response(status=status.HTTP_200_OK, data="수락 완료되었습니다.")

    @swagger_auto_schema(
        operation_description="친구 요청 삭제하기",
        manual_parameters=[jwt_header],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "sender": openapi.Schema(type=openapi.TYPE_NUMBER),
                "receiver": openapi.Schema(type=openapi.TYPE_NUMBER),
            },
        ),
        responses={204: "삭제 완료되었습니다."},
    )
    def delete(self, request):
        user = request.user
        if (user.id != request.data.get("sender")) and (
            user.id != request.data.get("receiver")
        ):
            return Response(status=status.HTTP_403_FORBIDDEN, data="권한이 없습니다.")
        serializer = FriendRequestAcceptDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.delete(serializer.validated_data)

        return Response(status=status.HTTP_204_NO_CONTENT, data="삭제 완료되었습니다.")


class UserFriendDeleteView(APIView):
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        operation_description="친구 삭제하기",
        manual_parameters=[jwt_header],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "friend": openapi.Schema(type=openapi.TYPE_NUMBER),
            },
        ),
        responses={204: "삭제 완료되었습니다."},
    )
    def delete(self, request):
        user = request.user
        friend = request.data.get("friend")
        if not friend:
            return Response(status=status.HTTP_400_BAD_REQUEST, data="friend를 입력해주세요")
        if not user.friends.filter(pk=friend).exists():
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data="해당 친구가 존재하지 않습니다."
            )
        user.friends.remove(friend)
        return Response(status=status.HTTP_204_NO_CONTENT, data="삭제 완료되었습니다.")


class UserSearchListView(ListAPIView):
    serializer_class = UserMutualFriendsSerializer
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = UserPagination

    @swagger_auto_schema(
        operation_description="유저 검색하기",
        manual_parameters=[
            jwt_header,
            openapi.Parameter(
                "q",
                openapi.IN_QUERY,
                description="search key",
                type=openapi.TYPE_STRING,
            ),
        ],
        responses={200: UserMutualFriendsSerializer(many=True)},
    )
    def get(self, request):
        user = request.user
        request.data["request_user"] = user
        search_key = request.GET.get("q")
        self.queryset = User.objects.filter(username__icontains=search_key)
        return super().list(request)


KAKAO_APP_KEY = get_secret("KAKAO_APP_KEY")


class KakaoView(APIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request):
        app_key = KAKAO_APP_KEY
        redirect_uri = "http://3.34.188.255/api/v1/kakao/callback"
        kakao_auth_api = "https://kauth.kakao.com/oauth/authorize?response_type=code"
        return redirect(
            f"{kakao_auth_api}&client_id={app_key}&redirect_uri={redirect_uri}"
        )


class KakaoCallbackView(APIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request):
        auth_code = request.GET.get("code")
        kakao_token_api = "https://kauth.kakao.com/oauth/token"
        data = {
            "grant_type": "authorization_code",
            "client_id": KAKAO_APP_KEY,
            "redirection_uri": "http://3.34.188.255/api/v1/kakao/callback",
            "code": auth_code,
        }

        token_response = requests.post(kakao_token_api, data=data)
        access_token = token_response.json().get("access_token")
        user_info_response = requests.get(
            "https://kapi.kakao.com/v2/user/me",
            headers={"Authorization": f"Bearer ${access_token}"},
        )
        kakao_id = user_info_response.json().get("id")
        if not kakao_id:
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data="카카오 계정식별번호가 전달되지 않았습니다"
            )

        # 유저가 로그인되어 있음 --> 카카오 계정 연결
        if request.user.is_authenticated:
            if hasattr(request.user, "kakao"):
                return Response(
                    status=status.HTTP_400_BAD_REQUEST, data="이미 연결된 카카오 계정이 있습니다."
                )

            try:
                KakaoId.objects.create(user=request.user, identifier=kakao_id)
                return Response(status=status.HTTP_200_OK, data="성공적으로 연결되었습니다.")
            except IntegrityError:
                return Response(
                    status=status.HTTP_400_BAD_REQUEST,
                    data="이 카카오 계정은 다른 계정과 이미 연결되어있습니다.",
                )

        # 유저가 로그인되어있지 않음 --> 카카오 계정으로 로그인
        else:
            kakao = KakaoId.objects.filter(identifier=kakao_id).first()
            if kakao:
                user = kakao.user
                return Response(
                    status=status.HTTP_200_OK,
                    data={"email": user.email, "token": jwt_token_of(user)},
                )
            else:
                return Response(
                    status=status.HTTP_400_BAD_REQUEST, data="해당 카카오 계정과 연결된 계정이 없습니다."
                )


jwt_header = openapi.Parameter(
    "Authorization",
    openapi.IN_HEADER,
    type=openapi.TYPE_STRING,
    default="JWT [put token here]",
)


class UserNewsfeedView(ListAPIView):
    serializer_class = PostListSerializer
    queryset = Post.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        operation_description="선택된 유저가 작성한 게시글을 가져오기",
        manual_parameters=[jwt_header],
        responses={200: PostListSerializer(), 404: "유저를 찾을 수 없습니다."},
    )
    def get(self, request, user_id=None):
        user = get_object_or_404(User, pk=user_id)
        self.queryset = Post.objects.filter(author=user, mainpost=None)
        return super().list(request)


class UserFriendListView(ListAPIView):
    serializer_class = UserSerializer
    queryset = User.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = LimitOffsetPagination

    @swagger_auto_schema(
        operation_description="선택된 유저의 친구들을 가져오기",
        manual_parameters=[jwt_header],
        responses={200: UserSerializer(), 404: "유저를 찾을 수 없습니다."},
    )
    def get(self, request, user_id=None):
        user = get_object_or_404(User, pk=user_id)
        self.queryset = User.objects.filter(friends=user)
        return super().list(request)


class UserProfileView(RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    queryset = User.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, pk=None):
        return super().retrieve(request, pk=pk)

    def put(self, request, pk=None):
        user = get_object_or_404(User, pk=pk)
        if user != request.user:
            return Response(
                status=status.HTTP_401_UNAUTHORIZED, data="다른 유저의 프로필을 고칠 수 없습니다."
            )
        profile_image = request.FILES.get("profile_image")
        if profile_image:
            user.profile_image.save(profile_image.name, profile_image, save=True)
        cover_image = request.FILES.get("cover_image")
        if cover_image:
            user.cover_image.save(cover_image.name, cover_image, save=True)
        return super().update(request, pk=pk, partial=True)


class CompanyCreateView(CreateAPIView):
    serializer_class = CompanySerializer
    queryset = Company.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        data = request.data.copy()
        data["user"] = request.user.id
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        company = serializer.save()
        return Response(
            self.serializer_class(company).data, status=status.HTTP_201_CREATED
        )


class CompanyView(RetrieveUpdateDestroyAPIView):
    serializer_class = CompanySerializer
    queryset = Company.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, pk=None):
        return super().retrieve(request, pk=pk)

    def put(self, request, pk=None):
        company = get_object_or_404(Company, pk=pk)
        if request.user != company.user:
            return Response(
                status=status.HTTP_401_UNAUTHORIZED, data="다른 유저의 프로필을 고칠 수 없습니다."
            )
        return super().update(request, pk=pk, partial=True)

    def delete(self, request, pk=None):
        company = get_object_or_404(Company, pk=pk)
        if request.user != company.user:
            return Response(
                status=status.HTTP_401_UNAUTHORIZED, data="다른 유저의 프로필을 고칠 수 없습니다."
            )
        return super().destroy(request, pk=pk)


class UniversityCreateView(CreateAPIView):
    serializer_class = UniversitySerializer
    queryset = University.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        data = request.data.copy()
        data["user"] = request.user.id
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        university = serializer.save()
        return Response(
            self.serializer_class(university).data, status=status.HTTP_201_CREATED
        )


class UniversityView(RetrieveUpdateDestroyAPIView):
    serializer_class = UniversitySerializer
    queryset = University.objects.all()
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, pk=None):
        return super().retrieve(request, pk=pk)

    def put(self, request, pk=None):
        university = get_object_or_404(University, pk=pk)
        if request.user != university.user:
            return Response(
                status=status.HTTP_401_UNAUTHORIZED, data="다른 유저의 프로필을 고칠 수 없습니다."
            )
        return super().update(request, pk=pk, partial=True)

    def delete(self, request, pk=None):
        university = get_object_or_404(University, pk=pk)
        if request.user != university.user:
            return Response(
                status=status.HTTP_401_UNAUTHORIZED, data="다른 유저의 프로필을 고칠 수 없습니다."
            )
        return super().destroy(request, pk=pk)
