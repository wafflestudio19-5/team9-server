import json
import secrets
import os
from django.core.management.utils import get_random_secret_key

print("###########################")
print(os.environ.get("AWS_SECRET_ACCESS_KEY"))
print("###########################")

f = open("secrets.json", "w")
data = {
    "SECRET_KEY": get_random_secret_key(),
    "KAKAO_APP_KEY": secrets.token_hex(32),
    "AWS_SECRET_ACCESS_KEY": os.environ.get("AWS_SECRET_ACCESS_KEY"),
    "AWS_ACCESS_KEY_ID": os.environ.get("AWS_ACCESS_KEY_ID"),
}
f.write(json.dumps(data))
