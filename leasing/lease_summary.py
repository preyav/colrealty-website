"""Read-only management overview; original contracts and operational balances are untouched."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from common.models import FormFieldSetting
from .agreement_history import agreement_history
from .lease_sections import INFORMATION_FIELDS


def populated(value):
    return value is not None and (not isinstance(value, str) or bool(value.strip())) and value != [] and value != {}


def summary_settings():
    return {item.field_key: item for item in FormFieldSetting.objects.filter(form_key='lease_summary')}


def summary_navigation():
    ui = summary_settings()
    return [{'id': key, 'title': ui['lease-overview' if key == 'lease-essentials' else 'documents' if key == 'lease-agreement-history' else 'requests_maintenance' if key == 'lease-maintenance-history' else key].label, 'navigation_only': True} for key in
            ('lease-essentials', 'lease-agreement-history', 'lease-maintenance-history', 'lease-activity-history')]


def format_value(value, kind):
    if kind == 'money':
        try:
            return f'${Decimal(str(value)):,.2f}'
        except (InvalidOperation, ValueError):
            return str(value)
    if isinstance(value, (date, datetime)):
        return value.strftime('%b %d, %Y')
    if kind == 'date' and isinstance(value, str):
        try:
            return date.fromisoformat(value).strftime('%b %d, %Y')
        except ValueError:
            pass
    return str(value)


def management_summary(lease, as_of=None):
    ui = summary_settings()
    history = agreement_history(lease, as_of=as_of)
    values = dict(lease.contract_details or {})
    members = list(lease.lease_tenants.all())
    values.update(status=lease.get_status_display(), start_date=lease.start_date,
                  end_date=history['recorded_terms']['expiration_date'],
                  monthly_rent=history['recorded_terms']['monthly_rent'], security_deposit=lease.security_deposit,
                  registered_tenants='; '.join(str(m.tenant) for m in members if m.role != 'occupant'),
                  registered_occupants='; '.join(str(m.tenant) for m in members if m.role == 'occupant'),
                  move_in_date=lease.move_in_date, move_out_date=lease.move_out_date, signed_date=lease.signed_date)
    applicable = [item['agreement'] for item in history['history_items'] if item['applicable']]
    latest = applicable[-1] if applicable else None
    if latest:
        values['latest_named_tenants'] = latest.named_tenants
    for agreement in applicable:
        if agreement.contact_action == 'changed' and agreement.contact_details:
            values['designated_contact_details'] = agreement.contact_details
            for key in ('designated_contact_name', 'designated_contact_phone', 'designated_contact_email', 'designated_contact_address'):
                values.pop(key, None)
    amendments = [a for a in applicable if a.paragraph_references or a.amendment_text]
    values['other_paragraphs'] = '\n'.join(a.title + (' · ' + a.paragraph_references if a.paragraph_references else '') for a in amendments)
    rows = {'essentials': [], 'operations': []}
    ordered = sorted(ui.items(), key=lambda pair: int(pair[1].option_labels.get('position', '9999')) if str(pair[1].option_labels.get('position', '9999')).isdigit() else 9999)
    for key, item in ordered:
        section = item.option_labels.get('section')
        value = values.get(key)
        if section not in rows or item.option_labels.get('subsection') == 'documents' or not populated(value):
            continue
        information = [{'label': item.label, 'text': item.help_text}] if item.help_text else []
        for clause, target in INFORMATION_FIELDS.items():
            if target == key and populated(values.get(clause)):
                clause_setting = ui.get(clause)
                information.append({'label': clause_setting.label if clause_setting else clause, 'text': str(values[clause])})
        if key in ('monthly_rent', 'end_date'):
            source_key = 'rent_source' if key == 'monthly_rent' else 'expiration_source'
            information.append({'label': ui['source'].label, 'text': history['recorded_terms'][source_key]})
        rows[section].append({'key': key, 'label': item.label, 'value': format_value(value, item.option_labels.get('format')), 'information': information, 'subsection':item.option_labels.get('subsection','additional'), 'amendments':[{'id':a.pk,'title':a.title,'text':a.amendment_text} for a in amendments] if key == 'other_paragraphs' else []})
    subsections = {}
    for section, section_rows in rows.items():
        buckets = {}
        for row in section_rows:
            buckets.setdefault(row['subsection'], []).append(row)
        subsections[section] = [{'title':ui.get('group-'+key,ui['group-additional']).label,'rows':items} for key,items in buckets.items()]
    # A clause must remain accessible even when its usual value field is blank.
    visible_keys = {row['key'] for section_rows in rows.values() for row in section_rows}
    for clause, target in INFORMATION_FIELDS.items():
        item = ui.get(clause)
        if not item or not populated(values.get(clause)) or clause in visible_keys or target in visible_keys:
            continue
        group = item.option_labels.get('information_group')
        if not group:
            continue
        title = ui.get('group-'+group, ui['group-additional']).label
        subgroup = next((g for section_groups in subsections.values() for g in section_groups if g['title'] == title), None)
        if subgroup is None:
            subgroup = {'title': title, 'rows': []}
            subsections['operations'].append(subgroup)
        subgroup.setdefault('information', []).append({'label': item.label, 'text': str(values[clause])})
    return {'ui': ui, 'sections': [{'id':'lease-essentials', 'title':ui['lease-overview'].label, 'rows':rows['essentials'] + rows['operations'], 'subsections':subsections['essentials'] + subsections['operations']}],
            'navigation':summary_navigation(), 'history':history}
