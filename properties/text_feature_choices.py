"""Screenshot-sourced multi-select choices stored in existing text columns."""
import json
from django import forms
from django.core.exceptions import ValidationError

TEXT_FEATURE_CHOICES = {'laundry_location': {'label': 'Laundry Location', 'limit': 5, 'choices': [('none', 'None'), ('see_remarks', 'See Remarks'), ('common_area', 'Common Area'), ('in_basement', 'In Basement'), ('in_bathroom', 'In Bathroom'), ('in_carport', 'In Carport'), ('in_garage', 'In Garage'), ('in_hall', 'In Hall'), ('in_kitchen', 'In Kitchen'), ('in_unit', 'In Unit'), ('inside', 'Inside'), ('laundry_closet', 'Laundry Closet'), ('laundry_room', 'Laundry Room'), ('lower_level', 'Lower Level'), ('main_level', 'Main Level'), ('multiple_locations', 'Multiple Locations'), ('outside', 'Outside'), ('upper_level', 'Upper Level')]}, 'parking_features': {'label': 'Parking Features', 'limit': None, 'choices': [('none', 'None'), ('see_remarks', 'See Remarks'), ('additional_parking', 'Additional Parking'), ('aggregate', 'Aggregate'), ('alley_access', 'Alley Access'), ('asphalt', 'Asphalt'), ('assigned', 'Assigned'), ('attached', 'Attached'), ('attached_carport', 'Attached Carport'), ('basement', 'Basement'), ('boat', 'Boat'), ('carport', 'Carport'), ('circular_driveway', 'Circular Driveway'), ('common', 'Common'), ('community_structure', 'Community Structure'), ('concrete', 'Concrete'), ('converted_garage', 'Converted Garage'), ('covered', 'Covered'), ('deck', 'Deck'), ('deeded', 'Deeded'), ('detached', 'Detached'), ('detached_carport', 'Detached Carport'), ('direct_access', 'Direct Access'), ('door_multi', 'Door-Multi'), ('door_single', 'Door-Single'), ('drive_through', 'Drive Through'), ('driveway', 'Driveway'), ('elec_vehicle_charge_station_s', 'Elec Vehicle Charge Station(s)'), ('electric_gate', 'Electric Gate'), ('enclosed', 'Enclosed'), ('garage', 'Garage'), ('garage_door_opener', 'Garage Door Opener'), ('garage_faces_front', 'Garage Faces Front'), ('garage_faces_rear', 'Garage Faces Rear'), ('garage_faces_side', 'Garage Faces Side'), ('gated', 'Gated'), ('golf_cart_garage', 'Golf Cart Garage'), ('gravel', 'Gravel'), ('guest', 'Guest'), ('heated_garage', 'Heated Garage'), ('inside_entrance', 'Inside Entrance'), ('kitchen_level', 'Kitchen Level'), ('leased', 'Leased'), ('lighted', 'Lighted'), ('off_site', 'Off Site'), ('off_street', 'Off Street'), ('open', 'Open'), ('outside', 'Outside'), ('oversized', 'Oversized'), ('parking_lot', 'Parking Lot'), ('parking_pad', 'Parking Pad'), ('parking_permit_required', 'Parking Permit Required'), ('paved', 'Paved'), ('paver_block', 'Paver Block'), ('private', 'Private'), ('reserved', 'Reserved'), ('rv_access_parking', 'RV Access/Parking'), ('rv_carport', 'RV Carport'), ('rv_garage', 'RV Garage'), ('rv_gated', 'RV Gated'), ('secured', 'Secured'), ('shared_driveway', 'Shared Driveway'), ('side_by_side', 'Side By Side'), ('storage', 'Storage'), ('tandem', 'Tandem'), ('unassigned', 'Unassigned'), ('underground', 'Underground'), ('unpaved', 'Unpaved'), ('valet', 'Valet'), ('varies_by_unit', 'Varies by Unit'), ('workshop_in_garage', 'Workshop in Garage')]}, 'patio_porch_features': {'label': 'Patio / Porch Features', 'limit': 20, 'choices': [('none', 'None'), ('see_remarks', 'See Remarks'), ('arbor', 'Arbor'), ('awning_s', 'Awning(s)'), ('covered', 'Covered'), ('deck', 'Deck'), ('enclosed', 'Enclosed'), ('front_porch', 'Front Porch'), ('glass_enclosed', 'Glass Enclosed'), ('mosquito_system', 'Mosquito System'), ('patio', 'Patio'), ('porch', 'Porch'), ('rear_porch', 'Rear Porch'), ('screened', 'Screened'), ('side_porch', 'Side Porch'), ('terrace', 'Terrace'), ('wrap_around', 'Wrap Around')]}, 'fencing': {'label': 'Fencing', 'limit': 29, 'choices': [('none', 'None'), ('see_remarks', 'See Remarks'), ('back_yard', 'Back Yard'), ('barbed_wire', 'Barbed Wire'), ('block', 'Block'), ('brick', 'Brick'), ('chain_link', 'Chain Link'), ('cross_fenced', 'Cross Fenced'), ('electric', 'Electric'), ('fenced', 'Fenced'), ('front_yard', 'Front Yard'), ('full', 'Full'), ('gate', 'Gate'), ('invisible', 'Invisible'), ('livestock', 'Livestock'), ('masonry', 'Masonry'), ('partial', 'Partial'), ('perimeter', 'Perimeter'), ('pipe', 'Pipe'), ('privacy', 'Privacy'), ('security', 'Security'), ('slump_stone', 'Slump Stone'), ('split_rail', 'Split Rail'), ('stone', 'Stone'), ('vinyl', 'Vinyl'), ('wire', 'Wire'), ('wood', 'Wood'), ('wrought_iron', 'Wrought Iron')]}}

