# your_app/validators.py

import re

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.utils.translation import gettext_lazy as _


def validate_name(value: str) -> None:
    """
    Validates a person's name.
    Allows letters, spaces, apostrophes, periods, and hyphens.
    Examples:
    - John Doe
    - Preya Sundaram
    - Anne-Marie O'Neill
    """
    if value is None:
        raise ValidationError(_("Name is required."), code="required")

    value = value.strip()

    if not value:
        raise ValidationError(_("Name is required."), code="required")

    if len(value) < 2:
        raise ValidationError(
            _("Name must be at least 2 characters long."),
            code="min_length",
        )

    if len(value) > 100:
        raise ValidationError(
            _("Name must be no more than 100 characters long."),
            code="max_length",
        )

    # Letters + common punctuation used in names
    pattern = r"^[A-Za-z]+(?:[ .'-][A-Za-z]+)*$"
    if not re.fullmatch(pattern, value):
        raise ValidationError(
            _("Enter a valid name."),
            code="invalid_name",
        )


def normalize_us_phone(value: str) -> str:
    """
    Returns digits-only normalized US phone number.
    Removes spaces, dashes, parentheses, dots, etc.
    Keeps only digits.
    """
    if value is None:
        return ""

    return re.sub(r"\D", "", value)


def validate_us_phone(value: str) -> None:
    """
    Validates common US phone number formats.
    Accepts:
    - 1234567890
    - 123-456-7890
    - (123) 456-7890
    - +1 123 456 7890
    """
    if value is None:
        raise ValidationError(_("Phone number is required."), code="required")

    raw_value = value.strip()
    if not raw_value:
        raise ValidationError(_("Phone number is required."), code="required")

    digits = normalize_us_phone(raw_value)

    # Handle optional country code 1
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    if len(digits) != 10:
        raise ValidationError(
            _("Enter a valid US phone number."),
            code="invalid_phone",
        )

    # Optional stricter NANP rules:
    # area code and exchange code cannot start with 0 or 1
    if digits[0] in {"0", "1"} or digits[3] in {"0", "1"}:
        raise ValidationError(
            _("Enter a valid US phone number."),
            code="invalid_phone",
        )


def validate_email_with_domain(value: str, allowed_domains=None) -> None:
    """
    Validates email syntax using Django's EmailValidator,
    and optionally restricts email domains.

    allowed_domains example:
    ["gmail.com", "yahoo.com", "company.com"]
    """
    if value is None:
        raise ValidationError(_("Email is required."), code="required")

    value = value.strip().lower()

    if not value:
        raise ValidationError(_("Email is required."), code="required")

    # Django's built-in email syntax validation
    EmailValidator(message=_("Enter a valid email address."))(value)

    # Split local part and domain safely after syntax validation
    local_part, domain = value.rsplit("@", 1)

    if domain.startswith(".") or domain.endswith(".") or "." not in domain:
        raise ValidationError(
            _("Enter a valid email domain."),
            code="invalid_domain",
        )

    # Basic domain label check
    domain_pattern = r"^(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,63}$"
    if not re.fullmatch(domain_pattern, domain):
        raise ValidationError(
            _("Enter a valid email domain."),
            code="invalid_domain",
        )

    if allowed_domains:
        normalized_allowed = {d.strip().lower() for d in allowed_domains}
        if domain not in normalized_allowed:
            raise ValidationError(
                _("Email domain is not allowed."),
                code="domain_not_allowed",
            )