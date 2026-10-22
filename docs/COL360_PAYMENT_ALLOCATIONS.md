Payment allocation editor
=========================
Apply the patch, run python manage.py seed_rent_allocations, python manage.py check,
and restart the development server. No migration is required.

Lease 360 > Financials > Ledger: each active payment has Edit allocations.
The link opens the same lease-wide editor at that payment. Expand payments to
enter amounts per rent period; zero clears an assignment. All payments are saved
together, allowing occupied periods to be exchanged without deleting receipts.
The page displays remaining credit as amounts change. It does not suggest rent
months from payment dates: verify against the tenant's actual payment purpose.
Enter a correction reason before saving. Changes preserve payment dates,
references, amounts and bank accounts. Void receipt allocations remain untouched.

Users need accounting.change_rentallocation in addition to active staff access.
Manage this through COL360 Portal Settings > Roles/Staff access. Superusers
already have the permission. Labels and messages are in Form Field Settings,
form key rent_allocations, field key ui; the seed preserves custom values.

For the reviewed Killians records, June 30 2026 covers July 2026; July 31 covers
August; August 31 covers September. Other existing shifted allocations also need
review. Do not apply a generic date-to-month rule or import duplicate payments.

This editor supports unposted history. Any journal for the property or any
client-funds activity for the lease blocks corrections. Posted history needs a
separate reversal/reposting workflow. No accounting journal is changed here.
Writes lock the lease and validate the signed snapshot of all charges, payments
and allocations. One transaction validates totals and saves the correction audit.
Changing allocations can change month-level balances despite an unchanged total.

After correction, rerun reconcile_lease_rent with a new output filename and review
actual allocations, not just totals. Two flags for preserved void allocations can
remain. Keep accounting disabled until allocation review is finished.

Validation: 156 isolated Django tests passed on SQLite using schema sync.
No browser visual QA or actual project migrations were run. Validate locally,
then Render, then EC2 under the normal deployment process.
