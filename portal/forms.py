from datetime import date, datetime, timedelta
import re
from django import forms
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.utils import timezone

from maintenance.models import (
    MaintenancePhoto,
    MaintenanceRequest,
    VendorAssignment,
    VendorAward,
    VendorEstimate,
    VendorInvoice,
    VendorQuoteRequest,
    WorkOrder,
)
from vendors.models import Vendor, VendorTrade
from leasing.models import Lease, LeaseTenant, LeaseIntentRecord
from tenants.models import TenantProfile
from properties.models import Property, PropertyUnit
from owners.models import OwnerProfile, PropertyOwnership


def _next_quarter_hour():
    """Return the next local 15-minute boundary for datetime inputs."""
    current = timezone.localtime().replace(second=0, microsecond=0)
    minutes_to_add = 15 - (current.minute % 15)
    return current + timedelta(minutes=minutes_to_add)


def _validate_future_quarter_hour(value):
    if value is None:
        return value

    if value.minute % 15 or value.second or value.microsecond:
        raise ValidationError(
            "Select a time in 15-minute increments, such as 10:00 or 10:15."
        )

    if value < timezone.now():
        raise ValidationError(
            "The scheduled date and time cannot be in the past."
        )

    return value


class WorkOrderCreateForm(forms.ModelForm):
    class Meta:
        model = WorkOrder
        fields = [
            "title",
            "description",
            "scheduled_for",
            "estimated_cost",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "description": forms.Textarea(
                attrs={"class": "form-control", "rows": 4}
            ),
            "scheduled_for": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                },
                format="%Y-%m-%dT%H:%M",
            ),
            "estimated_cost": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                }
            ),
            "notes": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        minimum_time = _next_quarter_hour()
        self.fields["scheduled_for"].widget.attrs.update(
            {
                "min": minimum_time.strftime("%Y-%m-%dT%H:%M"),
                "step": "900",
            }
        )

    def clean_scheduled_for(self):
        scheduled_for = self.cleaned_data.get("scheduled_for")
        return _validate_future_quarter_hour(scheduled_for)

class VendorAssignmentForm(forms.ModelForm):

    DIRECT_REASON_CHOICES = [
        ("", "Select a reason"),
        ("urgent", "Urgent work"),
        ("warranty", "Warranty service"),
        ("trusted_vendor", "Known / trusted vendor"),
        ("known_price", "Vendor and price already known"),
        ("other", "Other"),
    ]
    direct_assignment_reason = forms.ChoiceField(
        choices=DIRECT_REASON_CHOICES,
        required=False,
        label="Reason quote is not required",
    )
    award_rationale = forms.ChoiceField(
        choices=[("", "Select a rationale")] + VendorAward.AWARD_REASON_CHOICES,
        required=False,
        label="Award rationale",
    )
    award_rationale_notes = forms.CharField(
        required=False,
        label="Award rationale details",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Explain why this quote provides the best value...",
            }
        ),
    )

    class Meta:
        model = VendorAssignment

        fields = [
            "vendor",
            "scheduled_for",
            "vendor_notes",
        ]

        widgets = {
            "vendor": forms.Select(
                attrs={"class": "form-control"}
            ),

            "scheduled_for": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                },
                format="%Y-%m-%dT%H:%M",
            ),

            "vendor_notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Instructions or notes for the vendor...",
                }
            ),
        }

    def __init__(
        self, *args, work_order=None, quote_selected=False,
        selected_estimate=None, **kwargs
    ):
        super().__init__(*args, **kwargs)

        minimum_time = _next_quarter_hour()
        self.fields["scheduled_for"].widget.attrs.update(
            {
                "min": minimum_time.strftime("%Y-%m-%dT%H:%M"),
                "step": "900",
            }
        )

        queryset = Vendor.objects.filter(
            status="active"
        ).order_by(
            "company_name",
            "name",
        )

        if work_order:
            assigned_vendor_ids = (
                work_order.vendor_assignments
                .filter(status__in=["assigned", "accepted", "scheduled"])
                .values_list(
                    "vendor_id",
                    flat=True,
                )
            )

            current_vendor_id = getattr(self.instance, "vendor_id", None)
            queryset = queryset.exclude(id__in=assigned_vendor_ids)
            if current_vendor_id:
                queryset = Vendor.objects.filter(
                    Q(pk=current_vendor_id) | Q(pk__in=queryset.values("pk"))
                ).order_by("company_name", "name")

        self.fields["vendor"].queryset = queryset
        if not quote_selected:
            self.fields["direct_assignment_reason"].required = True
        self.requires_award_rationale = False
        if quote_selected and work_order and selected_estimate:
            lowest_amount = (
                work_order.vendor_estimates.exclude(status="expired")
                .order_by("amount")
                .values_list("amount", flat=True)
                .first()
            )
            self.requires_award_rationale = (
                lowest_amount is not None and selected_estimate.amount > lowest_amount
            )
            if self.requires_award_rationale:
                self.fields["award_rationale"].required = True

    def clean_scheduled_for(self):
        scheduled_for = self.cleaned_data.get("scheduled_for")
        return _validate_future_quarter_hour(scheduled_for)

    def clean(self):
        cleaned = super().clean()
        if (
            self.requires_award_rationale
            and cleaned.get("award_rationale") == "other"
            and not cleaned.get("award_rationale_notes", "").strip()
        ):
            self.add_error(
                "award_rationale_notes",
                "Explain why the higher quote was selected.",
            )
        return cleaned


class ChangeVendorForm(forms.Form):
    reason = forms.ChoiceField(
        choices=[("", "Select a reason")] + VendorAward.CHANGE_REASON_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}),
    )
    replacement_estimate = forms.ModelChoiceField(
        queryset=VendorEstimate.objects.none(),
        required=False,
        empty_label="Return to sourcing — do not select a replacement yet",
        label="Next step",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, work_order, active_award, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["replacement_estimate"].queryset = (
            VendorEstimate.objects.filter(work_order=work_order)
            .exclude(vendor=active_award.vendor)
            .exclude(status="expired")
            .select_related("vendor")
            .order_by("amount", "vendor__company_name")
        )
        self.fields["replacement_estimate"].label_from_instance = (
            lambda quote: f"{quote.vendor} — ${quote.amount:,.2f}"
        )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("reason") == "other" and not cleaned.get("notes", "").strip():
            self.add_error("notes", "Explain the reason for changing vendors.")
        return cleaned


class CancelVendorAssignmentForm(forms.Form):
    reason = forms.ChoiceField(
        choices=[("", "Select a reason")] + VendorAward.CHANGE_REASON_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    notes = forms.CharField(
        required=True,
        label="Cancellation explanation",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}),
    )

    def clean_notes(self):
        notes = self.cleaned_data.get("notes", "").strip()
        if not notes:
            raise forms.ValidationError("Explain why the assignment is being cancelled.")
        return notes

class VendorScheduleForm(forms.Form):
    scheduled_for = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                "class": "form-control",
                "type": "datetime-local",
            },
            format="%Y-%m-%dT%H:%M",
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
    )

    vendor_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Optional scheduling instructions...",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        minimum_time = _next_quarter_hour()
        self.fields["scheduled_for"].widget.attrs.update(
            {
                "min": minimum_time.strftime("%Y-%m-%dT%H:%M"),
                "step": "900",
            }
        )

    def clean_scheduled_for(self):
        scheduled_for = self.cleaned_data["scheduled_for"]
        return _validate_future_quarter_hour(scheduled_for)

class WorkOrderCompleteForm(forms.Form):
    actual_cost = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "step": "0.01",
            }
        ),
    )

    completion_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Describe the completed work...",
            }
        ),
    )

    completed_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(
            attrs={
                "class": "form-control",
                "type": "datetime-local",
            },
            format="%Y-%m-%dT%H:%M",
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
    )         

class WorkOrderCancelForm(forms.Form):
    cancellation_reason = forms.CharField(
        label="Reason for Cancellation",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": (
                    "Explain why this work order is being cancelled."
                ),
            }
        ),
        required=True,
    )

class VendorInvoiceForm(forms.ModelForm):
    class Meta:
        model = VendorInvoice

        fields = [
            "vendor",
            "invoice_number",
            "amount",
            "invoice_date",
            "due_date",
            "notes",
        ]

        widgets = {
            "vendor": forms.Select(
                attrs={"class": "form-control"}
            ),

            "invoice_number": forms.TextInput(
                attrs={"class": "form-control"}
            ),

            "amount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                }
            ),

            "invoice_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "due_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                }
            ),
        }


