# COL360 development rules

- PostgreSQL is the only permitted application and test database. Never use SQLite or an alternate database backend, even for temporary or isolated tests.
- Never disable migrations, replace project URLs with placeholder views, or substitute a reduced app registry when claiming project validation.
- Use the actual Django project settings and migrations. PostgreSQL must be available; otherwise report database validation as blocked. Do not claim a passing database test from syntax checks, mocked SQL, or a different database.
- Run `python manage.py validate_postgres` for the reviewed regression suite. Review failures and skipped tests; preserve the resulting report.
- Preserve valid operational and accounting records. No automatic data deletion, reconstruction, duplicate postings or destructive migration shortcuts.
- Follow local → Render → EC2. Never edit production directly.
- Business values and editable wording come from database/configuration, not hardcoded property names, people, amounts, account IDs or dates.
