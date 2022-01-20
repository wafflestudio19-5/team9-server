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
            first_name="재현",
            last_name="이",
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
            author=cls.test_user, content="알림 테스트 게시물입니다.", likes=0
        )
        cls.test_comment = CommentFactory.create(
            author=cls.test_user, post=cls.test_post, depth=0, content="알림 테스트 댓글입니다."
        )

        cls.content_type = "multipart/form-data; boundary=BoUnDaRyStRiNg"

    def test_notice(self):

        tmp_comment_list = []

        # 깊이 1인 답글 알림
        for i, friend_token in enumerate(self.friends_token):
            data = {"content": f"알림 테스트 답글입니다...{i}", "parent": self.test_comment.id}
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
            data["results"][0]["parent_comment"]["comment_id"], self.test_comment.id
        )
        self.assertEqual(len(data["results"][0]["senders"]), 9)
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], self.test_friends[-1].id
        )
        self.assertEqual(
            data["results"][0]["url"],
            f"api/v1/newsfeed/{self.test_post.id}/{self.test_comment.id}/",
        )
        self.assertEqual(data["results"][0]["is_checked"], False)
        self.assertEqual(
            data["results"][0]["sender_preview"]["content"], "알림 테스트 답글입니다...9"
        )

        tmp_comment_id = data["results"][0]["sender_preview"]["comment_id"]

        # 깊이 2인 답글 알림
        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart(
                "BoUnDaRyStRiNg",
                {"content": "알림 테스트 답글의 답글입니다.", "parent": tmp_comment_id},
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
        self.assertEqual(
            data["results"][0]["parent_comment"]["comment_id"], tmp_comment_id
        )
        self.assertEqual(len(data["results"][0]["senders"]), 0)
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], self.test_user.id
        )
        self.assertEqual(
            data["results"][0]["url"],
            f"api/v1/newsfeed/{self.test_post.id}/{tmp_comment_id}/",
        )
        self.assertEqual(
            data["results"][0]["sender_preview"]["content"], "알림 테스트 답글의 답글입니다."
        )
        tmp_comment_id = data["results"][0]["sender_preview"]["comment_id"]

        # 깊이 2인 답글 삭제 --> 알림 취소
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

        # 깊이 1인 답글들 삭제 --> 알림 취소
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

        # 댓글알림
        for i, friend_token in enumerate(self.friends_token):
            response = self.client.post(
                f"/api/v1/newsfeed/{self.test_post.id}/comment/",
                data=encode_multipart(
                    "BoUnDaRyStRiNg", {"content": f"알림 테스트 댓글입니다...{i}"}
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
            data["results"][0]["sender_preview"]["user"]["id"], self.test_friends[-1].id
        )
        self.assertEqual(
            data["results"][0]["url"], f"api/v1/newsfeed/{self.test_post.id}/"
        )
        self.assertEqual(data["results"][0]["is_checked"], False)
        self.assertEqual(
            data["results"][0]["sender_preview"]["content"], "알림 테스트 댓글입니다...9"
        )

        # 댓글을 단 사람이 또 다른 댓글을 다는 경우
        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart(
                "BoUnDaRyStRiNg",
                {"content": "이미 댓글을 단 사람은, 또 댓글을 달아도 count가 늘어나지 않습니다."},
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
            data["results"][0]["sender_preview"]["user"]["id"], self.test_friends[0].id
        )
        self.assertEqual(
            data["results"][0]["sender_preview"]["content"],
            "이미 댓글을 단 사람은, 또 댓글을 달아도 count가 늘어나지 않습니다.",
        )
        recent_comment_id = data["results"][0]["sender_preview"]["comment_id"]

        # 알림 is_checked
        response = self.client.get(
            f"/api/v1/notices/{notice_id}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["is_checked"], True)

        # 자기자신 알림 X
        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart(
                "BoUnDaRyStRiNg", {"content": "본인이 단 댓글은 알림에 뜨지 않습니다."}
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
                {"content": "본인이 단 답글은 알림에 뜨지 않습니다.", "parent": recent_comment_id},
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

        # 댓글을 2개 이상 단 사람이, 하나를 삭제해도 count는 그대로 !
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
            data["results"][0]["sender_preview"]["user"]["id"], self.test_friends[-1].id
        )
        self.assertEqual(
            data["results"][0]["sender_preview"]["content"], "알림 테스트 댓글입니다...9"
        )
        recent_comment_id = data["results"][0]["sender_preview"]["comment_id"]

        # 댓글 좋아요
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
            data["results"][0]["parent_comment"]["comment_id"], self.test_comment.id
        )
        self.assertEqual(len(data["results"][0]["senders"]), 9)
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], self.test_friends[-1].id
        )
        self.assertEqual(
            data["results"][0]["url"],
            f"api/v1/newsfeed/{self.test_post.id}/",
        )
        self.assertEqual(data["results"][0]["is_checked"], False)
        self.assertEqual(
            data["results"][0]["parent_comment"]["content"], "알림 테스트 댓글입니다."
        )

        # 게시글 좋아요
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
            data["results"][0]["sender_preview"]["user"]["id"], self.test_friends[-1].id
        )
        self.assertEqual(
            data["results"][0]["url"],
            f"api/v1/newsfeed/{self.test_post.id}/",
        )
        self.assertEqual(data["results"][0]["is_checked"], False)

        # 알림 취소
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
            data["results"][0]["sender_preview"]["user"]["id"], self.test_friends[-1].id
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
            data["results"][1]["sender_preview"]["user"]["id"], self.test_friends[-1].id
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
            data["results"][2]["sender_preview"]["content"], "알림 테스트 댓글입니다...8"
        )
        self.assertEqual(
            data["results"][2]["sender_preview"]["user"]["id"], self.test_friends[-2].id
        )

        # 알림 삭제
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

        # 댓글 알림 삭제한 후에 댓글이 달려 알림이 오는 경우
        for i, friend_token in enumerate(self.friends_token):
            response = self.client.post(
                f"/api/v1/newsfeed/{self.test_post.id}/comment/",
                data=encode_multipart(
                    "BoUnDaRyStRiNg", {"content": f"새로운 알림 테스트 댓글입니다...{i}"}
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
            data["results"][0]["sender_preview"]["user"]["id"], self.test_friends[-1].id
        )
        self.assertEqual(
            data["results"][0]["url"], f"api/v1/newsfeed/{self.test_post.id}/"
        )
        self.assertEqual(data["results"][0]["is_checked"], False)
        self.assertEqual(
            data["results"][0]["sender_preview"]["content"], "새로운 알림 테스트 댓글입니다...9"
        )

        # 좋아요 알림 삭제한 후에 좋아요 알림이 새로 오는 경우
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
            data["results"][0]["sender_preview"]["user"]["id"], self.test_friends[-1].id
        )
        self.assertEqual(
            data["results"][0]["url"],
            f"api/v1/newsfeed/{self.test_post.id}/",
        )
        self.assertEqual(data["results"][0]["is_checked"], False)

        # 친구요청
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
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], stranger.id
        )
        self.assertEqual(len(data["results"][0]["senders"]), 0)

        # 친구수락
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
        self.assertEqual(data["results"][0]["content"], "isFriend")
        self.assertEqual(data["results"][0]["is_checked"], True)
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], stranger.id
        )
        self.assertEqual(len(data["results"][0]["senders"]), 0)

        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=stranger_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "FriendAccept")
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], self.test_user.id
        )
        self.assertEqual(len(data["results"][0]["senders"]), 0)

        # 친구 요청 후, 요청한 사람이 친구 요청을 취소할 시, 보내졌던 알림 삭제
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
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], stranger2.id
        )
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
        self.assertNotEqual(
            data["results"][0]["sender_preview"]["user"]["id"], stranger2.id
        )

        # 친구 요청 후, 요청 받은 사람의 친구 요청 삭제시 알림도 삭제
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
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], stranger2.id
        )
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
        self.assertNotEqual(
            data["results"][0]["sender_preview"]["user"]["id"], stranger2.id
        )

    def test_notice_on_off(self):

        # 게시물 작성자가 게시물에 대한 알림 끄기
        response = self.client.put(
            f"/api/v1/newsfeed/{self.test_post.id}/notice/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["is_noticed"], False)

        # 댓글 작성, 알림 X
        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart("BoUnDaRyStRiNg", {"content": "알림이 발생하지 않습니다."}),
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

        # 게시글 좋아요, 알림 X
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

        # 게시글 좋아요 취소, 에러 발생 X
        response = self.client.put(
            f"/api/v1/newsfeed/{self.test_post.id}/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )

        # 게시글 댓글 삭제, 에러 발생 X
        response = self.client.delete(
            f"/api/v1/newsfeed/{self.test_post.id}/{comment_id}/",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # 게시물에 대한 알림 켜기
        response = self.client.put(
            f"/api/v1/newsfeed/{self.test_post.id}/notice/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["is_noticed"], True)

        # 댓글 작성, 알림 O
        test_image = SimpleUploadedFile(
            name="testimage2.jpg",
            content=open(os.path.join(BASE_DIR, "testimage2.jpg"), "rb").read(),
            content_type="image/jpeg",
        )

        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart(
                "BoUnDaRyStRiNg", {"content": "알림이 발생합니다.", "file": test_image}
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
            data["results"][0]["sender_preview"]["user"]["id"], self.test_friends[0].id
        )
        self.assertEqual(
            data["results"][0]["url"], f"api/v1/newsfeed/{self.test_post.id}/"
        )
        self.assertEqual(data["results"][0]["is_checked"], False)
        self.assertEqual(data["results"][0]["sender_preview"]["content"], "알림이 발생합니다.")
        self.assertIn("photo", data["results"][0]["sender_preview"]["is_file"])

        # 게시글 좋아요, 알림 O
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
            data["results"][0]["sender_preview"]["user"]["id"], self.test_friends[0].id
        )
        self.assertEqual(
            data["results"][0]["url"],
            f"api/v1/newsfeed/{self.test_post.id}/",
        )
        self.assertEqual(data["results"][0]["is_checked"], False)

        # 댓글 작성자의 게시물에 대한 알림 끄기
        response = self.client.put(
            f"/api/v1/newsfeed/{self.test_post.id}/notice/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["is_noticed"], False)

        # 댓글 좋아요 해도 알림 X
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

        # 답글 달기, 알림 X
        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart(
                "BoUnDaRyStRiNg",
                {"content": f"알림이 발생하지 않는 답글입니다.", "parent": comment_id},
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

        # 댓글 작성자의 게시물에 대한 알림 켜기
        response = self.client.put(
            f"/api/v1/newsfeed/{self.test_post.id}/notice/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["is_noticed"], True)

        # 댓글 좋아요, 알림 O
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
        self.assertEqual(data["results"][0]["parent_comment"]["comment_id"], comment_id)
        self.assertEqual(len(data["results"][0]["senders"]), 0)
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], self.test_friends[1].id
        )
        self.assertEqual(
            data["results"][0]["url"],
            f"api/v1/newsfeed/{self.test_post.id}/",
        )
        self.assertEqual(data["results"][0]["is_checked"], False)
        self.assertEqual(data["results"][0]["parent_comment"]["content"], "알림이 발생합니다.")

        # 답글 달기, 알림 O
        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data=encode_multipart(
                "BoUnDaRyStRiNg", {"content": "알림이 발생하는 답글입니다.", "parent": comment_id}
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
        self.assertEqual(data["results"][0]["parent_comment"]["comment_id"], comment_id)
        self.assertEqual(len(data["results"][0]["senders"]), 0)
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], self.test_friends[3].id
        )
        self.assertEqual(
            data["results"][0]["url"],
            f"api/v1/newsfeed/{self.test_post.id}/{comment_id}/",
        )
        self.assertEqual(data["results"][0]["is_checked"], False)
        self.assertEqual(
            data["results"][0]["sender_preview"]["content"], "알림이 발생하는 답글입니다."
        )

        # subpost 단위로 알림 꺼보기
        data = {
            "content": "메인 포스트입니다.",
            "subposts": ["첫번째 포스트입니다."],
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
                "BoUnDaRyStRiNg", {"content": "subpost 알림이 발생하지 않습니다."}
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

        # subpost 단위로 알림 받기
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
            data=encode_multipart("BoUnDaRyStRiNg", {"content": "subpost 알림이 발생합니다."}),
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
            data["results"][0]["sender_preview"]["user"]["id"], self.test_friends[1].id
        )
        self.assertEqual(
            data["results"][0]["sender_preview"]["content"], "subpost 알림이 발생합니다."
        )

    def test_tag_notice(self):

        # Mainpost에서 친구랑 작성자 본인 언급
        friend_1 = self.test_friends[0]
        friend_2 = self.test_friends[1]
        data = {
            "content": f"@{friend_1.username}, @{friend_2.username}, @{self.test_user.username} 친구 태그 테스트입니다.",
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

        # 작성자 본인을 알림 X
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 0)

        # 친구들은 알림 O
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
                data["results"][0]["sender_preview"]["user"]["id"], self.test_user.id
            )
            self.assertEqual(data["results"][0]["count"], 0)

        # Mainpost 삭제시 알림 취소
        response = self.client.delete(
            f"/api/v1/newsfeed/{mainpost_id}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # 친구들 알림 취소
        for i in range(2):
            response = self.client.get(
                "/api/v1/notices/",
                content_type="application/json",
                HTTP_AUTHORIZATION=self.friends_token[i],
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = response.json()
            self.assertEqual(len(data["results"]), 0)

        # Subpost에서 친구 언급
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
                f"@{friend_1.username}, @{friend_2.username}",
                f"@{friend_3.username}",
            ],
            "file": [test_image, test_image],
            "subposts_tagged_users": [
                [friend_1.id, friend_2.id],
                [friend_3.id],
            ],
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
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], self.test_user.id
        )
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
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], self.test_user.id
        )
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
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], self.test_user.id
        )
        self.assertEqual(data["results"][0]["count"], 0)

        # Subpost 삭제시 알림 취소
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

        # 댓글에서 친구 언급, 작성자 본인 언급시 알림 X
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

        # 작성자 본인을 알림 X
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 0)

        # 친구들은 알림 O
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
                data["results"][0]["sender_preview"]["user"]["id"], self.test_user.id
            )
            self.assertEqual(data["results"][0]["count"], 0)

        # 한 게시물에서 2번 이상 언급된 경우
        data = {
            "content": f"@{friend_1.username}, @{friend_2.username} @{self.test_user.username} 2번째 언급",
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
                data["results"][0]["sender_preview"]["user"]["id"],
                self.test_friends[2].id,
            )
            self.assertEqual(data["results"][0]["count"], 1)

        # 이미 언급한 적 있는 유저가 또 언급할 경우, 알림은 update 되나 count는 그대로
        data = {
            "content": f"@{friend_1.username}, @{friend_2.username} @{self.test_user.username} 또 언급",
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
                data["results"][0]["sender_preview"]["user"]["id"],
                self.test_user.id,
            )
            self.assertEqual(data["results"][0]["count"], 1)

        # 댓글 삭제시 알림 취소
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
                data["results"][0]["sender_preview"]["user"]["id"],
                self.test_user.id,
            )
            self.assertEqual(data["results"][0]["count"], 0)

        # 답글에서 친구 언급
        data = {
            "content": f"@{friend_1.username}, @{friend_2.username} @{self.test_user.username} 답글에서 언급",
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

        # 작성자 본인을 알림 X
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 0)

        # 친구들은 알림 O
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
                data["results"][0]["parent_comment"]["comment_id"], parent_id
            )
            self.assertEqual(
                data["results"][0]["sender_preview"]["user"]["id"], self.test_user.id
            )
            self.assertEqual(data["results"][0]["count"], 0)

        # 한 댓글에서 2번 이상 답글 언급된 경우
        data = {
            "content": f"@{friend_1.username}, @{friend_2.username} @{self.test_user.username} 2번째 언급",
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
                data["results"][0]["sender_preview"]["user"]["id"],
                self.test_friends[2].id,
            )
            self.assertEqual(
                data["results"][0]["parent_comment"]["comment_id"], parent_id
            )
            self.assertEqual(data["results"][0]["count"], 1)

        # 답글 삭제시 알림 취소
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
                data["results"][0]["sender_preview"]["user"]["id"],
                self.test_user.id,
            )
            self.assertEqual(data["results"][0]["count"], 0)

    def test_tag_update(self):

        # MainPost와 SubPost에서 친구들 태그 수정
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
            "subposts": [f"@{friend_2.username}, @{friend_3.username}"],
            "file": [test_image],
            "tagged_users": [friend_1.id],
            "subposts_tagged_users": [[friend_2.id, friend_3.id]],
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
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], self.test_user.id
        )
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
                data["results"][0]["sender_preview"]["user"]["id"], self.test_user.id
            )
            self.assertEqual(data["results"][0]["count"], 0)

        data = {
            "content": f"@{friend_4.username}, @{self.test_user.username}",
            "subposts": [
                f"@{friend_1.username}, @{friend_3.username}",
                f"@{friend_2.username}",
            ],
            "file": [test_image],
            "subposts_id": [subpost_id],
            "tagged_users": [friend_4.id, self.test_user.id],
            "subposts_tagged_users": [[friend_1.id, friend_3.id], [friend_2.id]],
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

        # 친구1 mainpost 태그 -> subpost 태그로 변경
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
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], self.test_user.id
        )
        self.assertEqual(data["results"][0]["count"], 0)

        # 친구 2 subpost 태그 -> subpost2 태그로 변경 (파일 추가)
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
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], self.test_user.id
        )
        self.assertEqual(data["results"][0]["count"], 0)

        # 친구 3 그대로
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
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], self.test_user.id
        )
        self.assertEqual(data["results"][0]["count"], 0)

        # 친구 4 태그 X -> mainpost에 태그
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
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], self.test_user.id
        )
        self.assertEqual(data["results"][0]["count"], 0)

        # 작성자 본인 -> 알림X
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 0)

        # 댓글 작성
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

        # 댓글 수정
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

        # 친구1 --> 댓글 알림 취소
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertNotEqual(data["results"][0]["content"], "CommentTag")

        # 친구2 --> 댓글 알림 그대로
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
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], self.test_user.id
        )
        self.assertEqual(data["results"][0]["count"], 0)

        # 친구4 --> 댓글 알림 생성
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
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], self.test_user.id
        )
        self.assertEqual(data["results"][0]["count"], 0)

        # 답글 작성
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

        # 답글 수정
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

        # 친구1 --> 답글 알림 그대로
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "CommentTag")
        self.assertEqual(data["results"][0]["post"]["id"], self.test_post.id)
        self.assertEqual(data["results"][0]["parent_comment"]["comment_id"], comment_id)
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], self.test_user.id
        )
        self.assertEqual(data["results"][0]["count"], 0)

        # 친구2 --> 답글 알림 취소
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

        # 친구3 --> 답글 알림 생성
        response = self.client.get(
            "/api/v1/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[2],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "CommentTag")
        self.assertEqual(data["results"][0]["post"]["id"], self.test_post.id)
        self.assertEqual(data["results"][0]["parent_comment"]["comment_id"], comment_id)
        self.assertEqual(
            data["results"][0]["sender_preview"]["user"]["id"], self.test_user.id
        )
        self.assertEqual(data["results"][0]["count"], 0)