def decode_features(value):
    if isinstance(value, (list, tuple)):
        return list(value)
    if not value:
        return []
    try:
        decoded = json.loads(value)
        if isinstance(decoded, list) and all(isinstance(item, str) for item in decoded):
            return decoded
    except (TypeError, ValueError):
        pass
    return [value]

class TextFeatureChoiceField(forms.MultipleChoiceField):
    def __init__(self, *, limit=None, **kwargs):
        self.limit = limit
        super().__init__(widget=forms.CheckboxSelectMultiple, **kwargs)

    def prepare_value(self, value):
        return decode_features(value)

    def clean(self, value):
        selected = list(dict.fromkeys(super().clean(value)))
        if 'none' in selected and len(selected) > 1:
            raise ValidationError('None cannot be combined with another feature.')
        if self.limit and len(selected) > self.limit:
            raise ValidationError(f'Select no more than {self.limit} options.')
        encoded = json.dumps(selected, ensure_ascii=False) if selected else ''
        if len(encoded) > 4000:
            raise ValidationError('The selected values exceed the 4,000-character storage limit.')
        return encoded

# Reuse the vocabularies documented in the existing green-feature help.
TEXT_FEATURE_CHOICES['energy_features'] = {'label': 'Green Energy Efficient (max 20)', 'limit': 20, 'choices': [('none', 'None'), ('see_remarks', 'See Remarks'), ('appliances', 'Appliances'), ('construction', 'Construction'), ('doors', 'Doors'), ('exposure_shade', 'Exposure/Shade'), ('healthy_living_features', 'Healthy Living Features'), ('incentives', 'Incentives'), ('hvac', 'HVAC'), ('insulation', 'Insulation'), ('lighting', 'Lighting'), ('materials_and_construction', 'Materials and Construction'), ('roof', 'Roof'), ('solar_panels', 'Solar Panels'), ('sustainability', 'Sustainability'), ('thermostat', 'Thermostat'), ('water_heater', 'Water Heater'), ('wind_turbines', 'Wind Turbines'), ('windows', 'Windows')]}
TEXT_FEATURE_CHOICES['sustainability_features'] = {'label': 'Green Sustainability (max 9)', 'limit': 9, 'choices': [('none', 'None'), ('see_remarks', 'See Remarks'), ('conserving_methods', 'Conserving Methods'), ('onsite_recycling_center', 'Onsite Recycling Center'), ('recyclable_materials', 'Recyclable Materials'), ('recycled_materials', 'Recycled Materials'), ('regionally_sourced_materials', 'Regionally-Sourced Materials'), ('renewable_materials', 'Renewable Materials'), ('salvaged_materials', 'Salvaged Materials')]}

TEXT_FEATURE_CHOICES['waterfront_features'] = {'label': 'Waterfront Features (Must be on or directly adjacent to the property, not just near it) (max 12)', 'limit': 12, 'choices': [('none', 'None'), ('see_remarks', 'See Remarks'), ('canal_front', 'Canal Front'), ('creek', 'Creek'), ('dry_seasonal', 'Dry/Seasonal'), ('lake_front', 'Lake Front'), ('lake_privileges', 'Lake Privileges'), ('pond', 'Pond'), ('river_front', 'River Front'), ('stream', 'Stream'), ('waterfront', 'Waterfront')]}

