from django.template.loader import render_to_string
from django.conf import settings

def render_issue_email(issue):
    site = getattr(settings, "SITE_URL", "https://colrealty.com").rstrip("/")
    issue_url = f"{site}{issue.get_absolute_url()}"
    subject = f"Col Realty Market Insider — {issue.edition_label or issue.published_date.strftime('%b %Y')}"
    html = render_to_string("newsletter/email_issue.html", {"issue": issue, "issue_url": issue_url})
    return subject, html, issue_url