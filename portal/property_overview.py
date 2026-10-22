"""Read-only Property 360 presentation using existing lease and accounting readers."""
from collections import defaultdict
from urllib.parse import urlsplit
from django.utils import timezone
from common.models import FormFieldSetting
from accounting.book_models import PropertyBooks
from accounting.book_reports import owner_funds
from .dashboard_data import current_terms


def wording():
    row = FormFieldSetting.objects.get(form_key='property_overview', field_key='ui')
    return row.option_labels


def build_overview(prop, unit_rows, current_leases, requests, work_orders, today=None):
    today = today or timezone.localdate()
    ui = wording()
    rows = list(unit_rows)
    active = [r for r in rows if r['unit'].status != 'inactive']
    occupied = sum(bool(r['current_lease']) for r in active)
    unconfirmed = any(not r['current_lease'] and r['unit'].status in ('occupied', 'notice') for r in active)
    multi = prop.is_multi_unit or len(rows) > 1
    if not active:
        occupancy = ui['not_configured']
    elif unconfirmed:
        occupancy = ui['unconfirmed']
    elif multi:
        occupancy = f'{occupied} / {len(active)} {ui["occupied"]}'
    else:
        occupancy = ui['occupied'] if occupied else ui['vacant']
        if not occupied and active[0]['upcoming_lease']:
            occupancy += ' · ' + ui['upcoming']
    single = rows[0]['unit'] if len(rows) == 1 else None
    for lease in current_leases:
        lease.overview_terms = current_terms(lease, today)
    image = getattr(prop, ui.get('image_field', 'main_image_url'), '') or ''
    try:
        if not isinstance(image, str) or urlsplit(image).scheme not in ('http', 'https'):
            image = ''
    except ValueError:
        image = ''
    marketing = getattr(prop, 'marketing_defaults', None)
    manager = (getattr(marketing, 'assigned_manager_name', '') or getattr(marketing, 'assigned_manager', None)) if marketing else None
    instructions = getattr(marketing, 'showing_instructions', '') if marketing else ''
    config = PropertyBooks.objects.select_related('entity', 'operating_bank', 'deposit_bank').filter(property=prop).first()
    funds = owner_funds(config, today) if config else None
    banking = []
    if config:
        for key in ['operating_bank', 'deposit_bank']:
            bank = getattr(config, key)
            banking.append({'label': ui[key], 'bank': bank, 'active': bank.is_active if bank else False})
    grouped = defaultdict(list)
    orphaned = []
    for order in work_orders:
        if order.maintenance_request_id:
            grouped[order.maintenance_request_id].append(order)
        else:
            orphaned.append(order)
    maintenance = []
    for item in requests:
        maintenance.append({'request': item, 'work_orders': grouped.pop(item.pk, [])})
    # Keep direct work orders and requests beyond the preview accessible, rather
    # than silently dropping them while merging the two displays.
    for orders in grouped.values():
        maintenance.append({'request': orders[0].maintenance_request, 'work_orders': orders})
    return {'ui': ui, 'single_unit': single, 'show_units': multi, 'occupancy': occupancy,
            'image': image, 'funds': funds, 'config': config, 'banking': banking,
            'maintenance': maintenance, 'standalone_work_orders': orphaned,
            'current_count': len(current_leases), 'manager': manager, 'instructions': instructions}