class MaintenancePhotoForm(forms.ModelForm):
    class Meta:
        model = MaintenancePhoto

        fields = [
            "photo_type",
            "image",
            "caption",
        ]

        widgets = {
            "photo_type": forms.Select(
                attrs={"class": "form-control"}
            ),

            "image": forms.ClearableFileInput(
                attrs={"class": "form-control"}
            ),

            "caption": forms.TextInput(
                attrs={"class": "form-control"}
            ),
        }    

class VendorQuoteRequestForm(forms.Form):
    vendors = forms.ModelMultipleChoiceField(
        queryset=Vendor.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        help_text="Select one or more vendors to receive this request.",
    )
    response_due = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    scope = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 5}),
    )
    instructions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def __init__(self, *args, vendor_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if vendor_queryset is not None:
            self.fields["vendors"].queryset = vendor_queryset

    def clean_vendors(self):
        vendors = self.cleaned_data["vendors"]
        missing_email = [str(vendor) for vendor in vendors if not vendor.email]
        if missing_email:
            raise ValidationError(
                "Add an email address before requesting a quote from: "
                + ", ".join(missing_email)
            )
        return vendors


class VendorEstimateForm(forms.ModelForm):
    class Meta:
        model = VendorEstimate
        fields = [
            "vendor",
            "entry_method",
            "source",
            "amount",
            "labor_amount",
            "materials_amount",
            "tax_amount",
            "other_fees",
            "discount_amount",
            "received_date",
            "valid_through",
            "attachment",
            "description",
            "notes",
        ]

        widgets = {
            "vendor": forms.Select(
                attrs={"class": "form-control"}
            ),
            "amount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                }
            ),
        }        

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["amount"].required = False

    def clean(self):
        cleaned_data = super().clean()
        entry_method = cleaned_data.get("entry_method")
        amount = cleaned_data.get("amount")

        if entry_method == "total":
            if amount is None:
                self.add_error("amount", "Enter the total quote amount.")
            return cleaned_data

        if entry_method == "itemized":
            component_names = [
                "labor_amount",
                "materials_amount",
                "tax_amount",
                "other_fees",
            ]
            components = [cleaned_data.get(name) for name in component_names]
            if not any(value is not None for value in components):
                raise ValidationError(
                    "Enter at least one itemized cost component."
                )
            subtotal = sum((value or 0) for value in components)
            discount = cleaned_data.get("discount_amount") or 0
            calculated_total = subtotal - discount
            if calculated_total < 0:
                self.add_error(
                    "discount_amount",
                    "The discount cannot exceed the itemized subtotal.",
                )
            else:
                cleaned_data["amount"] = calculated_total

        return cleaned_data

    def _get_validation_exclusions(self):
        exclusions = super()._get_validation_exclusions()
        if self.cleaned_data.get("entry_method") == "itemized":
            exclusions.add("amount")
        return exclusions

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.amount = self.cleaned_data["amount"]
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class MaintenanceRequestCreateForm(forms.ModelForm):
    property = forms.ModelChoiceField(
        queryset=Property.objects.none(),
        empty_label="Select property",
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "id": "id_property",
            }
        ),
    )

    class Meta:
        model = MaintenanceRequest

        fields = [
            "property",
            "unit",
            "lease",
            "reported_by_tenant",
            "title",
            "category",
            "description",
            "priority",
            "permission_to_enter",
            "availability_date",
            "availability_start_time",
            "availability_end_time",
        ]

        widgets = {
            "unit": forms.Select(
                attrs={
                    "class": "form-control",
                    "id": "id_unit",
                }
            ),

            "lease": forms.Select(
                attrs={
                    "class": "form-control",
                    "id": "id_lease",
                }
            ),

            "reported_by_tenant": forms.Select(
                attrs={
                    "class": "form-control",
                    "id": "id_reported_by_tenant",
                }
            ),

            "title": forms.TextInput(
                attrs={"class": "form-control"}
            ),

            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                }
            ),

            "category": forms.Select(
                attrs={"class": "form-control"}
            ),

            "priority": forms.Select(
                attrs={"class": "form-control"}
            ),

            "permission_to_enter": forms.CheckboxInput(),

            "availability_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
        }

    def __init__(
        self,
        *args,
        context_unit=None,
        context_lease=None,
        context_tenant=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.fields["lease"].label = "Lease Period"
        self.fields["unit"].label_from_instance = (
            lambda unit: (
                f"Unit {unit.unit_number}"
                if unit.unit_number
                else "Main Unit"
            )
        )
        self.fields["lease"].label_from_instance = (
            lambda lease: (
                f"{lease.start_date.strftime('%b %d, %Y')} – "
                f"{lease.end_date.strftime('%b %d, %Y')}"
            )
        )

        self.context_unit = context_unit
        self.context_lease = context_lease
        self.context_tenant = context_tenant

        self.fields["property"].queryset = (
            Property.objects
            .exclude(management_status="inactive")
            .order_by("street_address", "city")
        )

        time_choices = []
        current_time = datetime(2000, 1, 1, 0, 0)
        end_of_day = current_time + timedelta(days=1)
        while current_time < end_of_day:
            value = current_time.strftime("%H:%M")
            label = current_time.strftime("%I:%M %p").lstrip("0")
            time_choices.append((value, label))
            current_time += timedelta(minutes=15)

        self.fields["availability_start_time"].widget = forms.Select(
            choices=[("", "Start time")] + time_choices,
            attrs={"class": "form-control"},
        )
        self.fields["availability_end_time"].widget = forms.Select(
            choices=[("", "End time")] + time_choices,
            attrs={"class": "form-control"},
        )

        self.fields["unit"].queryset = PropertyUnit.objects.none()
        self.fields["lease"].queryset = Lease.objects.none()
        self.fields["reported_by_tenant"].queryset = (
            TenantProfile.objects.none()
        )

        property_id = None
        unit_id = None

        # -------------------------------------------------
        # Context-driven intake
        # Lease 360 / Tenant 360 / Property workflow
        # -------------------------------------------------

        if context_unit:
            property_id = context_unit.property_id
            unit_id = context_unit.id

            self.fields["property"].queryset = Property.objects.filter(
                pk=context_unit.property_id
            )
            self.fields["property"].initial = context_unit.property
            self.fields["property"].disabled = True

            self.fields["unit"].queryset = (
                PropertyUnit.objects.filter(
                    pk=context_unit.id
                )
            )

            self.fields["unit"].initial = context_unit
            self.fields["unit"].disabled = True

        # -------------------------------------------------
        # Normal staff intake
        # -------------------------------------------------

        elif self.data:
            try:
                property_id = int(self.data.get("property"))
            except (TypeError, ValueError):
                pass

            try:
                unit_id = int(
                    self.data.get("unit")
                )
            except (TypeError, ValueError):
                pass

        elif self.instance.pk and self.instance.unit_id:
            property_id = self.instance.unit.property_id
            unit_id = self.instance.unit_id

            self.fields["property"].initial = self.instance.unit.property

        if property_id and not context_unit:
            self.fields["unit"].queryset = (
                PropertyUnit.objects
                .filter(property_id=property_id)
                .exclude(status="inactive")
                .order_by("unit_number")
            )

        # -------------------------------------------------
        # Load active leases for selected unit
        # -------------------------------------------------

        if unit_id:
            leases = (
                Lease.objects
                .filter(
                    unit_id=unit_id,
                    status__in=["active", "notice"],
                )
                .order_by("-start_date")
            )

            self.fields["lease"].queryset = leases

            # Lease context means the lease is known
            # and should not be changed.
            if context_lease:
                self.fields["lease"].queryset = (
                    Lease.objects.filter(
                        pk=context_lease.id,
                        unit_id=unit_id,
                        status__in=["active", "notice"],
                    )
                )

                self.fields["lease"].initial = (
                    context_lease
                )

                self.fields["lease"].disabled = True

                tenant_queryset = (
                    TenantProfile.objects
                    .filter(
                        lease_memberships__lease=context_lease,
                        is_active=True,
                    )
                    .distinct()
                    .order_by(
                        "last_name",
                        "first_name",
                    )
                )

            else:
                tenant_queryset = (
                    TenantProfile.objects
                    .filter(
                        lease_memberships__lease__in=leases,
                        is_active=True,
                    )
                    .distinct()
                    .order_by(
                        "last_name",
                        "first_name",
                    )
                )

            self.fields[
                "reported_by_tenant"
            ].queryset = tenant_queryset

        # -------------------------------------------------
        # Tenant context means reporter is already known
        # -------------------------------------------------

        if context_tenant:
            self.fields[
                "reported_by_tenant"
            ].queryset = TenantProfile.objects.filter(
                pk=context_tenant.id,
                is_active=True,
            )

            self.fields[
                "reported_by_tenant"
            ].initial = context_tenant

            self.fields[
                "reported_by_tenant"
            ].disabled = True

    def clean(self):
        cleaned_data = super().clean()

        unit = cleaned_data.get("unit")
        property_obj = cleaned_data.get("property")
        lease = cleaned_data.get("lease")
        tenant = cleaned_data.get(
            "reported_by_tenant"
        )

        availability_date = cleaned_data.get("availability_date")
        start_time = cleaned_data.get("availability_start_time")
        end_time = cleaned_data.get("availability_end_time")

        if property_obj and unit and unit.property_id != property_obj.id:
            self.add_error(
                "unit",
                "The selected unit does not belong to this property.",
            )

        availability_values = [availability_date, start_time, end_time]
        if any(availability_values) and not all(availability_values):
            raise ValidationError(
                "Enter an availability date, start time, and end time."
            )

        if start_time and end_time and end_time <= start_time:
            self.add_error(
                "availability_end_time",
                "End time must be later than start time.",
            )

        if lease and unit:
            if lease.unit_id != unit.id:
                self.add_error(
                    "lease",
                    (
                        "The selected lease does not "
                        "belong to this unit."
                    ),
                )

        if lease and lease.status not in ["active", "notice"]:
            self.add_error(
                "lease",
                "Only an active lease or a lease on notice can be selected.",
            )

        if tenant and lease:
            tenant_is_on_lease = (
                lease.lease_tenants
                .filter(
                    tenant=tenant
                )
                .exists()
            )

            if not tenant_is_on_lease:
                self.add_error(
                    "reported_by_tenant",
                    (
                        "The selected tenant is not "
                        "associated with this lease."
                    ),
                )

        # Additional protection for context-driven forms.

        if (
            self.context_unit
            and unit
            and unit.id != self.context_unit.id
        ):
            self.add_error(
                "unit",
                "The unit cannot be changed.",
            )

        if (
            self.context_lease
            and lease
            and lease.id != self.context_lease.id
        ):
            self.add_error(
                "lease",
                "The lease cannot be changed.",
            )

        if (
            self.context_tenant
            and tenant
            and tenant.id != self.context_tenant.id
        ):
            self.add_error(
                "reported_by_tenant",
                "The reporting tenant cannot be changed.",
            )

        return cleaned_data

class MaintenanceRequestReviewForm(forms.ModelForm):
    """Staff review decision for a maintenance service ticket."""

    DECISION_CHOICES = [
        ("under_review", "Save as Under Review"),
        ("pending_information", "Request More Information"),
        ("approved", "Approve Request"),
        ("declined", "Decline Request"),
    ]

    decision = forms.ChoiceField(
        choices=DECISION_CHOICES,
        required=False,
        widget=forms.HiddenInput(),
    )

    class Meta:
        model = MaintenanceRequest
        fields = [
            "category",
            "priority",
            "assigned_reviewer",
            "review_due_at",
            "pending_reason",
            "review_notes",
        ]
        labels = {
            "assigned_reviewer": "Assigned reviewer",
            "review_due_at": "Decision / follow-up due",
            "pending_reason": "Reason more time is needed",
            "review_notes": "Review explanation / internal notes",
        }
        widgets = {
            "category": forms.Select(attrs={"class": "form-control"}),
            "priority": forms.Select(attrs={"class": "form-control"}),
            "assigned_reviewer": forms.Select(attrs={"class": "form-control"}),
            "review_due_at": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "pending_reason": forms.Select(attrs={"class": "form-control"}),
            "review_notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": (
                        "Explain what is needed, the approval rationale, "
                        "or the reason for declining..."
                    ),
                }
            ),
            "entry_method": forms.RadioSelect(),
            "source": forms.Select(attrs={"class": "form-control"}),
            "labor_amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "materials_amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "tax_amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "other_fees": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "discount_amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "received_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "valid_through": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "attachment": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_reviewer"].required = False
        self.fields["review_due_at"].required = False
        self.fields["pending_reason"].required = False
        self.fields["review_notes"].required = False
        self.fields["review_due_at"].input_formats = ["%Y-%m-%dT%H:%M"]

    def clean(self):
        cleaned_data = super().clean()
        decision = cleaned_data.get("decision") or "approved"
        cleaned_data["decision"] = decision
        notes = (cleaned_data.get("review_notes") or "").strip()

        if decision in {"under_review", "pending_information"}:
            if not cleaned_data.get("assigned_reviewer"):
                self.add_error("assigned_reviewer", "Assign a staff reviewer.")
            if not cleaned_data.get("review_due_at"):
                self.add_error("review_due_at", "Set a follow-up deadline.")
            if not notes:
                self.add_error("review_notes", "Explain what must happen before a decision can be made.")

        if decision == "pending_information" and not cleaned_data.get("pending_reason"):
            self.add_error("pending_reason", "Select why more information or time is needed.")

        if decision == "declined" and not notes:
            self.add_error("review_notes", "Explain why this request is being declined.")

        return cleaned_data


