# Register your models here.
from django.contrib import admin
from .models import Agent, AgentSpecialty, AgentTestimonial
from .models import LegalDocument

class AgentSpecialtyInline(admin.TabularInline):
    model   = AgentSpecialty
    extra   = 2
    fields  = ('name', 'order')


class AgentTestimonialInline(admin.StackedInline):
    model   = AgentTestimonial
    extra   = 1
    fields  = ('author', 'text', 'order')


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display  = ('name', 'role', 'email', 'phone', 'rating', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    list_filter   = ('role', 'is_active')
    search_fields = ('name', 'email')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Core Info', {
            'fields': ('name', 'slug', 'role', 'photo', 'location', 'bio')
        }),
        ('Contact', {
            'fields': ('email', 'phone')
        }),
        ('Stats', {
            'fields': ('years_exp', 'deals', 'rating')
        }),
        ('Social Media', {
            'fields': ('linkedin', 'facebook', 'instagram', 'twitter'),
            'classes': ('collapse',),
        }),
        ('Display Settings', {
            'fields': ('order', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    inlines = [AgentSpecialtyInline, AgentTestimonialInline]

#___________________________________________________
#    LEGAL DOCUMENTS
#_________________________________________________

@admin.register(LegalDocument)
class LegalDocumentAdmin(admin.ModelAdmin):
    list_display  = ['title', 'doc_type', 'is_active', 'order', 'updated_at']
    list_editable = ['is_active', 'order']
    list_filter   = ['doc_type', 'is_active']
