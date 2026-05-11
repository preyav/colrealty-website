from django import forms

from .validators import (
    format_us_phone,
    validate_choice,
    validate_email,
    validate_long_text,
    validate_move_in_date,
    validate_name,
    validate_phone,
    validate_short_text,
)


CONTACT_ISSUE_CHOICES = [
    "buying",
    "selling",
    "renting",
    "property_management",
    "general",
]

AGENT_INTEREST_CHOICES = [
    "buying",
    "selling",
    "renting",
    "investing",
    "other",
]

LEAD_SOURCE_TYPES = [
    "listing",
    "rental",
]


class SharedContactFieldsMixin(forms.Form):
    name = forms.CharField(max_length=100)
    email = forms.CharField(max_length=254)
    phone = forms.CharField(max_length=25, required=False)

    def clean_name(self):
        return validate_name(self.cleaned_data.get("name", ""))

    def clean_email(self):
        return validate_email(self.cleaned_data.get("email", ""))

    def clean_phone(self):
        digits = validate_phone(self.cleaned_data.get("phone", ""), required=False)
        return format_us_phone(digits) if digits else ""


class ContactSubmitForm(SharedContactFieldsMixin, forms.Form):
    issue = forms.CharField(required=False, max_length=50)
    subject = forms.CharField(max_length=150)
    description = forms.CharField(max_length=2000)

    def clean_issue(self):
        return validate_choice(
            self.cleaned_data.get("issue", ""),
            CONTACT_ISSUE_CHOICES,
            "Issue",
            required=False,
        )

    def clean_subject(self):
        return validate_short_text(self.cleaned_data.get("subject", ""), "Subject", 150)

    def clean_description(self):
        return validate_long_text(
            self.cleaned_data.get("description", ""),
            label="Description",
            required=True,
            max_length=2000,
        )


class AgentContactForm(SharedContactFieldsMixin, forms.Form):
    interest = forms.CharField(required=False, max_length=50)
    message = forms.CharField(required=False, max_length=2000)

    def clean_interest(self):
        return validate_choice(
            self.cleaned_data.get("interest", ""),
            AGENT_INTEREST_CHOICES,
            "Interest",
            required=False,
        )

    def clean_message(self):
        return validate_long_text(
            self.cleaned_data.get("message", ""),
            label="Message",
            required=False,
            max_length=2000,
        )


class LeadCreateForm(SharedContactFieldsMixin, forms.Form):
    source_type = forms.CharField(max_length=20)
    source_id = forms.IntegerField()
    page_url = forms.CharField(required=False)
    move_in_date = forms.DateField(required=False, input_formats=["%Y-%m-%d"])
    message = forms.CharField(required=False, max_length=2000)

    def clean_source_type(self):
        return validate_choice(
            self.cleaned_data.get("source_type", ""),
            LEAD_SOURCE_TYPES,
            "Source type",
            required=True,
        )

    def clean_move_in_date(self):
        return validate_move_in_date(self.cleaned_data.get("move_in_date"))

    def clean_message(self):
        return validate_long_text(
            self.cleaned_data.get("message", ""),
            label="Message",
            required=False,
            max_length=2000,
        )