"""Lease form sections and supplemental contractual data."""
from django import forms

SECTIONS = [('overview', 'Lease Overview', ['property', 'unit', 'status'], [('legal_description', 'Legal description'), ('included_non_real_property_items', 'Included non-real-property items')]), ('parties', 'Landlord, Tenants & Occupants', ['primary_tenant', 'co_tenants'], [('landlords', 'Landlords'), ('authorized_landlord_representative', 'Authorized landlord representative'), ('occupants_and_ages', 'Occupants and ages'), ('property_manager_contact', 'Property manager contact'), ('broker_and_license_information', 'Broker and license information')]), ('term', 'Term, Renewal & Termination', ['start_date', 'end_date'], [('occupancy_deadline_days', 'Occupancy deadline (days)'), ('automatic_renewal_terms', 'Automatic renewal terms'), ('primary_term_notice_days', 'Primary-term notice (days)'), ('month_to_month_termination_terms', 'Month-to-month termination terms'), ('rent_increase_notice_days', 'Rent increase notice (days)'), ('renewal_rent_increase_terms', 'Renewal rent increase terms'), ('early_termination_terms', 'Early termination terms'), ('assignment_and_subletting_terms', 'Assignment and subletting terms'), ('tenant_procured_replacement_fee', 'Tenant-procured replacement fee'), ('landlord_procured_replacement_fee', 'Landlord-procured replacement fee')]), ('rent', 'Rent & Payment', ['monthly_rent'], [('first_full_rent_due_date', 'First full rent due date'), ('rent_due_day', 'Rent due day'), ('prorated_rent_amount', 'Prorated rent amount'), ('prorated_rent_due_date', 'Prorated rent due date'), ('payment_methods', 'Payment methods'), ('payment_payee', 'Payment payee'), ('payment_address', 'Payment address'), ('payment_processing_fee_terms', 'Payment processing fee terms'), ('single_monthly_payment_required', 'Single monthly payment required'), ('late_charge_starts_on_day', 'Late charge starts on day'), ('initial_late_charge_amount', 'Initial late charge amount'), ('initial_late_charge_percentage', 'Initial late charge percentage'), ('daily_late_charge_amount', 'Daily late charge amount'), ('maximum_late_charge_days', 'Maximum late charge days'), ('returned_payment_charge', 'Returned payment charge'), ('application_of_funds', 'Application of funds')]), ('deposit', 'Security Deposit', ['security_deposit'], [('deposit_due_date', 'Deposit due date'), ('deposit_payment_methods', 'Deposit payment methods'), ('additional_deposits', 'Additional deposits'), ('deposit_interest_terms', 'Deposit interest terms'), ('refund_notice_days', 'Refund notice (days)'), ('deposit_refund_and_deduction_terms', 'Deposit refund and deduction terms'), ('forwarding_address', 'Forwarding address')]), ('pets', 'Pets & Pet Agreement', [], [('pet_authorization', 'Pet authorization'), ('pet_type', 'Pet type'), ('pet_breed', 'Pet breed'), ('pet_name', 'Pet name'), ('pet_color', 'Pet color'), ('pet_weight', 'Pet weight'), ('pet_age', 'Pet age'), ('pet_gender', 'Pet gender'), ('pet_neutered_status', 'Pet neutered status'), ('pet_declawed_status', 'Pet declawed status'), ('pet_rabies_shots_current', 'Pet rabies shots current'), ('additional_pets_one_animal_per_line_with_description_and_health_status', 'Additional pets (one animal per line with description and health status)'), ('pet_deposit_amount', 'Pet deposit amount'), ('pet_adjusted_monthly_rent', 'Pet-adjusted monthly rent'), ('non_refundable_pet_fee_amount', 'Non-refundable pet fee amount'), ('unauthorized_pet_initial_charge', 'Unauthorized pet initial charge'), ('unauthorized_pet_daily_charge', 'Unauthorized pet daily charge'), ('bite_or_injury_history_and_explanation', 'Bite or injury history and explanation'), ('predisposition_to_bite_and_explanation', 'Predisposition to bite and explanation'), ('pet_rules_access_and_liability', 'Pet rules, access and liability'), ('pet_special_provisions', 'Pet special provisions')]), ('utilities', 'Utilities, Occupancy & Parking', [], [('tenant_paid_utilities', 'Tenant-paid utilities'), ('landlord_paid_utilities', 'Landlord-paid utilities'), ('utilities_required_to_remain_connected', 'Utilities required to remain connected'), ('guest_stay_limit_days', 'Guest stay limit (days)'), ('hoa_rules_and_common_area_fees', 'HOA rules and common-area fees'), ('use_and_occupancy_restrictions', 'Use and occupancy restrictions'), ('maximum_vehicles', 'Maximum vehicles'), ('vehicle_details_and_parking_rules', 'Vehicle details and parking rules')]), ('access', 'Access, Keys & Security', [], [('advertising_and_photography_permissions', 'Advertising and photography permissions'), ('entry_and_showing_terms', 'Entry and showing terms'), ('denied_access_trip_charge', 'Denied access trip charge'), ('keybox_authorization', 'Keybox authorization'), ('keybox_period_before_expiry_days', 'Keybox period before expiry (days)'), ('keybox_withdrawal_fee', 'Keybox withdrawal fee'), ('keys_and_access_devices', 'Keys and access devices'), ('locks_and_rekeying_requirements', 'Locks and rekeying requirements'), ('smoke_alarm_requirements', 'Smoke alarm requirements')]), ('move', 'Move-In & Move-Out', ['move_in_date', 'move_out_date'], [('move_in_condition_and_agreed_work', 'Move-in condition and agreed work'), ('condition_report_deadline_days', 'Condition report deadline (days)'), ('condition_report_received_date', 'Condition report received date'), ('move_out_condition_and_cleaning', 'Move-out condition and cleaning'), ('surrender_and_abandonment_terms', 'Surrender and abandonment terms'), ('keys_returned_date', 'Keys returned date'), ('personal_property_left_behind', 'Personal property left behind')]), ('maintenance', 'Maintenance & Repairs', [], [('tenant_maintenance_responsibilities', 'Tenant maintenance responsibilities'), ('landlord_maintenance_responsibilities', 'Landlord maintenance responsibilities'), ('yard_watering_instructions', 'Yard watering instructions'), ('yard_maintenance_responsible_party', 'Yard maintenance responsible party'), ('yard_maintenance_contractor', 'Yard maintenance contractor'), ('pool_and_spa_maintenance', 'Pool and spa maintenance'), ('alteration_restrictions', 'Alteration restrictions'), ('repair_request_instructions', 'Repair request instructions'), ('emergency_repair_contact', 'Emergency repair contact'), ('excluded_repair_items_and_appliances', 'Excluded repair items and appliances'), ('repair_trip_charges', 'Repair trip charges'), ('advance_payments_and_reimbursements', 'Advance payments and reimbursements')]), ('provisions', 'Insurance & Contract Provisions', [], [('renters_insurance_requirement', 'Renters insurance requirement'), ('insurance_proof_received_date', 'Insurance proof received date'), ('liability_terms', 'Liability terms'), ('holdover_rent_multiplier', 'Holdover rent multiplier'), ('default_and_remedies', 'Default and remedies'), ('notice_to_vacate_period_days', 'Notice to vacate period (days)'), ('landlord_lien_and_subordination', 'Landlord lien and subordination'), ('casualty_loss_and_condemnation', 'Casualty loss and condemnation'), ('attorney_fees', 'Attorney fees'), ('representations', 'Representations'), ('agreement_of_parties', 'Agreement of parties'), ('additional_information_and_disclosures', 'Additional information and disclosures')]), ('notices', 'Notices & Contacts', [], [('tenant_notice_address', 'Tenant notice address'), ('tenant_notice_email', 'Tenant notice email'), ('tenant_notice_fax', 'Tenant notice fax'), ('tenant_electronic_notice_consent', 'Tenant electronic notice consent'), ('landlord_notice_recipient', 'Landlord notice recipient'), ('landlord_notice_address', 'Landlord notice address'), ('landlord_notice_email', 'Landlord notice email'), ('landlord_notice_fax', 'Landlord notice fax'), ('landlord_electronic_notice_consent', 'Landlord electronic notice consent'), ('designated_contact_name', 'Designated contact name'), ('designated_contact_phone', 'Designated contact phone'), ('designated_contact_address', 'Designated contact address'), ('designated_contact_email', 'Designated contact email')]), ('documents', 'Documents, Addenda & Signatures', ['signed_date'], [('executed_lease_link', 'Executed lease link'), ('included_addenda_and_exhibits', 'Included addenda and exhibits'), ('special_provisions', 'Special provisions'), ('special_provisions_addendum', 'Special provisions addendum'), ('pet_agreement_link', 'Pet agreement link'), ('condition_report_link', 'Condition report link'), ('other_document_links', 'Other document links'), ('landlord_signatures_and_dates', 'Landlord signatures and dates'), ('tenant_signatures_and_dates', 'Tenant signatures and dates'), ('representative_signature_and_authority', 'Representative signature and authority'), ('broker_associate_and_firm', 'Broker associate and firm'), ('lease_copy_delivered_date', 'Lease copy delivered date'), ('lease_copy_recipient', 'Lease copy recipient'), ('lease_copy_delivery_method', 'Lease copy delivery method')]), ('notes', 'Notes & Change History', ['notes', 'change_reason'], [])]

