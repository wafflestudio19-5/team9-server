from abc import ABC
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import update_last_login
from django.db import transaction
from drf_yasg.utils import swagger_serializer_method
from rest_framework import serializers
from rest_framework_jwt.settings import api_settings
from .models import User, Company, University, FriendRequest
from datetime import datetime
from django.contrib.auth.password_validation import validate_password
from .utils import validate_gender, validate_birth


# 토큰 사용을 위한 기본 세팅
User = get_user_model()
JWT_PAYLOAD_HANDLER = api_settings.JWT_PAYLOAD_HANDLER
JWT_ENCODE_HANDLER = api_settings.JWT_ENCODE_HANDLER

# [ user -> jwt_token ] function
def jwt_token_of(user):
    payload = JWT_PAYLOAD_HANDLER(user)
    jwt_token = JWT_ENCODE_HANDLER(payload)
    return jwt_token


class UserCreateSerializer(serializers.Serializer):
    GENDER_CHOICES = {"Male": "M", "Female": "F"}

    email = serializers.EmailField(required=True)
    first_name = serializers.CharField(max_length=25, required=True)
    last_name = serializers.CharField(max_length=25, required=True)
    birth = serializers.DateField(
        format="%Y-%m-%d",
        input_formats=[
            "%Y-%m-%d",
        ],
        required=True,
        help_text="Format: YYYY-MM-DD",
        validators=[validate_birth],
    )
    gender = serializers.CharField(
        max_length=10,
        required=True,
        help_text="'Male' or 'Female'",
        validators=[validate_gender],
    )
    password = serializers.CharField(
        max_length=128, required=True, validators=[validate_password]
    )

    # validate 정의
    def validate(self, data):
        # if not first_name or not last_name:
        #    raise serializers.ValidationError("성이나 이름은 빈칸일 수 없습니다.")
        # 필드가 blank일 수 없게 되는 조건이 이미 존재
        return data

    def create(self, validated_data):
        validated_data["username"] = (
            validated_data["last_name"] + validated_data["first_name"]
        )
        user = User.objects.create_user(**validated_data)
        return user, jwt_token_of(user)


class UserLoginSerializer(serializers.Serializer):

    # 이메일 대신 핸드폰 번호를 아이디에 입력해도 로그인 되면 좋을 것 같습니다.

    email = serializers.CharField(max_length=64, required=True)
    password = serializers.CharField(max_length=128, write_only=True)
    token = serializers.CharField(max_length=255, read_only=True)

    def validate(self, data):
        email = data.get("email", None)
        password = data.get("password", None)
        user = authenticate(email=email, password=password)

        if not user:
            raise serializers.ValidationError("이메일 또는 비밀번호가 잘못되었습니다.")

        update_last_login(None, user)
        return {"user": user, "token": jwt_token_of(user)}


class UserSerializer(serializers.ModelSerializer):

    # 추가 필드 선언

    class Meta:
        model = User
        # Django 기본 User 모델에 존재하는 필드 중 일부
        fields = ("id", "email", "username", "profile_image")
        extra_kwargs = {"password": {"write_only": True}}

    def validate(self, data):

        # validate 함수 구현

        return data

    def create(self, validated_data):

        user = super().create(validated_data)
        return user


class UserMutualFriendsSerializer(serializers.ModelSerializer):
    is_friend = serializers.SerializerMethodField()
    mutual_friends = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "profile_image",
            "is_friend",
            "mutual_friends",
        )
        extra_kwargs = {"password": {"write_only": True}}

    # 공통 친구의 개수와 예시 최대 2명까지 나열
    def get_mutual_friends(self, user):
        request_user = self.context["request"].user
        if user == request_user:
            return None
        mutual_friends = request_user.friends.all() & user.friends.all()
        count = len(mutual_friends)
        example = mutual_friends.first()
        example_username = example.username if example else None
        data = {"count": count, "example": example_username}
        return data

    def get_is_friend(self, user):
        request_user = self.context["request"].user
        if user == request_user:
            return None
        return user.friends.filter(pk=request_user.id).exists()


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = (
            "id",
            "user",
            "name",
            "role",
            "location",
            "join_date",
            "leave_date",
            "is_active",
            "detail",
        )
        read_only_fields = ["id", "is_active"]
        extra_kwargs = {
            "user": {"required": True},
            "name": {"required": True},
            "join_date": {"required": True},
        }

    def validate(self, data):
        join_date = data.get("join_date")
        leave_date = data.get("leave_date")
        if leave_date and leave_date < join_date:
            raise serializers.ValidationError("기간이 유효하지 않습니다.")
        return data

    def create(self, validated_data):
        leave_date = validated_data.get("leave_date")
        validated_data["is_active"] = (
            not leave_date or leave_date > datetime.now().date()
        )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        instance.is_active = (
            not instance.leave_date or instance.leave_date > datetime.now().date()
        )
        instance.save()
        return instance

    def to_internal_value(self, data):
        if data.get("leave_date") == "":
            data["leave_date"] = None
        return super().to_internal_value(data)


