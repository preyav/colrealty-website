Invoice payee selection
======================
The invoice creation queryset previously contained only assigned contractors;
the edit queryset contained only the invoice's existing vendor. Both now use
active Vendor records plus the current/default vendor, even if now inactive.
Other inactive or pending vendors are excluded. No vendor is created by name.
No work-order assignment, award, payment, invoice or journal is modified by
applying the patch. Existing submitted-only edit and provider checks remain.

No migration or seed is needed. Run manage.py check and restart the server.
Maintenance > Vendors > + Add Vendor: add the actual bill payee as Active if it
does not already exist. Then edit the submitted invoice, select its payee and
update. Do not rename the contractor or change the work-order assignment.
For the current example AHS collected the fee; H&C performed the repair.

Validation: 161 isolated SQLite tests passed, including new payee eligibility
tests. The snapshot does not include financial/providers implementations, so
provider update, approval, payment, and dual-basis posting must be verified in
the actual local project before Render and EC2 deployment. A future payment
entry must preserve the actual payment date/account and must not send money
again for an already-paid fee.
