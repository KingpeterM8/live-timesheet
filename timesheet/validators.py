import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

class ComplexityValidator:
    def validate(self, password, user=None):
        if not re.findall('[A-Z]', password):
            raise ValidationError(
                _("Your password must contain at least 1 uppercase letter."),
                code='password_no_upper',
            )
        if not re.findall('[0-9]', password):
            raise ValidationError(
                _("Your password must contain at least 1 digit."),
                code='password_no_number',
            )
        if not re.findall('[^A-Za-z0-9]', password):
            raise ValidationError(
                _("Your password must contain at least 1 special character."),
                code='password_no_symbol',
            )

    def get_help_text(self):
        return _(
            "Your password must contain at least 1 uppercase letter, 1 digit, and 1 special character."
        )