class VendorForm(forms.ModelForm):
    class Meta:
        model = Vendor
        fields = [
            "name",
            "company_name",
            "email",
            "phone",
            "status",
            "notes",
        ]

        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "company_name": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "email": forms.EmailInput(
                attrs={"class": "form-control"}
            ),
            "phone": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "status": forms.Select(
                attrs={"class": "form-control"}
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                }
            ),
        }

class VendorTradeForm(forms.Form):
    trades = forms.MultipleChoiceField(
        choices=VendorTrade.TRADE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )    

US_STATE_CHOICES = [
    ("AL", "Alabama"), ("AK", "Alaska"), ("AZ", "Arizona"), ("AR", "Arkansas"),
    ("CA", "California"), ("CO", "Colorado"), ("CT", "Connecticut"), ("DE", "Delaware"),
    ("FL", "Florida"), ("GA", "Georgia"), ("HI", "Hawaii"), ("ID", "Idaho"),
    ("IL", "Illinois"), ("IN", "Indiana"), ("IA", "Iowa"), ("KS", "Kansas"),
    ("KY", "Kentucky"), ("LA", "Louisiana"), ("ME", "Maine"), ("MD", "Maryland"),
    ("MA", "Massachusetts"), ("MI", "Michigan"), ("MN", "Minnesota"), ("MS", "Mississippi"),
    ("MO", "Missouri"), ("MT", "Montana"), ("NE", "Nebraska"), ("NV", "Nevada"),
    ("NH", "New Hampshire"), ("NJ", "New Jersey"), ("NM", "New Mexico"), ("NY", "New York"),
    ("NC", "North Carolina"), ("ND", "North Dakota"), ("OH", "Ohio"), ("OK", "Oklahoma"),
    ("OR", "Oregon"), ("PA", "Pennsylvania"), ("RI", "Rhode Island"), ("SC", "South Carolina"),
    ("SD", "South Dakota"), ("TN", "Tennessee"), ("TX", "Texas"), ("UT", "Utah"),
    ("VT", "Vermont"), ("VA", "Virginia"), ("WA", "Washington"), ("WV", "West Virginia"),
    ("WI", "Wisconsin"), ("WY", "Wyoming"), ("DC", "District of Columbia"),
]

