from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from datetime import datetime
import six
from django.contrib.auth.tokens import PasswordResetTokenGenerator


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


class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return (six.text_type(user.pk) + six.text_type(timestamp)) + six.text_type(
            user.is_active
        )


account_activation_token = AccountActivationTokenGenerator()


def message(domain, uidb64, token):
    return f"아래 링크를 클릭하면 회원가입 인증이 완료됩니다.\n\n회원가입 링크 : http://{domain}/account/activate/{uidb64}/{token}\n\n감사합니다."
