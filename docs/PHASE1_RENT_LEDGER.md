# Phase 1 manual rent ledger

## Install locally after the dashboard and Create Lease styling patches

    git apply --check COL360_Phase1_Manual_Rent_Ledger.patch
    git apply COL360_Phase1_Manual_Rent_Ledger.patch
    python manage.py makemigrations accounting --name phase1_rent_ledger
    python manage.py migrate
    python manage.py seed_rent_ledger
    python manage.py check
    python manage.py test accounting.test_rent_phase1 portal.test_dashboard_phase1

Restart the development server. Open a lease's Rent ledger button, Finance > Rent ledger, or the dashboard's Rent ledger action. Existing leases and executed agreements are not rewritten. No historical rent is automatically charged or marked paid.

## Local pilot sequence

Use test financial records in your local database. On an Active test lease:

1. Add a rent charge with a confirmed period, amount, and due date. The current effective monthly rent is only an initial suggestion; manually verify historical terms and any proration.
2. Record a smaller payment already received. Confirm the charge shows the remaining balance.
3. Record the rest. Confirm the balance is zero.
4. Try an overpayment. Confirm the excess is unallocated credit. Post a subsequent rent period and use Apply available credit on that receipt.
5. Void a receipt with a reason and confirm the charge balance is restored. The receipt, allocation history, and audit events remain visible in storage. Voiding does not refund funds.
6. Verify dashboard outstanding, overdue, and unallocated-credit figures match the lease ledger. Dashboard totals cover actively managed properties; Finance > Rent ledger also includes historical records outside that portfolio.

## Rules

- Charge, receipt, credit-application, and void writes run in one transaction with their audit event, serialized by locking the lease. PostgreSQL locks must be validated locally/Render before production deployment.
- An entry form has a session-bound token. A repeated successful POST returns the existing entry without creating another charge or receipt. Opening another form of the same kind replaces that session token, so an older tab may need to be reopened.
- Live rent periods cannot overlap. Amounts must be positive. Receipt dates cannot be future dates. Nonblank payment references must be unique per lease/payment method among recorded receipts; blank references cannot be used to detect duplicates.
- Receipts apply oldest due rent first within the same lease. This is a rent-only manual subledger, not a rule for allocating other fees, deposits, or legal priorities.
- A charge with recorded payments cannot be voided until the incorrect receipts have been voided. Fully unallocated receipts stay as credit until staff explicitly apply that credit to new charges.
- Draft/Pending/Cancelled leases cannot receive rent postings. New charges require Active/Notice status; historical Expired/Terminated leases can receive payments against their recorded charges.
- Amounts and allocations are not edited through the UI. Corrections use void-and-reenter, with a mandatory void reason. The immutable audit ledger records the changes atomically; an audit write failure rolls back the financial operation.
- All pages require active staff access. Writes require CSRF protection and use the lease from the URL; another lease's entry IDs are rejected.
- Labels, help text, interface wording, and payment method options are editable under Form Field Settings > rent_ledger. Seeds preserve existing edits.

## Boundaries

This is an operational rent subledger with manual receipts, not double-entry general-ledger posting, bank reconciliation, payment processing, QuickBooks synchronization, or receipt-email delivery. Selecting a receiving account is a reference only and does not adjust that account's opening balance. Security deposits, refunds, fees, waivers, write-offs, owner distributions, and automated monthly billing are outside this patch.

Outstanding charges and unallocated credit are displayed separately. No tenant balance is inferred from lease monthly rent alone. An empty ledger is explicitly described as having no recorded entries, rather than asserting a tenant has paid all rent.

## Validation

22 included Django tests (16 rent tests and 6 dashboard tests) passed against the supplied models in an isolated SQLite database, including render/POST tests with actual templates. Coverage includes partial payments, credit application, repeat submits, overlap rejection, void reversal, audit-failure rollback, lease scope, staff and CSRF access, extension carry-forward, and dashboard calculations. The project check passed in that isolated configuration. Your normal local PostgreSQL settings and Render validation remain the next release gates.
