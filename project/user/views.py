import requests
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Model
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.db import IntegrityError
from rest_framework import status, viewsets, permissions
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from rest_framework.views import APIView
from rest_framework.decorators import action, api_view
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from drf_yasg import openapi
from config.settings import get_secret
from user.models import KakaoId
from user.serializers import (
    UserSerializer,
    UserLoginSerializer,
    UserCreateSerializer,
    CompanySerializer,
    UniversitySerializer,
    UserProfileSerializer,
    jwt_token_of,
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
            {"user": user.email, "token": jwt_token}, status=status.HTTP_201_CREATED
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


class UserFriendView(ListAPIView):
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
