"""Shared contact validation for vendor create and edit forms."""
import re
from django import forms
from django.core.validators import validate_email


class VendorContactValidationMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields["phone"]
        field.widget.attrs.update({"type": "tel", "inputmode": "tel", "autocomplete": "tel-national", "placeholder": "(XXX) XXX-XXXX"})
        if not self.is_bound and self.initial.get("phone"):
            try:
                self.initial["phone"] = self.normalize_phone(self.initial["phone"])
            except forms.ValidationError:
                pass  # Keep legacy values visible so users can correct them.
        self.fields["email"].widget.attrs.update({"type": "email", "autocomplete": "email"})

    @staticmethod
    def normalize_phone(value):
        value = (value or "").strip()
        if not value:
            return ""
        if not re.fullmatch(r"(?:\+?1[ .-]?)?[0-9() .-]+", value):
            raise forms.ValidationError("Enter a valid phone number in (XXX) XXX-XXXX format.")
        digits = re.sub(r"\D", "", value)
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) != 10 or digits[0] in "01" or digits[3] in "01":
            raise forms.ValidationError("Enter a valid 10-digit U.S. phone number.")
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"

    def clean_phone(self):
        return self.normalize_phone(self.cleaned_data.get("phone"))

    def clean_email(self):
        value = (self.cleaned_data.get("email") or "").strip()
        if value:
            validate_email(value)
        return value
