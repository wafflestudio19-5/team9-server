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


class NoticeTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.test_user = UserFactory.create(
            email="notice@test.com",
            password="password",
            first_name="??????",
            last_name="???",
            birth="1997-02-03",
            gender="M",
            phone_number="01000000000",
        )
        cls.test_friends = UserFactory.create_batch(10)
        cls.user_token = "JWT " + jwt_token_of(cls.test_user)
        cls.friends_token = []
        for friend in cls.test_friends:
            cls.test_user.friends.add(friend)
            cls.friends_token.append("JWT " + jwt_token_of(friend))

        cls.test_post = PostFactory.create(
            author=cls.test_user, content="?????? ????????? ??????????????????.", likes=0
        )
        cls.test_comment = CommentFactory.create(
            author=cls.test_user, post=cls.test_post, depth=0, content="?????? ????????? ???????????????."
        )

        cls.content_type = "multipart/form-data; boundary=BoUnDaRyStRiNg"

    def test_notice(self):

        tmp_comment_list = []

        # ?????? 1??? ?????? ??????
        for i, friend_token in enumerate(self.friends_token):
            data = {"content": f"?????? ????????? ???????????????...{i}", "parent": self.test_comment.id}
            content = encode_multipart("BoUnDaRyStRiNg", data)
            response = self.client.post(
                f"/api/v1/newsfeed/{self.test_post.id}/comment/",
                data=content,
                HTTP_AUTHORIZATION=friend_token,
                content_type=self.content_type,
            )
            tmp_comment_list.append(response.json()["id"])
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "CommentComment")
        self.assertEqual(data["results"][0]["count"], 9)
        self.assertEqual(data["results"][0]["post"]["id"], self.test_post.id)
        self.assertEqual(
            data["results"][0]["parent_comment"]["id"], self.test_comment.id
        )
        self.assertEqual(len(data["results"][0]["senders"]), 9)
        self.assertEqual(
            data["results"][0]["sender_preview"]["id"], self.test_friends[-1].id
        )
        self.assertEqual(
            data["results"][0]["url"],
            f"api/v1/newsfeed/{self.test_post.id}/{self.test_comment.id}/",
        )
        self.assertEqual(data["results"][0]["is_checked"], False)
        self.assertEqual(
            data["results"][0]["comment_preview"]["content"], "?????? ????????? ???????????????...9"
        )

        tmp_comment_id = data["results"][0]["comment_preview"]["id"]

        # ?????? 2??? ?????? ??????
        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart(
                "BoUnDaRyStRiNg",
                {"content": "?????? ????????? ????????? ???????????????.", "parent": tmp_comment_id},
            ),
            HTTP_AUTHORIZATION=self.user_token,
            content_type=self.content_type,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[-1],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "CommentComment")
        self.assertEqual(data["results"][0]["count"], 0)
        self.assertEqual(data["results"][0]["post"]["id"], self.test_post.id)
        self.assertEqual(data["results"][0]["parent_comment"]["id"], tmp_comment_id)
        self.assertEqual(len(data["results"][0]["senders"]), 0)
        self.assertEqual(data["results"][0]["sender_preview"]["id"], self.test_user.id)
        self.assertEqual(
            data["results"][0]["url"],
            f"api/v1/newsfeed/{self.test_post.id}/{tmp_comment_id}/",
        )
        self.assertEqual(
            data["results"][0]["comment_preview"]["content"], "?????? ????????? ????????? ???????????????."
        )
        tmp_comment_id = data["results"][0]["comment_preview"]["id"]

        # ?????? 2??? ?????? ?????? --> ?????? ??????
        response = self.client.delete(
            f"/api/v1/newsfeed/{self.test_post.id}/{tmp_comment_id}/",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[-1],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 0)

        # ?????? 1??? ????????? ?????? --> ?????? ??????
        for i, friend_token in enumerate(self.friends_token):
            tmp_comment_id = tmp_comment_list[i]
            response = self.client.delete(
                f"/api/v1/newsfeed/{self.test_post.id}/{tmp_comment_id}/",
                HTTP_AUTHORIZATION=friend_token,
            )
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(len(data["results"]), 0)

        # ????????????
        for i, friend_token in enumerate(self.friends_token):
            response = self.client.post(
                f"/api/v1/newsfeed/{self.test_post.id}/comment/",
                data=encode_multipart(
                    "BoUnDaRyStRiNg", {"content": f"?????? ????????? ???????????????...{i}"}
                ),
                HTTP_AUTHORIZATION=friend_token,
                content_type=self.content_type,
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        notice_id = data["results"][0]["id"]

        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["content"], "PostComment")
        self.assertEqual(data["results"][0]["count"], 9)
        self.assertEqual(data["results"][0]["post"]["id"], self.test_post.id)
        self.assertEqual(len(data["results"][0]["senders"]), 9)
        self.assertEqual(
            data["results"][0]["sender_preview"]["id"], self.test_friends[-1].id
        )
        self.assertEqual(
            data["results"][0]["url"], f"api/v1/newsfeed/{self.test_post.id}/"
        )
        self.assertEqual(data["results"][0]["is_checked"], False)
        self.assertEqual(
            data["results"][0]["comment_preview"]["content"], "?????? ????????? ???????????????...9"
        )

        # ????????? ??? ????????? ??? ?????? ????????? ?????? ??????
        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart(
                "BoUnDaRyStRiNg",
                {"content": "?????? ????????? ??? ?????????, ??? ????????? ????????? count??? ???????????? ????????????."},
            ),
            HTTP_AUTHORIZATION=self.friends_token[0],
            content_type=self.content_type,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            f"/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["count"], 9)
        self.assertEqual(len(data["results"][0]["senders"]), 9)
        self.assertEqual(
            data["results"][0]["sender_preview"]["id"], self.test_friends[0].id
        )
        self.assertEqual(
            data["results"][0]["comment_preview"]["content"],
            "?????? ????????? ??? ?????????, ??? ????????? ????????? count??? ???????????? ????????????.",
        )
        recent_comment_id = data["results"][0]["comment_preview"]["id"]

        # ?????? is_checked
        response = self.client.get(
            f"/api/v1/notices/{notice_id}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["is_checked"], True)

        # ???????????? ?????? X
        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart(
                "BoUnDaRyStRiNg", {"content": "????????? ??? ????????? ????????? ?????? ????????????."}
            ),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            f"/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["count"], 9)
        self.assertEqual(len(data["results"][0]["senders"]), 9)

        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart(
                "BoUnDaRyStRiNg",
                {"content": "????????? ??? ????????? ????????? ?????? ????????????.", "parent": recent_comment_id},
            ),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            f"/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 0)

        # ????????? 2??? ?????? ??? ?????????, ????????? ???????????? count??? ????????? !
        response = self.client.delete(
            f"/api/v1/newsfeed/{self.test_post.id}/{recent_comment_id}/",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        response = self.client.get(
            f"/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["count"], 9)
        self.assertEqual(len(data["results"][0]["senders"]), 9)
        self.assertEqual(
            data["results"][0]["sender_preview"]["id"], self.test_friends[-1].id
        )
        self.assertEqual(
            data["results"][0]["comment_preview"]["content"], "?????? ????????? ???????????????...9"
        )
        recent_comment_id = data["results"][0]["comment_preview"]["id"]

        # ?????? ?????????
        for friend_token in self.friends_token:
            response = self.client.put(
                f"/api/v1/newsfeed/{self.test_post.id}/{self.test_comment.id}/like/",
                content_type="application/json",
                HTTP_AUTHORIZATION=friend_token,
            )
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 2)
        self.assertEqual(data["results"][0]["content"], "CommentLike")
        self.assertEqual(data["results"][0]["count"], 9)
        self.assertEqual(data["results"][0]["post"]["id"], self.test_post.id)
        self.assertEqual(
            data["results"][0]["parent_comment"]["id"], self.test_comment.id
        )
        self.assertEqual(len(data["results"][0]["senders"]), 9)
        self.assertEqual(
            data["results"][0]["sender_preview"]["id"], self.test_friends[-1].id
        )
        self.assertEqual(
            data["results"][0]["url"],
            f"api/v1/newsfeed/{self.test_post.id}/",
        )
        self.assertEqual(data["results"][0]["is_checked"], False)
        self.assertEqual(
            data["results"][0]["parent_comment"]["content"], "?????? ????????? ???????????????."
        )

        # ????????? ?????????
        for friend_token in self.friends_token:
            response = self.client.put(
                f"/api/v1/newsfeed/{self.test_post.id}/like/",
                content_type="application/json",
                HTTP_AUTHORIZATION=friend_token,
            )
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 3)
        notice_id_2 = data["results"][0]["id"]
        self.assertEqual(data["results"][0]["content"], "PostLike")
        self.assertEqual(data["results"][0]["count"], 9)
        self.assertEqual(data["results"][0]["post"]["id"], self.test_post.id)
        self.assertEqual(len(data["results"][0]["senders"]), 9)
        self.assertEqual(
            data["results"][0]["sender_preview"]["id"], self.test_friends[-1].id
        )
        self.assertEqual(
            data["results"][0]["url"],
            f"api/v1/newsfeed/{self.test_post.id}/",
        )
        self.assertEqual(data["results"][0]["is_checked"], False)

        # ?????? ??????
        response = self.client.put(
            f"/api/v1/newsfeed/{self.test_post.id}/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["count"], 8)
        self.assertEqual(len(data["results"][0]["senders"]), 8)
        self.assertEqual(
            data["results"][0]["sender_preview"]["id"], self.test_friends[-1].id
        )

        response = self.client.put(
            f"/api/v1/newsfeed/{self.test_post.id}/{self.test_comment.id}/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][1]["count"], 8)
        self.assertEqual(len(data["results"][1]["senders"]), 8)
        self.assertEqual(
            data["results"][1]["sender_preview"]["id"], self.test_friends[-1].id
        )

        response = self.client.delete(
            f"/api/v1/newsfeed/{self.test_post.id}/{recent_comment_id}/",
            HTTP_AUTHORIZATION=self.friends_token[9],
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][2]["count"], 8)
        self.assertEqual(len(data["results"][2]["senders"]), 8)
        self.assertEqual(
            data["results"][2]["comment_preview"]["content"], "?????? ????????? ???????????????...8"
        )
        self.assertEqual(
            data["results"][2]["sender_preview"]["id"], self.test_friends[-2].id
        )

        # ?????? ??????
        response = self.client.delete(
            f"/api/v1/notices/{notice_id}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 2)
        self.assertNotEqual(data["results"][-1]["id"], notice_id)

        # ?????? ?????? ????????? ?????? ????????? ?????? ????????? ?????? ??????
        for i, friend_token in enumerate(self.friends_token):
            response = self.client.post(
                f"/api/v1/newsfeed/{self.test_post.id}/comment/",
                data=encode_multipart(
                    "BoUnDaRyStRiNg", {"content": f"????????? ?????? ????????? ???????????????...{i}"}
                ),
                content_type=self.content_type,
                HTTP_AUTHORIZATION=friend_token,
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(len(data["results"]), 3)
        self.assertEqual(data["results"][0]["content"], "PostComment")
        self.assertEqual(data["results"][0]["count"], 9)
        self.assertEqual(data["results"][0]["post"]["id"], self.test_post.id)
        self.assertEqual(len(data["results"][0]["senders"]), 9)
        self.assertEqual(
            data["results"][0]["sender_preview"]["id"], self.test_friends[-1].id
        )
        self.assertEqual(
            data["results"][0]["url"], f"api/v1/newsfeed/{self.test_post.id}/"
        )
        self.assertEqual(data["results"][0]["is_checked"], False)
        self.assertEqual(
            data["results"][0]["comment_preview"]["content"], "????????? ?????? ????????? ???????????????...9"
        )

        # ????????? ?????? ????????? ?????? ????????? ????????? ?????? ?????? ??????
        response = self.client.delete(
            f"/api/v1/notices/{notice_id_2}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        for i in range(1, 10):
            response = self.client.put(
                f"/api/v1/newsfeed/{self.test_post.id}/like/",
                content_type="application/json",
                HTTP_AUTHORIZATION=self.friends_token[i],
            )
        for friend_token in self.friends_token:
            response = self.client.put(
                f"/api/v1/newsfeed/{self.test_post.id}/like/",
                content_type="application/json",
                HTTP_AUTHORIZATION=friend_token,
            )
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 3)
        self.assertEqual(data["results"][0]["content"], "PostLike")
        self.assertEqual(data["results"][0]["count"], 9)
        self.assertEqual(data["results"][0]["post"]["id"], self.test_post.id)
        self.assertEqual(len(data["results"][0]["senders"]), 9)
        self.assertEqual(
            data["results"][0]["sender_preview"]["id"], self.test_friends[-1].id
        )
        self.assertEqual(
            data["results"][0]["url"],
            f"api/v1/newsfeed/{self.test_post.id}/",
        )
        self.assertEqual(data["results"][0]["is_checked"], False)

        # ????????????
        stranger = UserFactory.create()
        stranger_token = "JWT " + jwt_token_of(stranger)

        response = self.client.post(
            f"/api/v1/friend/request/{self.test_user.id}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=stranger_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "FriendRequest")
        self.assertEqual(data["results"][0]["sender_preview"]["id"], stranger.id)
        self.assertEqual(len(data["results"][0]["senders"]), 0)

        # ????????????
        response = self.client.put(
            f"/api/v1/friend/request/{stranger.id}/",
            data={"sender": stranger.id},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["is_accepted"], True)
        self.assertEqual(data["results"][0]["is_checked"], True)
        self.assertEqual(data["results"][0]["sender_preview"]["id"], stranger.id)
        self.assertEqual(len(data["results"][0]["senders"]), 0)

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=stranger_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "FriendAccept")
        self.assertEqual(data["results"][0]["sender_preview"]["id"], self.test_user.id)
        self.assertEqual(len(data["results"][0]["senders"]), 0)

        # ?????? ?????? ???, ????????? ????????? ?????? ????????? ????????? ???, ???????????? ?????? ??????
        stranger2 = UserFactory.create()
        stranger2_token = "JWT " + jwt_token_of(stranger2)

        response = self.client.post(
            f"/api/v1/friend/request/{self.test_user.id}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=stranger2_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "FriendRequest")
        self.assertEqual(data["results"][0]["is_accepted"], False)
        self.assertEqual(data["results"][0]["sender_preview"]["id"], stranger2.id)
        self.assertEqual(len(data["results"][0]["senders"]), 0)

        response = self.client.delete(
            f"/api/v1/friend/request/{self.test_user.id}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=stranger2_token,
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertNotEqual(data["results"][0]["sender_preview"]["id"], stranger2.id)

        # ?????? ?????? ???, ?????? ?????? ????????? ?????? ?????? ????????? ????????? ??????
        response = self.client.post(
            f"/api/v1/friend/request/{self.test_user.id}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=stranger2_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "FriendRequest")
        self.assertEqual(data["results"][0]["sender_preview"]["id"], stranger2.id)
        self.assertEqual(len(data["results"][0]["senders"]), 0)

        response = self.client.delete(
            f"/api/v1/friend/request/{stranger2.id}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertNotEqual(data["results"][0]["sender_preview"]["id"], stranger2.id)

    def test_notice_on_off(self):

        # ????????? ???????????? ???????????? ?????? ?????? ??????
        response = self.client.put(
            f"/api/v1/newsfeed/{self.test_post.id}/notice/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["is_noticed"], False)

        # ?????? ??????, ?????? X
        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart("BoUnDaRyStRiNg", {"content": "????????? ???????????? ????????????."}),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        comment_id = data["id"]

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 0)

        # ????????? ?????????, ?????? X
        response = self.client.put(
            f"/api/v1/newsfeed/{self.test_post.id}/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 0)

        # ????????? ????????? ??????, ?????? ?????? X
        response = self.client.put(
            f"/api/v1/newsfeed/{self.test_post.id}/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )

        # ????????? ?????? ??????, ?????? ?????? X
        response = self.client.delete(
            f"/api/v1/newsfeed/{self.test_post.id}/{comment_id}/",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # ???????????? ?????? ?????? ??????
        response = self.client.put(
            f"/api/v1/newsfeed/{self.test_post.id}/notice/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["is_noticed"], True)

        # ?????? ??????, ?????? O
        test_image = SimpleUploadedFile(
            name="testimage2.jpg",
            content=open(os.path.join(BASE_DIR, "testimage2.jpg"), "rb").read(),
            content_type="image/jpeg",
        )

        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart(
                "BoUnDaRyStRiNg", {"content": "????????? ???????????????.", "file": test_image}
            ),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        comment_id = data["id"]

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["content"], "PostComment")
        self.assertEqual(data["results"][0]["count"], 0)
        self.assertEqual(data["results"][0]["post"]["id"], self.test_post.id)
        self.assertEqual(len(data["results"][0]["senders"]), 0)
        self.assertEqual(
            data["results"][0]["sender_preview"]["id"], self.test_friends[0].id
        )
        self.assertEqual(
            data["results"][0]["url"], f"api/v1/newsfeed/{self.test_post.id}/"
        )
        self.assertEqual(data["results"][0]["is_checked"], False)
        self.assertEqual(data["results"][0]["comment_preview"]["content"], "????????? ???????????????.")
        self.assertIn("photo", data["results"][0]["comment_preview"]["is_file"])

        # ????????? ?????????, ?????? O
        response = self.client.put(
            f"/api/v1/newsfeed/{self.test_post.id}/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 2)
        self.assertEqual(data["results"][0]["content"], "PostLike")
        self.assertEqual(data["results"][0]["count"], 0)
        self.assertEqual(data["results"][0]["post"]["id"], self.test_post.id)
        self.assertEqual(len(data["results"][0]["senders"]), 0)
        self.assertEqual(
            data["results"][0]["sender_preview"]["id"], self.test_friends[0].id
        )
        self.assertEqual(
            data["results"][0]["url"],
            f"api/v1/newsfeed/{self.test_post.id}/",
        )
        self.assertEqual(data["results"][0]["is_checked"], False)

        # ?????? ???????????? ???????????? ?????? ?????? ??????
        response = self.client.put(
            f"/api/v1/newsfeed/{self.test_post.id}/notice/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["is_noticed"], False)

        # ?????? ????????? ?????? ?????? X
        response = self.client.put(
            f"/api/v1/newsfeed/{self.test_post.id}/{comment_id}/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[1],
        )

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 0)

        # ?????? ??????, ?????? X
        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart(
                "BoUnDaRyStRiNg",
                {"content": f"????????? ???????????? ?????? ???????????????.", "parent": comment_id},
            ),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.friends_token[2],
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 0)

        # ?????? ???????????? ???????????? ?????? ?????? ??????
        response = self.client.put(
            f"/api/v1/newsfeed/{self.test_post.id}/notice/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["is_noticed"], True)

        # ?????? ?????????, ?????? O
        response = self.client.put(
            f"/api/v1/newsfeed/{self.test_post.id}/{comment_id}/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[1],
        )

        response = self.client.put(
            f"/api/v1/newsfeed/{self.test_post.id}/{comment_id}/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[1],
        )

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["content"], "CommentLike")
        self.assertEqual(data["results"][0]["count"], 0)
        self.assertEqual(data["results"][0]["post"]["id"], self.test_post.id)
        self.assertEqual(data["results"][0]["parent_comment"]["id"], comment_id)
        self.assertEqual(len(data["results"][0]["senders"]), 0)
        self.assertEqual(
            data["results"][0]["sender_preview"]["id"], self.test_friends[1].id
        )
        self.assertEqual(
            data["results"][0]["url"],
            f"api/v1/newsfeed/{self.test_post.id}/",
        )
        self.assertEqual(data["results"][0]["is_checked"], False)
        self.assertEqual(data["results"][0]["parent_comment"]["content"], "????????? ???????????????.")

        # ?????? ??????, ?????? O
        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart(
                "BoUnDaRyStRiNg", {"content": "????????? ???????????? ???????????????.", "parent": comment_id}
            ),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.friends_token[3],
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "CommentComment")
        self.assertEqual(data["results"][0]["count"], 0)
        self.assertEqual(data["results"][0]["post"]["id"], self.test_post.id)
        self.assertEqual(data["results"][0]["parent_comment"]["id"], comment_id)
        self.assertEqual(len(data["results"][0]["senders"]), 0)
        self.assertEqual(
            data["results"][0]["sender_preview"]["id"], self.test_friends[3].id
        )
        self.assertEqual(
            data["results"][0]["url"],
            f"api/v1/newsfeed/{self.test_post.id}/{comment_id}/",
        )
        self.assertEqual(data["results"][0]["is_checked"], False)
        self.assertEqual(
            data["results"][0]["comment_preview"]["content"], "????????? ???????????? ???????????????."
        )

        # subpost ????????? ?????? ?????????
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
        subpost_id = response.json()["subposts"][0]["id"]

        response = self.client.put(
            f"/api/v1/newsfeed/{subpost_id}/notice/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["is_noticed"], False)

        response = self.client.post(
            f"/api/v1/newsfeed/{subpost_id}/comment/",
            data=encode_multipart(
                "BoUnDaRyStRiNg", {"content": "subpost ????????? ???????????? ????????????."}
            ),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertNotEqual(data["results"][0]["content"], "PostComment")

        # subpost ????????? ?????? ??????
        response = self.client.put(
            f"/api/v1/newsfeed/{subpost_id}/notice/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["is_noticed"], True)

        response = self.client.post(
            f"/api/v1/newsfeed/{subpost_id}/comment/",
            data=encode_multipart("BoUnDaRyStRiNg", {"content": "subpost ????????? ???????????????."}),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.friends_token[1],
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "PostComment")
        self.assertEqual(data["results"][0]["count"], 0)
        self.assertEqual(data["results"][0]["post"]["id"], subpost_id)
        self.assertEqual(len(data["results"][0]["senders"]), 0)
        self.assertEqual(
            data["results"][0]["sender_preview"]["id"], self.test_friends[1].id
        )
        self.assertEqual(
            data["results"][0]["comment_preview"]["content"], "subpost ????????? ???????????????."
        )

    def test_tag_notice(self):

        # Mainpost?????? ????????? ????????? ?????? ??????
        friend_1 = self.test_friends[0]
        friend_2 = self.test_friends[1]
        data = {
            "content": f"@{friend_1.username}, @{friend_2.username}, @{self.test_user.username} ?????? ?????? ??????????????????.",
            "tagged_users": [friend_1.id, friend_2.id, self.test_user.id],
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

        # ????????? ????????? ?????? X
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 0)

        # ???????????? ?????? O
        for i in range(2):
            response = self.client.get(
                "/api/v1/notices/",
                content_type="application/json",
                HTTP_AUTHORIZATION=self.friends_token[i],
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()
            self.assertEqual(data["results"][0]["content"], "PostTag")
            self.assertEqual(
                data["results"][0]["sender_preview"]["id"], self.test_user.id
            )
            self.assertEqual(data["results"][0]["count"], 0)

        # Mainpost ????????? ?????? ??????
        response = self.client.delete(
            f"/api/v1/newsfeed/{mainpost_id}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # ????????? ?????? ??????
        for i in range(2):
            response = self.client.get(
                "/api/v1/notices/",
                content_type="application/json",
                HTTP_AUTHORIZATION=self.friends_token[i],
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()
            self.assertEqual(len(data["results"]), 0)

        # Subpost?????? ?????? ??????
        test_image = SimpleUploadedFile(
            name="testimage2.jpg",
            content=open(os.path.join(BASE_DIR, "testimage2.jpg"), "rb").read(),
            content_type="image/jpeg",
        )

        friend_3 = self.test_friends[2]
        friend_4 = self.test_friends[3]
        data = {
            "content": "",
            "subposts": [
                {
                    "content": f"@{friend_1.username}, @{friend_2.username}",
                    "tagged_users": [friend_1.id, friend_2.id],
                },
                {"content": f"@{friend_3.username}", "tagged_users": [friend_3.id]},
            ],
            "file": [test_image, test_image],
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
        subpost_id = data["subposts"][0]["id"]
        subpost2_id = data["subposts"][1]["id"]

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["post"]["id"], subpost_id)
        self.assertEqual(data["results"][0]["content"], "PostTag")
        self.assertEqual(data["results"][0]["sender_preview"]["id"], self.test_user.id)
        self.assertEqual(data["results"][0]["count"], 0)

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[1],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["post"]["id"], subpost_id)
        self.assertEqual(data["results"][0]["content"], "PostTag")
        self.assertEqual(data["results"][0]["sender_preview"]["id"], self.test_user.id)
        self.assertEqual(data["results"][0]["count"], 0)

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[2],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["post"]["id"], subpost2_id)
        self.assertEqual(data["results"][0]["content"], "PostTag")
        self.assertEqual(data["results"][0]["sender_preview"]["id"], self.test_user.id)
        self.assertEqual(data["results"][0]["count"], 0)

        # Subpost ????????? ?????? ??????
        response = self.client.delete(
            f"/api/v1/newsfeed/{mainpost_id}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        for i in range(3):

            response = self.client.get(
                "/api/v1/notices/",
                content_type="application/json",
                HTTP_AUTHORIZATION=self.friends_token[i],
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()
            self.assertEqual(len(data["results"]), 0)

        # ???????????? ?????? ??????, ????????? ?????? ????????? ?????? X
        data = {
            "content": f"@{friend_1.username}, @{friend_2.username} @{self.test_user.username}",
            "tagged_users": [friend_1.id, friend_2.id, self.test_user.id],
        }

        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        # ????????? ????????? ?????? X
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 0)

        # ???????????? ?????? O
        for i in range(2):
            response = self.client.get(
                "/api/v1/notices/",
                content_type="application/json",
                HTTP_AUTHORIZATION=self.friends_token[i],
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()
            self.assertEqual(data["results"][0]["content"], "CommentTag")
            self.assertEqual(
                data["results"][0]["sender_preview"]["id"], self.test_user.id
            )
            self.assertEqual(data["results"][0]["count"], 0)

        # ??? ??????????????? 2??? ?????? ????????? ??????
        data = {
            "content": f"@{friend_1.username}, @{friend_2.username} @{self.test_user.username} 2?????? ??????",
            "tagged_users": [friend_1.id, friend_2.id, self.test_user.id],
        }

        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.friends_token[2],
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        comment_id = data["id"]

        for i in range(2):
            response = self.client.get(
                "/api/v1/notices/",
                content_type="application/json",
                HTTP_AUTHORIZATION=self.friends_token[i],
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()
            self.assertEqual(data["results"][0]["content"], "CommentTag")
            self.assertEqual(
                data["results"][0]["sender_preview"]["id"],
                self.test_friends[2].id,
            )
            self.assertEqual(data["results"][0]["count"], 1)

        # ?????? ????????? ??? ?????? ????????? ??? ????????? ??????, ????????? update ?????? count??? ?????????
        data = {
            "content": f"@{friend_1.username}, @{friend_2.username} @{self.test_user.username} ??? ??????",
            "tagged_users": [friend_1.id, friend_2.id, self.test_user.id],
        }

        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        parent_id = data["id"]

        for i in range(2):
            response = self.client.get(
                "/api/v1/notices/",
                content_type="application/json",
                HTTP_AUTHORIZATION=self.friends_token[i],
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()
            self.assertEqual(data["results"][0]["content"], "CommentTag")
            self.assertEqual(
                data["results"][0]["sender_preview"]["id"],
                self.test_user.id,
            )
            self.assertEqual(data["results"][0]["count"], 1)

        # ?????? ????????? ?????? ??????
        response = self.client.delete(
            f"/api/v1/newsfeed/{self.test_post.id}/{comment_id}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[2],
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        for i in range(2):
            response = self.client.get(
                "/api/v1/notices/",
                content_type="application/json",
                HTTP_AUTHORIZATION=self.friends_token[i],
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()
            self.assertEqual(data["results"][0]["content"], "CommentTag")
            self.assertEqual(
                data["results"][0]["sender_preview"]["id"],
                self.test_user.id,
            )
            self.assertEqual(data["results"][0]["count"], 0)

        # ???????????? ?????? ??????
        data = {
            "content": f"@{friend_1.username}, @{friend_2.username} @{self.test_user.username} ???????????? ??????",
            "tagged_users": [friend_1.id, friend_2.id, self.test_user.id],
            "parent": parent_id,
        }

        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        # ????????? ????????? ?????? X
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 0)

        # ???????????? ?????? O
        for i in range(2):
            response = self.client.get(
                "/api/v1/notices/",
                content_type="application/json",
                HTTP_AUTHORIZATION=self.friends_token[i],
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()
            self.assertEqual(data["results"][0]["content"], "CommentTag")
            self.assertEqual(data["results"][0]["parent_comment"]["id"], parent_id)
            self.assertEqual(
                data["results"][0]["sender_preview"]["id"], self.test_user.id
            )
            self.assertEqual(data["results"][0]["count"], 0)

        # ??? ???????????? 2??? ?????? ?????? ????????? ??????
        data = {
            "content": f"@{friend_1.username}, @{friend_2.username} @{self.test_user.username} 2?????? ??????",
            "tagged_users": [friend_1.id, friend_2.id, self.test_user.id],
            "parent": parent_id,
        }

        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.friends_token[2],
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        comment_id = data["id"]

        for i in range(2):
            response = self.client.get(
                "/api/v1/notices/",
                content_type="application/json",
                HTTP_AUTHORIZATION=self.friends_token[i],
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()
            self.assertEqual(data["results"][0]["content"], "CommentTag")
            self.assertEqual(
                data["results"][0]["sender_preview"]["id"],
                self.test_friends[2].id,
            )
            self.assertEqual(data["results"][0]["parent_comment"]["id"], parent_id)
            self.assertEqual(data["results"][0]["count"], 1)

        # ?????? ????????? ?????? ??????
        response = self.client.delete(
            f"/api/v1/newsfeed/{self.test_post.id}/{comment_id}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[2],
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        for i in range(2):
            response = self.client.get(
                "/api/v1/notices/",
                content_type="application/json",
                HTTP_AUTHORIZATION=self.friends_token[i],
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()
            self.assertEqual(data["results"][0]["content"], "CommentTag")
            self.assertEqual(
                data["results"][0]["sender_preview"]["id"],
                self.test_user.id,
            )
            self.assertEqual(data["results"][0]["count"], 0)

    def test_tag_update(self):

        # MainPost??? SubPost?????? ????????? ?????? ??????
        test_image = SimpleUploadedFile(
            name="testimage2.jpg",
            content=open(os.path.join(BASE_DIR, "testimage2.jpg"), "rb").read(),
            content_type="image/jpeg",
        )

        friend_1 = self.test_friends[0]
        friend_2 = self.test_friends[1]
        friend_3 = self.test_friends[2]
        friend_4 = self.test_friends[3]

        data = {
            "content": f"@{friend_1.username}",
            "subposts": [
                {
                    "content": f"@{friend_2.username}, @{friend_3.username}",
                    "tagged_users": [friend_2.id, friend_3.id],
                }
            ],
            "file": [test_image],
            "tagged_users": [friend_1.id],
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
        subpost_id = data["subposts"][0]["id"]

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "PostTag")
        self.assertEqual(data["results"][0]["post"]["id"], mainpost_id)
        self.assertEqual(data["results"][0]["sender_preview"]["id"], self.test_user.id)
        self.assertEqual(data["results"][0]["count"], 0)

        for i in range(1, 3):
            response = self.client.get(
                "/api/v1/notices/",
                content_type="application/json",
                HTTP_AUTHORIZATION=self.friends_token[i],
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()
            self.assertEqual(data["results"][0]["content"], "PostTag")
            self.assertEqual(data["results"][0]["post"]["id"], subpost_id)
            self.assertEqual(
                data["results"][0]["sender_preview"]["id"], self.test_user.id
            )
            self.assertEqual(data["results"][0]["count"], 0)

        data = {
            "content": f"@{friend_4.username}, @{self.test_user.username}",
            "subposts": [
                {
                    "id": subpost_id,
                    "contetnt": f"@{friend_1.username}, @{friend_3.username}",
                    "tagged_users": [friend_1.id, friend_3.id],
                }
            ],
            "new_subposts": [
                {"content": f"@{friend_2.username}", "tagged_users": [friend_2.id]}
            ],
            "file": [test_image],
            "tagged_users": [friend_4.id, self.test_user.id],
        }
        response = self.client.put(
            f"/api/v1/newsfeed/{mainpost_id}/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        subpost2_id = data["subposts"][1]["id"]

        # ??????1 mainpost ?????? -> subpost ????????? ??????
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["content"], "PostTag")
        self.assertEqual(data["results"][0]["post"]["id"], subpost_id)
        self.assertEqual(data["results"][0]["sender_preview"]["id"], self.test_user.id)
        self.assertEqual(data["results"][0]["count"], 0)

        # ?????? 2 subpost ?????? -> subpost2 ????????? ?????? (?????? ??????)
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[1],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["content"], "PostTag")
        self.assertEqual(data["results"][0]["post"]["id"], subpost2_id)
        self.assertEqual(data["results"][0]["sender_preview"]["id"], self.test_user.id)
        self.assertEqual(data["results"][0]["count"], 0)

        # ?????? 3 ?????????
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[2],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["content"], "PostTag")
        self.assertEqual(data["results"][0]["post"]["id"], subpost_id)
        self.assertEqual(data["results"][0]["sender_preview"]["id"], self.test_user.id)
        self.assertEqual(data["results"][0]["count"], 0)

        # ?????? 4 ?????? X -> mainpost??? ??????
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[3],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["content"], "PostTag")
        self.assertEqual(data["results"][0]["post"]["id"], mainpost_id)
        self.assertEqual(data["results"][0]["sender_preview"]["id"], self.test_user.id)
        self.assertEqual(data["results"][0]["count"], 0)

        # ????????? ?????? -> ??????X
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 0)

        # ?????? ??????
        data = {
            "content": f"@{friend_1.username}, @{friend_2.username}",
            "tagged_users": [friend_1.id, friend_2.id],
        }

        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        comment_id = data["id"]

        # ?????? ??????
        data = {
            "content": f"@{friend_4.username}, @{friend_2.username}",
            "tagged_users": [friend_4.id, friend_2.id],
        }
        response = self.client.put(
            f"/api/v1/newsfeed/{self.test_post.id}/{comment_id}/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # ??????1 --> ?????? ?????? ??????
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertNotEqual(data["results"][0]["content"], "CommentTag")

        # ??????2 --> ?????? ?????? ?????????
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[1],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "CommentTag")
        self.assertEqual(data["results"][0]["post"]["id"], self.test_post.id)
        self.assertEqual(data["results"][0]["parent_comment"], None)
        self.assertEqual(data["results"][0]["sender_preview"]["id"], self.test_user.id)
        self.assertEqual(data["results"][0]["count"], 0)

        # ??????4 --> ?????? ?????? ??????
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[3],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "CommentTag")
        self.assertEqual(data["results"][0]["post"]["id"], self.test_post.id)
        self.assertEqual(data["results"][0]["parent_comment"], None)
        self.assertEqual(data["results"][0]["sender_preview"]["id"], self.test_user.id)
        self.assertEqual(data["results"][0]["count"], 0)

        # ?????? ??????
        data = {
            "content": f"@{friend_1.username}, @{friend_2.username}",
            "tagged_users": [friend_1.id, friend_2.id],
            "parent": comment_id,
        }

        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        child_comment_id = response.json()["id"]

        # ?????? ??????
        data = {
            "content": f"@{friend_1.username}, @{friend_3.username}",
            "tagged_users": [friend_1.id, friend_3.id],
            "parent": comment_id,
        }

        response = self.client.put(
            f"/api/v1/newsfeed/{self.test_post.id}/{child_comment_id}/",
            data=encode_multipart("BoUnDaRyStRiNg", data),
            content_type=self.content_type,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # ??????1 --> ?????? ?????? ?????????
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "CommentTag")
        self.assertEqual(data["results"][0]["post"]["id"], self.test_post.id)
        self.assertEqual(data["results"][0]["parent_comment"]["id"], comment_id)
        self.assertEqual(data["results"][0]["sender_preview"]["id"], self.test_user.id)
        self.assertEqual(data["results"][0]["count"], 0)

        # ??????2 --> ?????? ?????? ??????
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[1],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "CommentTag")
        self.assertEqual(data["results"][0]["post"]["id"], self.test_post.id)
        self.assertEqual(data["results"][0]["parent_comment"], None)

        # ??????3 --> ?????? ?????? ??????
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[2],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "CommentTag")
        self.assertEqual(data["results"][0]["post"]["id"], self.test_post.id)
        self.assertEqual(data["results"][0]["parent_comment"]["id"], comment_id)
        self.assertEqual(data["results"][0]["sender_preview"]["id"], self.test_user.id)
        self.assertEqual(data["results"][0]["count"], 0)
