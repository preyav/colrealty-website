"""Atomic property editor and audit tracking, separate from listing publication."""

from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from common.audit.services import record_event, snapshot, changed_values
from .models import Property, PropertyProfile, PropertyMarketingDefaults, PropertyUnit, PropertyEditorDraft
from .editor_drafts import draft_payload, restore_draft
from .editor_forms import (
    PropertyRecordForm,
    PropertyProfileForm,
    PropertyMarketingForm,
    DocumentLinkFormSet,
    EnergyCertificationFormSet,
    build_sections,
)


def tracked_fields(instance):
    return [
        f.name
        for f in instance._meta.concrete_fields
        if f.name
        not in (
            "id",
            "property",
            "created_at",
            "updated_at",
            "created_by",
            "property_code",
            "access_code",
        )
    ]


def audit_save(request, instance, before, property_id, created):
    after = snapshot(instance, tracked_fields(instance))
    old, new = changed_values(before, after)
    if old or new or created:
        record_event(
            action=(
                "PROPERTY_CREATED"
                if created and isinstance(instance, Property)
                else "PROPERTY_UPDATED"
            ),
            instance=instance,
            actor=request.user,
            request=request,
            old_values=old,
            new_values=new,
            reason="Property profile saved in COL360.",
            property_id=property_id,
        )


def save_children(request, formset, property_obj):
    formset.instance = property_obj
    pending = formset.save(commit=False)
    for obj in formset.deleted_objects:
        record_event(
            action="PROPERTY_UPDATED",
            instance=obj,
            actor=request.user,
            request=request,
            old_values=snapshot(obj, tracked_fields(obj)),
            new_values={},
            reason="Property reference entry removed.",
            property_id=property_obj.pk,
        )
        obj.delete()
    for obj in pending:
        created = not obj.pk
        before = (
            {}
            if created
            else snapshot(type(obj).objects.get(pk=obj.pk), tracked_fields(obj))
        )
        obj.property = property_obj
        obj.save()
        audit_save(request, obj, before, property_obj.pk, created)
    # Attach staged files only when their document reference is committed.
    for form in formset.forms:
        upload = getattr(form, 'document_upload', None)
        if upload is not None and not form.cleaned_data.get('DELETE'):
            upload.property = property_obj
            upload.save(update_fields=['property'])
    formset.save_m2m()


def property_editor(request, property_obj=None):
    creating = property_obj is None
    property_obj = property_obj or Property()
    # Existing edits are locked by the view throughout validation and saving.
    profile = (
        PropertyProfile.objects.filter(property=property_obj).first()
        if property_obj.pk
        else None
    )
    marketing = (
        PropertyMarketingDefaults.objects.filter(property=property_obj).first()
        if property_obj.pk
        else None
    )
    profile = profile or PropertyProfile(property=property_obj)
    marketing = marketing or PropertyMarketingDefaults(property=property_obj)
    instances = (property_obj, profile, marketing)
    before = [snapshot(obj, tracked_fields(obj)) if obj.pk else {} for obj in instances]
    old_access_code = marketing.access_code
    draft = PropertyEditorDraft.objects.filter(created_by=request.user, property=property_obj if property_obj.pk else None).first()
    if request.method == 'POST' and request.POST.get('save_action') == 'incomplete':
        if draft is None:
            draft = PropertyEditorDraft(created_by=request.user, property=property_obj if property_obj.pk else None)
        draft.payload = draft_payload(request.POST)
        draft.save()
        messages.success(request, 'Saved as incomplete. Your draft will reopen here; the property record has not been updated.')
        return redirect(request.path)
    draft_data = None
    if request.method != 'POST' and draft:
        from django.http import QueryDict
        draft_data = QueryDict('', mutable=True)
        for key, values in draft.payload.items():
            draft_data.setlist(key, values)
    post = request.POST if request.method == "POST" else None
    core = PropertyRecordForm(post, instance=property_obj)
    pf = PropertyProfileForm(post, instance=profile, prefix="profile")
    mf = PropertyMarketingForm(post, instance=marketing, prefix="marketing")
    documents = DocumentLinkFormSet(post, instance=property_obj, prefix="documents", form_kwargs={"upload_user": request.user})
    certifications = EnergyCertificationFormSet(
        post, instance=property_obj, prefix="certifications"
    )
    if draft_data is not None:
        documents = DocumentLinkFormSet(draft_data, instance=property_obj, prefix='documents', form_kwargs={'upload_user': request.user})
        certifications = EnergyCertificationFormSet(draft_data, instance=property_obj, prefix='certifications')
    forms = (core, pf, mf, documents, certifications)
    if draft_data is not None:
        restore_draft(forms, draft.payload)
    for editor_form in (core, pf, mf):
        for field in editor_form.fields.values():
            if field.required:
                label = str(field.label or "This field").split(" (max", 1)[0].strip()
                field.error_messages["required"] = label + " is required."
    valid = [form.is_valid() for form in forms] if post is not None else []
    if valid and all(valid):
        with transaction.atomic():
            property_obj = core.save(commit=False)
            if creating:
                property_obj.created_by = request.user
            property_obj.save()
            audit_save(request, property_obj, before[0], property_obj.pk, creating)
            for form, old in ((pf, before[1]), (mf, before[2])):
                obj = form.save(commit=False)
                created = not obj.pk
                obj.property = property_obj
                obj.save()
                audit_save(request, obj, old, property_obj.pk, created)
            if old_access_code != marketing.access_code:
                record_event(
                    action="PROPERTY_UPDATED",
                    instance=marketing,
                    actor=request.user,
                    request=request,
                    old_values={"access_code": "[redacted]"},
                    new_values={"access_code": "[redacted]"},
                    reason="Staff access code changed.",
                    property_id=property_obj.pk,
                )
            if not property_obj.is_multi_unit:
                unit, _ = PropertyUnit.objects.get_or_create(property=property_obj)
                unit_before = snapshot(unit, tracked_fields(unit))
                unit.unit_number = property_obj.unit_number
                unit.beds = property_obj.bedrooms
                unit.bathrooms_full = property_obj.bathrooms_full
                unit.bathrooms_half = property_obj.bathrooms_half
                unit.baths = (property_obj.bathrooms_full or 0) + (
                    property_obj.bathrooms_half or 0
                ) / 2
                unit.sqft = property_obj.sqft
                unit.save()
                audit_save(request, unit, unit_before, property_obj.pk, False)
            save_children(request, documents, property_obj)
            save_children(request, certifications, property_obj)
            if draft:
                draft.delete()
        messages.success(request, "Property profile saved successfully.")
        return redirect("portal:properties")
    return render(
        request,
        "portal/property_form.html",
        {
            "incomplete_draft": draft,
            "form": core,
            "profile_form": pf,
            "marketing_form": mf,
            "property_sections": build_sections(core, pf, mf),
            "occupancy_summary": occupancy_summary(property_obj),
            "document_formset": documents,
            "certification_formset": certifications,
            "property_obj": None if creating else property_obj,
            "page_heading": "Add Property" if creating else "Edit Property",
            "submit_label": "Create Property" if creating else "Save Changes",
            "section": "properties",
        },
    )


def occupancy_summary(property_obj):
    """Read existing unit state; opening or saving the editor never changes it."""
    if not property_obj.pk:
        return []
    counts = {}
    for status in property_obj.units.values_list("status", flat=True):
        counts[status] = counts.get(status, 0) + 1
    return [
        {"label": label, "count": counts[code]}
        for code, label in PropertyUnit.STATUS_CHOICES
        if counts.get(code)
    ]
