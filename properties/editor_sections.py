from .address_fields import ADDRESS_ORDER
from .ownership_choices import OWNERSHIP_CHOICES
"""Shared field groups for the staff property editor and Property 360."""

SECTION_ORDER = ['Ownership & Management',
 'Property Overview',
 'Physical Features & Construction',
 'Utilities, Access & Services',
 'Rules, Associations & Compliance',
 'Documents, Financial Setup & Activity']

CORE_FIELDS = [n for n in ADDRESS_ORDER if n != 'tax_legal_description'] + ['street_address',
 'unit_number',
 'city',
 'state',
 'zip_code',
 'county',
 'subdivision',
 'property_type',
 'property_type_other',
 'management_status',
 'is_multi_unit',
 'year_built',
 'bedrooms',
 'main_level_bedrooms',
 'other_level_beds',
 'bathrooms_full',
 'bathrooms_half',
 'sqft',
 'lot_size_sqft',
 'latitude',
 'longitude']

CORE_SECTIONS = {'Ownership & Management': ['management_status', 'property_type', 'property_type_other'],
 'Property Overview': [n for n in ADDRESS_ORDER if n != 'tax_legal_description'] + ['is_multi_unit', 'latitude', 'longitude', 'main_level_bedrooms', 'other_level_beds', 'bathrooms_full', 'bathrooms_half', 'sqft', 'year_built', 'lot_size_sqft'],
 'Physical Features & Construction': [],
 'Utilities, Access & Services': [],
 'Rules, Associations & Compliance': [],
 'Documents, Financial Setup & Activity': ['notes']}

