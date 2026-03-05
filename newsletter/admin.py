from django.contrib import admin
from .models import NewsletterIssue, NewsletterSection, Subscriber

class NewsletterSectionInline(admin.TabularInline):
    model = NewsletterSection
    extra = 1

@admin.register(NewsletterIssue)
class NewsletterIssueAdmin(admin.ModelAdmin):
    list_display = ("title", "edition_label", "published_date", "status")
    list_filter = ("status",)
    search_fields = ("title", "edition_label", "slug")
    prepopulated_fields = {"slug": ("title", "edition_label")}
    inlines = [NewsletterSectionInline]

@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "is_active", "hubspot_submitted", "created_at")
    list_filter = ("is_active", "hubspot_submitted")
    search_fields = ("email", "first_name", "last_name", "zip_code")