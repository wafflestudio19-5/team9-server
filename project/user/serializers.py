from abc import ABC
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import update_last_login
from rest_framework import serializers
from rest_framework_jwt.settings import api_settings
from .models import User, Company, University
from datetime import datetime
from django.contrib.auth.password_validation import validate_password


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
    )
    gender = serializers.CharField(
        max_length=10, required=True, help_text="'Male' or 'Female'"
    )
    password = serializers.CharField(max_length=128, required=True)

    # validate 정의
    def validate(self, data):
        gender = data.get("gender")
        if not gender:
            raise serializers.ValidationError("성별이 설정되지 않았습니다.")
        if gender != "Male" and gender != "Female":
            raise serializers.ValidationError("성별이 잘못되었습니다.")
        first_name = data.get("first_name")
        last_name = data.get("last_name")
        if not first_name or not last_name:
            raise serializers.ValidationError("성이나 이름은 빈칸일 수 없습니다.")
        birth = data.get("birth")
        if birth > datetime.now().date():
            raise serializers.ValidationError("생일이 현재 시간보다 나중일 수는 없습니다.")
        password = data.get("password")
        validate_password(password)
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
        return {"email": user.email, "token": jwt_token_of(user)}


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


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = (
            "user",
            "name",
            "role",
            "location",
            "join_date",
            "leave_date",
            "is_active",
            "detail",
        )
        read_only_fields = ["is_active"]

    def validate(self, data):
        join_date = data.get("join_date")
        leave_date = data.get("leave_date")
        if leave_date and leave_date < join_date:
            raise serializers.ValidationError("기간이 유효하지 않습니다.")
        return data


class UniversitySerializer(serializers.ModelSerializer):
    class Meta:
        model = University
        fields = (
            "user",
            "name",
            "major",
            "join_date",
            "graduate_date",
            "is_active",
        )
        read_only_fields = ["is_active"]

    def validate(self, data):
        join_date = data.get("join_date")
        graduate_date = data.get("graduate_date")
        if graduate_date and graduate_date < join_date:
            raise serializers.ValidationError("기간이 유효하지 않습니다.")
        return data


class UserProfileSerializer(serializers.ModelSerializer):
    company = CompanySerializer(many=True, read_only=True)
    university = UniversitySerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "username",
            "email",
            "birth",
            "gender",
            "self_intro",
            "profile_image",
            "cover_image",
        )
        read_only_fields = ("username", "email")
