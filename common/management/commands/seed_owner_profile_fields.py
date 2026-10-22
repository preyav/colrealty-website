from django.core.management.base import BaseCommand
from common.models import FormFieldSetting
from owners.models import OwnerProfile


class Command(BaseCommand):
    help = "Initialize editable owner field labels and action wording; preserve existing settings."

    def handle(self, *args, **options):
        fields = ["owner_type", "first_name", "last_name", "entity_name", "email", "phone", "mailing_address", "mailing_city", "mailing_state", "mailing_zip_code", "is_active", "notes"]
        variants = {
            "first_name": {"individual_label": "Owner First Name", "entity_label": "Contact First Name"},
            "last_name": {"individual_label": "Owner Last Name", "entity_label": "Contact Last Name"},
            "email": {"individual_label": "Owner Email", "entity_label": "Contact Email"},
            "phone": {"individual_label": "Owner Phone", "entity_label": "Contact Phone"},
        }
        for name in fields:
            field = OwnerProfile._meta.get_field(name)
            options = variants.get(name, {})
            if name == "owner_type":
                options = dict(field.choices)
            FormFieldSetting.objects.get_or_create(form_key="owner_profile", field_key=name,
                defaults={"label":str(field.verbose_name).capitalize(), "option_labels":options})
        FormFieldSetting.objects.get_or_create(form_key="owner_profile", field_key="actions", defaults={
            "label":"Owner form actions", "option_labels":{"create":"Add Owner", "edit":"Edit Owner", "save":"Save Changes", "save_add_another":"Save & Add Another", "cancel":"Cancel", "back":"Back to Owners"}})
        self.stdout.write(self.style.SUCCESS("Owner form settings initialized; existing edits preserved."))
