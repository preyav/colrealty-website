COL360 V1.5A.1 — Unified Vendors & Estimates

Replace:
  portal/views.py
  templates/portal/work_order_detail.html

Add/replace:
  templates/portal/add_vendor_estimate.html

No model changes. No migration required. No settings changes.
Keep COL360_FINANCIAL_PROVIDER=disabled for this test.

Changes:
- Consolidates Vendor Assignments + Estimate Comparison + Vendor Estimates into one Vendors & Estimates card.
- Estimates can now be entered for any ACTIVE vendor; assignment is no longer required first.
- Prevents duplicate estimate entry for the same vendor on the same work order through the UI queryset.
- Prevents new estimates after one is selected/approved.
- Prevents estimate changes on completed/cancelled work orders.
- Adds estimate add/approve/reject events to the Audit Ledger.
- Selected estimate still updates WorkOrder.estimated_cost.
- Assignment/scheduling remains a separate operational record under the unified UI.
- Financial-provider abstraction from V1.5A remains unchanged.
