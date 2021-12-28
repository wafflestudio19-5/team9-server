from django.test import TestCase
from factory.django import DjangoModelFactory
from faker import Faker
from user.models import User
from newsfeed.models import Post, Comment
from django.test import TestCase
from rest_framework import status
import json
from datetime import datetime
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart
import os
from pathlib import Path
from user.serializers import jwt_token_of
from user.tests import UserFactory

"""'
def generate_photo_file(self):
    image = Image.new("RGBA", size=(100, 100), color=(155, 0, 0))
    file = BytesIO(image.tobytes())
    file.name = "test.png"
    file.seek(0)
    return file
"""

BASE_DIR = Path(__file__).resolve().parent.parent
# Create your tests here.
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

        PostFactory.create(author=cls.test_friend, content="친구의 테스트 게시물입니다.", likes=20)

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

        data = {
            "author": self.test_user.id,
            "content": content,
            "subposts": [{"content": "첫번째 사진입니다."}],
        }
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
        data = response
        print(data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(content, data["content"])
        self.assertEqual(self.test_user.id, data["author"])
        self.assertEqual(1, len(data["subposts"]))
        post_id = data["id"]
        self.assertEqual(post_id, data["subposts"][0]["mainpost"])
        # self.assertIn("picsum.photos/300/300", data["subposts"][0]["file"])
        print(data["subposts"][0]["file"])

        # Content 내용이 없을 경우 오류
        data = {
            "author": self.test_user.id,
            "subposts": [{"content": "첫번째 사진입니다."}],
        }
        response = self.client.post(
            "/api/v1/newsfeed/",
            data=data,
            files=files,
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertEqual(data["non_field_errors"], ["내용을 입력해주세요."])

        # 뉴스피드에 추가됐는지 여부
        response = self.client.get(
            "/api/v1/newsfeed/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["results"][0]["id"], post_id)
        # self.assertIn(
        #     "picsum.photos/300/300", data["results"][0]["subposts"][0]["file"]
        # )
        print(data["results"][0]["subposts"][0]["file"])


"""
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

        response = self.client.delete(
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

    def test_duplicate_like_or_dislike(self):  # 2회 이상 좋아요 혹은 좋아요 취소
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
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        post.refresh_from_db()
        self.assertEqual(post.likes, 1)

        response = self.client.delete(
            "/api/v1/newsfeed/" + str(post.id) + "/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["likes"], 0)

        response = self.client.delete(
            "/api/v1/newsfeed/" + str(post.id) + "/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        post.refresh_from_db()
        self.assertEqual(post.likes, 0)

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

        response = self.client.delete(
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


class CommentFactory(DjangoModelFactory):
    class Meta:
        model = Comment


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

        cls.depth_zero = CommentFactory.create(
            author=cls.test_friend, post=cls.my_post, depth=0, content="depth 0"
        )
        CommentFactory.create_batch(
            35, author=cls.test_friend, post=cls.my_post, depth=0
        )
        cls.depth_one = CommentFactory.create(
            author=cls.test_friend,
            post=cls.my_post,
            depth=1,
            content="depth 1",
            parent=cls.depth_zero,
        )
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

        # 모든 계층에서 시간 오름차순으로 배열 (먼저 생성된 게 앞에)
        self.assertEqual(data["results"][0]["content"], "depth 0")
        self.assertEqual(data["results"][0]["children"][0]["content"], "depth 1")
        self.assertEqual(
            data["results"][0]["children"][0]["children"][0]["content"], "depth 2"
        )

        # 부모자식 관계 확인
        self.assertEqual(
            data["results"][0]["children"][0]["parent"], data["results"][0]["id"]
        )

        # child comment 개수 확인
        self.assertEqual(data["results"][0]["children_count"], 6)
        self.assertEqual(len(data["results"][0]["children"]), 6)

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
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertEqual(content, data["content"])
        self.assertEqual(self.test_user.id, data["author"])

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
        self.assertEqual(data["non_field_errors"], ["내용을 입력해주세요."])

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

        response = self.client.delete(
            f"/api/v1/newsfeed/{self.my_post.id}/{self.depth_zero.id}/like/",
            content_type="application/json",
            HTTP_AUTHORIZATION=user_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # DELETE, 좋아요 취소 반영됐는지 확인
        self.assertEqual(data["likes"], 0)
        self.assertEqual(self.depth_zero.likes, 0)
"""
