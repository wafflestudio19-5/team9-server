import requests
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Model, Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.db import IntegrityError, transaction
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.core.mail import EmailMessage
from django.utils.encoding import force_bytes, force_text
from drf_yasg import openapi
from rest_framework import status, viewsets, permissions, parsers
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
from user.models import KakaoId, FriendRequest
from user.pagination import UserPagination, FriendPagination
from newsfeed.serializers import PostSerializer
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
from user.swagger import (
    UserPutSwaggerSerializer,
    UserLoginSwaggerSerializer,
    UserProfileImageSwaggerSerializer,
)
from newsfeed.models import Post
from drf_yasg.utils import swagger_auto_schema
from .utils import account_activation_token, message
from config.permissions import IsValidAccount
import uuid

from newsfeed.views import NoticeCreate, NoticeCancel

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
            return Response(status=status.HTTP_409_CONFLICT, data="?????? ???????????? ?????? ??????????????????.")

        current_site = get_current_site(request)
        domain = current_site.domain
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = account_activation_token.make_token(user)
        message_data = message(domain, uidb64, token)
        mail_title = "????????? ????????? ??????????????????"
        mail_to = request.data["email"]
        email = EmailMessage(mail_title, message_data, to=[mail_to])
        email.send()

        return Response(
            {"user": UserSerializer(user).data, "token": jwt_token},
            status=status.HTTP_201_CREATED,
        )


class UserActivateView(APIView):
    permission_classes = (permissions.AllowAny,)

    def get(self, request, uidb64, token):
        uid = force_text(urlsafe_base64_decode(uidb64))
        user = get_object_or_404(User.objects.all(), pk=uid)
        if account_activation_token.check_token(user, token):
            user.is_valid = True
            user.save()
            return Response("???????????? ?????????????????????.", status=status.HTTP_200_OK)
        return Response("???????????? ??????????????????.", status=status.HTTP_400_BAD_REQUEST)


class UserLoginView(APIView):
    permission_classes = (permissions.AllowAny,)

    @swagger_auto_schema(
        request_body=UserLoginSerializer, responses={200: UserLoginSwaggerSerializer()}
    )
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]
        user = serializer.validated_data["user"]

        return Response(
            {
                "user": UserSerializer(user).data,
                "token": token,
            },
            status=status.HTTP_200_OK,
        )


class UserStatusView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        return Response(
            data=UserSerializer(request.user).data, status=status.HTTP_200_OK
        )


class UserLogoutView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        request.user.jwt_secret = uuid.uuid4()
        request.user.save()

        return Response("???????????? ???????????????.", status=status.HTTP_200_OK)


