from django.test import TestCase
from django.test.client import encode_multipart
from factory.django import DjangoModelFactory
from faker import Faker
from user.models import User
from newsfeed.models import Post, Comment
from django.test import TestCase
from rest_framework import status
import json
from datetime import datetime
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

    def test_notice(self):

        tmp_comment_list = []

        # 깊이 1인 답글 알림
        for i, friend_token in enumerate(self.friends_token):
            response = self.client.post(
                f"/api/v1/newsfeed/{self.test_post.id}/comment/",
                data={"content": f"알림 테스트 답글입니다...{i}", "parent": self.test_comment.id},
                HTTP_AUTHORIZATION=friend_token,
            )
            tmp_comment_list.append(response.json()["id"])
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/v1/newsfeed/notices/",
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
            data["results"][0]["comment_preview"]["content"], "알림 테스트 답글입니다...9"
        )

        tmp_comment_id = data["results"][0]["comment_preview"]["id"]

        # 깊이 2인 답글 알림
        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data={"content": "알림 테스트 답글의 답글입니다.", "parent": tmp_comment_id},
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/v1/newsfeed/notices/",
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
            data["results"][0]["comment_preview"]["content"], "알림 테스트 답글의 답글입니다."
        )
        tmp_comment_id = data["results"][0]["comment_preview"]["id"]

        # 깊이 2인 답글 삭제 --> 알림 취소
        response = self.client.delete(
            f"/api/v1/newsfeed/{self.test_post.id}/{tmp_comment_id}/",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        response = self.client.get(
            "/api/v1/newsfeed/notices/",
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
            "/api/v1/newsfeed/notices/",
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
                data={"content": f"알림 테스트 댓글입니다...{i}"},
                HTTP_AUTHORIZATION=friend_token,
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/v1/newsfeed/notices/",
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
            data["results"][0]["comment_preview"]["content"], "알림 테스트 댓글입니다...9"
        )

        # 댓글을 단 사람이 또 다른 댓글을 다는 경우
        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data={"content": "이미 댓글을 단 사람은, 또 댓글을 달아도 count가 늘어나지 않습니다."},
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            f"/api/v1/newsfeed/notices/",
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
            "이미 댓글을 단 사람은, 또 댓글을 달아도 count가 늘어나지 않습니다.",
        )
        recent_comment_id = data["results"][0]["comment_preview"]["id"]

        # 알림 is_checked
        response = self.client.get(
            f"/api/v1/newsfeed/notices/{notice_id}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["is_checked"], True)

        # 자기자신 알림 X
        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data={"content": "본인이 단 댓글은 알림에 뜨지 않습니다."},
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            f"/api/v1/newsfeed/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["count"], 9)
        self.assertEqual(len(data["results"][0]["senders"]), 9)

        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data={"content": "본인이 단 답글은 알림에 뜨지 않습니다.", "parent": recent_comment_id},
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            f"/api/v1/newsfeed/notices/",
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
            f"/api/v1/newsfeed/notices/",
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
            data["results"][0]["comment_preview"]["content"], "알림 테스트 댓글입니다...9"
        )
        recent_comment_id = data["results"][0]["comment_preview"]["id"]

        # 댓글 좋아요
        for friend_token in self.friends_token:
            response = self.client.put(
                f"/api/v1/newsfeed/{self.test_post.id}/{self.test_comment.id}/like/",
                content_type="application/json",
                HTTP_AUTHORIZATION=friend_token,
            )
        response = self.client.get(
            "/api/v1/newsfeed/notices/",
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
            "/api/v1/newsfeed/notices/",
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

        # 알림 취소
        response = self.client.put(
            f"/api/v1/newsfeed/{self.test_post.id}/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.friends_token[0],
        )
        response = self.client.get(
            "/api/v1/newsfeed/notices/",
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
            "/api/v1/newsfeed/notices/",
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
            "/api/v1/newsfeed/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][2]["count"], 8)
        self.assertEqual(len(data["results"][2]["senders"]), 8)
        self.assertEqual(
            data["results"][2]["comment_preview"]["content"], "알림 테스트 댓글입니다...8"
        )
        self.assertEqual(
            data["results"][2]["sender_preview"]["id"], self.test_friends[-2].id
        )

        # 알림 삭제
        response = self.client.delete(
            f"/api/v1/newsfeed/notices/{notice_id}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        response = self.client.get(
            "/api/v1/newsfeed/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["results"]), 2)
        self.assertNotEqual(data["results"][-1]["id"], notice_id)

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
            "/api/v1/newsfeed/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "FriendRequest")
        self.assertEqual(data["results"][0]["sender_preview"]["id"], stranger.id)
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
            "/api/v1/newsfeed/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "isFriend")
        self.assertEqual(data["results"][0]["is_checked"], True)
        self.assertEqual(data["results"][0]["sender_preview"]["id"], stranger.id)
        self.assertEqual(len(data["results"][0]["senders"]), 0)

        response = self.client.get(
            "/api/v1/newsfeed/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=stranger_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "FriendAccept")
        self.assertEqual(data["results"][0]["sender_preview"]["id"], self.test_user.id)
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
            "/api/v1/newsfeed/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "FriendRequest")
        self.assertEqual(data["results"][0]["sender_preview"]["id"], stranger2.id)
        self.assertEqual(len(data["results"][0]["senders"]), 0)

        response = self.client.delete(
            f"/api/v1/friend/request/{self.test_user.id}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=stranger2_token,
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        response = self.client.get(
            "/api/v1/newsfeed/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertNotEqual(data["results"][0]["sender_preview"]["id"], stranger2.id)

        # 친구 요청 후, 요청 받은 사람의 친구 요청 삭제시 알림도 삭제
        response = self.client.post(
            f"/api/v1/friend/request/{self.test_user.id}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=stranger2_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/v1/newsfeed/notices/",
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
            "/api/v1/newsfeed/notices/",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertNotEqual(data["results"][0]["sender_preview"]["id"], stranger2.id)


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

        PostFactory.create(author=cls.test_user, content="나의 테스트 게시물입니다.", likes=10)

        cls.friend_post = PostFactory.create(
            author=cls.test_friend, content="친구의 테스트 게시물입니다.", likes=20
        )
        cls.friend_post.likeusers.add(cls.test_user)
        cls.friend_post.save()

        PostFactory.create(
            author=cls.test_stranger, content="모르는 사람의 테스트 게시물입니다.", likes=30
        )

    def test_post_list(self):

        # test_user의 피드
        user_token = "JWT " + jwt_token_of(self.test_user)

        response = self.client.get(
            "/api/v1/newsfeed/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # 포스트의 개수
        self.assertEqual(len(data["results"]), 2)

        # 피드에 친구와 내 게시물들이 존재
        # 내 게시물이 친구 게시물보다 일찍 생성되었으므로, 친구 게시물이 먼저 떠야함 (최신순)

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

        # is_liked 확인
        self.assertTrue(data["results"][0]["is_liked"])

        # test_stranger의 피드
        user_token = "JWT " + jwt_token_of(self.test_stranger)

        response = self.client.get(
            "/api/v1/newsfeed/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # 포스트의 개수
        self.assertEqual(len(data["results"]), 1)

        # 피드에 내 게시물만 존재
        self.assertEqual(
            data["results"][0]["content"], self.test_stranger.posts.last().content
        )
        self.assertEqual(
            data["results"][0]["likes"], self.test_stranger.posts.last().likes
        )

        # 친구가 9명일 때 피드 게시글 개수
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

        # 페이지네이션 때문에 20개씩 총 5페이지가 있다.
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
            "subposts": ["첫번째 사진입니다."],
            "file": test_image,
        }

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=data,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertEqual(content, data["content"])
        self.assertEqual(self.test_user.id, data["author"]["id"])
        self.assertEqual(1, len(data["subposts"]))
        post_id = data["id"]
        self.assertEqual(post_id, data["subposts"][0]["mainpost"])
        self.assertEqual("첫번째 사진입니다.", data["subposts"][0]["content"])
        self.assertEqual(False, data["subposts"][0]["is_liked"])
        self.assertIn("testimage.jpg", data["subposts"][0]["file"])

        # 뉴스피드에 추가됐는지 여부
        response = self.client.get(
            "/api/v1/newsfeed/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["id"], post_id)
        self.assertIn("testimage.jpg", data["results"][0]["subposts"][0]["file"])

        # File이 없는데 Content 내용이 없을 경우 오류, File이 하나라도 있으면 content 없어도 댐
        data = {
            "subposts": ["첫번째 사진입니다."],
            "file": test_image,
        }
        response = self.client.post(
            "/api/v1/newsfeed/",
            data=data,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = {
            "file": test_image,
        }
        response = self.client.post(
            "/api/v1/newsfeed/",
            data=data,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = {
            "content": "FOR TEST !!",
            "file": test_image,
        }
        response = self.client.post(
            "/api/v1/newsfeed/",
            data=data,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = {}
        response = self.client.post(
            "/api/v1/newsfeed/",
            data=data,
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_update(self):
        user_token = "JWT " + jwt_token_of(self.test_user)

        # 파일 없는 게시글 수정
        data = {
            "content": "메인 포스트입니다.",
        }
        response = self.client.post(
            "/api/v1/newsfeed/",
            data=data,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        mainpost_id = data["id"]

        data = {
            "content": "메인 포스트입니다. (수정됨)",
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
        self.assertEqual(data["content"], "메인 포스트입니다. (수정됨)")

        # 파일 없는데 content 빌 경우 400 에러
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
            "content": "메인 포스트입니다.",
            "subposts": ["첫번째 포스트입니다.", "두번째 포스트입니다.", "세번째 포스트입니다."],
            "file": [test_image, test_image, test_image],
        }

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=data,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        mainpost_id = data["id"]
        subpost_1 = data["subposts"][0]["id"]
        subpost_2 = data["subposts"][1]["id"]
        subpost_3 = data["subposts"][2]["id"]

        # 내용 수정
        data = {
            "content": "메인 포스트입니다. (수정됨)",
            "subposts": ["첫번째 포스트입니다. (수정됨)", "두번째 포스트입니다. (수정됨)", "세번째 포스트입니다. (수정됨)"],
            "subposts_id": [subpost_1, subpost_2, subpost_3],
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
        self.assertEqual(data["content"], "메인 포스트입니다. (수정됨)")
        self.assertEqual(data["subposts"][0]["content"], "첫번째 포스트입니다. (수정됨)")
        self.assertEqual(data["subposts"][0]["id"], subpost_1)
        self.assertEqual(data["subposts"][1]["content"], "두번째 포스트입니다. (수정됨)")
        self.assertEqual(data["subposts"][1]["id"], subpost_2)
        self.assertEqual(data["subposts"][2]["content"], "세번째 포스트입니다. (수정됨)")
        self.assertEqual(data["subposts"][2]["id"], subpost_3)

        # 파일 삭제
        data = {
            "content": "메인 포스트입니다. (수정됨)",
            "subposts": ["첫번째 포스트입니다. (수정됨)", "두번째 포스트입니다. (수정됨)", "세번째 포스트입니다. (수정됨)"],
            "subposts_id": [subpost_1, subpost_2, subpost_3],
            "removed_subposts_id": subpost_1,
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
        self.assertEqual(data["content"], "메인 포스트입니다. (수정됨)")
        self.assertEqual(len(data["subposts"]), 2)
        self.assertEqual(data["subposts"][0]["content"], "두번째 포스트입니다. (수정됨)")
        self.assertEqual(data["subposts"][0]["id"], subpost_2)
        self.assertEqual(data["subposts"][1]["content"], "세번째 포스트입니다. (수정됨)")
        self.assertEqual(data["subposts"][1]["id"], subpost_3)

        # 파일 추가
        data = {
            "content": "메인 포스트입니다. (수정됨)",
            "subposts": ["두번째 포스트입니다. (수정됨)", "세번째 포스트입니다. (수정됨)", "네번째 포스트입니다."],
            "file": [test_image],
            "subposts_id": [subpost_2, subpost_3],
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
        self.assertEqual(data["content"], "메인 포스트입니다. (수정됨)")
        self.assertEqual(len(data["subposts"]), 3)
        self.assertEqual(data["subposts"][0]["content"], "두번째 포스트입니다. (수정됨)")
        self.assertEqual(data["subposts"][0]["id"], subpost_2)
        self.assertEqual(data["subposts"][1]["content"], "세번째 포스트입니다. (수정됨)")
        self.assertEqual(data["subposts"][1]["id"], subpost_3)
        subpost_4 = data["subposts"][2]["id"]
        self.assertEqual(data["subposts"][2]["content"], "네번째 포스트입니다.")

        # 파일 삭제와 추가 동시에 (2장 제거, 3장 추가)
        data = {
            "content": "메인 포스트입니다. (수정됨)",
            "subposts": [
                "두번째 포스트입니다. (수정됨)",
                "세번째 포스트입니다. (수정됨)",
                "네번째 포스트입니다.",
                "다섯번째 포스트입니다.",
                "여섯번째 포스트입니다.",
                "일곱번째 포스트입니다.",
            ],
            "file": [
                test_image,
                test_image,
                test_image,
            ],
            "subposts_id": [subpost_2, subpost_3, subpost_4],
            "removed_subposts_id": [subpost_2, subpost_3],
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
        self.assertEqual(data["content"], "메인 포스트입니다. (수정됨)")
        self.assertEqual(len(data["subposts"]), 4)
        self.assertEqual(data["subposts"][0]["content"], "네번째 포스트입니다.")
        self.assertEqual(data["subposts"][0]["id"], subpost_4)
        self.assertEqual(data["subposts"][1]["content"], "다섯번째 포스트입니다.")
        subpost_5 = data["subposts"][1]["id"]
        self.assertEqual(data["subposts"][2]["content"], "여섯번째 포스트입니다.")
        subpost_6 = data["subposts"][2]["id"]
        self.assertEqual(data["subposts"][3]["content"], "일곱번째 포스트입니다.")
        subpost_7 = data["subposts"][3]["id"]

        # mainpost 단위에 한해서만 수정 가능
        data = {
            "content": "메인 포스트아니면 수정 불가합니다.",
            "subposts": ["네번째 포스트입니다.", "다섯번째 포스트입니다.", "여섯번째 포스트입니다."],
            "subposts_id": [subpost_4, subpost_5, subpost_6],
        }
        content = encode_multipart("BoUnDaRyStRiNg", data)
        response = self.client.put(
            f"/api/v1/newsfeed/{subpost_4}/",
            data=content,
            content_type=content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # 파일 있으면 content 비워져 있어도 200
        data = {
            "content": "",
            "subposts": ["", "", "", ""],
            "subposts_id": [subpost_4, subpost_5, subpost_6, subpost_7],
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

        # subposts_id 개수가 subposts들과 다르면 400
        data = {
            "content": "메인 포스트입니다. (수정됨)",
            "subposts": ["네번째 포스트입니다.", "다섯번째 포스트입니다.", "여섯번째 포스트입니다.", "일곱번째 포스트입니다."],
            "subposts_id": [subpost_4, subpost_5, subpost_6],
        }
        content = encode_multipart("BoUnDaRyStRiNg", data)
        response = self.client.put(
            f"/api/v1/newsfeed/{mainpost_id}/",
            data=content,
            content_type=content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # subposts_id 중 기존 subposts가 아닌 것이 있으면 404
        data = {
            "content": "메인 포스트입니다. (수정됨)",
            "subposts": ["네번째 포스트입니다.", "다섯번째 포스트입니다.", "여섯번째 포스트입니다.", "일곱번째 포스트입니다."],
            "subposts_id": [subpost_4, subpost_5, subpost_6, 9999],
        }
        content = encode_multipart("BoUnDaRyStRiNg", data)
        response = self.client.put(
            f"/api/v1/newsfeed/{mainpost_id}/",
            data=content,
            content_type=content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # 파일 지우기
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

    def test_post_share(self):

        # 게시물 공유하기
        data = {
            "content": "공유할 게시글입니다.",
            "subposts": [""],
            "file": self.test_image,
        }

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=data,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        sharing_post_id = data["id"]
        subpost_id = data["subposts"][0]["id"]
        sharing_post = self.test_user.posts.get(id=sharing_post_id)

        data = {"content": "게시글을 공유했습니다.", "shared_post": sharing_post_id}

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=data,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(sharing_post_id, data["shared_post"]["id"])
        self.assertEqual("공유할 게시글입니다.", data["shared_post"]["content"])

        # 게시물 공유 시, 공유된 게시물의 공유된 횟수 증가
        response = self.client.get(
            f"/api/v1/newsfeed/{sharing_post_id}/",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["shared_counts"], 1)

        # 친구 뉴스피드와 개인 뉴스피드에서 확인 가능
        response = self.client.get(
            "/api/v1/newsfeed/",
            HTTP_AUTHORIZATION=self.friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "게시글을 공유했습니다.")
        self.assertEqual(data["results"][0]["shared_post"]["id"], sharing_post_id)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.stranger_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "게시글을 공유했습니다.")
        self.assertEqual(data["results"][0]["shared_post"]["id"], sharing_post_id)

        # 내 공유를 본 사람이 공유된 게시글의 보기 권한이 없는 경우
        data = {
            "content": "",
            "subposts": [""],
            "subposts_id": [subpost_id],
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
        self.assertEqual(data["results"][0]["content"], "게시글을 공유했습니다.")
        self.assertEqual(data["results"][0]["shared_post"], "AccessDenied")

        data = {
            "content": "",
            "subposts": [""],
            "subposts_id": [subpost_id],
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
        self.assertEqual(data["results"][0]["content"], "게시글을 공유했습니다.")
        self.assertEqual(data["results"][0]["shared_post"], "AccessDenied")

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "게시글을 공유했습니다.")
        self.assertEqual(data["results"][0]["shared_post"]["id"], sharing_post_id)

        # 공유된 게시글이 삭제된 경우
        sharing_post.delete()
        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "게시글을 공유했습니다.")
        self.assertEqual(data["results"][0]["shared_post"], "AccessDenied")


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

    def test_scope_list(self):

        # 전체공개 게시글
        data = {
            "content": "전체 공개 게시글입니다.",
        }

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=data,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/v1/newsfeed/",
            HTTP_AUTHORIZATION=self.friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "전체 공개 게시글입니다.")
        self.assertEqual(data["results"][0]["scope"], 3)

        response = self.client.get(
            "/api/v1/newsfeed/",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "전체 공개 게시글입니다.")
        self.assertEqual(data["results"][0]["scope"], 3)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.stranger_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "전체 공개 게시글입니다.")
        self.assertEqual(data["results"][0]["scope"], 3)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "전체 공개 게시글입니다.")
        self.assertEqual(data["results"][0]["scope"], 3)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "전체 공개 게시글입니다.")
        self.assertEqual(data["results"][0]["scope"], 3)

        # 친구공개 게시글
        data = {"content": "친구 공개 게시글입니다.", "scope": 2}

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=data,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/v1/newsfeed/",
            HTTP_AUTHORIZATION=self.friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "친구 공개 게시글입니다.")
        self.assertEqual(data["results"][0]["scope"], 2)

        response = self.client.get(
            "/api/v1/newsfeed/",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "친구 공개 게시글입니다.")
        self.assertEqual(data["results"][0]["scope"], 2)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.stranger_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertNotEqual(data["results"][0]["content"], "친구 공개 게시글입니다.")
        self.assertNotEqual(data["results"][0]["scope"], 2)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "친구 공개 게시글입니다.")
        self.assertEqual(data["results"][0]["scope"], 2)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "친구 공개 게시글입니다.")
        self.assertEqual(data["results"][0]["scope"], 2)

        # 나만보기 게시글
        data = {"content": "나만 보기 게시글입니다.", "scope": 1}

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=data,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            "/api/v1/newsfeed/",
            HTTP_AUTHORIZATION=self.friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertNotEqual(data["results"][0]["content"], "나만 보기 게시글입니다.")
        self.assertNotEqual(data["results"][0]["scope"], 1)

        response = self.client.get(
            "/api/v1/newsfeed/",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertNotEqual(data["results"][0]["content"], "나만 보기 게시글입니다.")
        self.assertNotEqual(data["results"][0]["scope"], 1)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.stranger_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertNotEqual(data["results"][0]["content"], "나만 보기 게시글입니다.")
        self.assertNotEqual(data["results"][0]["scope"], 1)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertNotEqual(data["results"][0]["content"], "나만 보기 게시글입니다.")
        self.assertNotEqual(data["results"][0]["scope"], 1)

        response = self.client.get(
            f"/api/v1/user/{self.test_user.id}/newsfeed/",
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["results"][0]["content"], "나만 보기 게시글입니다.")
        self.assertEqual(data["results"][0]["scope"], 1)

    def test_scope_create(self):

        # 파일을 여러 장 업로드 하는 경우, scope가 subposts에 일관되게 적용 되는지

        data = {
            "content": "친구 공개 게시글 입니다",
            "subposts": ["첫번째 사진입니다.", "두번째 사진입니다."],
            "file": [self.test_image, self.test_image],
            "scope": 2,
        }

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=data,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertEqual(data["scope"], 2)
        self.assertEqual(data["subposts"][0]["scope"], 2)
        self.assertEqual(data["subposts"][1]["scope"], 2)

        # 디폴트 값은 3 (전체공개)
        data = {
            "content": "친구 공개 게시글 입니다",
            "subposts": ["첫번째 사진입니다.", "두번째 사진입니다."],
            "file": [self.test_image, self.test_image],
        }

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=data,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertEqual(data["scope"], 3)
        self.assertEqual(data["subposts"][0]["scope"], 3)
        self.assertEqual(data["subposts"][1]["scope"], 3)

        # scope를 1, 2, 3이 아닌 다른 것을 했을 때 오류
        data = {
            "content": "친구 공개 게시글 입니다",
            "subposts": ["첫번째 사진입니다.", "두번째 사진입니다."],
            "file": [self.test_image, self.test_image],
            "scope": 4,
        }
        response = self.client.post(
            "/api/v1/newsfeed/",
            data=data,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data = {
            "content": "친구 공개 게시글 입니다",
            "subposts": ["첫번째 사진입니다.", "두번째 사진입니다."],
            "file": [self.test_image, self.test_image],
            "scope": 0,
        }
        response = self.client.post(
            "/api/v1/newsfeed/",
            data=data,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data = {
            "content": "친구 공개 게시글 입니다",
            "subposts": ["첫번째 사진입니다.", "두번째 사진입니다."],
            "file": [self.test_image, self.test_image],
            "scope": "친구공개",
        }
        response = self.client.post(
            "/api/v1/newsfeed/",
            data=data,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_scope_update(self):

        data = {
            "content": "친구 공개 게시글 입니다",
            "subposts": ["첫번째 사진입니다.", "두번째 사진입니다."],
            "file": [self.test_image, self.test_image],
            "scope": 2,
        }

        response = self.client.post(
            "/api/v1/newsfeed/",
            data=data,
            HTTP_AUTHORIZATION=self.user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        mainpost_id = data["id"]
        subpost_1 = data["subposts"][0]["id"]
        subpost_2 = data["subposts"][1]["id"]

        data = {
            "content": "전체 공개 게시글입니다.",
            "subposts": ["첫번째 사진입니다. (수정됨)", "두번째 사진입니다. (수정됨)"],
            "subposts_id": [subpost_1, subpost_2],
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

        self.assertEqual(data["content"], "전체 공개 게시글입니다.")
        self.assertEqual(data["scope"], 3)
        self.assertEqual(data["subposts"][0]["scope"], 3)
        self.assertEqual(data["subposts"][1]["scope"], 3)

        # scope를 1, 2, 3이 아닌 다른 것을 했을 때 오류
        data = {
            "content": "전체 공개 게시글입니다.",
            "subposts": ["첫번째 사진입니다. (수정됨)", "두번째 사진입니다. (수정됨)"],
            "subposts_id": [subpost_1, subpost_2],
            "scope": "나만 보기",
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
            "content": "전체 공개 게시글입니다.",
            "subposts": ["첫번째 사진입니다. (수정됨)", "두번째 사진입니다. (수정됨)"],
            "subposts_id": [subpost_1, subpost_2],
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
            "content": "전체 공개 게시글입니다.",
            "subposts": ["첫번째 사진입니다. (수정됨)", "두번째 사진입니다. (수정됨)"],
            "subposts_id": [subpost_1, subpost_2],
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

        # 알림을 눌러서 해당 게시글 링크로 갔는데, 공개범위가 그 전에 수정된 경우 404
        # 알림을 눌러서 해당 댓글 링크로 갔는데, 공개범위가 그 전에 수정된 경우
        response = self.client.get(
            f"/api/v1/newsfeed/{mainpost_id}/",
            HTTP_AUTHORIZATION=self.stranger_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(
            f"/api/v1/newsfeed/{mainpost_id}/comment/",
            data={"content": "전체공개 게시글의 댓글입니다."},
            HTTP_AUTHORIZATION=self.stranger_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        comment_id = data["id"]

        data = {
            "content": "친구 공개 게시글입니다.",
            "subposts": ["첫번째 사진입니다. (수정됨)", "두번째 사진입니다. (수정됨)"],
            "subposts_id": [subpost_1, subpost_2],
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
            "content": "나만 보기 게시글입니다.",
            "subposts": ["첫번째 사진입니다. (수정됨)", "두번째 사진입니다. (수정됨)"],
            "subposts_id": [subpost_1, subpost_2],
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

        PostFactory.create(author=cls.test_user, content="나의 테스트 게시물입니다.", likes=0)

        PostFactory.create(author=cls.test_friend, content="친구의 테스트 게시물입니다.", likes=0)

        PostFactory.create(
            author=cls.test_stranger, content="모르는 사람의 테스트 게시물입니다.", likes=0
        )

        for user in cls.users:
            cls.test_friend.friends.add(user)
        cls.test_friend.save()

    def test_like_and_unlike(self):  # 좋아요하고 해제하기
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

    # def test_like_not_friend(self):  # 친구 아닌데 게시글 좋아요
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

    def test_like_or_dislike_myself(self):  # 자기 추천 / 비추천
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
            author=cls.test_user, content="나의 테스트 게시물입니다.", likes=10
        )

        cls.friend_post = PostFactory.create(
            author=cls.test_friend, content="친구의 테스트 게시물입니다.", likes=20
        )

        cls.stranger_post = PostFactory.create(
            author=cls.test_stranger, content="모르는 사람의 테스트 게시물입니다.", likes=30
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

    def test_comment_list(self):

        # test_user의 피드
        user_token = "JWT " + jwt_token_of(self.test_user)

        response = self.client.get(
            f"/api/v1/newsfeed/{self.my_post.id}/comment/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # 최상위 계층에서는 생성 순서가 (21, ..., 41), (1, ..., 20)과 같이 페이지네이션됨
        # 그 아래 계층들에서 시간 오름차순으로 배열 (먼저 생성된 게 앞에)
        self.assertEqual(data["results"][-1]["content"], "depth 0")
        self.assertEqual(data["results"][-1]["children"][0]["content"], "depth 1")
        self.assertTrue(data["results"][-1]["children"][0]["is_liked"])
        self.assertEqual(
            data["results"][-1]["children"][0]["children"][0]["content"], "depth 2"
        )

        # 부모자식 관계 확인
        self.assertEqual(
            data["results"][-1]["children"][0]["parent"], data["results"][-1]["id"]
        )

        # child comment 개수 확인
        self.assertEqual(data["results"][-1]["children_count"], 6)
        self.assertEqual(len(data["results"][-1]["children"]), 6)

        # 페이지네이션 확인
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
            data=data,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertEqual(content, data["content"])
        self.assertEqual(self.test_user.id, data["author"]["id"])

        # 댓글에 파일이 첨부된 경우
        test_image = SimpleUploadedFile(
            name="testimage.jpg",
            content=open(os.path.join(BASE_DIR, "testimage.jpg"), "rb").read(),
            content_type="image/jpeg",
        )

        data = {"content": content, "file": test_image}

        response = self.client.post(
            f"/api/v1/newsfeed/{self.friend_post.id}/comment/",
            data=data,
            HTTP_AUTHORIZATION=user_token,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertEqual(content, data["content"])
        self.assertEqual(self.test_user.id, data["author"]["id"])
        self.assertIn("testimage.jpg", data["file"])

        # Content 내용이 없을 경우 오류
        data = {}
        response = self.client.post(
            f"/api/v1/newsfeed/{self.my_post.id}/comment/",
            data=data,
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()

        # Parent가 존재하지 않을 경우 오류
        data = {
            "content": content,
            "parent": -1,
        }
        response = self.client.post(
            f"/api/v1/newsfeed/{self.my_post.id}/comment/",
            data=data,
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # 친구가 아닌 사람의 게시물인 경우 오류
        data = {
            "content": content,
        }
        response = self.client.post(
            f"/api/v1/newsfeed/{self.stranger_post.id}/comment/",
            data=data,
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # depth가 2인 댓글 (대대댓글)을 parent으로 두려는 경우 오류
        data = {"content": content, "parent": self.depth_two.id}
        response = self.client.post(
            f"/api/v1/newsfeed/{self.my_post.id}/comment/",
            data=data,
            content_type="application/json",
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

        # PUT, 좋아요 반영됐는지 확인
        self.assertEqual(data["likes"], 1)

        response = self.client.get(
            f"/api/v1/newsfeed/{self.my_post.id}/{self.depth_zero.id}/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # GET, likeusers 확인
        self.assertEqual(data["likes"], 1)
        self.assertEqual(data["likeusers"][0]["id"], self.test_user.id)

        response = self.client.put(
            f"/api/v1/newsfeed/{self.my_post.id}/{self.depth_zero.id}/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # DELETE, 좋아요 취소 반영됐는지 확인
        self.assertEqual(data["likes"], 0)
        self.assertEqual(self.depth_zero.likes, 0)

    def test_comment_edit(self):
        friend_token = "JWT " + jwt_token_of(self.test_friend)

        data = {"content": "edited"}

        response = self.client.put(
            f"/api/v1/newsfeed/{self.my_post.id}/{self.depth_zero.id}/",
            data=data,
            content_type="application/json",
            HTTP_AUTHORIZATION=friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["content"], "edited")

        # content가 비어있는 경우
        response = self.client.put(
            f"/api/v1/newsfeed/{self.my_post.id}/{self.depth_zero.id}/",
            data={"content": ""},
            content_type="application/json",
            HTTP_AUTHORIZATION=friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # 자신의 댓글이 아닌 경우
        response = self.client.put(
            f"/api/v1/newsfeed/{self.my_post.id}/{self.depth_zero.id}/",
            data=data,
            content_type="application/json",
            HTTP_AUTHORIZATION="JWT " + jwt_token_of(self.test_user),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # 존재하지 않는 댓글일 경우
        response = self.client.put(
            f"/api/v1/newsfeed/{self.my_post.id}/10000000/",
            data=data,
            content_type="application/json",
            HTTP_AUTHORIZATION=friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_comment_delete(self):
        friend_token = "JWT " + jwt_token_of(self.test_friend)

        # 자신의 댓글이 아닌 경우
        response = self.client.delete(
            f"/api/v1/newsfeed/{self.my_post.id}/{self.depth_zero.id}/",
            HTTP_AUTHORIZATION="JWT " + jwt_token_of(self.test_user),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # 존재하지 않는 댓글일 경우
        response = self.client.delete(
            f"/api/v1/newsfeed/{self.my_post.id}/10000000/",
            HTTP_AUTHORIZATION=friend_token,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # 댓글 삭제
        response = self.client.delete(
            f"/api/v1/newsfeed/{self.my_post.id}/{self.depth_zero.id}/",
            content_type="application/json",
            HTTP_AUTHORIZATION=friend_token,
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
