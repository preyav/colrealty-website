from common.models import FormFieldSetting
from django.urls import reverse


def settings():
    return {row.field_key:row for row in FormFieldSetting.objects.filter(form_key='accounting_workspace')}


def workspace_ui():
    row=FormFieldSetting.objects.filter(form_key='accounting_workspace',field_key='ui').first()
    return row.option_labels if row else {}


def navigation():
    ui=workspace_ui()
    destinations={'operations':('accounting_operations',''),'general_ledger':('general_ledger',''),'rent':('rent_overview',''),'financials':('finance_dashboard',''),'banking':('finance_accounts','?view=banking'),
        'bills':('finance_vendor_invoices',''),'chart':('finance_accounts',''),'quickbooks':('finance_quickbooks','')}
    keys=['operations','rent','financials','general_ledger','banking','bills','recurring','eft','budgets','chart','company','tax','quickbooks']
    return [{'key':key,'label':ui.get(key,''),'url':reverse('portal:'+destinations[key][0])+destinations[key][1] if key in destinations else ''} for key in keys]


def configure_form(form,kind):
    rows=settings()
    for name,field in form.fields.items():
        row=rows.get(kind+'_'+name)
        if row:
            field.label=row.label;field.help_text=row.help_text
            if hasattr(field,'choices') and row.option_labels:
                field.choices=[(code,row.option_labels.get(str(code),label)) for code,label in field.choices]
        field.widget.attrs.pop('placeholder',None)