class UserDeleteView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(operation_description="?????? ????????????")
    @transaction.atomic
    def delete(self, request):
        user = request.user
        """
        for notice in user.sent_notices.all():
            if notice.senders.count() > 1:
                notice.senders.remove(user)
                notice.count -= 1
                notice.save()
            else:
                notice.delete()
        """

        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserFriendRequestListView(ListAPIView):
    serializer_class = FriendRequestCreateSerializer
    queryset = FriendRequest.objects.all()
    permission_classes = (permissions.IsAuthenticated & IsValidAccount,)

    @swagger_auto_schema(
        operation_description="?????? ?????? ?????? ????????????",
        responses={200: FriendRequestCreateSerializer(many=True)},
    )
    def get(self, request):
        self.queryset = request.user.received_friend_request.all()
        return super().list(request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["request"] = self.request
        return context


class UserFriendRequestView(APIView):
    queryset = User.objects.all()
    permission_classes = (permissions.IsAuthenticated & IsValidAccount,)

    @swagger_auto_schema(
        operation_description="?????? ???????????? ?????? ?????? ?????????",
        responses={201: FriendRequestCreateSerializer()},
    )
    def post(self, request, pk=None):
        sender = request.user
        receiver = get_object_or_404(self.queryset, pk=pk)

        data = {"sender": sender.id, "receiver": receiver.id}
        serializer = FriendRequestCreateSerializer(
            data=data, context={"request": self.request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        NoticeCreate(
            sender=sender,
            content="FriendRequest",
            receiver=receiver.id,
        )

        return Response(status=status.HTTP_201_CREATED, data=serializer.data)

    @swagger_auto_schema(
        operation_description="?????? ????????? ?????? ?????? ?????? ????????????",
        responses={200: "?????? ?????????????????????."},
    )
    def put(self, request, pk=None):
        sender = get_object_or_404(self.queryset, pk=pk)
        receiver = request.user

        data = {"sender": sender.id, "receiver": receiver.id}
        serializer = FriendRequestAcceptDeleteSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.accept(serializer.validated_data)

        NoticeCreate(sender=receiver, content="FriendAccept", receiver=sender.id)

        return Response(status=status.HTTP_200_OK, data="?????? ?????????????????????.")

    @swagger_auto_schema(
        operation_description="?????? ???????????? ????????? ???????????? ?????? ?????? ?????? ????????????",
        responses={204: "?????? ?????????????????????."},
    )
    def delete(self, request, pk=None):
        target_user = get_object_or_404(self.queryset, pk=pk)
        user = request.user

        if user.sent_friend_request.filter(receiver=target_user):
            data = {"sender": request.user.id, "receiver": target_user.id}
            NoticeCancel(receiver=target_user, sender=user, content="FriendRequest")

        elif user.received_friend_request.filter(sender=target_user):
            data = {"sender": target_user.id, "receiver": request.user.id}
            NoticeCancel(receiver=user, sender=target_user, content="FriendRequest")

        else:
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data="?????? ???????????? ???????????? ?????? ?????? ????????? ????????????."
            )

        serializer = FriendRequestAcceptDeleteSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.delete(serializer.validated_data)

        return Response(status=status.HTTP_204_NO_CONTENT, data="?????? ?????????????????????.")


class UserFriendDeleteView(APIView):
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated & IsValidAccount,)

    @swagger_auto_schema(
        operation_description="?????? ????????????",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "friend": openapi.Schema(type=openapi.TYPE_NUMBER),
            },
        ),
        responses={204: "?????? ?????????????????????."},
    )
    def delete(self, request):
        user = request.user
        friend = request.data.get("friend")
        if not friend:
            return Response(status=status.HTTP_400_BAD_REQUEST, data="friend??? ??????????????????")
        if not user.friends.filter(pk=friend).exists():
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data="?????? ????????? ???????????? ????????????."
            )
        user.friends.remove(friend)
        return Response(status=status.HTTP_204_NO_CONTENT, data="?????? ?????????????????????.")


class UserSearchListView(ListAPIView):
    serializer_class = UserMutualFriendsSerializer
    permission_classes = (permissions.IsAuthenticated & IsValidAccount,)
    pagination_class = UserPagination

    @swagger_auto_schema(
        operation_description="?????? ????????????",
        manual_parameters=[
            openapi.Parameter(
                "q",
                openapi.IN_QUERY,
                description="search key",
                type=openapi.TYPE_STRING,
                required=True,
            ),
        ],
        responses={200: UserMutualFriendsSerializer(many=True)},
    )
    def get(self, request):
        search_key = request.GET.get("q")
        if not search_key:
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data="search key??? ??????????????????"
            )
        self.queryset = User.objects.filter(username__icontains=search_key)
        return super().list(request)


class KakaoLoginView(APIView):
    permission_classes = (permissions.AllowAny,)

    @swagger_auto_schema(
        operation_description="????????? ???????????? ???????????????",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "access_token": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={200: UserLoginSwaggerSerializer()},
    )
    def post(self, request):
        access_token = request.data.get("access_token")
        if not access_token:
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data="access_token??? ??????????????????."
            )

        # ?????? ?????? ????????????
        user_info_response = requests.get(
            "https://kapi.kakao.com/v2/user/me",
            headers={"Authorization": f"Bearer ${access_token}"},
        )

        kakao_id = user_info_response.json().get("id")
        if not kakao_id:
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data="access_token??? ???????????? ????????????."
            )

        kakao = KakaoId.objects.filter(identifier=kakao_id)
        if not kakao.exists():
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data="?????? ????????? ????????? ????????? ????????? ????????????."
            )

        user = kakao.first().user
        token = jwt_token_of(user)

        return Response(
            {
                "user": UserSerializer(user).data,
                "token": token,
            },
            status=status.HTTP_200_OK,
        )


