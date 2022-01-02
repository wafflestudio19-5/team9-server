from django.test import TestCase
from factory.django import DjangoModelFactory
from faker import Faker

from user.models import User, FriendRequest
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
        user.username = user.last_name + user.first_name
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
        self.assertIn(data["results"][0]["sender"], [sender.id for sender in self.senders])

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
        self.assertTrue(FriendRequest.objects.filter(sender=self.test_user, receiver=self.test_stranger))

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
            data={"friend":friend.id},
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


class SearchTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.test_user = UserFactory.create(
            first_name="와플",
            last_name="김",
        )
        cls.test_stranger = UserFactory.create(
            first_name="cd",
            last_name="ab",
        )
        # username = 공통친구
        cls.test_mutual_friends = UserFactory.create_batch(25, first_name="친구", last_name="공통")
        for mutual_friend in cls.test_mutual_friends:
            cls.test_user.friends.add(mutual_friend)
            cls.test_stranger.friends.add(mutual_friend)

    def test_search(self):
        user = self.test_user
        user_token = "JWT " + jwt_token_of(user)
        response = self.client.get(
            "/api/v1/search/?q=Bc",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["results"]
        self.assertEqual(len(data), 1)
        self.assertFalse(data[0]["is_friend"])
        self.assertEqual(data[0]["mutual_friends"]["count"], 25)
        self.assertEqual(data[0]["mutual_friends"]["example"], "공통친구")

        # test_mutual_friends 검색
        response = self.client.get(
            "/api/v1/search/?q=공통친구",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 20)
        self.assertTrue(data["results"][0]["is_friend"])
        self.assertEqual(data["results"][0]["mutual_friends"]["count"], 0)
