# your_app/forms.py

from django import forms
from django.core.exceptions import ValidationError
from .validators import normalize_us_phone

from .validators import (
    validate_name,
    validate_us_phone,
    validate_email_with_domain,
)


ALLOWED_EMAIL_DOMAINS = [
    "gmail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    "test.com",
]


class LeadCreateForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        validators=[validate_name],
    )
    phone = forms.CharField(
        max_length=20,
        validators=[validate_us_phone],
    )
    email = forms.EmailField(
        max_length=320,
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea,
    )

    def clean_email(self):
        email = self.cleaned_data.get("email", "")
        validate_email_with_domain(email, allowed_domains=ALLOWED_EMAIL_DOMAINS)
        return email
    

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "")
        validate_us_phone(phone)

        digits = normalize_us_phone(phone)
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]

        # Save as 1234567890 or format it however you prefer
        return digits