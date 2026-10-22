"""Repair the previous reference-only display policy without editing lease records."""
from django.core.management.base import BaseCommand
from django.db import transaction
from common.models import FormFieldSetting
from leasing.lease_sections import SECTIONS, INFORMATION_FIELDS

GROUPS = {
    'parties': ('parties', 'Parties & Occupants'),
    'term': ('term', 'Term & Renewal'),
    'rent': ('payments', 'Rent & Payment'),
    'deposit': ('deposit', 'Security Deposit'),
    'pets': ('pets', 'Pets & Animal Agreement'),
    'utilities': ('utilities', 'Utilities, Occupancy & Parking'),
    'access': ('access', 'Access & Security'),
    'move': ('move', 'Move-in & Move-out'),
    'maintenance': ('maintenance', 'Maintenance Responsibilities'),
    'provisions': ('insurance', 'Insurance & Contract Provisions'),
    'notices': ('contact', 'Notices & Contacts'),
}


class Command(BaseCommand):
    help = 'Restore lease input fields to the configured overview; retain clauses in info icons.'

    @transaction.atomic
    def handle(self, *args, **options):
        restored = 0
        for section, _, _, fields in SECTIONS:
            if section not in GROUPS:
                continue
            group, title = GROUPS[section]
            FormFieldSetting.objects.get_or_create(form_key='lease_summary', field_key='group-'+group, defaults={'label': title})
            for key, label in fields:
                row, _ = FormFieldSetting.objects.get_or_create(form_key='lease_summary',field_key=key,defaults={'label':label,'option_labels':{'section':'reference','format':'text'}})
                policy = dict(row.option_labels)
                if key in INFORMATION_FIELDS:
                    # Used when its normal field anchor is blank, so clauses remain accessible.
                    policy.setdefault('information_group', group)
                elif policy.get('section') == 'reference':
                    policy.update(section='essentials' if section in ('parties','term','rent','deposit') else 'operations')
                    policy.setdefault('subsection', group)
                    restored += 1
                if policy != row.option_labels:
                    row.option_labels = policy
                    row.save(update_fields=['option_labels'])
        self.stdout.write(self.style.SUCCESS(f'Restored {restored} field display settings. Lease values and documents unchanged.'))
