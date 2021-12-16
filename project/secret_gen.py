import json
from django.core.management.utils import get_random_secret_key

f = open("secrets.json", "w")
data = {
    "SECRET_KEY": get_random_secret_key()
}
f.write(json.dumps(data))
