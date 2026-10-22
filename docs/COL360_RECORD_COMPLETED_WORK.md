Record completed work
=====================
Run seed_work_completion and check, then restart the development server.
No database migration is required. Applying this patch changes no records.

Work Order detail > Record completed work is available for Assigned, Scheduled,
and In Progress work. Enter the actual completion date/time and completion notes.
Actual cost may remain blank until supported by an invoice. Historical dates may
precede the work order's creation date; they cannot be future or precede a known
start. No scheduled date, start date, or approval is fabricated.

The write requires active staff and maintenance.change_workorder. It locks the
work order, validates a signed snapshot including vendor assignments/awards,
and requires exactly one active applicable vendor assignment. It marks that
assignment completed, preserves schedule/start values, records status history
and an audit event in the same transaction. A related maintenance request closes
only if no other open work orders remain. Cancellation/completion cannot be
overwritten through this action.

After completion, Record / view invoice links to the existing invoice-intake
route. That route retains its existing provider capabilities, current-invoice,
and invoice validation rules. Completion alone creates no bill, payment or
journal. Invoice intake and expense/payment posting still need end-to-end
validation with a real invoice and its actual payee, dates and receiving account.

The current upcoming-appointment scheduling form remains unchanged. Use this
actual-completion action for historical work instead of scheduling a fictitious
future visit. This does not implement a separate historical appointment editor.

Labels, help text and validation messages are configurable in Portal Settings >
Field labels & options, form key work_completion / ui. Seeding preserves edits.

Validation: 159 isolated Django tests passed on SQLite with schema sync, plus
compilation of the work-order and new completion templates. Browser visual QA
and actual-project integration were not performed here. Validate locally, then
Render, then EC2. Follow the same code/config seed deployment sequence.
