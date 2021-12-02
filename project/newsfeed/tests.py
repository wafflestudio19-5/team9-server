from django.test import TestCase
from factory.django import DjangoModelFactory
from faker import Faker
from user.models import User
from newsfeed.models import Post, PostImage
from django.test import TestCase
from rest_framework import status
import json
from datetime import datetime

from user.serializers import jwt_token_of
from user.tests import UserFactory

# Create your tests here.
class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = 'test@test.com'

    @classmethod
    def create(cls, **kwargs):

        fake = Faker('ko_KR')
        user = User.objects.create(
            email=kwargs.get('email',fake.email()),
            password=kwargs.get('password',fake.password()),
            first_name=kwargs.get('first_name',fake.first_name()),
            last_name=kwargs.get('last_name',fake.last_name()),
            birth=kwargs.get('birth',fake.date()),
            gender=kwargs.get('gender',fake.random_choices(elements=('M', 'F'), length=1)[0]),
            phone_number=kwargs.get('phone_number',fake.numerify(text="010########"))
        )
        user.set_password(kwargs.get('password', ''))
        user.save()
        
        return user


class PostFactory(DjangoModelFactory):
    class Meta:
        model = Post

    @classmethod
    def create(cls, **kwargs):

        fake = Faker('ko_KR')
        author = kwargs.pop('author')
        post = Post.objects.create(
            author=author,
            content=kwargs.get('content',fake.text(max_nb_chars=1000)),
            likes=kwargs.get('likes',fake.random_int(min=0, max=1000))
        )
        post.save()
        
        return post

class PostImageFactory(DjangoModelFactory):
    class Meta:
        model = PostImage

    @classmethod
    def create(cls, **kwargs):

        postImage = PostImage.objects.create(
            post=kwargs['post'],
            image=kwargs['image']
        )
        postImage.save()
        
        return postImage

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
            phone_number="01000000000"
        )

        cls.test_friend = UserFactory.create(
            email="test1@test.com",
            password="password",
            first_name="test",
            last_name="friend",
            birth="1997-02-03",
            gender="M",
            phone_number="01011111111"
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
            phone_number="01022222222"
        )

        PostFactory.create(author=cls.test_user, 
        content="나의 테스트 게시물입니다.",
        likes=10)

        PostFactory.create(author=cls.test_friend, 
        content="친구의 테스트 게시물입니다.",
        likes=20)

        PostFactory.create(author=cls.test_stranger, 
        content="모르는 사람의 테스트 게시물입니다.",
        likes=30)

    def test_post_list(self):
        
        #test_user의 피드
        user_token = 'JWT ' + jwt_token_of(self.test_user)
        
        response = self.client.get('/api/v1/newsfeed/',
                                content_type='application/json',
                                HTTP_AUTHORIZATION=user_token)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        #포스트의 개수
        self.assertEqual(len(data), 2)

        #피드에 친구와 내 게시물들이 존재
        #내 게시물이 친구 게시물보다 일찎 생성되었으므로, 친구 게시물이 먼저 떠야함 (최신순)
        self.assertEqual(data[1]['content'], self.test_user.posts.last().content)
        self.assertEqual(data[1]['likes'], self.test_user.posts.last().likes)
        self.assertEqual(data[0]['content'], self.test_friend.posts.last().content)
        self.assertEqual(data[0]['likes'], self.test_friend.posts.last().likes)

        #test_stranger의 피드
        user_token = 'JWT ' + jwt_token_of(self.test_stranger)
        
        response = self.client.get('/api/v1/newsfeed/',
                                content_type='application/json',
                                HTTP_AUTHORIZATION=user_token)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        #포스트의 개수
        self.assertEqual(len(data), 1)
        
        #피드에 내 게시물만 존재
        self.assertEqual(data[0]['content'], self.test_stranger.posts.last().content)
        self.assertEqual(data[0]['likes'], self.test_stranger.posts.last().likes)

        #친구가 9명일 때 피드 게시글 개수
        user = self.users[0]

        for i in range(1, 10):
            user.friends.add(self.users[i])

        user_token = 'JWT ' + jwt_token_of(user)
        
        response = self.client.get('/api/v1/newsfeed/',
                                content_type='application/json',
                                HTTP_AUTHORIZATION=user_token)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(len(data), 100)

    def test_post_image(self):

        #https://picsum.photos/300/300 --> 랜덤으로 사진을 주는 곳
        #이미지 하나만 업로드 했을 때

        user = self.test_stranger
        post = self.test_stranger.posts.last()
        postImage = PostImageFactory.create(post=post, image='https://picsum.photos/300/300')

        user_token = 'JWT ' + jwt_token_of(user)
        
        response = self.client.get('/api/v1/newsfeed/',
                                content_type='application/json',
                                HTTP_AUTHORIZATION=user_token)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data[0]['images'][0]['image'], '/media/https%3A/picsum.photos/300/300')

        #이미지 여러 장 업로드 했을 때
        postImages = PostImageFactory.create_batch(5, post=post, image='https://picsum.photos/300/300')

        response = self.client.get('/api/v1/newsfeed/',
                                content_type='application/json',
                                HTTP_AUTHORIZATION=user_token)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        #위에 포함해서 총 6개 이미지 있어야 함)
        self.assertEqual(len(data[0]['images']), 6)