# Property income statements and lease ledgers

Apply after COL360_Lease_Income_Statement.patch. Run seed_property_financials and
manage.py check, then restart the local Django server. No migration is required.

Navigation:
- Rentals > Leases > select lease > Financials: Ledger, charges and payments.
- Rentals > Properties > select property > Financials: Income Statement.
- The lease Ledger also links to its property's Income Statement.

The Property Financials route is /portal/properties/<property_id>/financials/.
Existing property/lease URLs, ledger entries, journal postings and calculations are unchanged.
The property report includes all units and property-level expenses and remains scoped to the
property's configured accounting entity. Cash/accrual defaults and timeframe options are reused.
Existing report settings are copied once into property_income_statement / ui, then preserved.
Property navigation labels live in property_financials / ui. Edit both in Portal Settings.
The former lease_income_statement settings/tag remain for compatibility with older templates.

Validate locally, then Render, then EC2. This patch does not create or backfill transactions.
Missing accounting configuration/posting coverage and unclassified NOI warnings remain.
148 isolated Django tests passed, including property-route rendering, scope, unchanged posting
counts, Ledger placement, permission checks and preserved settings. Browser visual validation
remains a local check; the workspace browser executable is unavailable.
