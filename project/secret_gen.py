import json

f = open("secrets.json", "w")
data = {
    "SECRET_KEY": "",
    "KAKAO_APP_KEY": "",
    "AWS_SECRET_ACCESS_KEY": "",
    "AWS_ACCESS_KEY_ID": "",
    "DATABASE_HOST": "localhost"
}
f.write(json.dumps(data))
