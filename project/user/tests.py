from django.test import TestCase
from factory.django import DjangoModelFactory
from user.models import User
from user.serializers import jwt_token_of
from rest_framework import status
import json

# Create your tests here.