PROFILE_SECTIONS = {'Ownership & Management': [('occupancy_status',
                             'choice:vacant=Vacant|owner_occupied=Owner '
                             'Occupied|tenant_occupied=Tenant Occupied|other=Other',
                             'Management Status Occupancy'),
                            ('ownership_type',
                             'choice:' + '|'.join(code + '=' + label for code, label in OWNERSHIP_CHOICES),
                             'Ownership Type')],
 'Property Overview': [('tax_legal_description', 'notes', 'Tax Legal Description'),
                       ('level_types', 'notes', 'Levels'),
                       ('living_area_source', 'text', 'Living Area Source'),
                       ('living_areas', 'int', 'Living'),
                       ('dining_areas', 'int', 'Dining'),
                       ('garage_spaces', 'int', 'Garage Spaces'),
                       ('parking_total', 'int', 'Total Parking Spaces'),
                       ('parking_features', 'notes', 'Parking Features'),
                       ('laundry_location', 'notes', 'Laundry Location'),
                       ('direction_faces', 'text', 'Direction Faces'),
                       ('lot_dimensions', 'text', 'Lot Dimensions (Frontage × Depth)'),
                       ('builder_name', 'text', 'Builder Name'),
                       ('school_district', 'text', 'School District'),
                       ('out_of_state_school_district', 'text', 'Out of State School District'),
                       ('elementary_school', 'text', 'Elementary'),
                       ('elementary_school_other', 'text', 'Elementary Other'),
                       ('middle_school', 'text', 'Middle Or Junior'),
                       ('middle_school_other', 'text', 'Middle or Junior Other'),
                       ('high_school', 'text', 'High School'),
                       ('high_school_other', 'text', 'High School Other')],
 'Physical Features & Construction': [('appliances_types', 'notes', 'Appliances'),
                                      ('interior_features', 'notes', 'Interior Features'),
                                      ('exterior_features', 'notes', 'Exterior Features'),
                                      ('flooring', 'notes', 'Flooring'),
                                      ('construction_materials', 'notes', 'Construction Materials'),
                                      ('foundation', 'notes', 'Foundation'),
                                      ('roof', 'notes', 'Roof'),
                                      ('property_condition', 'text', 'Property Condition'),
                                      ('move_in_special_yn',
                                       'choice:yes=Yes|no=No',
                                       'Move in Special YN'),
                                      ('move_in_special_description',
                                       'notes',
                                       'Move in Special Description'),
                                      ('lot_features_types', 'notes', 'Lot Features'),
                                      ('accessibility_features_types',
                                       'notes',
                                       'Accessibility Features'),
                                      ('patio_porch_features', 'notes', 'Patio / Porch Features'),
                                      ('window_features_types', 'multi', 'Window Features'),
                                      ('fencing', 'notes', 'Fencing'),
                                      ('other_structures', 'notes', 'Other Structures'),
                                      ('fireplaces', 'int', 'Fireplaces'),
                                      ('fireplace_features_types', 'notes', 'Fireplace Features'),
                                      ('has_pool', 'tri', 'Private Pool'),
                                      ('pool_features_types', 'notes', 'Pool Features'),
                                      ('spa_features_types', 'notes', 'Spa Features'),
                                      ('waterfront_features', 'notes', 'Waterfront Features'),
                                      ('water_body_name', 'text', 'Water Body Name'),
                                      ('energy_features', 'notes', 'Green Energy Efficient (max 20)'),
                                      ('sustainability_features',
                                       'notes',
                                       'Green Sustainability (max 9)'),
                                      ('solar', 'tri', 'Solar Installed'),
                                      ('solar_ownership',
                                       'choice:owned=Owned|leased=Leased|other=Other',
                                       'Solar Ownership')],
 'Utilities, Access & Services': [('cooling_types', 'notes', 'Cooling'),
                                  ('heating_types', 'notes', 'Heating'),
                                  ('water_source', 'text', 'Water Source'),
                                  ('sewer', 'text', 'Sewer'),
                                  ('utility_services_types', 'notes', 'Available Utility Services'),
                                  ('utility_providers', 'notes', 'Utility Providers / Contacts'),
                                  ('utility_responsibilities',
                                   'notes',
                                   'Utility Service Responsibilities'),
                                  ('security_features_types', 'notes', 'Security Features')],
 'Rules, Associations & Compliance': [('has_hoa', 'tri', 'HOA / Association'),
                                      ('hoa_management_company', 'text', 'HOA Management Company'),
                                      ('association_fee', 'money', 'Association Fee'),
                                      ('association_fee_frequency',
                                       'choice:monthly=Monthly|quarterly=Quarterly|semiannual=Semiannual|annual=Annual|other=Other',
                                       'Fee Frequency'),
                                      ('association_fees_include',
                                       'notes',
                                       'Association Fees Include'),
                                      ('association_requirements',
                                       'notes',
                                       'Association Requirements'),
                                      ('community_website', 'url', 'Community Website'),
                                      ('community_features', 'notes', 'Community Features'),
                                      ('housing_vouchers',
                                       'choice:yes=Yes|no=No',
                                       'Housing Vouchers'),
                                      ('etj', 'text', 'ETJ'),
                                      ('fema_flood_plain_types', 'notes', 'FEMA Flood Plain'),
                                      ('restrictions', 'notes', 'Restrictions'),
                                      ('special_assessment', 'money', 'Special Assessment'),
                                      ('disclosures', 'notes', 'Disclosures')],
 'Documents, Financial Setup & Activity': [('annual_tax_amount', 'money', 'Annual Property Tax'),
                                           ('tax_year', 'year', 'Tax Year'),
                                           ('tax_assessed_value', 'money', 'Tax Assessed Value'),
                                           ('tax_rate', 'rate', 'Tax Rate (%)'),
                                           ('tax_exemptions', 'notes', 'Tax Exemptions')]}

