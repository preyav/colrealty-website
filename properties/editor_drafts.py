"""Persist and resume staff-owned incomplete editor inputs."""
from django.http import QueryDict


def draft_payload(post):
    return {key: post.getlist(key) for key in post if key not in ('csrfmiddlewaretoken', 'save_action')}


def restore_form_initial(form, data):
    for name, field in form.fields.items():
        key = form.add_prefix(name)
        if key in data or field.widget.__class__.__name__ == 'CheckboxInput':
            form.initial[name] = field.widget.value_from_datadict(data, {}, key)
    form.is_bound = False
    form._errors = None


def restore_draft(forms, payload):
    data = QueryDict('', mutable=True)
    for key, values in payload.items():
        data.setlist(key, values)
    for item in forms:
        if hasattr(item, 'management_form'):
            # Construct submitted entry counts before switching each form to initial-only display.
            entries = list(item.forms)
            management = item.management_form
            restore_form_initial(management, data)
            for entry in entries:
                restore_form_initial(entry, data)
                entry.draft_active = entry.prefix in payload.get('draft_green_active', [])
            item.is_bound = False
            item._errors = None
            item._non_form_errors = None
        else:
            restore_form_initial(item, data)
