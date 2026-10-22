# COL360 Portal Settings — configuration move

This patch builds on the entity cash/accrual accounting foundation. It adds one Portal Settings page, using tabs and inline editors over the existing database records. It does not create a parallel configuration store, new companies, bank balances, accounting entities or property mappings.

## Apply locally

After applying and migrating the accounting foundation patch:

```powershell
git apply --check --ignore-space-change COL360_Portal_Settings.patch
git apply --ignore-space-change COL360_Portal_Settings.patch
python manage.py seed_portal_settings
python manage.py check
python manage.py test portal.test_settings
```

This patch needs no additional schema migration. The seed command only initializes editable labels and help text, preserving existing edits. Keep the established local → Render → EC2 validation sequence.

## Where to go

Sign in with your existing Portal account and choose **Settings** at the bottom of the sidebar. Existing superusers can use it immediately. No new account or Django Admin configuration is necessary.

- **Companies & accounting:** edit an existing accounting entity or add one; select its reporting default and active status. New companies inherit the configured initial reporting default.
- **Bank account ownership:** connect an existing bank account to its company. A link to Banking provides the existing bank-account create/edit workflow. Saved ownership links remain read-only under the existing accounting safeguards.
- **Property accounting:** configure existing property/control accounts and reserves. Once journals are posted, company/account mappings remain locked; reserve and posting-enabled settings remain editable. Do not enable automatic posting until historical review is complete.
- **Field labels & options:** search the existing Form Field Settings records and edit their labels, help, existing option values and configured error messages. Existing option identifiers stay unchanged, preserving references in stored transactions and forms. Reporting classification uses a dropdown rather than raw JSON.
- **Staff access:** superusers can manage existing user access/roles, create local staff accounts and set passwords without leaving the Portal. Superuser status is not granted or removed here. New local accounts remain subject to the existing authentication policy; no invitation or verification email is sent automatically. In an allauth deployment, new email records are unverified and existing sign-in email changes remain in the account's verified email-change flow.
- **Roles & permissions:** superusers manage the existing Django permission groups. This does not invent a separate role store or grant access to another company automatically.

Info icons sit next to the field labels and close when clicked outside or when Escape is pressed. The page uses the shared centered accounting layout and Portal font.

## Access and data protections

- Staff must have the relevant model view/add/change permissions for each configuration tab. View-only users cannot save. Superusers retain access.
- User/role management remains superuser-only, including on crafted POST requests. Staff access does not imply permission to change users or roles.
- Existing operational pages that currently use broad staff access are not converted to granular/property-scoped access by this patch. A subsequent permissions pass is required before representing those pages as company- or property-isolated for different customers.
- Saves are transactional and audited. Signed version checks reject stale edits rather than overwriting another person's changes. Passwords/hashes are not placed in audit payloads or client form tokens.
- You cannot remove your own active staff access or disable the last active staff administrator through this page.
- There is no destructive delete in the Settings interface. Financial posting/reconciliation history is not changed by opening Settings or running its seed command.
- The visible Django Admin shortcut is replaced by Settings. Login/logout links for this workflow use the existing account authentication routes. The technical Django Admin endpoint is not disabled.

## What stays outside Settings

This patch moves configuration only. It does not relocate the daily Accounting Operations actions yet. Tenant charges/payments/client funds belong in Lease 360 Financials; bill service periods, bill payments/credits belong in Bills; reconciliation belongs in Banking; owner reporting belongs with owner Financials. Those existing accounting services remain intact for the next workflow move.

## Validation

1. Apply and test locally against the current project and local PostgreSQL test database. Reuse existing entity/property/bank records; verify that edits retain their IDs and balances.
2. Check Settings with a superuser, a staff user with only a view permission, and a staff user without configuration permissions. Confirm server-side denials, not just hidden buttons.
3. Open a company in two windows and verify that the second stale save is rejected after the first window saves.
4. Verify that posted mappings cannot be changed by altering a browser request, while authorized reserve updates work.
5. Confirm field text edits appear in their original forms and keep existing option identifiers.
6. Test the actual allauth login/email-verification policy in this project. Confirm that changing your own password preserves your current session and does not expose credentials in audit records.
7. Repeat the Portal/browser and permissions checks in Render staging. Only deploy the tested commit to EC2 after local and staging sign-off.

The included isolated test run validates the supplied code snapshot with SQLite; it is not a validation of the live user database, PostgreSQL concurrency, allauth configuration or deployed browser layout.
