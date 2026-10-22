# Rentals and Maintenance navigation

The former rental-listings sidebar entry is now Leasing. Its URL and records stay unchanged.
Rentals opens a flyout containing Properties, Leases, Tenants, Owners and Outstanding balances.
Maintenance opens a flyout containing Vendors, Work orders, Property inspections,
Inventory and assets, and Maintenance requests. Existing work-order/request workflows are reused.
The flyouts start hidden, close on outside click or Escape, and only one group opens at a time.
Existing editor section links remain in the page's own navigation; separate sidebar section lists are removed.

## Local installation

Apply the patch on the latest working branch, using --ignore-space-change if necessary.
Then run:

    python manage.py makemigrations maintenance --name property_registers
    python manage.py migrate
    python manage.py seed_portal_navigation
    python manage.py check

The generated migration creates inspection and asset tables. It does not change financial records.
Keep the generated migration in git with the source changes. Validate locally, then Render,
then EC2 using the same migration. Do not generate a different migration in each environment.

## Configuration and permissions

Settings > Field labels & options contains:
- portal_navigation / ui: menu labels
- property_registers / ui: field labels and help text
- property_registers / inspection_status, inspection_type, asset_status: option labels
- outstanding_balances / ui: report wording

The seed command fills missing keys and retains edits. Stable status keys are used by validation;
rename their labels rather than removing the completed inspection status semantics.

Active staff with model view/add/change permissions can read/create/edit the new registers.
Superusers already have access. Assign staff permissions in Settings > Roles & permissions
and Settings > Staff access. New models: maintenance.PropertyInspection and maintenance.PropertyAsset.
There is no Django Admin dependency. Changes are audited atomically; stale edit forms are rejected.
View-only staff can open a disabled detail form without saving. Retire assets or cancel inspections
through their status rather than deleting their history.

## Registers

Inspections retain property/unit, title, type, assigned staff, scheduled/completed dates,
status, findings and a document URL. Completed inspections require a completion date.
This is a basic inspection register, not a checklist/signature or tenant-notification system.
Use the existing Maintenance requests workflow for resulting repair work.

Assets retain property/unit, name, quantity, status, manufacturer, model, serial,
installation and warranty dates, notes and a document URL. They do not post purchases,
depreciation or other accounting entries. Document links may point to Google Drive;
provider permissions continue to control access. Unit selections must belong to the chosen property.

## Outstanding balances

Read-only, rent-only report using the existing reconciliation calculation as of today.
Unpaid charges due today or earlier, overdue unpaid charges, unallocated rent credit,
net rent due (minimum zero), and future unpaid charges are separate columns.
A credit does not become negative rent owed. Credits are not automatically allocated or refunded.
Refundable deposits and unapplied advance funds are not treated as available rent credit.
Properties with credits or future unpaid charges may appear with zero net rent due.
The report uses current statuses and allocations, not reconstructed historical states.
No historical transactions are created or changed by opening the report.

## Validation

138 isolated Django tests passed, including existing rent/accounting/settings tests and new
navigation, register validation, access, CSRF, stale edits, audit rollback and balance tests.
Templates rendered in the isolated environment. Browser visual verification was unavailable
because the local browser executable was absent. Validate flyouts and mobile layouts locally
before the Render stage. Tables reuse the existing global sorting behavior; register sorting
operates on the displayed page (50 records per page).