class UniversitySerializer(serializers.ModelSerializer):
    class Meta:
        model = University
        fields = (
            "id",
            "user",
            "name",
            "major",
            "join_date",
            "graduate_date",
            "is_active",
        )
        read_only_fields = ["is_active"]
        extra_kwargs = {
            "user": {"required": True},
            "name": {"required": True},
            "join_date": {"required": True},
        }

    def validate(self, data):
        join_date = data.get("join_date")
        graduate_date = data.get("graduate_date")
        if graduate_date and graduate_date < join_date:
            raise serializers.ValidationError("기간이 유효하지 않습니다.")
        return data

    def create(self, validated_data):
        graduate_date = validated_data.get("graduate_date")
        validated_data["is_active"] = (
            not graduate_date or graduate_date > datetime.now().date()
        )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        instance.is_active = (
            not instance.graduate_date or instance.graduate_date > datetime.now().date()
        )
        instance.save()
        return instance

    def to_internal_value(self, data):
        if data.get("graduate_date") == "":
            data["graduate_date"] = None
        return super().to_internal_value(data)


class UserPutSwaggerSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    birth = serializers.DateField(required=False)
    gender = serializers.CharField(required=False)
    self_intro = serializers.CharField(required=False)


class UserLoginSwaggerSerializer(serializers.Serializer):
    user = UserSerializer()
    token = serializers.CharField()


class UserProfileImageSwaggerSerializer(serializers.Serializer):
    profile_image = serializers.BooleanField(required=False)
    cover_image = serializers.BooleanField(required=False)


class UserProfileSerializer(serializers.ModelSerializer):

    company = CompanySerializer(many=True, read_only=True)
    university = UniversitySerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "first_name",
            "last_name",
            "username",
            "email",
            "birth",
            "gender",
            "self_intro",
            "profile_image",
            "cover_image",
            "company",
            "university",
        )
        read_only_fields = (
            "id",
            "username",
            "email",
            "company",
            "university",
            "profile_image",
            "cover_image",
        )

    def validate(self, data):
        gender = data.get("gender")
        if gender and gender != "M" and gender != "F":
            raise serializers.ValidationError("성별이 잘못되었습니다.")
        birth = data.get("birth")
        if birth and birth > datetime.now().date():
            raise serializers.ValidationError("생일이 현재 시간보다 나중일 수는 없습니다.")
        return data

    def update(self, instance, validated_data):
        user = super().update(instance, validated_data)
        user.username = user.last_name + user.first_name
        user.save()
        return user


class FriendRequestCreateSerializer(serializers.ModelSerializer):
    sender_profile = serializers.SerializerMethodField()

    class Meta:
        model = FriendRequest
        fields = "__all__"

    def create(self, validated_data):
        sender = validated_data.get("sender")
        receiver = validated_data.get("receiver")
        friend_request = FriendRequest.objects.create(sender=sender, receiver=receiver)
        return friend_request

    def validate(self, data):
        receiver = data.get("receiver")
        sender = data["sender"]
        if sender.friends.filter(pk=receiver.id).exists():
            raise serializers.ValidationError("이미 친구입니다.")
        if sender.received_friend_request.filter(sender=receiver).exists():
            raise serializers.ValidationError("이 유저에게 이미 친구 요청을 받았습니다.")
        if sender.sent_friend_request.filter(receiver=receiver).exists():
            raise serializers.ValidationError("이미 이 유저에게 친구 요청을 보냈습니다.")

        if sender == receiver:
            raise serializers.ValidationError("자신에게 친구 요청을 보낼 수 없습니다.")
        return data

    @swagger_serializer_method(serializer_or_field=UserSerializer)
    def get_sender_profile(self, friend_request):
        return UserSerializer(friend_request.sender).data


# 친구 요청 수락 및 삭제
class FriendRequestAcceptDeleteSerializer(serializers.ModelSerializer):
    class Meta:
        model = FriendRequest
        fields = "__all__"

    def validate(self, data):
        receiver = data["receiver"]
        sender = data["sender"]
        friend_request = FriendRequest.objects.all().filter(
            sender=sender, receiver=receiver
        )
        if not friend_request.exists():
            raise serializers.ValidationError("해당 친구 요청이 존재하지 않습니다.")
        data["friend_request"] = friend_request.first()
        return data

    @transaction.atomic
    def accept(self, validated_data):
        friend_request = validated_data.get("friend_request")
        friend_request.delete()
        sender = validated_data.get("sender")
        receiver = validated_data.get("receiver")
        sender.friends.add(receiver)

    def delete(self, validated_data):
        friend_request = validated_data.get("friend_request")
        friend_request.delete()