def supplemental_fields():
    for _, _, _, fields in SECTIONS:
        yield from fields


# Display explanations in popovers; preserve the saved source clauses.
INFORMATION_FIELDS = {'automatic_renewal_terms': 'primary_term_notice_days', 'month_to_month_termination_terms': 'primary_term_notice_days', 'early_termination_terms': 'tenant_procured_replacement_fee', 'assignment_and_subletting_terms': 'landlord_procured_replacement_fee', 'application_of_funds': 'monthly_rent', 'deposit_interest_terms': 'security_deposit', 'deposit_refund_and_deduction_terms': 'refund_notice_days', 'pet_rules_access_and_liability': 'pet_authorization', 'utilities_required_to_remain_connected': 'tenant_paid_utilities', 'hoa_rules_and_common_area_fees': 'guest_stay_limit_days', 'use_and_occupancy_restrictions': 'guest_stay_limit_days', 'vehicle_details_and_parking_rules': 'maximum_vehicles', 'advertising_and_photography_permissions': 'keybox_authorization', 'entry_and_showing_terms': 'denied_access_trip_charge', 'locks_and_rekeying_requirements': 'keys_and_access_devices', 'smoke_alarm_requirements': 'keys_and_access_devices', 'move_out_condition_and_cleaning': 'move_out_date', 'surrender_and_abandonment_terms': 'move_out_date', 'personal_property_left_behind': 'keys_returned_date', 'tenant_maintenance_responsibilities': 'yard_maintenance_responsible_party', 'landlord_maintenance_responsibilities': 'excluded_repair_items_and_appliances', 'alteration_restrictions': 'yard_maintenance_responsible_party', 'repair_request_instructions': 'emergency_repair_contact', 'repair_trip_charges': 'emergency_repair_contact', 'advance_payments_and_reimbursements': 'excluded_repair_items_and_appliances', 'liability_terms': 'renters_insurance_requirement', 'default_and_remedies': 'notice_to_vacate_period_days', 'landlord_lien_and_subordination': 'holdover_rent_multiplier', 'casualty_loss_and_condemnation': 'renters_insurance_requirement', 'attorney_fees': 'notice_to_vacate_period_days', 'representations': 'renters_insurance_requirement', 'agreement_of_parties': 'renters_insurance_requirement'}

