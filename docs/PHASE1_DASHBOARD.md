# COL360 Phase 1 dashboard

This patch replaces the mixed marketing/property-management dashboard with six operational cards: Needs Attention, Maintenance, Lease Expirations, Rent & Bills, Occupancy & Leasing, and Recent Activity. Listings, rentals, and leads remain available through the existing navigation.

## Local installation

Apply the patch from the project root, then run:

    python manage.py seed_pm_dashboard
    python manage.py check
    python manage.py test portal.test_dashboard_phase1

No model migration is required. Restart the local development server and open /portal/.
Dashboard labels, help text, activity descriptions, row count, and date windows are editable in Django admin under Form Field Settings, form key `pm_dashboard`. The seed command preserves edits.

## Behavior

- Portfolio figures include properties with Management Lifecycle `active`, using the existing management_status field. Inactive units are excluded.
- Applicable executed extensions use leasing.agreement_history, the same read model used by Lease 360. Original lease dates and rent remain intact. Draft extensions and unsigned fallback terms never become current terms.
- The lease directory displays the effective expiration and rent. Property 360's current lease lookup also uses effective expiration and recorded move-out dates.
- Occupied units require an Active or Notice lease covering today. A vacant status is required before an unoccupied unit is counted vacant. Occupied/Notice units lacking a current lease, and overlapping current leases, contribute to a review count.
- Upcoming starts are commencement dates on Pending/Active leases; they are not claims that a tenant physically moved in.
- Request counts exclude completed, cancelled, declined, and converted requests, preventing converted requests from being counted again as open intake.
- Vendor outstanding balance is approved/partially-paid invoice amount minus recorded payments. Void invoices/payments are excluded. Review bills are separate from approved liabilities.
- Past scheduled arrival means an Assigned/Scheduled work order's recorded schedule is before now; it is not an invented contractual completion deadline.
- Recent Activity reads existing audit events belonging to actively managed properties and opens Property 360 for context.
- Links and quick actions open existing forms; the dashboard itself performs no financial or workflow writes.

## Important Phase 1 boundary

The manual rent-ledger follow-up now supplies posted rent charges, recorded receipts, allocations, unallocated credit, and void corrections. Scheduled monthly rent is never presented as cash received or rent outstanding. See PHASE1_RENT_LEDGER.md for installation and testing. Online collection, renewals, payment automation, bank/QuickBooks reconciliation, statement sending, and approval-limit enforcement remain outside these patches.

Existing financial/workflow actions continue to use their existing validations and audit processes. Other original-core consumers, including scheduled lease-status commands, need a separate review before enabling automated lifecycle changes; this dashboard does not modify them.

## Validation

Six included Django tests cover empty states, executed extension carry-forward and draft exclusion, expiration boundaries, recorded versus void vendor payments, active portfolio scope, and seed preservation. Additional isolated integration checks exercised directory filtering, effective rent, staff-only access, and rendering against the supplied base template. Checks used the actual supplied models with SQLite; local PostgreSQL and Render validation remain required.

For 1800 Killians Cove / Lease 21, verify that Lease 360 and the directory agree on the extension-derived term (July 31, 2027 expiration and $2,400 monthly rent, if the previously imported executed agreements remain unchanged). The original agreement must still retain its historical figures. Do not add test financial records to production.

After local validation, test in Render before EC2 deployment.
