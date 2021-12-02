from django.test import TestCase
from factory.django import DjangoModelFactory
from user.models import User
from user.serializers import jwt_token_of
from rest_framework import status
import json
from django.db import transaction



class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = "test@test.com"

    @classmethod
    def create(cls, **kwargs):
        user = User.objects.create(**kwargs)
        user.set_password(kwargs.get("password", ""))
        user.save()

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
        data = self.post_data.copy()
        data["email"] = "waffle2@test.com"
        response = self.client.post("/api/v1/signup/", data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(User.objects.count(), 2)

    def test_post_user_confilct(self):
        with transaction.atomic():
            response = self.client.post("/api/v1/signup/", data=self.post_data)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

        self.assertEqual(User.objects.count(), 1)

    def test_post_user_bad_gender(self):
        data = self.post_data.copy()
        data["email"] = "waffle2@test.com"
        data["gender"] = "WOW"
        response = self.client.post("/api/v1/signup/", data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(User.objects.count(), 1)

    def test_post_user_no_argument(self):
        data = self.post_data.copy()
        data.pop("email")
        response = self.client.post("/api/v1/signup/", data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 1)

        data["email"] = "waffle2@test.com"
        data.pop("first_name")
        response = self.client.post("/api/v1/signup/", data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 1)

        data["first_name"] = self.post_data["first_name"]
        data.pop("last_name")
        response = self.client.post("/api/v1/signup/", data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 1)

        data["last_name"] = self.post_data["last_name"]
        data.pop("birth")
        response = self.client.post("/api/v1/signup/", data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 1)

        data["birth"] = self.post_data["birth"]
        data.pop("gender")
        response = self.client.post("/api/v1/signup/", data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 1)

        data["gender"] = self.post_data["gender"]
        data.pop("password")
        response = self.client.post("/api/v1/signup/", data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 1)


class LoginTestCase(TestCase):
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
            "password": "password",
        }

    def test_login(self):
        response = self.client.post(
            "/api/v1/login/", data=self.post_data, content_type="application/json"
        )
        data = response.json()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(data["token"], jwt_token_of((self.user)))

    def test_login_fail(self):
        response = self.client.post(
            "/api/v1/login/",
            data={"email": "waffle@test.com", "password": "qlalfqjsgh"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
