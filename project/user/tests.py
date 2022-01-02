from django.test import TestCase
from factory.django import DjangoModelFactory
from user.models import User, Company, University, FriendRequest
from faker import Faker
from newsfeed.models import Post
from user.serializers import jwt_token_of
from rest_framework import status
from rest_framework.test import APITestCase
import datetime
import os
from pathlib import Path
import json
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction

BASE_DIR = Path(__file__).resolve().parent.parent


class UserFactory(DjangoModelFactory):
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


class CompanyFactory(DjangoModelFactory):
    class Meta:
        model = Company

    @classmethod
    def create(cls, **kwargs):
        fake = Faker("ko_KR")
        company = Company.objects.create(
            user=kwargs.get("user"),
            name=kwargs.get("name", fake.text(max_nb_chars=30)),
            role=kwargs.get("role", fake.text(max_nb_chars=30)),
            location=kwargs.get("location", fake.text(max_nb_chars=50)),
            join_date=kwargs.get("join_date", fake.date()),
            leave_date=kwargs.get("leave_date"),
            is_active=kwargs.get("is_active", True),
            detail=kwargs.get("detail", fake.text(max_nb_chars=300)),
        )
        company.save()
        return company


class UniversityFactory(DjangoModelFactory):
    class Meta:
        model = University

    @classmethod
    def create(cls, **kwargs):
        fake = Faker("ko_KR")
        university = University.objects.create(
            user=kwargs.get("user"),
            name=kwargs.get("name", fake.text(max_nb_chars=30)),
            major=kwargs.get("role", fake.text(max_nb_chars=30)),
            join_date=kwargs.get("join_date", fake.date()),
            graduate_date=kwargs.get("graduate_date"),
            is_active=kwargs.get("is_active", True),
        )
        university.save()
        return university


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

    def test_user_post_list(self):

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

    def test_user_post_notfound(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        response = self.client.get(
            "/api/v1/user/100/newsfeed/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_post_unauthorized(self):
        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserFriendTestCase(TestCase):
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

        cls.test_user.friends.add(cls.test_friend)
        cls.test_user.save()
        cls.users = NewUserFactory.create_batch(30)
        for user in cls.users:
            cls.test_user.friends.add(user)
        cls.test_user.save()

    def test_post_user_list(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        response = self.client.get(
            f"/api/v1/user/{self.test_friend.id}/friend/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # 테스트 프렌트의 친구는 유저뿐
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["username"], self.test_user.username)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/friend/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # 페이지네이션 돼서 20개
        self.assertEqual(len(data["results"]), 20)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/friend/?limit=9",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # 9개로 제한
        self.assertEqual(len(data["results"]), 9)

    def test_post_user_notfound(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        response = self.client.get(
            "/api/v1/user/100/friend/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_post_user_unauthorized(self):
        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/friend/",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserProfileTestCase(APITestCase):
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
        cls.test_user.self_intro = "hihi~~"
        cls.test_user.profile_image = SimpleUploadedFile(
            name="testimage.jpg",
            content=open(os.path.join(BASE_DIR, "testimage.jpg"), "rb").read(),
            content_type="image/jpeg",
        )
        cls.test_user.cover_image = SimpleUploadedFile(
            name="testimage.jpg",
            content=open(os.path.join(BASE_DIR, "testimage.jpg"), "rb").read(),
            content_type="image/jpeg",
        )
        cls.test_user.save()
        cls.test_friend = NewUserFactory.create()
        CompanyFactory.create_batch(3, user=cls.test_user)
        UniversityFactory.create_batch(3, user=cls.test_user)

        cls.company_data = {
            "name": "Nexon",
            "role": "programmer",
            "location": "pangyo",
            "join_date": "2021-01-01",
            "leave_date": "2021-12-31",
            "detail": "nexon programmer",
        }
        cls.university_data = {
            "name": "SNU",
            "major": "CSE",
            "join_date": "2021-01-01",
            "graduate_date": "2021-12-31",
        }

    def test_get_user_profile(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/profile/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["id"], self.test_user.id)
        self.assertEqual(data["email"], self.test_user.email)
        self.assertEqual(data["first_name"], self.test_user.first_name)
        self.assertEqual(data["last_name"], self.test_user.last_name)
        self.assertEqual(data["username"], self.test_user.username)
        self.assertEqual(data["birth"], self.test_user.birth)
        self.assertEqual(data["gender"], self.test_user.gender)
        self.assertEqual(data["self_intro"], self.test_user.self_intro)
        self.assertIn("testimage.jpg", data["profile_image"])
        self.assertIn("testimage.jpg", data["cover_image"])
        self.assertEqual(len(data["company"]), 3)
        self.assertEqual(len(data["university"]), 3)
        friend_token = "JWT " + jwt_token_of(self.test_friend)
        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/profile/",
            content_type="application/json",
            HTTP_AUTHORIZATION=friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        newdata = response.json()
        self.assertEqual(data, newdata)

    def test_get_user_profile_unauthorized(self):
        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/profile/",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_user_profile_notfound(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        response = self.client.get(
            f"/api/v1/user/{100}/profile/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_put_user_profile(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        testimage2 = SimpleUploadedFile(
            name="testimage2.jpg",
            content=open(os.path.join(BASE_DIR, "testimage2.jpg"), "rb").read(),
            content_type="image/jpeg",
        )
        data = {
            "first_name": "ttest",
            "birth": "2002-05-14",
            "gender": "F",
            "self_intro": "nice to meet you",
            "profile_image": testimage2,
            "email": "asdf@asdf.com",
        }
        response = self.client.put(
            f"/api/v1/user/{self.test_user.id}/profile/",
            data=data,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.test_user.refresh_from_db()
        self.assertEqual("test0@test.com", self.test_user.email)
        self.assertEqual(data["first_name"], self.test_user.first_name)
        self.assertEqual("user", self.test_user.last_name)
        self.assertEqual("userttest", self.test_user.username)
        self.assertEqual(datetime.date(2002, 5, 14), self.test_user.birth)
        self.assertEqual(data["gender"], self.test_user.gender)
        self.assertEqual(data["self_intro"], self.test_user.self_intro)
        self.assertIn("testimage2.jpg", self.test_user.profile_image.name)
        self.assertNotIn("testimage2.jpg", self.test_user.cover_image.name)

    def test_put_user_profile_unauthorized(self):
        friend_token = "JWT " + jwt_token_of(self.test_friend)
        testimage2 = SimpleUploadedFile(
            name="testimage2.jpg",
            content=open(os.path.join(BASE_DIR, "testimage2.jpg"), "rb").read(),
            content_type="image/jpeg",
        )
        data = {
            "first_name": "ttest",
            "birth": "2002-05-14",
            "gender": "F",
            "self_intro": "nice to meet you",
            "profile_image": testimage2,
        }
        response = self.client.put(
            f"/api/v1/user/{self.test_user.id}/profile/",
            data=data,
            HTTP_AUTHORIZATION=friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        response = self.client.put(
            f"/api/v1/user/{self.test_user.id}/profile/",
            data=data,
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_user_profile_notfound(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        response = self.client.put(
            f"/api/v1/user/{100}/profile/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_post_company_profile(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        response = self.client.post(
            f"/api/v1/user/company/",
            data=self.company_data,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["user"], self.test_user.id)
        self.assertEqual(data["name"], self.company_data["name"])
        self.assertEqual(data["role"], self.company_data["role"])
        self.assertEqual(data["location"], self.company_data["location"])
        self.assertEqual(data["join_date"], self.company_data["join_date"])
        self.assertEqual(data["leave_date"], self.company_data["leave_date"])
        self.assertEqual(data["detail"], self.company_data["detail"])
        self.assertEqual(data["is_active"], False)
        self.test_user.refresh_from_db()
        self.assertEqual(self.test_user.company.count(), 4)

    def test_post_company_profile_request_incomplete(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        self.company_data.pop("name")
        response = self.client.post(
            f"/api/v1/user/company/",
            data=self.company_data,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_company_profile_bad_request(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        self.company_data["join_date"] = "2200-01-01"
        response = self.client.post(
            f"/api/v1/user/company/",
            data=self.company_data,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_post_company_profile_unauthorized(self):
        response = self.client.post(
            f"/api/v1/user/company/",
            data=self.company_data,
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_put_company_profile_request(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        self.company_data.pop("role")  # to check partial update
        role = self.test_user.company.last().role
        response = self.client.put(
            f"/api/v1/user/company/{self.test_user.company.last().id}/",
            data=self.company_data,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["user"], self.test_user.id)
        self.assertEqual(data["name"], self.company_data["name"])
        self.assertEqual(data["role"], role)
        self.assertEqual(data["location"], self.company_data["location"])
        self.assertEqual(data["join_date"], self.company_data["join_date"])
        self.assertEqual(data["leave_date"], self.company_data["leave_date"])
        self.assertEqual(data["detail"], self.company_data["detail"])
        self.assertEqual(data["is_active"], False)

    def test_put_company_profile_bad_request(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        self.company_data["join_date"] = "2200-01-01"
        response = self.client.put(
            f"/api/v1/user/company/{self.test_user.company.last().id}/",
            data=self.company_data,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_put_company_profile_unauthorized(self):
        response = self.client.put(
            f"/api/v1/user/company/{self.test_user.company.last().id}/",
            data=self.company_data,
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        friend_token = "JWT " + jwt_token_of(self.test_friend)
        response = self.client.put(
            f"/api/v1/user/company/{self.test_user.company.last().id}/",
            data=self.company_data,
            HTTP_AUTHORIZATION=friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_put_company_profile_not_found(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        response = self.client.put(
            f"/api/v1/user/company/{100}/",
            data=self.company_data,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_company_profile(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        response = self.client.delete(
            f"/api/v1/user/company/{self.test_user.company.last().id}/",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.test_user.refresh_from_db()
        self.assertEqual(self.test_user.company.count(), 2)

    def test_delete_company_profile_unauthorized(self):
        response = self.client.delete(
            f"/api/v1/user/company/{self.test_user.company.last().id}/",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        friend_token = "JWT " + jwt_token_of(self.test_friend)
        response = self.client.delete(
            f"/api/v1/user/company/{self.test_user.company.last().id}/",
            HTTP_AUTHORIZATION=friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_company_profile_not_found(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        response = self.client.delete(
            f"/api/v1/user/company/{100}/",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_post_university_profile(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        response = self.client.post(
            f"/api/v1/user/university/",
            data=self.university_data,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["user"], self.test_user.id)
        self.assertEqual(data["name"], self.university_data["name"])
        self.assertEqual(data["major"], self.university_data["major"])
        self.assertEqual(data["join_date"], self.university_data["join_date"])
        self.assertEqual(data["graduate_date"], self.university_data["graduate_date"])
        self.assertEqual(data["is_active"], False)
        self.test_user.refresh_from_db()
        self.assertEqual(self.test_user.university.count(), 4)

    def test_post_university_profile_bad_request(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        self.university_data["join_date"] = "2200-01-01"
        response = self.client.post(
            f"/api/v1/user/university/",
            data=self.university_data,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_post_university_profile_unauthorized(self):
        response = self.client.post(
            f"/api/v1/user/university/",
            data=self.university_data,
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def tet_put_university_profile(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        self.university_data.pop("major")  # to check partial update
        major = self.test_user.university.last().major
        response = self.client.post(
            f"/api/v1/user/university/{self.test_user.university.last()}/",
            data=self.university_data,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["user"], self.test_user.id)
        self.assertEqual(data["name"], self.university_data["name"])
        self.assertEqual(data["major"], major)
        self.assertEqual(data["join_date"], self.university_data["join_date"])
        self.assertEqual(data["graduate_date"], self.university_data["graduate_date"])
        self.assertEqual(data["is_active"], False)

    def test_put_university_profile_unauthorized(self):
        response = self.client.put(
            f"/api/v1/user/university/{self.test_user.university.last().id}/",
            data=self.university_data,
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        friend_token = "JWT " + jwt_token_of(self.test_friend)
        response = self.client.put(
            f"/api/v1/user/university/{self.test_user.university.last().id}/",
            data=self.university_data,
            HTTP_AUTHORIZATION=friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_put_university_profile_not_found(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        response = self.client.put(
            f"/api/v1/user/university/{100}/",
            data=self.university_data,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_university_profile(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        response = self.client.delete(
            f"/api/v1/user/university/{self.test_user.university.last().id}/",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.test_user.refresh_from_db()
        self.assertEqual(self.test_user.university.count(), 2)

    def test_delete_university_profile_unauthorized(self):
        response = self.client.delete(
            f"/api/v1/user/university/{self.test_user.university.last().id}/",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        friend_token = "JWT " + jwt_token_of(self.test_friend)
        response = self.client.delete(
            f"/api/v1/user/university/{self.test_user.university.last().id}/",
            HTTP_AUTHORIZATION=friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_university_profile_not_found(self):
        user_token = "JWT " + jwt_token_of(self.test_user)
        response = self.client.delete(
            f"/api/v1/user/university/{100}/",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        
class FriendRequestFactory(DjangoModelFactory):
    class Meta:
        model = FriendRequest


class FriendTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.friends = UserFactory.create_batch(25)
        cls.test_user = UserFactory.create()
        for friend in cls.friends:
            cls.test_user.friends.add(friend)
        cls.senders = UserFactory.create_batch(25)
        for sender in cls.senders:
            FriendRequestFactory.create(sender=sender, receiver=cls.test_user)

        cls.test_stranger = UserFactory.create()

    def test_get_friend_request(self):
        user = self.test_user
        user_token = "JWT " + jwt_token_of(user)
        response = self.client.get(
            "/api/v1/friend/request/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(len(data["results"]), 20)
        self.assertIn(
            data["results"][0]["sender"], [sender.id for sender in self.senders]
        )

        next_page = data["next"]
        response = self.client.get(
            next_page,
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(len(response.data["results"]), 5)

    def test_send_friend_request(self):
        user = self.test_user
        user_token = "JWT " + jwt_token_of(user)
        response = self.client.post(
            "/api/v1/friend/request/",
            data={"receiver": self.test_stranger.id},
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            FriendRequest.objects.filter(
                sender=self.test_user, receiver=self.test_stranger
            )
        )

        # 자기 자신에게 친구 요청
        response = self.client.post(
            "/api/v1/friend/request/",
            data={"receiver": self.test_user.id},
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # 이미 친구인 유저에 친구 요청
        response = self.client.post(
            "/api/v1/friend/request/",
            data={"receiver": self.friends[0].id},
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # 자신에게 이미 친구 요청을 보낸 유저에게 친구 요청
        response = self.client.post(
            "/api/v1/friend/request/",
            data={"receiver": self.senders[0].id},
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
          
        # 유효하지 않은 유저 id에 친구 요청
        response = self.client.post(
            "/api/v1/friend/request/",
            data={"receiver": -1},
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
          
    def test_accept_friend_request(self):
        user = self.test_user
        user_token = "JWT " + jwt_token_of(user)
        sender = self.senders[0]
        response = self.client.put(
            "/api/v1/friend/request/",
            data={"sender": sender.id},
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse((FriendRequest.objects.filter(sender=sender, receiver=user)))
        self.assertIn(sender, user.friends.all())

        # sender에 해당하는 친구 요청이 없는 경우
        response = self.client.put(
            "/api/v1/friend/request/",
            data={"sender": self.test_stranger.id},
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_friend_request(self):
        user = self.test_user
        user_token = "JWT " + jwt_token_of(user)
        sender = self.senders[0]
        response = self.client.delete(
            "/api/v1/friend/request/",
            data={"sender": sender.id, "receiver": user.id},
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse((FriendRequest.objects.filter(sender=sender, receiver=user)))

        # sender에 해당하는 친구 요청이 없는 경우
        response = self.client.delete(
            "/api/v1/friend/request/",
            data={"sender": self.test_stranger.id, "receiver": user.id},
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # 자신이 sender 혹은 receiver가 아닌 경우
        response = self.client.delete(
            "/api/v1/friend/request/",
            data={"sender": sender.id, "receiver": self.test_stranger.id},
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_friend(self):
        user = self.test_user
        user_token = "JWT " + jwt_token_of(user)
        friend = self.friends[0]
        response = self.client.delete(
            "/api/v1/friend/",
            data={"friend": friend.id},
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(user.friends.filter(pk=friend.id))

        # friend와 친구 관계가 없는 경우
        response = self.client.delete(
            "/api/v1/friend/",
            data={"friend": self.test_stranger.id},
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

