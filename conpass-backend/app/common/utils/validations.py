from django.core.exceptions import ValidationError
import re


class CustomPasswordValidator():
    msg = 'パスワードには英字と数字の両方を含む必要があります。'

    def __init__(self):
        pass

    def validate(self, password, user=None):
        if all((re.search('[0-9]', password), re.search('[a-zA-Z]', password))):
            return
        raise ValidationError(self.msg)

    def get_help_text(self):
        return self.msg
