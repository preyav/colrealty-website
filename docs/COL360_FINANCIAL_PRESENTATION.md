# Financial presentation refinement

Apply after COL360_Property_Income_Statement_Placement.patch, run
seed_financial_presentation and manage.py check. No migration or transaction changes.

Lease Ledger columns: Date, Invoice, Account, Transaction, Reference, Amount, Balance,
Actions. Invoice and Account can be sorted; sorting uses the revised column positions.
Invoice shows a stored invoice_number when present, otherwise an em dash. Existing rent
entries do not have issued tenant invoice numbers; payment references are never relabeled
as invoices. This change does not introduce tenant invoice creation or numbering.

Account uses names from linked income postings. For unposted entries the property's
configured rent-income account is shown; credit refunds and advance/deposit applications
fall back to the corresponding configured liability account. Missing mappings show an em
dash. This is a chart-account display, not the receiving bank. Void/reversal amounts and
running balances remain unchanged.

Property Income Statement omits the repeated property summary/address row. Its page header
still identifies the property. Configured active income and expense chart accounts are
itemized, including accounts with no activity, so an unposted statement still has account
rows. Settings > Field labels & options > property_income_statement / ui contains
show_empty_accounts: '1' shows them, '0' hides zero-activity rows. No categories or amounts
are copied from Buildium. Completeness and disabled-posting warnings remain visible.

Expand all rows / Collapse all rows has a plus/minus icon, opens account and subtotal rows
within the relevant Income/Expenses section, and updates when individual rows are toggled.
Its labels are configurable. The shared Accounting Financials page receives the same controls.
The property address summary remains on the multi-property Accounting Financials report,
where it is needed to distinguish property groups.

All table headings under the Portal main area display uppercase through shared CSS.
Underlying labels, search values, row text and stored data retain their original case.
Shared theme rules preserve text-link styling for report expansion controls.

152 isolated Django tests passed. New checks cover zero-activity account itemization,
account metadata, no fabricated invoice IDs, heading/sort columns and retained custom labels.
JavaScript syntax checks and patch application checks passed. Browser visual verification
remains a local check. Continue local > Render > EC2 validation after checking the new columns
and expansion controls. No bank connections, historical posting or classification changes
are performed by this patch.