TEXAS_CITY_SUGGESTIONS = [
    "Abilene", "Addison", "Alamo", "Alamo Heights", "Alice", "Allen", "Alpine",
    "Amarillo", "Andrews", "Angleton", "Anna", "Aransas Pass", "Arlington",
    "Austin", "Azle", "Bastrop", "Bay City", "Baytown", "Beaumont", "Bedford",
    "Bee Cave", "Beeville", "Bellaire", "Belton", "Big Spring", "Boerne",
    "Bonham", "Brenham", "Bridge City", "Brownsville", "Brownwood", "Bryan",
    "Buda", "Burleson", "Burnet", "Canyon", "Carrollton", "Cedar Hill",
    "Cedar Park", "Cibolo", "Cleburne", "Cleveland", "College Station",
    "Colleyville", "Conroe", "Coppell", "Copperas Cove", "Corpus Christi",
    "Corsicana", "Dallas", "DeSoto", "Del Rio", "Denton", "Dripping Springs",
    "Duncanville", "Eagle Pass", "Edinburg", "El Paso", "Ennis", "Euless",
    "Farmers Branch", "Flower Mound", "Forney", "Fort Worth", "Fredericksburg",
    "Friendswood", "Frisco", "Galveston", "Georgetown", "Giddings", "Grapevine",
    "Greenville", "Harker Heights", "Harlingen", "Hewitt", "Hutto", "Houston",
    "Huntsville", "Irving", "Jacksonville", "Katy", "Keller", "Kerrville",
    "Killeen", "Kyle", "La Grange", "Lakeway", "Lancaster", "Laredo",
    "League City", "Leander", "Lewisville", "Liberty Hill", "Lockhart",
    "Longview", "Lubbock", "Lufkin", "Manor", "Mansfield", "Marble Falls",
    "McAllen", "McKinney", "Mesquite", "Midland", "Mission", "Missouri City",
    "Nacogdoches", "New Braunfels", "North Richland Hills", "Odessa",
    "Orange", "Palestine", "Paris", "Pasadena", "Pearland", "Pflugerville",
    "Plano", "Port Arthur", "Portland", "Prosper", "Richardson", "Richmond",
    "Rockport", "Rockwall", "Rosenberg", "Round Rock", "Rowlett",
    "San Angelo", "San Antonio", "San Marcos", "Schertz", "Seguin",
    "Sherman", "Southlake", "Spicewood", "Spring", "Stafford", "Sugar Land",
    "Taylor", "Temple", "Terrell", "Texarkana", "Texas City", "The Colony",
    "The Woodlands", "Tomball", "Tyler", "Universal City", "Victoria",
    "Waco", "Waxahachie", "Weatherford", "Webster", "West Lake Hills",
    "Wichita Falls", "Wimberley"
]

