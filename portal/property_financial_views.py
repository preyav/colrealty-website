from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404,render,redirect
from django.views.decorators.http import require_http_methods
from properties.models import Property
from portal.templatetags.lease_income import statement_context
from portal.property_registers import labels


@staff_member_required(login_url='/accounts/login/')
@require_http_methods(['GET','POST'])
def property_financials(request,property_id):
    prop=get_object_or_404(Property,pk=property_id)
    from accounting.statement_preferences import StatementRowsForm,wording
    from django.contrib import messages
    from django.urls import reverse
    from urllib.parse import urlencode
    rows_form=None
    if request.method=='POST':
        rows_form=StatementRowsForm(request.POST,user=request.user)
        if rows_form.is_valid():
            rows_form.save(request.user,show_all=request.POST.get('row_action')=='show_all')
            messages.success(request,wording().get('saved',''))
            params={}
            if request.POST.get('income_period') in ('three','six','twelve','year','month'):params['income_period']=request.POST['income_period']
            if request.POST.get('income_basis') in ('cash','accrual'):params['income_basis']=request.POST['income_basis']
            return redirect(reverse('portal:property_financials',args=[prop.pk])+'?'+urlencode(params)+'#property-financials')
    income=statement_context({'request':request},prop)
    if rows_form is not None:
        income['rows_form']=rows_form
    return render(request,'portal/property_financials.html',{'property':prop,'income':income,'ui':labels('property_financials'),'section':'properties','property_financial_active':True})
