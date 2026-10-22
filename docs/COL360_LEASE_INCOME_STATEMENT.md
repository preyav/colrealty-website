# Lease 360 Income Statement

Apply after the Lease Financials report-layout patch. Run seed_lease_income_statement
and manage.py check. No model changes or migrations. The seed fills missing labels
and preserves existing configuration; it does not post journals or modify transactions.

Lease 360 > Financials now defaults to Income Statement, with Ledger as a separate
subtab on the same page. GET filters provide current month, three/six/twelve months
to date and year to date. Cash/accrual selection defaults to the property's accounting
entity preference. Control wording/default_period is configurable in Portal Settings
under lease_income_statement / ui. Period labels reuse financials / ui.

The income statement is PROPERTY-wide, including other leases/units and shared expenses.
This matches the property's income-statement model and avoids implying that common
expenses are assigned to one tenant. The Ledger remains lease-specific. Scope and entity
cannot be changed using query parameters on this report.

Monthly income, expenses, subtotals, net operating income and net income reuse the existing
accounting financial_report function. Expand account rows for location breakdowns and follow
amount links to the scoped General Ledger. No report amounts are inferred from the signed
rent figure or a tenant's balance. Only journals for the selected basis/entity are included.
Missing posting coverage and disabled property accounting display notices. Missing property
accounting configuration displays setup guidance rather than a fabricated statement.

NOI requires operating/non_operating account classification. Configure it in Portal Settings
> Field labels & options > financial_account_classification for accounts with activity.
Unclassified activity shows NOI as unavailable; net income remains income less expenses.
Deposits, owner funding/distributions and transfers are excluded unless incorrectly posted
against income/expense accounts. Existing record classification must be reviewed independently.

144 isolated Django tests passed, covering basis/date differences, income and expense totals,
NOI classification, default basis, invalid filters, property scoping, unposted coverage, missing
configuration, preserved labels and template rendering. Browser visual verification was not
available in this workspace. Validate locally, then Render, then EC2. Reporting does not backfill
historical rent or bill postings. If totals are incomplete, review posting coverage before import.
