"""Read-only PM dashboard. Existing workflow views remain the write boundary."""
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Case, When, Value, IntegerField
from django.urls import reverse
from django.utils import timezone
from common.models import FormFieldSetting
from common.audit.models import AuditEvent
from properties.models import Property, PropertyUnit
from leasing.models import Lease
from leasing.agreement_history import agreement_history
from maintenance.models import MaintenanceRequest, WorkOrder, VendorAssignment, VendorInvoice


def link(name, **query):
    if name in ('maintenance', 'work_orders', 'finance_vendor_invoices'):
        query.setdefault('managed', '1')
    url = reverse('portal:' + name)
    return url + ('?' + urlencode(query) if query else '')


def detail(name, key, value):
    return reverse('portal:' + name, kwargs={key: value})


def current_terms(lease, today):
    return agreement_history(lease, as_of=today)['recorded_terms']


def covers_today(lease, today, terms=None):
    terms = terms or current_terms(lease, today)
    return (lease.status in ('active', 'notice') and lease.start_date <= today <= terms['expiration_date']
            and (not lease.move_out_date or lease.move_out_date > today))


def configured_ui():
    rows = {row.field_key: row for row in FormFieldSetting.objects.filter(form_key='pm_dashboard')}
    if 'ui' not in rows:
        raise ImproperlyConfigured('Run python manage.py seed_pm_dashboard before opening the dashboard.')
    ui = rows['ui'].option_labels
    return ui, rows


