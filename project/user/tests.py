from django.test import TestCase
from factory.django import DjangoModelFactory
from user.models import User
from faker import Faker
from newsfeed.models import Post
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


class NewUserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = "test@test.com"

    @classmethod
    def create(cls, **kwargs):

        fake = Faker("ko_KR")
        user = User.objects.create(
            email=kwargs.get("email", fake.email()),
            password=kwargs.get("password", fake.password()),
            first_name=kwargs.get("first_name", fake.first_name()),
            last_name=kwargs.get("last_name", fake.last_name()),
            birth=kwargs.get("birth", fake.date()),
            gender=kwargs.get(
                "gender", fake.random_choices(elements=("M", "F"), length=1)[0]
            ),
            phone_number=kwargs.get("phone_number", fake.numerify(text="010########")),
        )
        user.username = user.first_name + user.last_name
        user.set_password(kwargs.get("password", ""))
        user.save()

        return user


class PostFactory(DjangoModelFactory):
    class Meta:
        model = Post

    @classmethod
    def create(cls, **kwargs):

        fake = Faker("ko_KR")
        post = Post.objects.create(
            author=kwargs.get("author"),
            content=kwargs.get("content", fake.text(max_nb_chars=1000)),
            file=kwargs.get("file", None),
            likes=kwargs.get("likes", fake.random_int(min=0, max=1000)),
        )
        post.save()

        return post


class SignUpUserTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory(
            email="waffle@test.com",
            first_name="민준",
            last_name="이",
            birth="2002-05-14",
            gender="Male",
            password="yiminj",
        )

        cls.post_data = {
            "email": "waffle@test.com",
            "first_name": "민준",
            "last_name": "이",
            "birth": "2002-05-14",
            "gender": "Male",
            "password": "yiminj",
        }

    def test_post_user_successful(self):
        data = self.post_data.copy()
        data["email"] = "waffle2@test.com"
        response = self.client.post("/api/v1/signup/", data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(User.objects.last().username, "이민준")

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

    def test_post_user_validation_fail(self):
        # first_name empty
        data = self.post_data.copy()
        data["first_name"] = ""
        response = self.client.post("/api/v1/signup/", data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 1)

        # last_name empty
        data = self.post_data.copy()
        data["last_name"] = ""
        response = self.client.post("/api/v1/signup/", data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 1)

        # common password
        data = self.post_data.copy()
        data["password"] = "12345678"
        response = self.client.post("/api/v1/signup/", data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 1)

        # short password
        data = self.post_data.copy()
        data["password"] = "!nn?"
        response = self.client.post("/api/v1/signup/", data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 1)

        # invalid birth
        data = self.post_data.copy()
        data["birth"] = "2100-12-23"
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
        # self.assertEqual(data["token"], jwt_token_of((self.user)))

    def test_login_fail(self):
        response = self.client.post(
            "/api/v1/login/",
            data={"email": "waffle@test.com", "password": "qlalfqjsgh"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LogoutTestCase(TestCase):
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

    def test_logout(self):
        user_token = "JWT " + jwt_token_of(self.user)
        response = self.client.get(
            "/api/v1/logout/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(user_token, "JWT " + jwt_token_of(self.user))


class UserNewsFeedTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):

        cls.test_user = NewUserFactory.create(
            email="test0@test.com",
            password="password",
            first_name="test",
            last_name="user",
            birth="1997-02-03",
            gender="M",
            phone_number="01000000000",
        )

        cls.test_friend = NewUserFactory.create(
            email="test1@test.com",
            password="password",
            first_name="test",
            last_name="friend",
            birth="1997-02-03",
            gender="M",
            phone_number="01011111111",
        )

        PostFactory.create_batch(40, author=cls.test_friend)
        PostFactory.create(author=cls.test_user, content="나의 첫번째 테스트 게시물입니다.", likes=10)
        PostFactory.create(author=cls.test_user, content="나의 두번째 테스트 게시물입니다.", likes=20)

    def test_post_user_list(self):

        user_token = "JWT " + jwt_token_of(self.test_user)
        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # 나중 게시글이 먼저 떠야함, 유저의 게시글은 2개여야 함
        self.assertEqual(len(data["results"]), 2)
        self.assertEqual(data["results"][0]["likes"], 20)
        self.assertEqual(data["results"][1]["likes"], 10)

        response = self.client.get(
            f"/api/v1/user/{self.test_friend.id}/newsfeed/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # 20개 단위로 페이지네이션 되므로 20개가 떠야함
        self.assertEqual(len(data["results"]), 20)

    def test_post_user_notfound(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        response = self.client.get(
            "/api/v1/user/100/newsfeed/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_post_user_unauthorized(self):
        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