FIELD_HELP = {
 'start_date': 'Lease commencement date stated in the signed agreement.',
 'end_date': 'Lease expiration date stated in the signed agreement.',
 'monthly_rent': 'Rent for one full month; enter prorated rent separately.',
 'security_deposit': 'Refundable security deposit stated in the lease; record pet charges separately.',
 'move_in_date': 'Actual move-in date. Do not infer it from the commencement date.',
 'move_out_date': 'Actual move-out date, separate from the scheduled expiration date.',
 'signed_date': 'Date the agreement was executed; verify the signatures in the original document.',
 'primary_term_notice_days': 'Written termination-notice period. A separate renewal-intent requirement may also apply.',
 'renewal_rent_increase_terms': 'Enter the specific agreed increase or formula from the lease or addendum.',
 'pet_age': 'Record the age and its unit as stated in the animal agreement.',
 'change_reason': 'Explain the operational change. This is recorded in the permanent Audit Ledger.',
}

def field_information(name, label, values):
    key = name.removeprefix('contract_')
    description = FIELD_HELP.get(key)
    if not description:
        if key.endswith('_days'):
            description = 'Enter the number of days specified for this requirement in the agreement.'
        elif key.endswith('_date'):
            description = 'Enter the date recorded for this item; leave blank when not specified.'
        elif key.endswith('_link'):
            description = 'Paste the original document link, including a Google Drive link. Access follows the document permissions.'
        else:
            description = 'Record ' + label.lower() + ' from the lease or related record. Leave blank when not specified.'
    information = [{'label': label, 'text': description}]
    labels = dict(supplemental_fields())
    for clause, target in INFORMATION_FIELDS.items():
        if target == key and values.get(clause):
            information.append({'label': labels[clause], 'text': values[clause]})
    return information

class LeaseSectionsMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        protected = bool(self.instance.pk and self.instance.status not in ('draft', 'pending'))
        self.contract_details_protected = protected
        values = self.instance.contract_details or {}
        for key, label in supplemental_fields():
            attrs = {'class': 'form-control'}
            if label.endswith('date'):
                field = forms.DateField(widget=forms.DateInput(attrs={**attrs, 'type': 'date'}, format='%Y-%m-%d'))
            elif any(word in label.lower() for word in ('amount', 'charge', 'fee amount', 'percentage', 'multiplier')) and not any(word in label.lower() for word in ('terms', 'charges')):
                field = forms.DecimalField(min_value=0, max_digits=12, decimal_places=2, widget=forms.NumberInput(attrs={**attrs, 'step': '0.01'}))
            elif label.endswith('(days)') or label in ('Maximum vehicles', 'Rent due day', 'Late charge starts on day'):
                field = forms.IntegerField(min_value=1 if label in ('Rent due day', 'Late charge starts on day') else 0, max_value=31 if label in ('Rent due day', 'Late charge starts on day') else None, widget=forms.NumberInput(attrs=attrs))
            elif label.endswith('link'):
                field = forms.URLField(widget=forms.URLInput(attrs=attrs))
            else:
                field = forms.CharField(widget=forms.Textarea(attrs={**attrs, 'rows': 2}), max_length=10000)
            field.required = False
            field.label = label
            field.disabled = protected
            self.fields['contract_' + key] = field
            self.initial['contract_' + key] = values.get(key, '')

    def save(self, commit=True):
        if not self.contract_details_protected:
            # Validate before mutating the instance; preserve unrelated future keys.
            if not self.is_valid():
                raise ValueError('Cannot save an invalid lease form.')
            values = dict(self.instance.contract_details or {})
            for key, _ in supplemental_fields():
                if key in INFORMATION_FIELDS or 'contract_' + key not in self.data:
                    continue
                value = self.cleaned_data.get('contract_' + key)
                values[key] = '' if value is None else str(value)
            self.instance.contract_details = values
        return super().save(commit=commit)

def build_sections(form=None, lease=None):
    values = (lease.contract_details or {}) if lease else ((form.instance.contract_details or {}) if form else {})
    result = [{'id':'lease-agreement-history','title':'Agreement History','fields':[],'rows':[],'navigation_only':True}] if lease else []
    for sid, title, core, extra in SECTIONS:
        fields = []
        if form:
            fields.extend(form[name] for name in core if name in form.fields)
            fields.extend(form['contract_' + key] for key, _ in extra if key not in INFORMATION_FIELDS and 'contract_' + key in form.fields)
            for field in fields:
                field.field.lease_information = field_information(field.name, field.label, values)
                if field.help_text:
                    field.field.lease_information.append({'label': 'Help', 'text': str(field.help_text)})
        rows = []
        if lease:
            for name in core:
                if name in ('property', 'unit'):
                    value = lease.unit.property if name == 'property' else lease.unit
                elif name == 'status':
                    value = lease.get_status_display()
                elif name in ('primary_tenant', 'co_tenants'):
                    value = ', '.join(str(m.tenant) for m in lease.lease_tenants.all() if (m.role == 'primary') == (name == 'primary_tenant') and m.role != 'occupant')
                elif name == 'change_reason':
                    continue
                else:
                    value = getattr(lease, name, '')
                label = name.replace('_', ' ').title()
                rows.append({'label': label, 'value': value, 'information': field_information(name, label, values)})
            if sid == 'parties':
                rows.append({'label': 'Registered Occupants', 'value': ', '.join(str(m.tenant) for m in lease.lease_tenants.all() if m.role == 'occupant')})
            rows.extend({'label': label, 'value': values.get(key, ''), 'information': field_information(key, label, values)} for key, label in extra if key not in INFORMATION_FIELDS)
        result.append({'id': 'lease-' + sid, 'title': title, 'fields': fields, 'rows': rows})
    return result
