from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from datetime import datetime


def jwt_get_secret_key(user_model):
    return user_model.jwt_secret


def validate_gender(gender):
    # if not gender:
    #    raise ValidationError(_("성별이 설정되지 않았습니다."), params={"gender": gender})
    # required 조건으로 이미 validation됨
    if gender != "Male" and gender != "Female":
        raise ValidationError(_("성별이 잘못되었습니다."), params={"gender": gender})


def validate_birth(birth):
    if birth > datetime.now().date():
        raise ValidationError(_("생일이 현재 시간보다 나중일 수는 없습니다."), params={"birth": birth})
