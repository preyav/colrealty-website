from django.core.management.base import BaseCommand
from common.models import FormFieldSetting


class Command(BaseCommand):
    help = "Initialize editable wording for save-and-add-another owner flows."

    def handle(self, *args, **options):
        FormFieldSetting.objects.get_or_create(form_key="owner_profile", field_key="flow_actions", defaults={
            "label":"Owner entry actions", "option_labels":{
                "save_add_another":"Save & Add Another Owner",
                "add_ownership":"Add Owner to Property",
                "edit_ownership":"Edit Property Ownership",
                "save_ownership":"Save Ownership",
                "save_changes":"Save Changes",
                "back_property":"Back to Property 360",
                "property":"Property", "cancel":"Cancel"}})
        row = FormFieldSetting.objects.get(form_key="owner_profile", field_key="flow_actions")
        labels = dict(row.option_labels)
        labels.setdefault("ownership_from", "Ownership From")
        labels.setdefault("ownership_until", "Ownership Until")
        labels.setdefault("ownership_until_help", "Leave blank while ownership continues.")
        if labels != row.option_labels:
            row.option_labels = labels
            row.save(update_fields=["option_labels"])
        self.stdout.write(self.style.SUCCESS("Owner flow wording initialized; existing edits preserved."))
