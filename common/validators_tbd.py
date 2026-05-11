import re
from django.core.exceptions import ValidationError
from django.utils import timezone


NAME_MAX_LENGTH = 100
EMAIL_MAX_LENGTH = 254
PHONE_MAX_LENGTH = 25
SUBJECT_MAX_LENGTH = 150
TEXTAREA_MAX_LENGTH = 2000


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def validate_required_text(value: str, label: str = "This field") -> str:
    value = normalize_spaces(value)
    if not value:
        raise ValidationError(f"{label} is required.")
    return value


def validate_name(value: str) -> str:
    value = validate_required_text(value, "Name")

    if len(value) < 2:
        raise ValidationError("Name must be at least 2 characters long.")

    if len(value) > NAME_MAX_LENGTH:
        raise ValidationError(f"Name must be {NAME_MAX_LENGTH} characters or fewer.")

    if not re.fullmatch(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s.'\-]*", value):
        raise ValidationError(
            "Name may contain only letters, spaces, apostrophes, periods, and hyphens."
        )

    return value


def validate_email(value: str) -> str:
    value = validate_required_text(value, "Email").lower()

    if len(value) > EMAIL_MAX_LENGTH:
        raise ValidationError("Email address is too long.")

    pattern = r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$"
    if not re.fullmatch(pattern, value, re.IGNORECASE):
        raise ValidationError("Enter a valid email address.")

    return value


def validate_phone(value: str, required: bool = False) -> str:
    value = normalize_spaces(value)

    if not value:
        if required:
            raise ValidationError("Phone number is required.")
        return ""

    if len(value) > PHONE_MAX_LENGTH:
        raise ValidationError("Phone number is too long.")

    digits = re.sub(r"\D", "", value)

    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    if len(digits) != 10:
        raise ValidationError("Enter a valid 10-digit phone number.")

    return digits


def format_us_phone(digits: str) -> str:
    if not digits:
        return ""
    return f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"


def validate_short_text(value: str, label: str, max_length: int = SUBJECT_MAX_LENGTH) -> str:
    value = validate_required_text(value, label)

    if len(value) > max_length:
        raise ValidationError(f"{label} must be {max_length} characters or fewer.")

    return value


def validate_long_text(
    value: str,
    label: str = "Message",
    required: bool = False,
    max_length: int = TEXTAREA_MAX_LENGTH,
) -> str:
    value = normalize_spaces(value)

    if not value:
        if required:
            raise ValidationError(f"{label} is required.")
        return ""

    if len(value) > max_length:
        raise ValidationError(f"{label} must be {max_length} characters or fewer.")

    if len(value) < 5:
        raise ValidationError(f"{label} is too short.")

    return value


def validate_choice(value: str, allowed_values: list[str], label: str, required: bool = False) -> str:
    value = normalize_spaces(value)

    if not value:
        if required:
            raise ValidationError(f"{label} is required.")
        return ""

    if value not in allowed_values:
        raise ValidationError(f"Invalid {label.lower()} selected.")

    return value


def validate_move_in_date(value):
    if not value:
        return value

    today = timezone.localdate()
    if value < today:
        raise ValidationError("Move-in date cannot be in the past.")

    return value