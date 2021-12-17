import json
import secrets
from django.core.management.utils import get_random_secret_key

f = open("secrets.json", "w")
data = {"SECRET_KEY": get_random_secret_key(), "KAKAO_APP_KEY": secrets.token_hex(32)}
f.write(json.dumps(data))