TEXAS_COUNTY_CHOICES = [
    ("Anderson", "Anderson"),
    ("Andrews", "Andrews"),
    ("Angelina", "Angelina"),
    ("Aransas", "Aransas"),
    ("Archer", "Archer"),
    ("Armstrong", "Armstrong"),
    ("Atascosa", "Atascosa"),
    ("Austin", "Austin"),
    ("Bailey", "Bailey"),
    ("Bandera", "Bandera"),
    ("Bastrop", "Bastrop"),
    ("Baylor", "Baylor"),
    ("Bee", "Bee"),
    ("Bell", "Bell"),
    ("Bexar", "Bexar"),
    ("Blanco", "Blanco"),
    ("Borden", "Borden"),
    ("Bosque", "Bosque"),
    ("Bowie", "Bowie"),
    ("Brazoria", "Brazoria"),
    ("Brazos", "Brazos"),
    ("Brewster", "Brewster"),
    ("Briscoe", "Briscoe"),
    ("Brooks", "Brooks"),
    ("Brown", "Brown"),
    ("Burleson", "Burleson"),
    ("Burnet", "Burnet"),
    ("Caldwell", "Caldwell"),
    ("Calhoun", "Calhoun"),
    ("Callahan", "Callahan"),
    ("Cameron", "Cameron"),
    ("Camp", "Camp"),
    ("Carson", "Carson"),
    ("Cass", "Cass"),
    ("Castro", "Castro"),
    ("Chambers", "Chambers"),
    ("Cherokee", "Cherokee"),
    ("Childress", "Childress"),
    ("Clay", "Clay"),
    ("Cochran", "Cochran"),
    ("Coke", "Coke"),
    ("Coleman", "Coleman"),
    ("Collin", "Collin"),
    ("Collingsworth", "Collingsworth"),
    ("Colorado", "Colorado"),
    ("Comal", "Comal"),
    ("Comanche", "Comanche"),
    ("Concho", "Concho"),
    ("Cooke", "Cooke"),
    ("Coryell", "Coryell"),
    ("Cottle", "Cottle"),
    ("Crane", "Crane"),
    ("Crockett", "Crockett"),
    ("Crosby", "Crosby"),
    ("Culberson", "Culberson"),
    ("Dallam", "Dallam"),
    ("Dallas", "Dallas"),
    ("Dawson", "Dawson"),
    ("Deaf Smith", "Deaf Smith"),
    ("Delta", "Delta"),
    ("Denton", "Denton"),
    ("DeWitt", "DeWitt"),
    ("Dickens", "Dickens"),
    ("Dimmit", "Dimmit"),
    ("Donley", "Donley"),
    ("Duval", "Duval"),
    ("Eastland", "Eastland"),
    ("Ector", "Ector"),
    ("Edwards", "Edwards"),
    ("Ellis", "Ellis"),
    ("El Paso", "El Paso"),
    ("Erath", "Erath"),
    ("Falls", "Falls"),
    ("Fannin", "Fannin"),
    ("Fayette", "Fayette"),
    ("Fisher", "Fisher"),
    ("Floyd", "Floyd"),
    ("Foard", "Foard"),
    ("Fort Bend", "Fort Bend"),
    ("Franklin", "Franklin"),
    ("Freestone", "Freestone"),
    ("Frio", "Frio"),
    ("Gaines", "Gaines"),
    ("Galveston", "Galveston"),
    ("Garza", "Garza"),
    ("Gillespie", "Gillespie"),
    ("Glasscock", "Glasscock"),
    ("Goliad", "Goliad"),
    ("Gonzales", "Gonzales"),
    ("Gray", "Gray"),
    ("Grayson", "Grayson"),
    ("Gregg", "Gregg"),
    ("Grimes", "Grimes"),
    ("Guadalupe", "Guadalupe"),
    ("Hale", "Hale"),
    ("Hall", "Hall"),
    ("Hamilton", "Hamilton"),
    ("Hansford", "Hansford"),
    ("Hardeman", "Hardeman"),
    ("Hardin", "Hardin"),
    ("Harris", "Harris"),
    ("Harrison", "Harrison"),
    ("Hartley", "Hartley"),
    ("Haskell", "Haskell"),
    ("Hays", "Hays"),
    ("Hemphill", "Hemphill"),
    ("Henderson", "Henderson"),
    ("Hidalgo", "Hidalgo"),
    ("Hill", "Hill"),
    ("Hockley", "Hockley"),
    ("Hood", "Hood"),
    ("Hopkins", "Hopkins"),
    ("Houston", "Houston"),
    ("Howard", "Howard"),
    ("Hudspeth", "Hudspeth"),
    ("Hunt", "Hunt"),
    ("Hutchinson", "Hutchinson"),
    ("Irion", "Irion"),
    ("Jack", "Jack"),
    ("Jackson", "Jackson"),
    ("Jasper", "Jasper"),
    ("Jeff Davis", "Jeff Davis"),
    ("Jefferson", "Jefferson"),
    ("Jim Hogg", "Jim Hogg"),
    ("Jim Wells", "Jim Wells"),
    ("Johnson", "Johnson"),
    ("Jones", "Jones"),
    ("Karnes", "Karnes"),
    ("Kaufman", "Kaufman"),
    ("Kendall", "Kendall"),
    ("Kenedy", "Kenedy"),
    ("Kent", "Kent"),
    ("Kerr", "Kerr"),
    ("Kimble", "Kimble"),
    ("King", "King"),
    ("Kinney", "Kinney"),
    ("Kleberg", "Kleberg"),
    ("Knox", "Knox"),
    ("Lamar", "Lamar"),
    ("Lamb", "Lamb"),
    ("Lampasas", "Lampasas"),
    ("LaSalle", "LaSalle"),
    ("Lavaca", "Lavaca"),
    ("Lee", "Lee"),
    ("Leon", "Leon"),
    ("Liberty", "Liberty"),
    ("Limestone", "Limestone"),
    ("Lipscomb", "Lipscomb"),
    ("Live Oak", "Live Oak"),
    ("Llano", "Llano"),
    ("Loving", "Loving"),
    ("Lubbock", "Lubbock"),
    ("Lynn", "Lynn"),
    ("Madison", "Madison"),
    ("Marion", "Marion"),
    ("Martin", "Martin"),
    ("Mason", "Mason"),
    ("Matagorda", "Matagorda"),
    ("Maverick", "Maverick"),
    ("McCulloch", "McCulloch"),
    ("McLennan", "McLennan"),
    ("McMullen", "McMullen"),
    ("Medina", "Medina"),
    ("Menard", "Menard"),
    ("Midland", "Midland"),
    ("Milam", "Milam"),
    ("Mills", "Mills"),
    ("Mitchell", "Mitchell"),
    ("Montague", "Montague"),
    ("Montgomery", "Montgomery"),
    ("Moore", "Moore"),
    ("Morris", "Morris"),
    ("Motley", "Motley"),
    ("Nacogdoches", "Nacogdoches"),
    ("Navarro", "Navarro"),
    ("Newton", "Newton"),
    ("Nolan", "Nolan"),
    ("Nueces", "Nueces"),
    ("Ochiltree", "Ochiltree"),
    ("Oldham", "Oldham"),
    ("Orange", "Orange"),
    ("Palo Pinto", "Palo Pinto"),
    ("Panola", "Panola"),
    ("Parker", "Parker"),
    ("Parmer", "Parmer"),
    ("Pecos", "Pecos"),
    ("Polk", "Polk"),
    ("Potter", "Potter"),
    ("Presidio", "Presidio"),
    ("Rains", "Rains"),
    ("Randall", "Randall"),
    ("Reagan", "Reagan"),
    ("Real", "Real"),
    ("Red River", "Red River"),
    ("Reeves", "Reeves"),
    ("Refugio", "Refugio"),
    ("Roberts", "Roberts"),
    ("Robertson", "Robertson"),
    ("Rockwall", "Rockwall"),
    ("Runnels", "Runnels"),
    ("Rusk", "Rusk"),
    ("Sabine", "Sabine"),
    ("San Augustine", "San Augustine"),
    ("San Jacinto", "San Jacinto"),
    ("San Patricio", "San Patricio"),
    ("San Saba", "San Saba"),
    ("Schleicher", "Schleicher"),
    ("Scurry", "Scurry"),
    ("Shackelford", "Shackelford"),
    ("Shelby", "Shelby"),
    ("Sherman", "Sherman"),
    ("Smith", "Smith"),
    ("Somervell", "Somervell"),
    ("Starr", "Starr"),
    ("Stephens", "Stephens"),
    ("Sterling", "Sterling"),
    ("Stonewall", "Stonewall"),
    ("Sutton", "Sutton"),
    ("Swisher", "Swisher"),
    ("Tarrant", "Tarrant"),
    ("Taylor", "Taylor"),
    ("Terrell", "Terrell"),
    ("Terry", "Terry"),
    ("Throckmorton", "Throckmorton"),
    ("Titus", "Titus"),
    ("Tom Green", "Tom Green"),
    ("Travis", "Travis"),
    ("Trinity", "Trinity"),
    ("Tyler", "Tyler"),
    ("Upshur", "Upshur"),
    ("Upton", "Upton"),
    ("Uvalde", "Uvalde"),
    ("Val Verde", "Val Verde"),
    ("Van Zandt", "Van Zandt"),
    ("Victoria", "Victoria"),
    ("Walker", "Walker"),
    ("Waller", "Waller"),
    ("Ward", "Ward"),
    ("Washington", "Washington"),
    ("Webb", "Webb"),
    ("Wharton", "Wharton"),
    ("Wheeler", "Wheeler"),
    ("Wichita", "Wichita"),
    ("Wilbarger", "Wilbarger"),
    ("Willacy", "Willacy"),
    ("Williamson", "Williamson"),
    ("Wilson", "Wilson"),
    ("Winkler", "Winkler"),
    ("Wise", "Wise"),
    ("Wood", "Wood"),
    ("Yoakum", "Yoakum"),
    ("Young", "Young"),
    ("Zapata", "Zapata"),
    ("Zavala", "Zavala"),
]


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property

        fields = [
            "street_address",
            "unit_number",
            "city",
            "state",
            "zip_code",
            "county",
            "subdivision",
            "property_type",
            "property_type_other",
            "year_built",
            "bedrooms",
            "bathrooms_full",
            "bathrooms_half",
            "sqft",
            "lot_size_sqft",
            "latitude",
            "longitude",
            "management_status",
            "is_multi_unit",
            "notes",
        ]

        widgets = {
            "street_address": forms.TextInput(
                attrs={"class": "form-control"}
            ),

            "unit_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "1602, A, Suite B, etc.",
                }
            ),

            "city": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "list": "texas-city-list",
                    "autocomplete": "off",
                    "placeholder": "Start typing a city",
                }
            ),

            "state": forms.Select(
                choices=[("", "Select State")] + US_STATE_CHOICES,
                attrs={"class": "form-control"}
            ),

            "zip_code": forms.TextInput(
                attrs={"class": "form-control"}
            ),

            "county": forms.Select(
                choices=[("", "Select County")] + TEXAS_COUNTY_CHOICES,
                attrs={"class": "form-control"}
            ),

            "subdivision": forms.TextInput(
                attrs={"class": "form-control"}
            ),

            "property_type": forms.Select(
                attrs={"class": "form-control"}
            ),

            "property_type_other": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Describe other property type",
                }
            ),

            "year_built": forms.NumberInput(
                attrs={"class": "form-control"}
            ),

            "bedrooms": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "step": "1",
                }
            ),

            "bathrooms_full": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "step": "1",
                }
            ),

            "bathrooms_half": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "step": "1",
                }
            ),

            "sqft": forms.NumberInput(
                attrs={"class": "form-control"}
            ),

            "lot_size_sqft": forms.NumberInput(
                attrs={"class": "form-control"}
            ),

            "latitude": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "any",
                }
            ),

            "longitude": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "any",
                }
            ),

            "management_status": forms.Select(
                attrs={"class": "form-control"}
            ),

            "is_multi_unit": forms.CheckboxInput(),

            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                }
            ),
        }


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # New properties should require an intentional State and County
        # selection. Existing properties retain their saved values.
        if not self.instance.pk:
            self.fields["state"].initial = ""
            self.fields["county"].initial = ""

        # City suggestions are passed to the template's datalist. The field
        # remains editable so valid Texas localities not in the suggestion
        # list can still be entered.
        self.fields["city"].widget.attrs["data-texas-cities"] = "|".join(
            TEXAS_CITY_SUGGESTIONS
        )

        # Core property facts must be explicitly entered.
        required_fields = [
            "county",
            "subdivision",
            "property_type",
            "bedrooms",
            "bathrooms_full",
            "bathrooms_half",
            "sqft",
        ]

        for field_name in required_fields:
            self.fields[field_name].required = True
            self.fields[field_name].widget.attrs["required"] = "required"

        # Zero is a valid explicit value for bedrooms/bathrooms where applicable.
        self.fields["bedrooms"].widget.attrs["min"] = "0"
        self.fields["bathrooms_full"].widget.attrs["min"] = "0"
        self.fields["bathrooms_half"].widget.attrs["min"] = "0"

        # Square footage must be a positive value.
        self.fields["sqft"].widget.attrs["min"] = "1"


    def clean(self):
        cleaned_data = super().clean()
        property_type = cleaned_data.get("property_type")
        other = (cleaned_data.get("property_type_other") or "").strip()

        if property_type == "other":
            if not other:
                self.add_error(
                    "property_type_other",
                    "Please describe the property type.",
                )
            else:
                cleaned_data["property_type_other"] = other
        else:
            cleaned_data["property_type_other"] = ""

        # Business rule: a Single Family Residential property is always
        # managed as a single rentable property in COL360. Other property
        # types may be configured as multi-unit.
        if property_type == "single_family_residential":
            cleaned_data["is_multi_unit"] = False

        return cleaned_data


