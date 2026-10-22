"""Shared ownership labels and suggested values from the supplied reference."""

OWNERSHIP_CHOICES = [('freehold', 'Fee Simple'), ('condominium', 'Condo Ownership (Airspace + Common Interest)'), ('fee_simple_or_pud', 'Fee Simple or PUD (Planned Unit Development)'), ('attached_fee_simple', 'Fee Simple (once permanently attached)'), ('chattel_or_real', 'Personal Property (Chattel) OR Real Property'), ('chattel_or_leasehold', 'Personal Property (Chattel) or Leasehold'), ('apartment_leasehold', 'No direct ownership of the real estate unit (leasehold/tenant rights only).'), ('duplex_ownership', 'Two residential dwelling units attached in one building.'), ('triplex_ownership', 'Three residential dwelling units contained within a single property.'), ('quadruplex_ownership', 'Four residential dwelling units contained within a single property.')]

PROPERTY_OWNERSHIP_DEFAULTS = {'single_family_residential': 'freehold', 'condominium': 'condominium', 'townhouse': 'fee_simple_or_pud', 'modular': 'attached_fee_simple', 'manufactured_home': 'chattel_or_real', 'mobile_home': 'chattel_or_leasehold', 'apartments': 'apartment_leasehold', 'duplex': 'duplex_ownership', 'triplex': 'triplex_ownership', 'quadruplex': 'quadruplex_ownership'}

LEGACY_OWNERSHIP_CHOICES = [('leasehold', 'Leasehold'), ('other', 'Other')]