class KakaoConnectView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @swagger_auto_schema(
        operation_description="????????? ?????? ????????????",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "access_token": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={201: "??????????????? ?????????????????????."},
    )
    def post(self, request):

        access_token = request.data.get("access_token")
        if not access_token:
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data="access_token??? ??????????????????."
            )

        # ?????? ?????? ????????????
        user_info_response = requests.get(
            "https://kapi.kakao.com/v2/user/me",
            headers={"Authorization": f"Bearer ${access_token}"},
        )

        kakao_id = user_info_response.json().get("id")
        if not kakao_id:
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data="access_token??? ???????????? ????????????."
            )

        if hasattr(request.user, "kakao"):
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data="?????? ????????? ????????? ????????? ????????????."
            )

        try:
            KakaoId.objects.create(user=request.user, identifier=kakao_id)
            return Response(status=status.HTTP_201_CREATED, data="??????????????? ?????????????????????.")

        except IntegrityError:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data="??? ????????? ????????? ?????? ????????? ?????? ????????????????????????.",
            )

    @swagger_auto_schema(
        operation_description="????????? ?????? ?????? ????????????.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "access_token": openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={200: "?????? ?????????????????????."},
    )
    def delete(self, request):
        if not hasattr(request.user, "kakao"):
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data="????????? ????????? ????????? ????????????."
            )
        kakao = request.user.kakao
        kakao.delete()

        access_token = request.data.get("access_token")
        if not access_token:
            return Response(
                status=status.HTTP_400_BAD_REQUEST, data="access_token??? ??????????????????."
            )

        requests.post(
            "https://kapi.kakao.com/v1/user/unlink",
            headers={"Authorization": f"Bearer ${access_token}"},
            data={"target_id_type": "user_id", "target_id": kakao.identifier},
        )

        return Response(status=status.HTTP_200_OK, data="?????? ?????????????????????.")


class UserNewsfeedView(ListAPIView):
    serializer_class = PostSerializer
    queryset = Post.objects.all()
    permission_classes = (permissions.IsAuthenticated & IsValidAccount,)

    @swagger_auto_schema(
        operation_description="????????? ????????? ????????? ???????????? ????????????",
        responses={200: PostSerializer()},
    )
    def get(self, request, user_id=None):
        user = get_object_or_404(User, pk=user_id)

        if request.user == user:
            self.queryset = user.posts.filter(mainpost=None)

        elif request.user in user.friends.all():
            self.queryset = user.posts.filter(mainpost=None, scope__gt=1)

        else:
            self.queryset = user.posts.filter(mainpost=None, scope__gt=2)

        return super().list(request)