class PropertyUnitForm(forms.ModelForm):
    class Meta:
        model = PropertyUnit

        fields = [
            "unit_number",
            "beds",
            "bathrooms_full",
            "bathrooms_half",
            "sqft",
            "market_rent",
            "status",
            "notes",
        ]

        widgets = {
            "unit_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "101, 102, A, B, etc.",
                }
            ),
            "beds": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "1",
                    "min": "0",
                }
            ),
            "bathrooms_full": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "1",
                    "min": "0",
                }
            ),
            "bathrooms_half": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "1",
                    "min": "0",
                }
            ),
            "sqft": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "1",
                }
            ),
            "market_rent": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                }
            ),
            "status": forms.Select(
                attrs={"class": "form-control"}
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                }
            ),
        }

    def __init__(self, *args, property_obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.property_obj = property_obj

        for field_name in [
            "unit_number",
            "beds",
            "bathrooms_full",
            "bathrooms_half",
            "sqft",
        ]:
            self.fields[field_name].required = True
            self.fields[field_name].widget.attrs["required"] = "required"

        # Existing units created before full/half bath fields were added can
        # still be edited cleanly. Use the legacy combined bath value only as
        # an initial display fallback; saving writes the new structured fields.
        if self.instance.pk and self.instance.bathrooms_full is None:
            legacy_baths = self.instance.baths
            if legacy_baths is not None:
                legacy_float = float(legacy_baths)
                self.fields["bathrooms_full"].initial = int(legacy_float)
                self.fields["bathrooms_half"].initial = (
                    1 if legacy_float % 1 else 0
                )

    def clean_unit_number(self):
        unit_number = (
            self.cleaned_data.get("unit_number") or ""
        ).strip()

        if not unit_number:
            raise forms.ValidationError(
                "Unit number is required for a Multi-Unit property."
            )

        if not self.property_obj:
            return unit_number

        existing_units = PropertyUnit.objects.filter(
            property=self.property_obj,
            unit_number=unit_number,
        )

        if self.instance.pk:
            existing_units = existing_units.exclude(
                pk=self.instance.pk
            )

        if existing_units.exists():
            raise forms.ValidationError(
                f'Unit "{unit_number}" already exists for this property.'
            )

        return unit_number

class OwnerProfileForm(forms.ModelForm):
    class Meta:
        model = OwnerProfile

        fields = [
            "owner_type",
            "first_name",
            "last_name",
            "entity_name",
            "email",
            "phone",
            "mailing_address",
            "mailing_city",
            "mailing_state",
            "mailing_zip_code",
            "is_active",
            "notes",
        ]

        widgets = {
            "owner_type": forms.Select(
                attrs={"class": "form-control"}
            ),

            "first_name": forms.TextInput(
                attrs={"class": "form-control"}
            ),

            "last_name": forms.TextInput(
                attrs={"class": "form-control"}
            ),

            "entity_name": forms.TextInput(
                attrs={"class": "form-control"}
            ),

            "email": forms.EmailInput(
                attrs={"class": "form-control"}
            ),

            "phone": forms.TextInput(
                attrs={"class": "form-control"}
            ),

            "mailing_address": forms.TextInput(
                attrs={"class": "form-control"}
            ),

            "mailing_city": forms.TextInput(
                attrs={"class": "form-control"}
            ),

            "mailing_state": forms.TextInput(
                attrs={"class": "form-control"}
            ),

            "mailing_zip_code": forms.TextInput(
                attrs={"class": "form-control"}
            ),

            "is_active": forms.CheckboxInput(),

            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        owner_type = cleaned_data.get("owner_type")
        first_name = cleaned_data.get("first_name")
        last_name = cleaned_data.get("last_name")
        entity_name = cleaned_data.get("entity_name")

        if owner_type == "individual":
            if not first_name:
                self.add_error(
                    "first_name",
                    "First name is required for an individual owner."
                )

            if not last_name:
                self.add_error(
                    "last_name",
                    "Last name is required for an individual owner."
                )

        if owner_type == "entity" and not entity_name:
            self.add_error(
                "entity_name",
                "Entity / company name is required."
            )

        return cleaned_data


class PropertyOwnershipForm(forms.ModelForm):
    class Meta:
        model = PropertyOwnership

        fields = [
            "owner",
            "ownership_percentage",
            "is_primary_contact",
            "start_date",
            "end_date",
            "notes",
        ]

        widgets = {
            "owner": forms.Select(
                attrs={"class": "form-control"}
            ),

            "ownership_percentage": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0.01",
                    "max": "100",
                }
            ),

            "is_primary_contact": forms.CheckboxInput(),

            "start_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "end_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                }
            ),
        }

    def __init__(self, *args, property_obj=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.property_obj = property_obj

        self.fields["owner"].queryset = (
            OwnerProfile.objects
            .filter(is_active=True)
            .order_by(
                "last_name",
                "first_name",
                "entity_name",
            )
        )

    def clean(self):
        cleaned_data = super().clean()

        owner = cleaned_data.get("owner")
        percentage = cleaned_data.get("ownership_percentage")

        if percentage is not None:
            if percentage <= 0 or percentage > 100:
                self.add_error(
                    "ownership_percentage",
                    "Ownership percentage must be greater than 0 and no more than 100."
                )

        if self.property_obj and owner:
            existing = PropertyOwnership.objects.filter(
                property=self.property_obj,
                owner=owner,
            )

            if self.instance.pk:
                existing = existing.exclude(
                    pk=self.instance.pk
                )

            if existing.exists():
                self.add_error(
                    "owner",
                    "This owner is already linked to this property."
                )

        return cleaned_data    

class TenantProfileForm(forms.ModelForm):
    class Meta:
        model = TenantProfile

        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "date_of_birth",
            "emergency_contact_name",
            "emergency_contact_phone",
            "is_active",
            "notes",
        ]

        widgets = {
            "first_name": forms.TextInput(
                attrs={"class": "form-control"}
            ),

            "last_name": forms.TextInput(
                attrs={"class": "form-control"}
            ),

            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "email",
                    "placeholder": "name@example.com",
                }
            ),

            "phone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "inputmode": "tel",
                    "autocomplete": "tel",
                    "placeholder": "512-555-0101",
                }
            ),

            "date_of_birth": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "emergency_contact_name": forms.TextInput(
                attrs={"class": "form-control"}
            ),

            "emergency_contact_phone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "inputmode": "tel",
                    "placeholder": "512-555-0101",
                }
            ),

            "is_active": forms.CheckboxInput(),

            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Core tenant contact information is required.
        self.fields["email"].required = True
        self.fields["phone"].required = True

    @staticmethod
    def _normalize_us_phone(value, *, required):
        value = (value or "").strip()

        if not value:
            if required:
                raise forms.ValidationError(
                    "Phone number is required."
                )
            return ""

        # Allow common U.S. presentation characters, but reject letters
        # or other unexpected content before normalizing.
        if not re.fullmatch(r"[0-9+()\-\.\s]+", value):
            raise forms.ValidationError(
                "Enter a valid U.S. phone number."
            )

        digits = re.sub(r"\D", "", value)

        # Accept an optional leading U.S. country code.
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]

        if len(digits) != 10:
            raise forms.ValidationError(
                "Enter a 10-digit U.S. phone number."
            )

        # NANP numbers cannot have 0 or 1 as the first digit of the
        # area code or central-office code.
        if digits[0] in "01" or digits[3] in "01":
            raise forms.ValidationError(
                "Enter a valid U.S. phone number."
            )

        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()

        if not email:
            raise forms.ValidationError(
                "Email address is required."
            )

        # Django's EmailField/model validation handles email syntax.
        return email

    def clean_phone(self):
        return self._normalize_us_phone(
            self.cleaned_data.get("phone"),
            required=True,
        )

    def clean_emergency_contact_phone(self):
        return self._normalize_us_phone(
            self.cleaned_data.get("emergency_contact_phone"),
            required=False,
        )

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get("date_of_birth")

        if dob and dob > date.today():
            raise forms.ValidationError(
                "Date of birth cannot be in the future."
            )

        return dob