MARKETING_SECTIONS = {'Ownership & Management': [('assigned_manager_name', 'text', 'Assigned Property Manager')],
 'Property Overview': [('listing_agent_name', 'text', 'Listing Agent'),
                       ('co_listing_agent_name', 'text', 'Co-listing Agent'),
                       ('office_notes', 'notes', 'Office / External Agent’s Notes'),
                       ('public_remarks', 'notes', 'Public Description'),
                       ('directions', 'notes', 'Directions'),
                       ('branded_tour_url', 'url', 'Branded Virtual Tour URL'),
                       ('unbranded_tour_url', 'url', 'Unbranded Virtual Tour URL'),
                       ('branded_video_url', 'url', 'Branded Video Tour URL'),
                       ('unbranded_video_url', 'url', 'Unbranded Video Tour URL'),
                       ('listing_detail_url', 'url', 'Listing Detail URL'),
                       ('allow_public_display', 'bool', 'Allow Public Property Display'),
                       ('allow_address_display', 'bool', 'Allow Public Address Display')],
 'Physical Features & Construction': [],
 'Utilities, Access & Services': [('showing_requirements', 'notes', 'Showing Requirements'),
                                  ('showing_contact_name', 'text', 'Showing Contact Name'),
                                  ('showing_contact_phone', 'phone', 'Showing Contact Phone'),
                                  ('showing_contact_email', 'email', 'Showing Contact Email'),
                                  ('lockbox_type', 'text', 'Lockbox Type'),
                                  ('lockbox_serial_number', 'text', 'Lockbox Serial Number'),
                                  ('lockbox_location', 'notes', 'Lockbox Location'),
                                  ('access_code', 'text', 'Access Code (Staff Only)'),
                                  ('showing_instructions', 'notes', 'Showing Instructions')],
 'Rules, Associations & Compliance': [],
 'Documents, Financial Setup & Activity': []}


# Section remarks are stored separately from internal property notes.
PROFILE_SECTIONS['Ownership & Management'].append(('ownership_management_remarks', 'notes', 'Ownership & Management Remarks'))
PROFILE_SECTIONS['Property Overview'].append(('property_overview_remarks', 'notes', 'Property Overview Remarks'))
PROFILE_SECTIONS['Physical Features & Construction'].append(('physical_features_remarks', 'notes', 'Physical Features & Construction Remarks'))
PROFILE_SECTIONS['Utilities, Access & Services'].append(('utilities_services_remarks', 'notes', 'Utilities, Access & Services Remarks'))
PROFILE_SECTIONS['Rules, Associations & Compliance'].append(('rules_compliance_remarks', 'notes', 'Rules & Compliance Remarks'))
PROFILE_SECTIONS['Physical Features & Construction'].append(('green_energy_remarks', 'notes', 'Green Energy Remarks'))

PROFILE_SECTIONS['Physical Features & Construction'].append(('spa', 'choice:yes=Yes|no=No', 'Spa'))

