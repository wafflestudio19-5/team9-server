from rest_framework import serializers

from user.serializers import UserSerializer


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