from django.db import models

# Create your models here.
from django.contrib.auth.models import (
    BaseUserManager,
    AbstractBaseUser,
    PermissionsMixin,
    UserManager,
)
from django.db.models.deletion import CASCADE
from django.utils import timezone


class CustomUserManager(BaseUserManager):

    use_in_migrations = True

    # create_user : 일반 유저 생성
    # create_superuser : 관리자 유저 생성
    # _create_user : 유저 생성
    # normalize : 중복 최소화를 위한 정규화

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("이메일을 설정해주세요.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.clean_phone_number()
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):

        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):

    objects = CustomUserManager()
    GENDER_CHOICES = (("M", "Male"), ("F", "Female"))

    # 회원가입시 필수로 입력해야하는 필드
    id = models.AutoField(primary_key=True)
    email = models.EmailField(max_length=64, unique=True)
    first_name = models.CharField(max_length=25)
    last_name = models.CharField(max_length=25)
    birth = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    password = models.CharField(max_length=128)
    phone_number = models.CharField(max_length=20, unique=True, blank=True, null=True)

    # 가입, 로그인 시점
    last_login = models.DateTimeField(auto_now=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    # 프로필에서 추가, 편집할 수 있는 필드
    # 나중에 유저의 커버이미지, 프로필이미지 view함수 만들 때, images폴더 안에 있는 사진들 중
    # 가장 최신 꺼를 불러오는 방향으로 하거나, 기존에 있는 사진 삭제하고 새로운 사진을 추가하는 방식으로
    # 짜야할 것 같습니다.
    self_intro = models.CharField(max_length=300, blank=True)
    profile_image = models.ImageField(
        upload_to=f"user/{email}/profile_images/%Y/%m/%d/", blank=True
    )
    cover_image = models.ImageField(
        upload_to=f"user/{email}/cover_images/%Y/%m/%d/", blank=True
    )

    # friends 는 다대다 + 재귀적 모델, symmetrical 옵션은 대칭이라는 뜻으로
    # 인스타그램처럼 내가 팔로우 해도 상대가 팔로우 안할 수 있는 경우 symmetrical = False
    # 페이스북처럼 친구 요청을 수락하면 서로의 친구목록에 동시에 추가되는 경우 symmetrical = True (default)
    friends = models.ManyToManyField("self", symmetrical=True)
    # is_staff = models.BooleanField(default=False)

    # 거주지는 나중에 구현

    EMAIL_FIELD = "email"

    # 유저 모델에서 필드의 이름을 설명하는 string입니다. 유니크 식별자로 사용됩니다
    USERNAME_FIELD = "email"

    # 필수로 받고 싶은 필드 값. USERNAME_FIELD 값과 패스워드는 항상 기본적으로 요구하기 때문에 따로 명시하지 않아도 된다.
    REQUIRED_FIELDS = [
        "first_name",
        "last_name",
        "birth",
        "gender",
        "phone_number",
    ]

    def __str__(self):
        return self.username

    def get_short_name(self):
        return self.email

    def clean_phone_number(self):
        if self.phone_number == "":
            self.phone_number = None


class Company(models.Model):

    # join_date, leave_date 입력 양식 정해주기
    user = models.ForeignKey(User, on_delete=CASCADE)
    name = models.CharField(max_length=30)
    role = models.CharField(max_length=30, blank=True)
    location = models.CharField(max_length=50, blank=True)
    join_date = models.DateField()
    leave_date = models.DateField(blank=True)
    is_active = models.BooleanField(default=False)
    detail = models.CharField(max_length=300, blank=True)


class University(models.Model):

    # join_date, leave_date 입력 양식 정해주기
    user = models.ForeignKey(User, on_delete=CASCADE)
    name = models.CharField(max_length=30)
    major = models.CharField(max_length=30, blank=True)
    join_date = models.DateField()
    graduate_date = models.DateField(blank=True)
    is_active = models.BooleanField(default=False)
