from django.core.management.base import BaseCommand
from django.utils import timezone

from newsletter.models import NewsletterIssue, Subscriber
from newsletter.services.newsletter_renderer import render_issue_email
from leads.services.hubspot import upsert_contact, create_note


class Command(BaseCommand):
    help = "Triggers HubSpot workflow for the latest published newsletter (sync + note + properties)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No HubSpot writes, just print actions.")
        parser.add_argument("--limit", type=int, default=0, help="Limit number of subscribers processed (0 = no limit).")
        parser.add_argument("--force", action="store_true", help="Allow sending even if issue.sent_at is set.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
        force = options["force"]

        issue = NewsletterIssue.objects.filter(status="published").order_by("-published_date").first()
        if not issue:
            self.stdout.write(self.style.ERROR("No published NewsletterIssue found."))
            return

        if issue.sent_at and not force:
            self.stdout.write(self.style.WARNING(
                f"Latest issue '{issue.slug}' already sent at {issue.sent_at}. Use --force to send again."
            ))
            return

        subject, html, issue_url = render_issue_email(issue)

        subs = Subscriber.objects.filter(is_active=True).order_by("created_at")
        if limit and limit > 0:
            subs = subs[:limit]

        total = subs.count()

        self.stdout.write(f"Issue: {issue.slug}")
        self.stdout.write(f"Subject: {subject}")
        self.stdout.write(f"URL: {issue_url}")
        self.stdout.write(f"Subscribers: {total}")
        self.stdout.write(f"Dry-run: {dry_run}")

        processed = 0
        failed = 0

        for sub in subs:
            processed += 1
            email = sub.email.strip().lower()

            if dry_run:
                self.stdout.write(f"[DRY] Would trigger workflow for {email}")
                continue

            try:
                props = {
                    # Keep your lead taxonomy consistent
                    "lead_source": "Newsletter",
                    "newsletter_opt_in": True,
                    "newsletter_zip": sub.zip_code or "",
                    "newsletter_last_issue_slug": issue.slug,
                    "newsletter_last_issue_url": issue_url,
                    "newsletter_last_issue_sent_at": timezone.now().isoformat(),  # create this property if you want
                }

                # upsert contact and set props (workflow will fire based on these props)
                contact_id = upsert_contact(
                    email=email,
                    firstname=sub.first_name or "",
                    lastname=sub.last_name or "",
                    props=props,
                )

                # note contains the rendered HTML preview link + subject (do NOT store full html if too big)
                note = (
                    f"<b>Newsletter Workflow Triggered</b><br>"
                    f"Issue: {issue.slug}<br>"
                    f"Subject: {subject}<br>"
                    f"Issue URL: <a href='{issue_url}'>{issue_url}</a><br>"
                    f"Triggered at: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}<br>"
                )
                create_note(contact_id, note)

                sub.hubspot_submitted = True
                sub.hubspot_response = f"workflow triggered (contact_id={contact_id})"
                sub.save(update_fields=["hubspot_submitted", "hubspot_response"])

            except Exception as e:
                failed += 1
                sub.hubspot_submitted = False
                sub.hubspot_response = str(e)[:5000]
                sub.save(update_fields=["hubspot_submitted", "hubspot_response"])
                self.stdout.write(self.style.WARNING(f"Failed for {email}: {e}"))

        if not dry_run:
            issue.sent_at = timezone.now()
            issue.sent_count = total - failed
            issue.save(update_fields=["sent_at", "sent_count"])

        self.stdout.write(self.style.SUCCESS(
            f"Done. processed={processed}, failed={failed}, marked_sent={(not dry_run)}"
        ))