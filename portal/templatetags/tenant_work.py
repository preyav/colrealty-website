from django import template
from django.core import signing
from portal.tenant_work import TenantWorkForm,wording,snapshot,eligible_tenants,eligible_owners
register=template.Library()
@register.simple_tag
def tenant_work_labels():return wording()
@register.inclusion_tag('portal/tenant_work_panel.html',takes_context=True)
def tenant_work_panel(context,work_order):
    ui=wording();tenants=eligible_tenants(work_order);owners=eligible_owners(work_order)
    initial={'performer_kind':'owner' if work_order.performer_owner_id else 'tenant','owner':work_order.performer_owner_id,'tenant':work_order.performer_tenant_id,'agreed_cost':work_order.estimated_cost,'terms':work_order.tenant_work_terms,'document':work_order.tenant_work_document,'schedule_confirmed':bool(work_order.is_self_performed and work_order.scheduled_for),'scheduled_for':work_order.scheduled_for if work_order.is_self_performed else None,'expected_completion':work_order.tenant_expected_completion}
    if not initial['tenant'] and tenants.count()==1:initial['tenant']=tenants.first().pk
    if not initial['owner'] and owners.count()==1:initial['owner']=owners.first().pk
    form=TenantWorkForm(work_order=work_order,initial=initial)
    return {'work_order':work_order,'form':form,'ui':ui,'eligible':tenants.exists() or owners.exists(),'csrf_token':context.get('csrf_token'),'version':signing.dumps({'id':work_order.pk,'values':snapshot(work_order)},salt='tenant-work')}
