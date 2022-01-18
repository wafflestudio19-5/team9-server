import json

f = open("secrets.json", "w")
data = {
    "SECRET_KEY": "",
    "KAKAO_APP_KEY": "",
    "AWS_SECRET_ACCESS_KEY": "",
    "AWS_ACCESS_KEY_ID": "",
    "DATABASE_HOST": "localhost",
    "EMAIL_HOST_USER": "",
    "EMAIL_HOST_PASSWORD": "",
    "SERVER_EMAIL": "",
}
f.write(json.dumps(data))
