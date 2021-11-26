from django.test import TestCase
from factory.django import DjangoModelFactory
from user.models import User
from user.serializers import jwt_token_of
from rest_framework import status
import json


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = "test@test.com"

    @classmethod
    def create(cls, **kwargs):
        user = User.objects.create(**kwargs)
        user.set_password(kwargs.get("password", ""))

        return user


class SignUpUserTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory(
            email="waffle@test.com",
            first_name="민준",
            last_name="이",
            birth="2002-05-14",
            gender="Male",
            password="password",
        )

        cls.post_data = {
            "email": "waffle@test.com",
            "first_name": "민준",
            "last_name": "이",
            "birth": "2002-05-14",
            "gender": "Male",
            "password": "password",
        }

    def test_post_user_successful(self):
        data = self.post_data
        data["email"] = "waffle2@test.com"
        response = self.client.post("/api/v1/signup/", data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(User.objects.count(), 2)