class LeaseForm(forms.ModelForm):
    property = forms.ModelChoiceField(
        queryset=Property.objects.none(),
        required=False,
        empty_label="Select property",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    primary_tenant = forms.ModelChoiceField(
        queryset=TenantProfile.objects.none(),
        required=False,
        empty_label="Select primary tenant",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    co_tenants = forms.ModelMultipleChoiceField(
        queryset=TenantProfile.objects.none(),
        required=False,
        widget=forms.SelectMultiple(
            attrs={"class": "form-control", "size": "5"}
        ),
    )

    class Meta:
        model = Lease

        fields = [
            "unit",
            "start_date",
            "end_date",
            "monthly_rent",
            "security_deposit",
            "status",
            "signed_date",
            "move_in_date",
            "move_out_date",
            "notes",
        ]

        widgets = {
            "unit": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),

            "start_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                    "min": "1900-01-01",
                    "max": "2100-12-31",
                },
                format="%Y-%m-%d",
            ),

            "end_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                    "min": "1900-01-01",
                    "max": "2100-12-31",
                },
                format="%Y-%m-%d",
            ),

            "monthly_rent": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0.01",
                    "inputmode": "decimal",
                    "placeholder": "0.00",
                }
            ),

            "security_deposit": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                    "inputmode": "decimal",
                    "placeholder": "0.00",
                }
            ),

            "status": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),

            "signed_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                    "min": "1900-01-01",
                    "max": "2100-12-31",
                },
                format="%Y-%m-%d",
            ),

            "move_in_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                    "min": "1900-01-01",
                    "max": "2100-12-31",
                },
                format="%Y-%m-%d",
            ),

            "move_out_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                    "min": "1900-01-01",
                    "max": "2100-12-31",
                },
                format="%Y-%m-%d",
            ),

            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                }
            ),
        }

    def __init__(
        self,
        *args,
        locked_unit=None,
        include_tenants=False,
        require_active_property=False,
        generic_property_select=False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.locked_unit = locked_unit
        self.include_tenants = include_tenants
        self.require_active_property = require_active_property
        self.generic_property_select = generic_property_select

        if generic_property_select:
            self.fields["property"].required = True
            self.fields["property"].queryset = (
                Property.objects
                .filter(management_status="active", units__isnull=False)
                .distinct()
                .order_by("street_address", "unit_number")
            )

            # Single-unit properties are resolved server-side. Multi-unit
            # properties reveal this selector and are validated in clean().
            self.fields["unit"].required = False
            self.fields["unit"].queryset = (
                PropertyUnit.objects
                .filter(property__management_status="active")
                .select_related("property")
                .order_by("property__street_address", "unit_number")
            )
        else:
            # Keep all existing locked-unit, renewal and edit workflows intact.
            self.fields.pop("property", None)

        # Foundation authorization rule: new leases may only be created
        # for properties that are under Active management.
        if (
            require_active_property
            and not locked_unit
            and not generic_property_select
        ):
            self.fields["unit"].queryset = (
                PropertyUnit.objects
                .filter(property__management_status="active")
                .select_related("property")
                .order_by("property__street_address", "unit_number")
            )

        if include_tenants:
            self.fields["primary_tenant"].required = True

            unavailable_tenant_ids = (
                LeaseTenant.objects
                .filter(
                    lease__status__in=[
                        "pending",
                        "active",
                        "notice",
                    ]
                )
                .values_list("tenant_id", flat=True)
            )

            available_tenants = (
                TenantProfile.objects
                .filter(is_active=True)
                .exclude(id__in=unavailable_tenant_ids)
                .order_by("last_name", "first_name")
            )

            self.fields["primary_tenant"].queryset = available_tenants
            self.fields["co_tenants"].queryset = available_tenants
        else:
            self.fields.pop("primary_tenant", None)
            self.fields.pop("co_tenants", None)

        # Browser date inputs submit dates as YYYY-MM-DD.
        for field_name in [
            "start_date",
            "end_date",
            "signed_date",
            "move_in_date",
            "move_out_date",
        ]:
            self.fields[field_name].input_formats = [
                "%Y-%m-%d",
            ]

        # When the lease is launched from a specific property/unit,
        # lock the unit server-side and render it only as a hidden value.
        if locked_unit:
            self.fields["unit"].queryset = (
                PropertyUnit.objects.filter(pk=locked_unit.pk)
            )

            self.fields["unit"].initial = locked_unit.pk
            self.fields["unit"].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()

        unit = cleaned_data.get("unit")
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        monthly_rent = cleaned_data.get("monthly_rent")
        security_deposit = cleaned_data.get("security_deposit")
        status = cleaned_data.get("status")
        signed_date = cleaned_data.get("signed_date")
        move_in_date = cleaned_data.get("move_in_date")
        move_out_date = cleaned_data.get("move_out_date")

        # ----------------------------
        # Date year validation
        # ----------------------------

        date_fields = {
            "start_date": start_date,
            "end_date": end_date,
            "signed_date": signed_date,
            "move_in_date": move_in_date,
            "move_out_date": move_out_date,
        }

        for field_name, date_value in date_fields.items():
            if date_value and (
                date_value.year < 1900
                or date_value.year > 2100
            ):
                self.add_error(
                    field_name,
                    "Year must be a valid 4-digit year between 1900 and 2100.",
                )

        # Never allow a submitted form to change a locked unit.
        if self.locked_unit:
            unit = self.locked_unit
            cleaned_data["unit"] = self.locked_unit

        # ----------------------------
        # Generic Create Lease: Property -> Unit
        # ----------------------------

        if self.generic_property_select:
            property_obj = cleaned_data.get("property")

            if property_obj:
                if property_obj.management_status != "active":
                    self.add_error(
                        "property",
                        "A lease can only be created for a property with Active management status.",
                    )
                    unit = None

                elif property_obj.is_multi_unit:
                    if not unit:
                        self.add_error(
                            "unit",
                            "Select a unit for this multi-unit property.",
                        )
                    elif unit.property_id != property_obj.id:
                        self.add_error(
                            "unit",
                            "The selected unit does not belong to this property.",
                        )
                        unit = None
                    elif not (unit.unit_number or "").strip():
                        self.add_error(
                            "unit",
                            "Select a real rentable unit. Blank internal units cannot be leased from this screen.",
                        )
                        unit = None

                else:
                    single_units = list(
                        PropertyUnit.objects
                        .filter(property=property_obj)
                        .order_by("id")[:2]
                    )

                    if len(single_units) == 1:
                        unit = single_units[0]
                        cleaned_data["unit"] = unit
                    elif len(single_units) == 0:
                        self.add_error(
                            "property",
                            "This property does not have a usable lease unit yet.",
                        )
                        unit = None
                    else:
                        self.add_error(
                            "property",
                            "This single-unit property has multiple internal units. Review the property before creating a lease.",
                        )
                        unit = None

        # ----------------------------
        # Property management authorization
        # ----------------------------

        if (
            self.require_active_property
            and unit
            and unit.property.management_status != "active"
        ):
            self.add_error(
                "unit",
                (
                    "A lease can only be created for a property with Active "
                    "management status. Confirm that an executed Property "
                    "Management Agreement is in place and change the property "
                    "status to Active before creating the lease."
                ),
            )

        # ----------------------------
        # Lease date validation
        # ----------------------------

        if start_date and end_date and end_date <= start_date:
            self.add_error(
                "end_date",
                "Lease end date must be after the start date.",
            )

        # ----------------------------
        # Financial validation
        # ----------------------------

        if monthly_rent is not None and monthly_rent <= 0:
            self.add_error(
                "monthly_rent",
                "Monthly rent must be greater than zero.",
            )

        if security_deposit is not None and security_deposit < 0:
            self.add_error(
                "security_deposit",
                "Security deposit cannot be negative.",
            )

        # ----------------------------
        # Signed date validation
        # ----------------------------

        if signed_date and end_date and signed_date > end_date:
            self.add_error(
                "signed_date",
                "Signed date cannot be after the lease end date.",
            )

        # ----------------------------
        # Move-in / move-out validation
        # ----------------------------

        if move_in_date and start_date and move_in_date < start_date:
            self.add_error(
                "move_in_date",
                "Move-in date cannot be before the lease start date.",
            )

        if move_in_date and end_date and move_in_date > end_date:
            self.add_error(
                "move_in_date",
                "Move-in date cannot be after the lease end date.",
            )

        if move_out_date and start_date and move_out_date < start_date:
            self.add_error(
                "move_out_date",
                "Move-out date cannot be before the lease start date.",
            )

        if move_out_date and end_date and move_out_date > end_date:
            self.add_error(
                "move_out_date",
                "Move-out date cannot be after the lease end date.",
            )

        if move_in_date and move_out_date:
            if move_out_date <= move_in_date:
                self.add_error(
                    "move_out_date",
                    "Move-out date must be after the move-in date.",
                )
                
        # ----------------------------
        # Prevent overlapping leases
        # ----------------------------

        if (
            unit
            and start_date
            and end_date
            and status in ["draft", "pending", "active", "notice"]
        ):
            overlapping = Lease.objects.filter(
                unit=unit,
                status__in=[
                    "draft",
                    "pending",
                    "active",
                    "notice",
                ],
                start_date__lte=end_date,
                end_date__gte=start_date,
            )

            if self.instance.pk:
                overlapping = overlapping.exclude(
                    pk=self.instance.pk
                )

            if overlapping.exists():
                self.add_error(
                    None,
                    (
                        "This property already has a lease that "
                        "overlaps these dates. Please review the "
                        "existing lease before creating another one."
                    ),
                )

        if self.include_tenants:
            primary_tenant = cleaned_data.get("primary_tenant")
            co_tenants = cleaned_data.get("co_tenants")

            if (
                primary_tenant
                and co_tenants is not None
                and co_tenants.filter(pk=primary_tenant.pk).exists()
            ):
                self.add_error(
                    "co_tenants",
                    "The primary tenant cannot also be selected as a co-tenant.",
                )

        return cleaned_data


class ActiveLeaseOperationalForm(forms.ModelForm):
    """
    Controlled edit surface for an executed Active lease.

    Contractual terms are intentionally absent. Active lease amendments will
    use a separate audited workflow instead of silently rewriting the lease.
    """
    change_reason = forms.CharField(
        required=True,
        label="Reason for Change",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Briefly explain why this active lease record is being updated.",
            }
        ),
    )

    class Meta:
        model = Lease
        fields = [
            "move_in_date",
            "move_out_date",
            "notes",
        ]
        widgets = {
            "move_in_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                    "min": "1900-01-01",
                    "max": "2100-12-31",
                },
                format="%Y-%m-%d",
            ),
            "move_out_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                    "min": "1900-01-01",
                    "max": "2100-12-31",
                },
                format="%Y-%m-%d",
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name in ["move_in_date", "move_out_date"]:
            self.fields[field_name].input_formats = ["%Y-%m-%d"]

    def clean(self):
        cleaned_data = super().clean()

        move_in_date = cleaned_data.get("move_in_date")
        move_out_date = cleaned_data.get("move_out_date")

        for field_name, date_value in {
            "move_in_date": move_in_date,
            "move_out_date": move_out_date,
        }.items():
            if date_value and not 1900 <= date_value.year <= 2100:
                self.add_error(
                    field_name,
                    "Year must be a valid 4-digit year between 1900 and 2100.",
                )

        if self.instance and self.instance.pk:
            if move_in_date and move_in_date < self.instance.start_date:
                self.add_error(
                    "move_in_date",
                    "Move-in date cannot be before the lease start date.",
                )

            if move_in_date and move_in_date > self.instance.end_date:
                self.add_error(
                    "move_in_date",
                    "Move-in date cannot be after the lease end date.",
                )

            if move_out_date and move_out_date < self.instance.start_date:
                self.add_error(
                    "move_out_date",
                    "Move-out date cannot be before the lease start date.",
                )

            if move_out_date and move_out_date > self.instance.end_date:
                self.add_error(
                    "move_out_date",
                    "Move-out date cannot be after the lease end date.",
                )

        if move_in_date and move_out_date and move_out_date <= move_in_date:
            self.add_error(
                "move_out_date",
                "Move-out date must be after the move-in date.",
            )

        cleaned_data["change_reason"] = (
            cleaned_data.get("change_reason") or ""
        ).strip()

        return cleaned_data


