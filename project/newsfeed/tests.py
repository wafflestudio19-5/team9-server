from django.test import TestCase
from django.test.client import encode_multipart
from factory.django import DjangoModelFactory
from faker import Faker
from user.models import User
from newsfeed.models import Post, Comment
from rest_framework import status
from django.core.files.uploadedfile import SimpleUploadedFile
import os
from pathlib import Path
from user.serializers import jwt_token_of
from user.tests import UserFactory

BASE_DIR = Path(__file__).resolve().parent.parent
# Create your tests here.
class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = "test@test.com"
    idx = 500

    @classmethod
    def create(cls, **kwargs):

        fake = Faker("ko_KR")
        user = User.objects.create(
            email=kwargs.get("email", f"test{cls.idx}@test.com"),
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
        cls.idx += 1
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


class CommentFactory(DjangoModelFactory):
    class Meta:
        model = Comment


class NewsFeedTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.users = UserFactory.create_batch(10)
        for user in cls.users:
            posts = PostFactory.create_batch(10, author=user)

        cls.test_user = UserFactory.create(
            email="test0@test.com",
            password="password",
            first_name="test",
            last_name="user",
            birth="1997-02-03",
            gender="M",
            phone_number="01000000000",
        )

        cls.test_friend = UserFactory.create(
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

        cls.test_stranger = UserFactory.create(
            email="test2@test.com",
            password="password",
            first_name="test",
            last_name="stranger",
            birth="1997-02-03",
            gender="M",
            phone_number="01022222222",
        )

        PostFactory.create(author=cls.test_user, content="?????? ????????? ??????????????????.", likes=10)

        cls.friend_post = PostFactory.create(
            author=cls.test_friend, content="????????? ????????? ??????????????????.", likes=20
        )
        cls.friend_post.likeusers.add(cls.test_user)
        cls.friend_post.save()

        PostFactory.create(
            author=cls.test_stranger, content="????????? ????????? ????????? ??????????????????.", likes=30
        )
        cls.content_type = "multipart/form-data; boundary=BoUnDaRyStRiNg"

    def test_post_list(self):

        # test_user??? ??????
        user_token = "JWT " + jwt_token_of(self.test_user)

        response = self.client.get(
            "/api/v1/newsfeed/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # ???????????? ??????
        self.assertEqual(len(data["results"]), 2)

        # ????????? ????????? ??? ??????????????? ??????
        # ??? ???????????? ?????? ??????????????? ?????? ?????????????????????, ?????? ???????????? ?????? ????????? (?????????)

        self.assertEqual(
            data["results"][1]["content"], self.test_user.posts.last().content
        )
        self.assertEqual(data["results"][1]["likes"], self.test_user.posts.last().likes)
        self.assertEqual(
            data["results"][0]["content"], self.test_friend.posts.last().content
        )
        self.assertEqual(
            data["results"][0]["likes"], self.test_friend.posts.last().likes
        )

        # is_liked ??????
        self.assertTrue(data["results"][0]["is_liked"])

        # test_stranger??? ??????
        user_token = "JWT " + jwt_token_of(self.test_stranger)

        response = self.client.get(
            "/api/v1/newsfeed/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # ???????????? ??????
        self.assertEqual(len(data["results"]), 1)

        # ????????? ??? ???????????? ??????
        self.assertEqual(
            data["results"][0]["content"], self.test_stranger.posts.last().content
        )
        self.assertEqual(
            data["results"][0]["likes"], self.test_stranger.posts.last().likes
        )

        # ????????? 9?????? ??? ?????? ????????? ??????
        user = self.users[0]

        for i in range(1, 10):
            user.friends.add(self.users[i])

        user_token = "JWT " + jwt_token_of(user)

        response = self.client.get(
            "/api/v1/newsfeed/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # ?????????????????? ????????? 20?????? ??? 5???????????? ??????.
        self.assertEqual(len(data["results"]), 20)

        for i in range(4):
            next_page = data["next"]
            response = self.client.get(
                next_page,
                content_type="application/json",
                HTTP_AUTHORIZATION=user_token,
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()
            self.assertEqual(len(data["results"]), 20)

    def test_post_create(self):

        user_token = "JWT " + jwt_token_of(self.test_user)
        fake = Faker("ko_KR")
        content = fake.text(max_nb_chars=100)

        test_image = SimpleUploadedFile(
            name="testimage.jpg",
            content=open(os.path.join(BASE_DIR, "testimage.jpg"), "rb").read(),
            content_type="image/jpeg",
        )
        data = {
            "content": content,
            "subposts": [{"content": "????????? ???????????????."}],
            "file": test_image,
        }

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertEqual(content, data["content"])
        self.assertEqual(self.test_user.id, data["author"]["id"])
        self.assertEqual(1, len(data["subposts"]))
        post_id = data["id"]
        self.assertEqual(post_id, data["subposts"][0]["mainpost"])
        self.assertEqual("????????? ???????????????.", data["subposts"][0]["content"])
        self.assertEqual(False, data["subposts"][0]["is_liked"])
        self.assertIn("testimage.jpg", data["subposts"][0]["file"])

        # ??????????????? ??????????????? ??????
        response = self.client.get(
            "/api/v1/newsfeed/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["id"], post_id)
        self.assertIn("testimage.jpg", data["results"][0]["subposts"][0]["file"])

        # File??? ????????? Content ????????? ?????? ?????? ??????, File??? ???????????? ????????? content ????????? ???
        data = {
            "subposts": [{"content": "????????? ???????????????."}],
            "file": test_image,
        }
        response = self.client.post(
            "/api/v1/newsfeed/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = {"content": "", "file": test_image, "subposts": [{"content": ""}]}
        response = self.client.post(
            "/api/v1/newsfeed/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = {"content": ""}
        response = self.client.post(
            "/api/v1/newsfeed/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_update(self):
        user_token = "JWT " + jwt_token_of(self.test_user)

        # ?????? ?????? ????????? ??????
        data = {
            "content": "?????? ??????????????????.",
        }
        response = self.client.post(
            "/api/v1/newsfeed/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        mainpost_id = data["id"]

        data = {
            "content": "?????? ??????????????????. (?????????)",
        }
        content = encode_multipart("BoUnDaRyStRiNg", data)
        content_type = "multipart/form-data; boundary=BoUnDaRyStRiNg"

        response = self.client.put(
            f"/api/v1/newsfeed/{mainpost_id}/",
            data=content,
            content_type=content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["id"], mainpost_id)
        self.assertEqual(data["content"], "?????? ??????????????????. (?????????)")

        # ?????? ????????? content ??? ?????? 400 ??????
        data = {"content": ""}
        content = encode_multipart("BoUnDaRyStRiNg", data)

        response = self.client.put(
            f"/api/v1/newsfeed/{mainpost_id}/",
            data=content,
            content_type=content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        test_image = SimpleUploadedFile(
            name="testimage2.jpg",
            content=open(os.path.join(BASE_DIR, "testimage2.jpg"), "rb").read(),
            content_type="image/jpeg",
        )
        data = {
            "content": "?????? ??????????????????.",
            "subposts": [
                {"content": "????????? ??????????????????."},
                {"content": "????????? ??????????????????."},
                {"content": "????????? ??????????????????."},
            ],
            "file": [test_image, test_image, test_image],
        }

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        mainpost_id = data["id"]
        subpost_1 = data["subposts"][0]["id"]
        subpost_2 = data["subposts"][1]["id"]
        subpost_3 = data["subposts"][2]["id"]

        # ?????? ??????
        data = {
            "content": "?????? ??????????????????. (?????????)",
            "subposts": [
                {"id": subpost_1, "content": "????????? ??????????????????. (?????????)"},
                {"id": subpost_2, "content": "????????? ??????????????????. (?????????)"},
                {"id": subpost_3, "content": "????????? ??????????????????. (?????????)"},
            ],
        }

        content = encode_multipart("BoUnDaRyStRiNg", data)

        response = self.client.put(
            f"/api/v1/newsfeed/{mainpost_id}/",
            data=content,
            content_type=content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["id"], mainpost_id)
        self.assertEqual(data["content"], "?????? ??????????????????. (?????????)")
        self.assertEqual(data["subposts"][0]["content"], "????????? ??????????????????. (?????????)")
        self.assertEqual(data["subposts"][0]["id"], subpost_1)
        self.assertEqual(data["subposts"][1]["content"], "????????? ??????????????????. (?????????)")
        self.assertEqual(data["subposts"][1]["id"], subpost_2)
        self.assertEqual(data["subposts"][2]["content"], "????????? ??????????????????. (?????????)")
        self.assertEqual(data["subposts"][2]["id"], subpost_3)

        # ?????? ??????
        data = {
            "content": "?????? ??????????????????. (?????????..2)",
            "subposts": [{"id": subpost_2, "content": "????????? ??????????????????. (?????????..2)"}],
            "removed_subposts": subpost_1,
        }
        content = encode_multipart("BoUnDaRyStRiNg", data)

        response = self.client.put(
            f"/api/v1/newsfeed/{mainpost_id}/",
            data=content,
            content_type=content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["id"], mainpost_id)
        self.assertEqual(data["content"], "?????? ??????????????????. (?????????..2)")
        self.assertEqual(len(data["subposts"]), 2)
        self.assertEqual(data["subposts"][0]["content"], "????????? ??????????????????. (?????????..2)")
        self.assertEqual(data["subposts"][0]["id"], subpost_2)
        self.assertEqual(data["subposts"][1]["content"], "????????? ??????????????????. (?????????)")
        self.assertEqual(data["subposts"][1]["id"], subpost_3)

        # ?????? ??????
        data = {
            "content": "?????? ??????????????????. (?????????)",
            "file": [test_image],
            "new_subposts": [{"content": "????????? ??????????????????."}],
        }
        content = encode_multipart("BoUnDaRyStRiNg", data)

        response = self.client.put(
            f"/api/v1/newsfeed/{mainpost_id}/",
            data=content,
            content_type=content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["id"], mainpost_id)
        self.assertEqual(data["content"], "?????? ??????????????????. (?????????)")
        self.assertEqual(len(data["subposts"]), 3)
        self.assertEqual(data["subposts"][0]["content"], "????????? ??????????????????. (?????????..2)")
        self.assertEqual(data["subposts"][0]["id"], subpost_2)
        self.assertEqual(data["subposts"][1]["content"], "????????? ??????????????????. (?????????)")
        self.assertEqual(data["subposts"][1]["id"], subpost_3)
        subpost_4 = data["subposts"][2]["id"]
        self.assertEqual(data["subposts"][2]["content"], "????????? ??????????????????.")

        # ?????? ????????? ?????? ????????? (2??? ??????, 3??? ??????)
        data = {
            "content": "?????? ??????????????????. (???????????????)",
            "file": [
                test_image,
                test_image,
                test_image,
            ],
            "new_subposts": [
                {"content": "???????????? ??????????????????."},
                {"content": "???????????? ??????????????????."},
                {"content": "???????????? ??????????????????."},
            ],
            "removed_subposts": [subpost_2, subpost_3],
        }
        content = encode_multipart("BoUnDaRyStRiNg", data)
        response = self.client.put(
            f"/api/v1/newsfeed/{mainpost_id}/",
            data=content,
            content_type=content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["id"], mainpost_id)
        self.assertEqual(data["content"], "?????? ??????????????????. (???????????????)")
        self.assertEqual(len(data["subposts"]), 4)
        self.assertEqual(data["subposts"][0]["content"], "????????? ??????????????????.")
        self.assertEqual(data["subposts"][0]["id"], subpost_4)
        self.assertEqual(data["subposts"][1]["content"], "???????????? ??????????????????.")
        subpost_5 = data["subposts"][1]["id"]
        self.assertEqual(data["subposts"][2]["content"], "???????????? ??????????????????.")
        subpost_6 = data["subposts"][2]["id"]
        self.assertEqual(data["subposts"][3]["content"], "???????????? ??????????????????.")
        subpost_7 = data["subposts"][3]["id"]

        # mainpost ????????? ???????????? ?????? ??????
        data = {
            "content": "?????? ?????????????????? ?????? ???????????????.",
            "subposts": [
                {"id": subpost_4, "content": "????????? ??????????????????. (?????????)"},
                {"id": subpost_5, "content": "???????????? ??????????????????. (?????????)"},
                {"id": subpost_6, "content": "???????????? ??????????????????. (?????????)"},
            ],
        }
        content = encode_multipart("BoUnDaRyStRiNg", data)
        response = self.client.put(
            f"/api/v1/newsfeed/{subpost_4}/",
            data=content,
            content_type=content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # ?????? ????????? content ????????? ????????? 200
        data = {
            "content": "",
            "subposts": [
                {"id": subpost_4, "content": ""},
                {"id": subpost_5, "content": ""},
                {"id": subpost_6, "content": ""},
                {"id": subpost_7, "content": ""},
            ],
        }
        content = encode_multipart("BoUnDaRyStRiNg", data)
        response = self.client.put(
            f"/api/v1/newsfeed/{mainpost_id}/",
            data=content,
            content_type=content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["content"], "")
        self.assertEqual(data["subposts"][0]["content"], "")
        self.assertEqual(data["subposts"][1]["content"], "")
        self.assertEqual(data["subposts"][2]["content"], "")
        self.assertEqual(data["subposts"][3]["content"], "")

        # subposts_id??? ?????? subpost??? 404
        data = {
            "content": "",
            "subposts": [
                {"id": subpost_1, "content": ""},
                {"id": subpost_5, "content": ""},
                {"id": subpost_6, "content": ""},
                {"id": subpost_7, "content": ""},
            ],
        }
        content = encode_multipart("BoUnDaRyStRiNg", data)
        response = self.client.put(
            f"/api/v1/newsfeed/{mainpost_id}/",
            data=content,
            content_type=content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # ?????? ?????????
        response = self.client.delete(
            f"/api/v1/newsfeed/{mainpost_id}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        response = self.client.get(
            f"/api/v1/newsfeed/{mainpost_id}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # subposts?????? ?????? remove??? ??? ??? content
        data = {
            "content": "?????? ????????? ?????????.",
            "subposts": [{"content": "????????? ???????????????."}, {"content": "????????? ???????????????."}],
            "file": [test_image, test_image],
        }

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        post_id = data["id"]
        subpost_1 = data["subposts"][0]["id"]
        subpost_2 = data["subposts"][1]["id"]

        data = {"content": "", "removed_subposts": [subpost_1, subpost_2]}
        response = self.client.put(
            f"/api/v1/newsfeed/{post_id}/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # ??? ?????? ????????? ??? ?????? ??????????
        data = {"content": "?????????", "removed_subposts": [subpost_1, subpost_2]}
        response = self.client.put(
            f"/api/v1/newsfeed/{post_id}/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ShareTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):

        cls.test_user = UserFactory.create(
            email="test0@test.com",
            password="password",
            first_name="test",
            last_name="user",
            birth="1997-02-03",
            gender="M",
            phone_number="01000000000",
        )

        cls.test_friend = UserFactory.create(
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

        cls.test_stranger = UserFactory.create(
            email="test2@test.com",
            password="password",
            first_name="test",
            last_name="stranger",
            birth="1997-02-03",
            gender="M",
            phone_number="01022222222",
        )

        cls.test_image = SimpleUploadedFile(
            name="testimage2.jpg",
            content=open(os.path.join(BASE_DIR, "testimage2.jpg"), "rb").read(),
            content_type="image/jpeg",
        )
        cls.user_token = "JWT " + jwt_token_of(cls.test_user)
        cls.friend_token = "JWT " + jwt_token_of(cls.test_friend)
        cls.stranger_token = "JWT " + jwt_token_of(cls.test_stranger)
        cls.content_type = "multipart/form-data; boundary=BoUnDaRyStRiNg"

    def test_post_share(self):

        # ????????? ????????????
        data = {
            "content": "????????? ??????????????????.",
            "subposts": [{"content": ""}],
            "file": self.test_image,
        }

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        sharing_post_id = data["id"]
        subpost_id = data["subposts"][0]["id"]
        sharing_post = self.test_user.posts.get(id=sharing_post_id)

        data = {"content": "???????????? ??????????????????.", "shared_post": sharing_post_id}

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(sharing_post_id, data["shared_post"]["id"])
        self.assertEqual("????????? ??????????????????.", data["shared_post"]["content"])

        # ????????? ?????? ???, ????????? ???????????? ????????? ?????? ??????
        response = self.client.get(
            f"/api/v1/newsfeed/{sharing_post_id}/",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["shared_counts"], 1)

        # ?????? ??????????????? ?????? ?????????????????? ?????? ??????
        response = self.client.get(
            "/api/v1/newsfeed/",
            HTTP_AUTHORIZATION=self.friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "???????????? ??????????????????.")
        self.assertEqual(data["results"][0]["shared_post"]["id"], sharing_post_id)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.stranger_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "???????????? ??????????????????.")
        self.assertEqual(data["results"][0]["shared_post"]["id"], sharing_post_id)

        # ??? ????????? ??? ????????? ????????? ???????????? ?????? ????????? ?????? ??????
        data = {
            "content": "",
            "subposts": [{"id": subpost_id, "content": ""}],
            "scope": 2,
        }

        content = encode_multipart("BoUnDaRyStRiNg", data)
        content_type = "multipart/form-data; boundary=BoUnDaRyStRiNg"

        response = self.client.put(
            f"/api/v1/newsfeed/{sharing_post_id}/",
            data=content,
            content_type=content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.stranger_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "???????????? ??????????????????.")
        self.assertEqual(data["results"][0]["shared_post"], None)

        data = {
            "content": "",
            "subposts": [{"id": subpost_id, "content": ""}],
            "scope": 1,
        }

        content = encode_multipart("BoUnDaRyStRiNg", data)

        response = self.client.put(
            f"/api/v1/newsfeed/{sharing_post_id}/",
            data=content,
            content_type=content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "???????????? ??????????????????.")
        self.assertEqual(data["results"][0]["shared_post"], None)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "???????????? ??????????????????.")
        self.assertEqual(data["results"][0]["shared_post"]["id"], sharing_post_id)

        # ????????? ???????????? ????????? ??????
        sharing_post.delete()
        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "???????????? ??????????????????.")
        self.assertEqual(data["results"][0]["shared_post"], None)

        # subpost??? ????????? ????????????
        test_image = SimpleUploadedFile(
            name="testimage2.jpg",
            content=open(os.path.join(BASE_DIR, "testimage2.jpg"), "rb").read(),
            content_type="image/jpeg",
        )
        data = {
            "content": "?????? ??????????????????.",
            "subposts": [{"content": "????????? ??????????????????."}],
            "file": [test_image],
        }

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        sharing_post_id = response.json()["subposts"][0]["id"]
        data = {"content": "", "shared_post": sharing_post_id}

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(sharing_post_id, data["shared_post"]["id"])
        self.assertEqual("????????? ??????????????????.", data["shared_post"]["content"])
        self.assertIn("testimage2.jpg", data["shared_post"]["file"])

        # ????????? ?????? ???, ????????? ???????????? ????????? ?????? ??????
        response = self.client.get(
            f"/api/v1/newsfeed/{sharing_post_id}/",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["shared_counts"], 1)


class ScopeTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):

        cls.test_user = UserFactory.create(
            email="test0@test.com",
            password="password",
            first_name="test",
            last_name="user",
            birth="1997-02-03",
            gender="M",
            phone_number="01000000000",
        )

        cls.test_friend = UserFactory.create(
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

        cls.test_stranger = UserFactory.create(
            email="test2@test.com",
            password="password",
            first_name="test",
            last_name="stranger",
            birth="1997-02-03",
            gender="M",
            phone_number="01022222222",
        )

        cls.test_image = SimpleUploadedFile(
            name="testimage2.jpg",
            content=open(os.path.join(BASE_DIR, "testimage2.jpg"), "rb").read(),
            content_type="image/jpeg",
        )
        cls.user_token = "JWT " + jwt_token_of(cls.test_user)
        cls.friend_token = "JWT " + jwt_token_of(cls.test_friend)
        cls.stranger_token = "JWT " + jwt_token_of(cls.test_stranger)
        cls.content_type = "multipart/form-data; boundary=BoUnDaRyStRiNg"

    def test_scope_list(self):

        # ???????????? ?????????
        data = {
            "content": "?????? ?????? ??????????????????.",
        }

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/v1/newsfeed/",
            HTTP_AUTHORIZATION=self.friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "?????? ?????? ??????????????????.")
        self.assertEqual(data["results"][0]["scope"], 3)

        response = self.client.get(
            "/api/v1/newsfeed/",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "?????? ?????? ??????????????????.")
        self.assertEqual(data["results"][0]["scope"], 3)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.stranger_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "?????? ?????? ??????????????????.")
        self.assertEqual(data["results"][0]["scope"], 3)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "?????? ?????? ??????????????????.")
        self.assertEqual(data["results"][0]["scope"], 3)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "?????? ?????? ??????????????????.")
        self.assertEqual(data["results"][0]["scope"], 3)

        # ???????????? ?????????
        data = {"content": "?????? ?????? ??????????????????.", "scope": 2}

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/v1/newsfeed/",
            HTTP_AUTHORIZATION=self.friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "?????? ?????? ??????????????????.")
        self.assertEqual(data["results"][0]["scope"], 2)

        response = self.client.get(
            "/api/v1/newsfeed/",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "?????? ?????? ??????????????????.")
        self.assertEqual(data["results"][0]["scope"], 2)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.stranger_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertNotEqual(data["results"][0]["content"], "?????? ?????? ??????????????????.")
        self.assertNotEqual(data["results"][0]["scope"], 2)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "?????? ?????? ??????????????????.")
        self.assertEqual(data["results"][0]["scope"], 2)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "?????? ?????? ??????????????????.")
        self.assertEqual(data["results"][0]["scope"], 2)

        # ???????????? ?????????
        data = {"content": "?????? ?????? ??????????????????.", "scope": 1}

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/v1/newsfeed/",
            HTTP_AUTHORIZATION=self.friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertNotEqual(data["results"][0]["content"], "?????? ?????? ??????????????????.")
        self.assertNotEqual(data["results"][0]["scope"], 1)

        response = self.client.get(
            "/api/v1/newsfeed/",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "?????? ?????? ??????????????????.")
        self.assertEqual(data["results"][0]["scope"], 1)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.stranger_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertNotEqual(data["results"][0]["content"], "?????? ?????? ??????????????????.")
        self.assertNotEqual(data["results"][0]["scope"], 1)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertNotEqual(data["results"][0]["content"], "?????? ?????? ??????????????????.")
        self.assertNotEqual(data["results"][0]["scope"], 1)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "?????? ?????? ??????????????????.")
        self.assertEqual(data["results"][0]["scope"], 1)

    def test_scope_create(self):

        # ????????? ?????? ??? ????????? ?????? ??????, scope??? subposts??? ???????????? ?????? ?????????

        data = {
            "content": "?????? ?????? ????????? ?????????",
            "subposts": [{"content": "????????? ???????????????."}, {"content": "????????? ???????????????."}],
            "file": [self.test_image, self.test_image],
            "scope": 2,
        }

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertEqual(data["scope"], 2)
        self.assertEqual(data["subposts"][0]["scope"], 2)
        self.assertEqual(data["subposts"][1]["scope"], 2)

        # ????????? ?????? 3 (????????????)
        data = {
            "content": "?????? ?????? ????????? ?????????",
            "subposts": [{"content": "????????? ???????????????."}, {"content": "????????? ???????????????."}],
            "file": [self.test_image, self.test_image],
        }

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertEqual(data["scope"], 3)
        self.assertEqual(data["subposts"][0]["scope"], 3)
        self.assertEqual(data["subposts"][1]["scope"], 3)

        # scope??? 1, 2, 3??? ?????? ?????? ?????? ?????? ??? ??????
        data = {
            "content": "?????? ?????? ????????? ?????????",
            "subposts": [{"content": "????????? ???????????????."}, {"content": "????????? ???????????????."}],
            "file": [self.test_image, self.test_image],
            "scope": 4,
        }
        response = self.client.post(
            "/api/v1/newsfeed/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data = {
            "content": "?????? ?????? ????????? ?????????",
            "subposts": [{"content": "????????? ???????????????."}, {"content": "????????? ???????????????."}],
            "file": [self.test_image, self.test_image],
            "scope": 0,
        }
        response = self.client.post(
            "/api/v1/newsfeed/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data = {
            "content": "?????? ?????? ????????? ?????????",
            "subposts": [{"content": "????????? ???????????????."}, {"content": "????????? ???????????????."}],
            "file": [self.test_image, self.test_image],
            "scope": "????????????",
        }
        response = self.client.post(
            "/api/v1/newsfeed/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_scope_update(self):

        data = {
            "content": "?????? ?????? ????????? ?????????",
            "subposts": [{"content": "????????? ???????????????."}, {"content": "????????? ???????????????."}],
            "file": [self.test_image, self.test_image],
            "scope": 2,
        }

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        mainpost_id = data["id"]
        subpost_1 = data["subposts"][0]["id"]
        subpost_2 = data["subposts"][1]["id"]

        data = {
            "content": "?????? ?????? ??????????????????.",
            "subposts": [
                {"id": subpost_1, "content": "????????? ???????????????. (?????????)"},
                {"id": subpost_2, "content": "????????? ???????????????. (?????????)"},
            ],
            "scope": 3,
        }

        content = encode_multipart("BoUnDaRyStRiNg", data)
        content_type = "multipart/form-data; boundary=BoUnDaRyStRiNg"

        response = self.client.put(
            f"/api/v1/newsfeed/{mainpost_id}/",
            data=content,
            content_type=content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["content"], "?????? ?????? ??????????????????.")
        self.assertEqual(data["scope"], 3)
        self.assertEqual(data["subposts"][0]["scope"], 3)
        self.assertEqual(data["subposts"][1]["scope"], 3)

        # scope??? 1, 2, 3??? ?????? ?????? ?????? ?????? ??? ??????
        data = {
            "content": "?????? ?????? ??????????????????.",
            "scope": "?????? ??????",
        }

        content = encode_multipart("BoUnDaRyStRiNg", data)

        response = self.client.put(
            f"/api/v1/newsfeed/{mainpost_id}/",
            data=content,
            content_type=content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data = {
            "content": "?????? ?????? ??????????????????.",
            "scope": 4,
        }

        content = encode_multipart("BoUnDaRyStRiNg", data)

        response = self.client.put(
            f"/api/v1/newsfeed/{mainpost_id}/",
            data=content,
            content_type=content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data = {
            "content": "?????? ?????? ??????????????????.",
            "scope": 0,
        }

        content = encode_multipart("BoUnDaRyStRiNg", data)

        response = self.client.put(
            f"/api/v1/newsfeed/{mainpost_id}/",
            data=content,
            content_type=content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # ????????? ????????? ?????? ????????? ????????? ?????????, ??????????????? ??? ?????? ????????? ?????? 404
        # ????????? ????????? ?????? ?????? ????????? ?????????, ??????????????? ??? ?????? ????????? ??????
        response = self.client.get(
            f"/api/v1/newsfeed/{mainpost_id}/",
            HTTP_AUTHORIZATION=self.stranger_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(
            f"/api/v1/newsfeed/{mainpost_id}/comment/",
            data=encode_multipart("BoUnDaRyStRiNg", {"content": "???????????? ???????????? ???????????????."}),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.stranger_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        comment_id = data["id"]

        data = {
            "content": "?????? ?????? ??????????????????.",
            "scope": 2,
        }

        content = encode_multipart("BoUnDaRyStRiNg", data)

        response = self.client.put(
            f"/api/v1/newsfeed/{mainpost_id}/",
            data=content,
            content_type=content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(
            f"/api/v1/newsfeed/{mainpost_id}/",
            HTTP_AUTHORIZATION=self.stranger_token,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        response = self.client.get(
            f"/api/v1/newsfeed/{mainpost_id}/{comment_id}/",
            HTTP_AUTHORIZATION=self.stranger_token,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        response = self.client.get(
            f"/api/v1/newsfeed/{mainpost_id}/",
            HTTP_AUTHORIZATION=self.friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(
            f"/api/v1/newsfeed/{mainpost_id}/{comment_id}/",
            HTTP_AUTHORIZATION=self.friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = {
            "content": "?????? ?????? ??????????????????.",
            "scope": 1,
        }

        content = encode_multipart("BoUnDaRyStRiNg", data)

        response = self.client.put(
            f"/api/v1/newsfeed/{mainpost_id}/",
            data=content,
            content_type=content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(
            f"/api/v1/newsfeed/{mainpost_id}/",
            HTTP_AUTHORIZATION=self.friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        response = self.client.get(
            f"/api/v1/newsfeed/{mainpost_id}/{comment_id}/",
            HTTP_AUTHORIZATION=self.friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class LikeTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.users = UserFactory.create_batch(10)

        cls.test_user = UserFactory.create(
            email="test0@test.com",
            password="password",
            first_name="test",
            last_name="user",
            birth="1997-02-03",
            gender="M",
            phone_number="01000000000",
        )

        cls.test_friend = UserFactory.create(
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

        cls.test_stranger = UserFactory.create(
            email="test2@test.com",
            password="password",
            first_name="test",
            last_name="stranger",
            birth="1997-02-03",
            gender="M",
            phone_number="01022222222",
        )

        PostFactory.create(author=cls.test_user, content="?????? ????????? ??????????????????.", likes=0)

        PostFactory.create(author=cls.test_friend, content="????????? ????????? ??????????????????.", likes=0)

        PostFactory.create(
            author=cls.test_stranger, content="????????? ????????? ????????? ??????????????????.", likes=0
        )

        for user in cls.users:
            cls.test_friend.friends.add(user)
        cls.test_friend.save()
        cls.content_type = "multipart/form-data; boundary=BoUnDaRyStRiNg"

    def test_like_and_unlike(self):  # ??????????????? ????????????
        user = self.test_user
        post = self.test_friend.posts.last()
        user_token = "JWT " + jwt_token_of(user)
        response = self.client.put(
            "/api/v1/newsfeed/" + str(post.id) + "/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["likes"], 1)

        response = self.client.put(
            "/api/v1/newsfeed/" + str(post.id) + "/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["likes"], 0)

    def test_unauthorized(self):
        post = self.test_friend.posts.last()
        response = self.client.put(
            "/api/v1/newsfeed/" + str(post.id) + "/like/",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # def test_like_not_friend(self):  # ?????? ????????? ????????? ?????????
    #     user = self.test_user
    #     post = self.test_stranger.posts.last()
    #     user_token = "JWT " + jwt_token_of(user)
    #     response = self.client.put(
    #         "/api/v1/newsfeed/" + str(post.id) + "/like/",
    #         content_type="application/json",
    #         HTTP_AUTHORIZATION=user_token,
    #     )
    #     self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    #     post.refresh_from_db()

    def test_like_or_dislike_myself(self):  # ?????? ?????? / ?????????
        user = self.test_friend
        post = self.test_friend.posts.last()
        user_token = "JWT " + jwt_token_of(user)
        response = self.client.put(
            "/api/v1/newsfeed/" + str(post.id) + "/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["likes"], 1)

        response = self.client.put(
            "/api/v1/newsfeed/" + str(post.id) + "/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["likes"], 0)

    def test_get_likes(self):
        post = self.test_friend.posts.last()
        for user in self.users:
            user_token = "JWT " + jwt_token_of(user)
            response = self.client.put(
                "/api/v1/newsfeed/" + str(post.id) + "/like/",
                content_type="application/json",
                HTTP_AUTHORIZATION=user_token,
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        post.refresh_from_db()
        self.assertEqual(post.likes, 10)
        user = self.test_user
        user_token = "JWT " + jwt_token_of(user)
        response = self.client.get(
            "/api/v1/newsfeed/" + str(post.id) + "/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["likes"], 10)
        self.assertEqual(len(data["likeusers"]), 10)


class CommentTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):

        cls.test_user = UserFactory.create(
            email="test0@test.com",
            password="password",
            first_name="test",
            last_name="user",
            birth="1997-02-03",
            gender="M",
            phone_number="01000000000",
        )

        cls.test_friend = UserFactory.create(
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

        cls.test_stranger = UserFactory.create(
            email="test2@test.com",
            password="password",
            first_name="test",
            last_name="stranger",
            birth="1997-02-03",
            gender="M",
            phone_number="01022222222",
        )

        cls.my_post = PostFactory.create(
            author=cls.test_user, content="?????? ????????? ??????????????????.", likes=10
        )

        cls.friend_post = PostFactory.create(
            author=cls.test_friend, content="????????? ????????? ??????????????????.", likes=20
        )

        cls.stranger_post = PostFactory.create(
            author=cls.test_stranger, content="????????? ????????? ????????? ??????????????????.", likes=30
        )

        CommentFactory.create_batch(
            35, author=cls.test_friend, post=cls.my_post, depth=0
        )
        cls.depth_zero = CommentFactory.create(
            author=cls.test_friend, post=cls.my_post, depth=0, content="depth 0"
        )
        cls.depth_one = CommentFactory.create(
            author=cls.test_friend,
            post=cls.my_post,
            depth=1,
            content="depth 1",
            parent=cls.depth_zero,
        )
        cls.depth_one.likeusers.add(cls.test_user)
        cls.depth_one.save()
        CommentFactory.create_batch(
            5, author=cls.test_friend, post=cls.my_post, depth=1, parent=cls.depth_zero
        )
        cls.depth_two = CommentFactory.create(
            author=cls.test_friend,
            post=cls.my_post,
            depth=2,
            content="depth 2",
            parent=cls.depth_one,
        )
        CommentFactory.create_batch(
            5, author=cls.test_friend, post=cls.my_post, depth=2, parent=cls.depth_one
        )
        cls.content_type = "multipart/form-data; boundary=BoUnDaRyStRiNg"

    def test_comment_list(self):

        # test_user??? ??????
        user_token = "JWT " + jwt_token_of(self.test_user)

        response = self.client.get(
            f"/api/v1/newsfeed/{self.my_post.id}/comment/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # ????????? ??????????????? ?????? ????????? (21, ..., 41), (1, ..., 20)??? ?????? ?????????????????????
        # ??? ?????? ??????????????? ?????? ?????????????????? ?????? (?????? ????????? ??? ??????)
        self.assertEqual(data["results"][-1]["content"], "depth 0")
        self.assertEqual(data["results"][-1]["children"][0]["content"], "depth 1")
        self.assertTrue(data["results"][-1]["children"][0]["is_liked"])
        self.assertEqual(
            data["results"][-1]["children"][0]["children"][0]["content"], "depth 2"
        )

        # ???????????? ?????? ??????
        self.assertEqual(
            data["results"][-1]["children"][0]["parent"], data["results"][-1]["id"]
        )

        # child comment ?????? ??????
        self.assertEqual(data["results"][-1]["children_count"], 6)
        self.assertEqual(len(data["results"][-1]["children"]), 6)

        # ?????????????????? ??????
        self.assertEqual(len(data["results"]), 20)
        next_page = data["next"]
        response = self.client.get(
            next_page,
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 16)

    def test_comment_create(self):

        user_token = "JWT " + jwt_token_of(self.test_user)
        fake = Faker("ko_KR")
        content = fake.text(max_nb_chars=100)

        data = {
            "content": content,
        }

        response = self.client.post(
            f"/api/v1/newsfeed/{self.friend_post.id}/comment/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertEqual(content, data["content"])
        self.assertEqual(self.test_user.id, data["author"]["id"])

        # ????????? ????????? ????????? ??????
        test_image = SimpleUploadedFile(
            name="testimage.jpg",
            content=open(os.path.join(BASE_DIR, "testimage.jpg"), "rb").read(),
            content_type="image/jpeg",
        )

        data = {"content": content, "file": test_image}

        response = self.client.post(
            f"/api/v1/newsfeed/{self.friend_post.id}/comment/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=user_token,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertEqual(content, data["content"])
        self.assertEqual(self.test_user.id, data["author"]["id"])
        self.assertIn("testimage.jpg", data["file"])

        # Content ????????? ?????? ?????? ??????
        data = {}
        response = self.client.post(
            f"/api/v1/newsfeed/{self.my_post.id}/comment/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()

        # Parent??? ???????????? ?????? ?????? ??????
        data = {
            "content": content,
            "parent": -1,
        }
        response = self.client.post(
            f"/api/v1/newsfeed/{self.my_post.id}/comment/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # ????????? ?????? ????????? ???????????? ?????? ??????
        data = {
            "content": content,
        }
        response = self.client.post(
            f"/api/v1/newsfeed/{self.stranger_post.id}/comment/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # depth??? 2??? ?????? (????????????)??? parent?????? ????????? ?????? ??????
        data = {"content": content, "parent": self.depth_two.id}
        response = self.client.post(
            f"/api/v1/newsfeed/{self.my_post.id}/comment/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_comment_like(self):
        user_token = "JWT " + jwt_token_of(self.test_user)

        response = self.client.put(
            f"/api/v1/newsfeed/{self.my_post.id}/{self.depth_zero.id}/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # PUT, ????????? ??????????????? ??????
        self.assertEqual(data["likes"], 1)

        response = self.client.get(
            f"/api/v1/newsfeed/{self.my_post.id}/{self.depth_zero.id}/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # GET, likeusers ??????
        self.assertEqual(data["likes"], 1)
        self.assertEqual(data["likeusers"][0]["id"], self.test_user.id)

        response = self.client.put(
            f"/api/v1/newsfeed/{self.my_post.id}/{self.depth_zero.id}/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # DELETE, ????????? ?????? ??????????????? ??????
        self.assertEqual(data["likes"], 0)
        self.assertEqual(self.depth_zero.likes, 0)

    def test_comment_edit(self):
        friend_token = "JWT " + jwt_token_of(self.test_friend)

        data = {"content": "edited"}

        response = self.client.put(
            f"/api/v1/newsfeed/{self.my_post.id}/{self.depth_zero.id}/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["content"], "edited")

        # content??? ???????????? ??????

        empty_data = {"content": ""}

        response = self.client.put(
            f"/api/v1/newsfeed/{self.my_post.id}/{self.depth_zero.id}/",
            data=encode_multipart("BoUnDaRyStRiNg", empty_data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # ????????? ????????? ?????? ??????
        response = self.client.put(
            f"/api/v1/newsfeed/{self.my_post.id}/{self.depth_zero.id}/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION="JWT " + jwt_token_of(self.test_user),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # ???????????? ?????? ????????? ??????
        response = self.client.put(
            f"/api/v1/newsfeed/{self.my_post.id}/10000000/",
            data=data,
            content_type="application/json",
            HTTP_AUTHORIZATION=friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_comment_delete(self):
        friend_token = "JWT " + jwt_token_of(self.test_friend)

        # ????????? ????????? ?????? ??????
        response = self.client.delete(
            f"/api/v1/newsfeed/{self.my_post.id}/{self.depth_zero.id}/",
            HTTP_AUTHORIZATION="JWT " + jwt_token_of(self.test_user),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # ???????????? ?????? ????????? ??????
        response = self.client.delete(
            f"/api/v1/newsfeed/{self.my_post.id}/10000000/",
            HTTP_AUTHORIZATION=friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # ?????? ??????
        response = self.client.delete(
            f"/api/v1/newsfeed/{self.my_post.id}/{self.depth_zero.id}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=friend_token,
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
