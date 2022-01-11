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

        # 댓글알림
        for i, friend_token in enumerate(self.friends_token):
            response = self.client.post(
                f"/api/v1/newsfeed/{self.test_post.id}/comment/",
                data={"content": f"알림 테스트 댓글입니다...{i}"},
                HTTP_AUTHORIZATION=friend_token,
            )

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
        self.assertEqual(len(data["results"][0]["senders"]), 10)
        self.assertEqual(
            data["results"][0]["url"], f"api/v1/newsfeed/{self.test_post.id}/"
        )
        self.assertEqual(data["results"][0]["is_checked"], False)
        self.assertEqual(data["results"][0]["comment"]["content"], "알림 테스트 댓글입니다...9")

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
        self.assertEqual(len(data["results"][0]["senders"]), 10)

        # 댓글을 단 사람이 또 다른 댓글을 다는 경우
        response = self.client.post(
            f"/api/v1/newsfeed/{self.test_post.id}/comment/",
            data={"content": "이미 댓글을 단 사람은, 또 댓글을 달아도 알림에 추가되지 않습니다."},
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
        self.assertEqual(len(data["results"][0]["senders"]), 10)
        self.assertEqual(
            data["results"][0]["comment"]["content"],
            "이미 댓글을 단 사람은, 또 댓글을 달아도 알림에 추가되지 않습니다.",
        )

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
        self.assertEqual(data["results"][0]["comment"]["id"], self.test_comment.id)
        self.assertEqual(len(data["results"][0]["senders"]), 10)
        self.assertEqual(
            data["results"][0]["url"],
            f"api/v1/newsfeed/{self.test_post.id}/{self.test_comment.id}/",
        )
        self.assertEqual(data["results"][0]["is_checked"], False)
        self.assertEqual(data["results"][0]["comment"]["content"], "알림 테스트 댓글입니다.")

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
        self.assertEqual(len(data["results"][0]["senders"]), 10)
        self.assertEqual(
            data["results"][0]["url"],
            f"api/v1/newsfeed/{self.test_post.id}/",
        )
        self.assertEqual(data["results"][0]["is_checked"], False)

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
        self.assertEqual(len(data["results"][0]["senders"]), 9)

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
        self.assertEqual(len(data["results"][1]["senders"]), 9)

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
        self.assertEqual(data["results"][0]["senders"][0]["id"], stranger.id)

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
            HTTP_AUTHORIZATION=stranger_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["content"], "FriendAccept")
        self.assertEqual(data["results"][0]["senders"][0]["id"], self.test_user.id)


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
            "author": self.test_user.id,
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
            "author": self.test_user.id,
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
            "author": self.test_user.id,
            "file": test_image,
        }
        response = self.client.post(
            "/api/v1/newsfeed/",
            data=data,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = {
            "author": self.test_user.id,
            "content": "FOR TEST !!",
            "file": test_image,
        }
        response = self.client.post(
            "/api/v1/newsfeed/",
            data=data,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = {
            "author": self.test_user.id,
        }
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
            "author": self.test_user.id,
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
            "author": self.test_user.id,
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
        data = {"author": self.test_user.id, "content": ""}
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
            "author": self.test_user.id,
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
            "author": self.test_user.id,
            "content": "메인 포스트입니다. (수정됨)",
            "subposts": ["첫번째 포스트입니다. (수정됨)", "두번째 포스트입니다. (수정됨)", "세번째 포스트입니다. (수정됨)"],
            "file": [test_image, test_image, test_image],
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
            "author": self.test_user.id,
            "content": "메인 포스트입니다. (수정됨)",
            "subposts": ["첫번째 포스트입니다. (수정됨)", "두번째 포스트입니다. (수정됨)", "세번째 포스트입니다. (수정됨)"],
            "file": [test_image, test_image, test_image],
            "subposts_id": [subpost_1, subpost_2, subpost_3],
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
            "file": [test_image, test_image, test_image],
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
                test_image,
                test_image,
                test_image,
            ],
            "subposts_id": [subpost_2, subpost_3, subpost_4],
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

        # 파일 있으면 content 비워져 있어도 200
        data = {
            "content": "",
            "subposts": ["", "", "", ""],
            "file": [test_image, test_image, test_image, test_image],
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

        # subposts와 files의 개수가 다르면 400
        data = {
            "content": "메인 포스트입니다. (수정됨)",
            "subposts": ["네번째 포스트입니다.", "다섯번째 포스트입니다.", "여섯번째 포스트입니다.", "일곱번째 포스트입니다."],
            "file": [test_image, test_image, test_image, test_image, test_image],
            "subposts_id": [subpost_4, subpost_5, subpost_6, subpost_7],
        }
        content = encode_multipart("BoUnDaRyStRiNg", data)
        response = self.client.put(
            f"/api/v1/newsfeed/{mainpost_id}/",
            data=content,
            content_type=content_type,
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # subposts_id 개수가 subposts들과 다르면 400
        data = {
            "content": "메인 포스트입니다. (수정됨)",
            "subposts": ["네번째 포스트입니다.", "다섯번째 포스트입니다.", "여섯번째 포스트입니다.", "일곱번째 포스트입니다."],
            "file": [test_image, test_image, test_image, test_image],
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
            "file": [test_image, test_image, test_image, test_image],
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

    """
    def test_like_not_friend(self):  # 친구 아닌데 게시글 좋아요
        user = self.test_user
        post = self.test_stranger.posts.last()
        user_token = "JWT " + jwt_token_of(user)
        response = self.client.put(
            "/api/v1/newsfeed/" + str(post.id) + "/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        post.refresh_from_db()
    """

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