def build_dashboard(request, today=None):
    today = today or timezone.localdate()
    now = timezone.now()
    ui, settings = configured_ui()
    limit = max(1, min(10, int(ui['row_limit'])))
    windows = (int(ui['window_short']), int(ui['window_medium']), int(ui['window_long']))
    chosen = request.GET.get('window', str(windows[0]))
    days = int(chosen) if chosen in {str(x) for x in windows} else windows[0]
    props = Property.objects.filter(management_status='active')
    units = list(PropertyUnit.objects.filter(property__management_status='active').exclude(status='inactive').select_related('property'))
    leases = list(Lease.objects.filter(unit__property__management_status='active').select_related('unit__property').prefetch_related('agreements'))
    current, expiry, starts = [], [], []
    for lease in leases:
        terms = current_terms(lease, today)
        lease.dashboard_terms = terms
        if covers_today(lease, today, terms):
            current.append(lease)
        if lease.status in ('active', 'notice') and not (lease.move_out_date and lease.move_out_date <= today):
            if today <= terms['expiration_date'] <= today + timedelta(days=days):
                expiry.append(lease)
        if lease.status in ('pending', 'active') and today < lease.start_date <= today + timedelta(days=windows[-1]):
            starts.append(lease)
    expiry.sort(key=lambda x:(x.dashboard_terms['expiration_date'], x.pk))
    starts.sort(key=lambda x:(x.start_date, x.pk))
    occupied_ids = {x.unit_id for x in current}
    occupied = sum(x.pk in occupied_ids for x in units)
    vacant = [u for u in units if u.pk not in occupied_ids and u.status == 'vacant']
    unconfirmed = [u for u in units if u.pk not in occupied_ids and u.status in ('occupied', 'notice')]
    conflicts = len(current) - len(occupied_ids)
    requests = MaintenanceRequest.objects.filter(unit__property__management_status='active').exclude(status__in=['completed','cancelled','declined','converted'])
    work = WorkOrder.objects.filter(unit__property__management_status='active').exclude(status__in=['completed','cancelled'])
    unassigned = work.exclude(vendor_assignments__status__in=['assigned','accepted','scheduled','completed'])
    overdue_work = work.filter(scheduled_for__lt=now, status__in=['assigned','scheduled'])
    invoices = list(VendorInvoice.objects.filter(work_order__unit__property__management_status='active').exclude(status='void').select_related('vendor','work_order__unit__property').prefetch_related('payments').order_by('due_date','pk'))
    awaiting = [i for i in invoices if i.status in ('submitted','disputed')]
    unpaid = [i for i in invoices if i.status in ('approved','partially_paid') and i.outstanding_amount > 0]
    overdue_bills = [i for i in unpaid if i.due_date and i.due_date < today]
    from accounting.rent_services import portfolio_rent_data, wording
    rent = portfolio_rent_data(today=today)
    rent_ui = wording()
    bill_total = sum((i.outstanding_amount for i in unpaid), Decimal('0'))
    urgent = list(requests.filter(priority__in=['emergency','high']).select_related('unit__property').order_by(Case(When(priority='emergency', then=Value(0)), default=Value(1), output_field=IntegerField()), 'submitted_at','pk')[:limit])
    urgent.sort(key=lambda x:0 if x.priority=='emergency' else 1)
    def row(title, meta, url, badge='', tone=''):
        return {'title':title, 'meta':meta, 'url':url, 'badge':badge, 'tone':tone}
    def metric(label, value, url=None):
        return {'label':label, 'value':value, 'url':url}
    def lease_row(lease, date):
        return row(str(lease.unit), date, detail('lease_detail','lease_id',lease.pk))
    attention_rows = [row(x.title, str(x.unit), detail('maintenance_detail','request_id',x.pk), x.get_priority_display(), 'urgent') for x in urgent]
    for x in overdue_work.select_related('unit__property').order_by('scheduled_for','pk')[:limit]:
        attention_rows.append(row(x.title, str(x.unit), detail('work_order_detail','work_order_id',x.pk),ui['overdue_schedule'],'urgent'))
    for x in unassigned.select_related('unit__property').order_by('created_at','pk')[:limit]:
        attention_rows.append(row(x.title, str(x.unit), detail('work_order_detail','work_order_id',x.pk),ui['unassigned']))
    for x in overdue_bills[:limit]:
        attention_rows.append(row(str(x.vendor), str(x.work_order.unit), detail('finance_vendor_invoice_detail','invoice_id',x.pk),ui['overdue_bills'],'urgent'))
    for x in awaiting[:limit]:
        attention_rows.append(row(str(x.vendor), str(x.work_order.unit), detail('finance_vendor_invoice_detail','invoice_id',x.pk),x.get_status_display()))
    for u in unconfirmed[:limit]:
        attention_rows.append(row(str(u), ui['occupancy_review'],detail('property_detail','property_id',u.property_id),ui['review']))
    attention_rows = list({item['url']:item for item in attention_rows}.values())
    maint_rows = [row(x.title,str(x.unit),detail('work_order_detail','work_order_id',x.pk),x.get_status_display()) for x in work.select_related('unit__property').order_by('scheduled_for','pk')[:limit]]
    occupancy_rows = [row(str(u),ui['vacant'],detail('property_detail','property_id',u.property_id)) for u in vacant[:limit]]
    occupancy_rows += [lease_row(x,x.start_date) for x in starts[:limit]]
    events = AuditEvent.objects.filter(property_id__in=[str(p.pk) for p in props]).order_by('-occurred_at','-id')[:limit]
    actions = settings.get('activity_actions')
    action_labels = actions.option_labels if actions else {}
    event_rows = []
    for event in events:
        url = detail('property_detail','property_id',event.property_id)
        event_rows.append(row(event.entity_display or event.entity_type, event.occurred_at, url, action_labels.get(event.action,ui['updated'])))
    def card(key, metrics, rows, url):
        config = settings[key]
        return {'key':key,'title':config.label,'help':config.help_text,'metrics':metrics,'rows':rows[:limit], 'url':url}
    cards = [
        card('attention',[
            metric(ui['urgent_requests'],requests.filter(priority__in=['emergency','high']).count(),link('maintenance',queue='urgent')),
            metric(ui['unassigned'],unassigned.count(),link('work_orders',queue='unassigned')),
            metric(ui['bills_review'],len(awaiting),link('finance_vendor_invoices',queue='attention')),
            metric(ui['overdue_schedule'],overdue_work.count(),link('work_orders',queue='overdue')),
            metric(ui['occupancy_review'],len(unconfirmed)+conflicts,link('properties',status='active'))],attention_rows,None),
        card('maintenance',[
            metric(ui['open_requests'],requests.count(),link('maintenance',queue='open')),
            metric(ui['open_work'],work.count(),link('work_orders',queue='open')),
            metric(ui['scheduled'],work.filter(status='scheduled').count(),link('work_orders',queue='scheduled'))],maint_rows,link('work_orders',queue='open')),
        card('expirations',[metric(ui['expiring'],len(expiry),link('leases',dashboard_expiring=days))],
             [lease_row(x,x.dashboard_terms['expiration_date']) for x in expiry[:limit]],link('leases',dashboard_expiring=days)),
        card('billing',[
            metric(rent_ui['rent_outstanding'],f"${rent['totals']['outstanding']:,.2f}",link('rent_overview',managed='1')),
            metric(rent_ui['rent_overdue'],f"${rent['totals']['overdue']:,.2f}",link('rent_overview',managed='1')),
            metric(rent_ui['rent_credit'],f"${rent['totals']['credit']:,.2f}",link('rent_overview',managed='1')),
            metric(ui['approved_unpaid'],f'${bill_total:,.2f}',link('finance_vendor_invoices',queue='outstanding')),
            metric(ui['overdue_bills'],len(overdue_bills),link('finance_vendor_invoices',queue='overdue'))],
             [row(str(x.vendor),str(x.work_order.unit),detail('finance_vendor_invoice_detail','invoice_id',x.pk),f'${x.outstanding_amount:,.2f}') for x in unpaid[:limit]],link('finance_vendor_invoices')),
        card('occupancy',[
            metric(ui['occupied'],occupied),metric(ui['vacant'],len(vacant)),metric(ui['upcoming_starts'],len(starts),link('leases',dashboard_upcoming='1'))],occupancy_rows,link('properties',status='active')),
        card('activity',[],event_rows,None),
    ]
    return {'ui':ui,'cards':cards,'today':today,'window':days,'windows':[{'days':x,'url':link('dashboard',window=x)} for x in windows],
        'summary':[metric(ui['managed_properties'],props.count(),link('properties',status='active')),metric(ui['occupied'],occupied),metric(ui['vacant'],len(vacant)),metric(ui['open_work'],work.count(),link('work_orders',queue='open'))],
        'quick_actions':[{'title':ui['new_request'],'url':link('create_maintenance_request')},{'title':ui['new_lease'],'url':link('create_lease')},{'title':ui['vendor_bills'],'url':link('finance_vendor_invoices')},{'title':rent_ui['ledger_link'],'url':link('rent_overview',managed='1')}],
        'rent_has_entries':rent['has_entries'],'rent_ui':rent_ui,
        'occupancy_rate':round(100*occupied/len(units),1) if units else None,'unit_count':len(units)}