class LeaseRenewalIntentForm(forms.Form):
    response_date = forms.DateField(
        label="Tenant Response Date",
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        ),
    )

    notice_method = forms.ChoiceField(
        label="Response Method",
        choices=LeaseIntentRecord.METHOD_CHOICES,
        widget=forms.Select(
            attrs={"class": "form-control"}
        ),
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Optional notes about the tenant's renewal intent.",
            }
        ),
    )


class LeaseVacateIntentForm(forms.Form):
    notice_received_date = forms.DateField(
        label="Notice Received Date",
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        ),
    )

    planned_move_out_date = forms.DateField(
        label="Planned Move-Out Date",
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        ),
    )

    notice_method = forms.ChoiceField(
        label="Notice Method",
        choices=LeaseIntentRecord.METHOD_CHOICES,
        widget=forms.Select(
            attrs={"class": "form-control"}
        ),
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Optional notes about the tenant's move-out plans.",
            }
        ),
    )

    def __init__(self, *args, lease=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.lease = lease

    def clean(self):
        cleaned_data = super().clean()

        notice_received_date = cleaned_data.get(
            "notice_received_date"
        )
        planned_move_out_date = cleaned_data.get(
            "planned_move_out_date"
        )

        if (
            notice_received_date
            and planned_move_out_date
            and planned_move_out_date < notice_received_date
        ):
            self.add_error(
                "planned_move_out_date",
                "Planned move-out date cannot be before the notice received date.",
            )

        if (
            self.lease
            and planned_move_out_date
            and planned_move_out_date > self.lease.end_date
        ):
            self.add_error(
                "planned_move_out_date",
                "Planned move-out date cannot be after the lease end date.",
            )

        return cleaned_data

class LeaseTenantForm(forms.ModelForm):
    class Meta:
        model = LeaseTenant

        fields = [
            "tenant",
            "role",
            "is_financially_responsible",
        ]

        widgets = {
            "tenant": forms.Select(
                attrs={"class": "form-control"}
            ),

            "role": forms.Select(
                attrs={"class": "form-control"}
            ),

            "is_financially_responsible": forms.CheckboxInput(),
        }

    def __init__(self, *args, lease=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.lease = lease

        # Tenants already attached to another current lease
        # should not appear in the Add Tenant dropdown.
        unavailable_tenant_ids = (
            LeaseTenant.objects
            .filter(
                lease__status__in=[
                    "pending",
                    "active",
                    "notice",
                ]
            )
            .values_list(
                "tenant_id",
                flat=True,
            )
        )

        available_tenants = (
            TenantProfile.objects
            .filter(is_active=True)
            .exclude(id__in=unavailable_tenant_ids)
        )

        # When editing an existing lease membership,
        # keep that current tenant available in the dropdown.
        if self.instance and self.instance.pk:
            available_tenants = (
                TenantProfile.objects
                .filter(
                    Q(id__in=available_tenants.values("id"))
                    | Q(id=self.instance.tenant_id)
                )
            )

        self.fields["tenant"].queryset = (
            available_tenants
            .order_by(
                "last_name",
                "first_name",
            )
        )

    def clean_tenant(self):
        tenant = self.cleaned_data.get("tenant")

        if not tenant:
            return tenant

        if self.lease:

            # Prevent duplicate membership on this lease.
            existing_same_lease = LeaseTenant.objects.filter(
                lease=self.lease,
                tenant=tenant,
            )

            if self.instance.pk:
                existing_same_lease = existing_same_lease.exclude(
                    pk=self.instance.pk
                )

            if existing_same_lease.exists():
                raise forms.ValidationError(
                    "This tenant is already attached to this lease."
                )

            # Prevent tenant from being attached to another
            # current operational lease.
            other_current_membership = (
                LeaseTenant.objects
                .filter(
                    tenant=tenant,
                    lease__status__in=[
                        "pending",
                        "active",
                        "notice",
                    ],
                )
                .exclude(
                    lease=self.lease
                )
            )

            if self.instance.pk:
                other_current_membership = (
                    other_current_membership.exclude(
                        pk=self.instance.pk
                    )
                )

            conflict = (
                other_current_membership
                .select_related(
                    "lease__unit__property"
                )
                .first()
            )

            if conflict:
                other_lease = conflict.lease

                property_name = (
                    other_lease.unit.property.street_address
                )

                unit_name = (
                    f"Unit {other_lease.unit.unit_number}"
                    if other_lease.unit.unit_number
                    else "Main Unit"
                )

                raise forms.ValidationError(
                    (
                        "This tenant is already attached to "
                        f"a current lease at {property_name} "
                        f"— {unit_name}."
                    )
                )

        return tenant

    def clean(self):
        cleaned_data = super().clean()

        role = cleaned_data.get("role")

        if self.lease and role == "primary":

            existing_primary = LeaseTenant.objects.filter(
                lease=self.lease,
                role="primary",
            )

            if self.instance.pk:
                existing_primary = existing_primary.exclude(
                    pk=self.instance.pk
                )

            if existing_primary.exists():
                self.add_error(
                    "role",
                    "This lease already has a primary tenant."
                )

        return cleaned_data