class UserFriendListView(ListAPIView):
    serializer_class = UserMutualFriendsSerializer
    queryset = User.objects.all()
    permission_classes = (permissions.IsAuthenticated & IsValidAccount,)
    pagination_class = FriendPagination

    @swagger_auto_schema(
        operation_description="????????? ????????? ???????????? ????????????",
        responses={200: UserSerializer()},
    )
    def get(self, request, user_id=None):
        user = get_object_or_404(User, pk=user_id)
        self.queryset = user.friends.all()
        return super().list(request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["request"] = self.request
        return context


class UserProfileView(RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    queryset = User.objects.all()
    permission_classes = (permissions.IsAuthenticated & IsValidAccount,)
    parser_classes = (parsers.MultiPartParser, parsers.FileUploadParser)

    @swagger_auto_schema(
        operation_description="????????? ????????? ?????? ????????????",
        responses={200: UserProfileSerializer()},
    )
    def get(self, request, pk=None):
        user = get_object_or_404(self.queryset, pk=pk)
        return Response(
            status=status.HTTP_200_OK,
            data=self.serializer_class(user, context={"request": request}).data,
        )

    @swagger_auto_schema(
        operation_description="????????? ?????? ????????????",
        manual_parameters=[
            openapi.Parameter(
                name="profile_image",
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=False,
            ),
            openapi.Parameter(
                name="cover_image",
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=False,
            ),
        ],
        request_body=UserPutSwaggerSerializer(),
        responses={200: UserProfileSerializer()},
    )
    def put(self, request, pk=None):
        user = get_object_or_404(User, pk=pk)
        if user != request.user:
            return Response(
                status=status.HTTP_403_FORBIDDEN, data="?????? ????????? ???????????? ?????? ??? ????????????."
            )
        profile_image = request.FILES.get("profile_image")
        if profile_image:
            user.profile_image.save(profile_image.name, profile_image, save=True)
        cover_image = request.FILES.get("cover_image")
        if cover_image:
            user.cover_image.save(cover_image.name, cover_image, save=True)
        return super().update(request, pk=pk, partial=True)

    # ????????? patch ???????????? drf-yasg??? ?????? ?????? ???????????????
    @swagger_auto_schema(auto_schema=None)
    def patch(self, request, *args, **kwargs):
        return Response(status.HTTP_204_NO_CONTENT)


class UserProfileImageView(APIView):
    serializer_class = UserProfileSerializer
    queryset = User.objects.all()
    permission_classes = (permissions.IsAuthenticated & IsValidAccount,)

    @swagger_auto_schema(
        operation_description="True????????? ????????? ?????????/?????? ?????? ????????????",
        request_body=UserProfileImageSwaggerSerializer(),
        responses={200: UserProfileSerializer()},
    )
    def delete(self, request, pk=None):
        user = get_object_or_404(User, pk=pk)
        if user != request.user:
            return Response(
                status=status.HTTP_403_FORBIDDEN, data="?????? ????????? ???????????? ?????? ??? ????????????."
            )
        serializer = UserProfileImageSwaggerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.data["profile_image"]:
            user.profile_image = None
        if serializer.data["cover_image"]:
            user.cover_image = None
        user.save()
        return Response(self.serializer_class(user).data, status.HTTP_200_OK)


class CompanyCreateView(CreateAPIView):
    serializer_class = CompanySerializer
    queryset = Company.objects.all()
    permission_classes = (permissions.IsAuthenticated & IsValidAccount,)

    @swagger_auto_schema(
        operation_description="?????? ?????? ????????????",
        responses={200: CompanySerializer()},
    )
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
    permission_classes = (permissions.IsAuthenticated & IsValidAccount,)

    @swagger_auto_schema(
        operation_description="?????? ?????? ????????????",
        responses={200: CompanySerializer()},
    )
    def get(self, request, pk=None):
        return super().retrieve(request, pk=pk)

    @swagger_auto_schema(
        operation_description="?????? ?????? ????????????",
        responses={200: CompanySerializer()},
    )
    def put(self, request, pk=None):
        company = get_object_or_404(Company, pk=pk)
        if request.user != company.user:
            return Response(
                status=status.HTTP_403_FORBIDDEN, data="?????? ????????? ???????????? ?????? ??? ????????????."
            )
        return super().update(request, pk=pk, partial=True)

    @swagger_auto_schema(
        operation_description="?????? ?????? ????????????",
    )
    def delete(self, request, pk=None):
        company = get_object_or_404(Company, pk=pk)
        if request.user != company.user:
            return Response(
                status=status.HTTP_403_FORBIDDEN, data="?????? ????????? ???????????? ?????? ??? ????????????."
            )
        return super().destroy(request, pk=pk)

    # ????????? patch ???????????? drf-yasg??? ?????? ?????? ???????????????
    @swagger_auto_schema(auto_schema=None)
    def patch(self, request, *args, **kwargs):
        return Response(status.HTTP_204_NO_CONTENT)


class UniversityCreateView(CreateAPIView):
    serializer_class = UniversitySerializer
    queryset = University.objects.all()
    permission_classes = (permissions.IsAuthenticated & IsValidAccount,)

    @swagger_auto_schema(
        operation_description="?????? ?????? ????????????",
        responses={200: UniversitySerializer()},
    )
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
    permission_classes = (permissions.IsAuthenticated & IsValidAccount,)

    @swagger_auto_schema(
        operation_description="?????? ?????? ????????????",
        responses={200: UniversitySerializer()},
    )
    def get(self, request, pk=None):
        return super().retrieve(request, pk=pk)

    @swagger_auto_schema(
        operation_description="?????? ?????? ????????????",
        responses={200: UniversitySerializer()},
    )
    def put(self, request, pk=None):
        university = get_object_or_404(University, pk=pk)
        if request.user != university.user:
            return Response(
                status=status.HTTP_403_FORBIDDEN, data="?????? ????????? ???????????? ?????? ??? ????????????."
            )
        return super().update(request, pk=pk, partial=True)

    @swagger_auto_schema(
        operation_description="?????? ?????? ????????????",
    )
    def delete(self, request, pk=None):
        university = get_object_or_404(University, pk=pk)
        if request.user != university.user:
            return Response(
                status=status.HTTP_403_FORBIDDEN, data="?????? ????????? ???????????? ?????? ??? ????????????."
            )
        return super().destroy(request, pk=pk)

    # ????????? patch ???????????? drf-yasg??? ?????? ?????? ???????????????
    @swagger_auto_schema(auto_schema=None)
    def patch(self, request, *args, **kwargs):
        return Response(status.HTTP_204_NO_CONTENT)