TEXT_FEATURE_CHOICES['water_source'] = {'label': 'Water Source (max 5)', 'limit': 5, 'choices': [('none', 'None'), ('see_remarks', 'See Remarks'), ('cistern', 'Cistern'), ('municipal_utility_district_mud', 'Municipal Utility District (MUD)'), ('private', 'Private'), ('public', 'Public'), ('shared_well', 'Shared Well'), ('spring', 'Spring'), ('well', 'Well')]}
TEXT_FEATURE_CHOICES['sewer'] = {'label': 'Sewer (max 10)', 'limit': 10, 'choices': [('none', 'None'), ('see_remarks', 'See Remarks'), ('aerobic_septic', 'Aerobic Septic'), ('cesspool', 'Cesspool'), ('engineered_septic', 'Engineered Septic'), ('holding_tank', 'Holding Tank'), ('mound_septic', 'Mound Septic'), ('municipal_utility_district_mud', 'Municipal Utility District (MUD)'), ('perc_test_on_file', 'Perc Test On File'), ('perc_test_required', 'Perc Test Required'), ('private_sewer', 'Private Sewer'), ('public_sewer', 'Public Sewer'), ('septic_needed', 'Septic Needed'), ('septic_shared', 'Septic Shared'), ('septic_tank', 'Septic Tank')]}
TEXT_FEATURE_CHOICES['utility_responsibilities'] = {'label': 'Utility Service Responsibilities', 'limit': None, 'choices': [('see_remarks', 'See Remarks'), ('tenant_pays_all_utilities', 'Tenant Pays All Utilities'), ('owner_pays_all_utilities', 'Owner Pays All Utilities'), ('utilities_included_in_rent', 'Utilities Included in Rent'), ('tenant_pays_electricity', 'Tenant Pays Electricity'), ('tenant_pays_gas', 'Tenant Pays Gas'), ('tenant_pays_water', 'Tenant Pays Water'), ('tenant_pays_sewer', 'Tenant Pays Sewer'), ('tenant_pays_trash_recycling', 'Tenant Pays Trash / Recycling'), ('tenant_pays_internet_cable', 'Tenant Pays Internet / Cable'), ('owner_pays_electricity', 'Owner Pays Electricity'), ('owner_pays_gas', 'Owner Pays Gas'), ('owner_pays_water', 'Owner Pays Water'), ('owner_pays_sewer', 'Owner Pays Sewer'), ('owner_pays_trash_recycling', 'Owner Pays Trash / Recycling'), ('owner_pays_internet_cable', 'Owner Pays Internet / Cable'), ('hoa_association_provides_utilities', 'HOA / Association Provides Utilities'), ('shared_allocated_utility_costs', 'Shared / Allocated Utility Costs'), ('tenant_establishes_utility_accounts', 'Tenant Establishes Utility Accounts'), ('owner_retains_utility_accounts', 'Owner Retains Utility Accounts')]}

# How to Apply options supplied in the reference screenshots.
APPLICATION_SINGLE_CHOICES = {'application_managed_by': ['Owner', 'Property Manager'], 'application_first_month_rent_payable_to': ['See Remarks', 'Broker', 'Owner'], 'application_lease_term': ['None', 'See Remarks', 'Weekly', 'Month to Month', '12 Months', 'Lease Purchase', 'Negotiable', 'Renewal Option'], 'application_policy': ['Best Qualified Application', 'First Qualified Application']}
TEXT_FEATURE_CHOICES['application_required'] = {'label': 'Application Required (max 3)', 'limit': 3, 'choices': [('see_attached', 'See Attached'), ('see_online_app', 'See Online App'), ('txr_app', 'TXR App')]}
TEXT_FEATURE_CHOICES['application_pets_allowed'] = {'label': 'Pets Allowed (max 9)', 'limit': 9, 'choices': [('cats_ok', 'Cats OK'), ('dogs_ok', 'Dogs OK'), ('small_20_lbs', 'Small (< 20 lbs)'), ('medium_35_lbs', 'Medium (< 35 lbs)'), ('large_50lbs', 'Large (< 50lbs)'), ('no_weight_limit', 'No Weight Limit'), ('number_limit', 'Number Limit'), ('size_limit', 'Size Limit'), ('breed_restrictions', 'Breed Restrictions'), ('no_breed_restrictions', 'No Breed restrictions'), ('all', 'All'), ('no', 'No'), ('call', 'Call'), ('negotiable', 'Negotiable')]}
TEXT_FEATURE_CHOICES['application_one_time_expenses'] = {'label': 'One Time Expenses (max 6)', 'limit': 6, 'choices': [('none', 'None'), ('see_remarks', 'See Remarks'), ('admin_fee', 'Admin Fee'), ('amenity_fee', 'Amenity Fee'), ('application_fee', 'Application Fee'), ('assigned_covered_parking', 'Assigned Covered Parking'), ('pet_deposit', 'Pet Deposit'), ('pet_fee', 'Pet Fee')]}

# Shared payee choices; preserve saved values through the form's legacy handling.
for _payee_field in ['application_fee_payable_to', 'application_security_deposit_payable_to', 'application_administration_fee_payable_to', 'application_first_month_rent_payable_to']:
    APPLICATION_SINGLE_CHOICES[_payee_field] = ['Broker', 'Owner', 'Property Manager', 'See Remarks']
TEXT_FEATURE_CHOICES['application_required']['choices'] = [
    ('online_app', 'Online App'), ('txr_application', 'TXR Application'), ('see_remarks', 'See Remarks'),
]