SECTION_ORDER.insert(SECTION_ORDER.index('Rules, Associations & Compliance'), 'How to Apply')
PROFILE_SECTIONS['How to Apply'] = [('application_association_yn', 'choice:yes=Yes|no=No', 'Association YN'), ('application_fee', 'money', 'Application Fee'), ('application_fee_per_person', 'choice:yes=Yes|no=No', 'Application Fee Per Person'), ('application_fee_payable_to', 'text', 'Application Fee Payable To'), ('application_managed_by', 'text', 'Managed By'), ('application_security_deposit', 'money', 'Security Deposit'), ('application_security_deposit_payable_to', 'text', 'Security Deposit Payable To'), ('application_required', 'notes', 'Application Required'), ('application_administration_fee', 'money', 'Administration Fee'), ('application_administration_fee_payable_to', 'text', 'Administration Fee Payable To'), ('application_first_month_rent_payable_to', 'text', 'First Month Rent Payable To'), ('application_renters_insurance_required', 'choice:yes=Yes|no=No', "Renter's Insurance Required"), ('application_short_term_premium', 'choice:yes=Yes|no=No', 'Short Term Premium'), ('application_short_term_premium_amount', 'money', 'Short Term Premium Amount'), ('application_on_site_compliance', 'choice:yes=Yes|no=No', 'On-Site Compliance'), ('application_certified_funds', 'choice:yes=Yes|no=No', 'Certified Funds'), ('application_minimum_lease_months', 'int', 'Minimum Lease Months'), ('application_maximum_lease_months', 'int', 'Maximum Lease Months'), ('application_available_date', 'date', 'Available Date'), ('application_lease_term', 'text', 'Lease Term'), ('application_lease_guarantor_yn', 'choice:yes=Yes|no=No', 'Lease Guarantor YN'), ('application_policy', 'notes', 'Application Policy'), ('application_max_number_of_pets', 'int', 'Max Number of Pets'), ('application_pet_deposit', 'money', 'Pet Deposit'), ('application_pet_deposit_per_pet', 'choice:yes=Yes|no=No', 'Pet Deposit Per Pet'), ('application_monthly_pet_rent', 'money', 'Monthly Pet Rent'), ('application_monthly_pet_rent_per_pet', 'choice:yes=Yes|no=No', 'Monthly Pet Rent Per Pet'), ('application_additional_pet_fee', 'money', 'Additional Pet Fee'), ('application_additional_pet_fee_description', 'notes', 'Additional Pet Fee Description'), ('application_pets_allowed', 'notes', 'Pets Allowed'), ('application_one_time_expenses', 'notes', 'One Time Expenses'), ('application_recurring_expenses', 'notes', 'Recurring Expenses'), ('application_deliver_address', 'text', 'Application Deliver Address'), ('application_public_link', 'url', 'Website App Link/Public View'), ('application_agent_link', 'url', 'Website App Link/Agent View'), ('application_rentspree_online_yn', 'choice:yes=Yes|no=No', 'RentSpree Online Application YN'), ('application_owner_contributions_yn', 'choice:yes=Yes|no=No', 'Owner Contributions YN'), ('application_intermediary_yn', 'choice:yes=Yes|no=No', 'Intermediary YN')]
_utility_top = ['utility_services_types', 'utility_providers', 'utility_responsibilities', 'security_features_types']
_utility_fields = PROFILE_SECTIONS['Utilities, Access & Services']
PROFILE_SECTIONS['Utilities, Access & Services'] = [next(item for item in _utility_fields if item[0] == n) for n in _utility_top] + [item for item in _utility_fields if item[0] not in _utility_top]
PROFILE_SECTIONS['Utilities, Access & Services'] = [(n, kind, 'Utility Services Available' if n == 'utility_services_types' else label) for n, kind, label in PROFILE_SECTIONS['Utilities, Access & Services']]

# Application defaults, staff access and marketing are the final editor section.
SECTION_ORDER.remove('How to Apply')
SECTION_ORDER.append('How to Apply, Agent Access & Services')
PROFILE_SECTIONS['How to Apply, Agent Access & Services'] = PROFILE_SECTIONS.pop('How to Apply')
MARKETING_SECTIONS['How to Apply, Agent Access & Services'] = MARKETING_SECTIONS['Utilities, Access & Services'] + MARKETING_SECTIONS['Property Overview']
MARKETING_SECTIONS['Utilities, Access & Services'] = []
MARKETING_SECTIONS['Property Overview'] = []
# Keep the application fee first; retain Association YN after the requested rows.
_application_section = 'How to Apply, Agent Access & Services'
_application_fields = PROFILE_SECTIONS[_application_section]
PROFILE_SECTIONS[_application_section] = [
    (name, kind, 'Property Managed By' if name == 'application_managed_by' else label)
    for name, kind, label in _application_fields if name != 'application_association_yn'
] + [item for item in _application_fields if item[0] == 'application_association_yn']

# Place compliance remarks immediately after Association YN in the application section.
PROFILE_SECTIONS['Rules, Associations & Compliance'] = [
    item for item in PROFILE_SECTIONS['Rules, Associations & Compliance']
    if item[0] != 'rules_compliance_remarks'
]
PROFILE_SECTIONS[_application_section].append(('rules_compliance_remarks', 'notes', 'Rules & Compliance Remarks'))
