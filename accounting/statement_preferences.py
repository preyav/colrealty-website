"""Per-user display preferences. These never filter accounting calculations."""
from django.conf import settings
from django.db import models
from django import forms
from common.models import FormFieldSetting


class IncomeStatementPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='income_statement_preference')
    hide_empty = models.BooleanField(default=True)
    hidden_account_ids = models.JSONField(default=list, blank=True)


def wording():
    row = FormFieldSetting.objects.filter(form_key='income_statement_rows', field_key='ui').first()
    return row.option_labels if row else {}


class StatementRowsForm(forms.Form):
    hide_empty = forms.BooleanField(required=False)
    accounts = forms.MultipleChoiceField(required=False, widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, user, **kwargs):
        from .models import ChartAccount
        ui = wording()
        preference = IncomeStatementPreference.objects.filter(user=user).first()
        accounts = list(ChartAccount.objects.filter(account_type__in=['income', 'expense']).order_by('account_type', 'code', 'name', 'pk'))
        hidden = set(str(pk) for pk in preference.hidden_account_ids) if preference else set()
        initial = {'hide_empty': preference.hide_empty if preference else ui.get('default_hide_empty', '1') == '1',
                   'accounts': [str(a.pk) for a in accounts if str(a.pk) not in hidden]}
        super().__init__(*args, initial=initial, **kwargs)
        self.account_rows = accounts
        self.fields['hide_empty'].label = ui.get('hide_empty', '')
        self.fields['accounts'].label = ui.get('customize', '')
        self.fields['accounts'].choices = [(str(a.pk), a.name) for a in accounts]
        self.groups = []
        widgets = {str(widget.data['value']): widget for widget in self['accounts']}
        for kind in ['income', 'expense']:
            self.groups.append({'title': ui.get(kind, ''), 'options': [widgets[str(a.pk)] for a in accounts if a.account_type == kind]})

    def save(self, user, show_all=False):
        selected = set(self.cleaned_data['accounts'])
        ids = [a.pk for a in self.account_rows]
        return IncomeStatementPreference.objects.update_or_create(user=user, defaults={
            'hide_empty': False if show_all else self.cleaned_data['hide_empty'],
            'hidden_account_ids': [] if show_all else [pk for pk in ids if str(pk) not in selected],
        })[0]


def apply_display(report, user):
    """Filter only final account rows, after all totals and drill-downs are built."""
    ui = wording()
    preference = IncomeStatementPreference.objects.filter(user=user).first()
    hidden = set(str(pk) for pk in preference.hidden_account_ids) if preference else set()
    hide_empty = preference.hide_empty if preference else ui.get('default_hide_empty', '1') == '1'
    hidden_activity = 0; hidden_empty = 0
    for item in report['properties']:
        for section in item['sections']:
            visible = []
            for row in section['accounts']:
                activity = bool(row['transactions'])
                if str(row['account'].pk) in hidden or (hide_empty and not activity):
                    if activity: hidden_activity += 1
                    else: hidden_empty += 1
                else:
                    visible.append(row)
            section['accounts'] = visible
    return {'hidden_activity': hidden_activity, 'hidden_empty': hidden_empty, 'hide_empty': hide_empty}
