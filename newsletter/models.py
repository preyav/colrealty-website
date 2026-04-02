from django.db import models
from django.utils import timezone
from django.urls import reverse

class NewsletterIssue(models.Model):
    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("published", "Published"),
        ("archived", "Archived"),
    )

    title = models.CharField(max_length=200)  # "Central Texas Market Insider"
    edition_label = models.CharField(max_length=50, blank=True)  # "March 2026"
    slug = models.SlugField(max_length=220, unique=True)
    published_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_count = models.PositiveIntegerField(default=0)
    body_html = models.TextField(blank=True)
    hero_title = models.CharField(max_length=220, blank=True)
    hero_subtitle = models.CharField(max_length=300, blank=True)

    # Optional: used for SEO / share
    meta_description = models.CharField(max_length=160, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_date"]

    def __str__(self):
        if self.edition_label:
            label = self.edition_label
        elif self.published_date:
            label = self.published_date.strftime("%b %Y")
        else:
            label = "Unscheduled"

        return f"{self.title} — {label}"

    def get_absolute_url(self):
        return reverse("newsletter:newsletter_detail", kwargs={"slug": self.slug})


class NewsletterSection(models.Model):
    issue = models.ForeignKey(NewsletterIssue, related_name="sections", on_delete=models.CASCADE)

    # "Market Snapshot", "For Buyers", "For Sellers", etc.
    heading = models.CharField(max_length=200)
    icon_emoji = models.CharField(max_length=10, blank=True)  # "📊"
    order = models.PositiveIntegerField(default=1)

    # CMS-managed rich content:
    body = models.TextField(blank=True)

    # Optional: allow a section to show MLS stats block automatically
    show_mls_stats = models.BooleanField(default=False)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.issue.slug} — {self.heading}"


class Subscriber(models.Model):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80, blank=True)
    zip_code = models.CharField(max_length=12, blank=True)

    is_active = models.BooleanField(default=True)
    source = models.CharField(max_length=50, default="website")  # website, openhouse, etc.

    hubspot_submitted = models.BooleanField(default=False)
    hubspot_response = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email
        