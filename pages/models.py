# Create your models here.
from django.db import models
from django.utils.text import slugify


class Agent(models.Model):

    ROLE_CHOICES = [
        ('broker',  'Broker'),
        ('agent',   'Agent'),
        ('investor', 'Investor & Broker'),
    ]

    # ── Core Info ──────────────────────────────────────────
    name        = models.CharField(max_length=100)
    slug        = models.SlugField(max_length=120, unique=True, blank=True,
                                   help_text="Auto-filled from name. Used in the URL e.g. /agents/preya-sundaram/")
    role        = models.CharField(max_length=20, choices=ROLE_CHOICES, default='agent')
    photo       = models.ImageField(upload_to='agents/', blank=True, null=True,
                                    help_text="Agent headshot (recommended: square crop)")
    location    = models.CharField(max_length=100, default='Cedar Park · Austin, TX')
    bio         = models.TextField(blank=True, help_text="About the agent — shown on their profile page")

    # ── Contact ────────────────────────────────────────────
    email       = models.EmailField()
    phone       = models.CharField(max_length=20, blank=True, help_text="Display format e.g. (512) 123-4567")

    # ── Stats ──────────────────────────────────────────────
    years_exp   = models.PositiveIntegerField(default=0, verbose_name="Years of Experience")
    deals       = models.CharField(max_length=20, blank=True, default='—',
                                   help_text="e.g. 120  or  —  if unknown")
    rating      = models.DecimalField(max_digits=3, decimal_places=1, default=5.0)

    # ── Social ─────────────────────────────────────────────
    linkedin    = models.URLField(blank=True)
    facebook    = models.URLField(blank=True)
    instagram   = models.URLField(blank=True)
    twitter     = models.URLField(blank=True)

    # ── Display order ──────────────────────────────────────
    order       = models.PositiveIntegerField(default=0,
                                              help_text="Lower number = appears first on the team page")
    is_active   = models.BooleanField(default=True, help_text="Uncheck to hide agent from the website")

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Agent'
        verbose_name_plural = 'Agents'

    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"

    def save(self, *args, **kwargs):
        # Auto-generate slug from name if not set
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def first_name(self):
        return self.name.split()[0]

    @property
    def initials(self):
        parts = self.name.split()
        return ''.join(p[0].upper() for p in parts[:2])

    @property
    def phone_raw(self):
        """Strip formatting for tel: links e.g. +15121234567"""
        digits = ''.join(filter(str.isdigit, self.phone))
        return f"+1{digits}" if len(digits) == 10 else f"+{digits}"

    @property
    def role_display(self):
        return self.get_role_display()


class AgentSpecialty(models.Model):
    agent       = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='specialties')
    name        = models.CharField(max_length=80, help_text="e.g. Buyer's Agent, Relocation, Commercial")
    order       = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Specialty'
        verbose_name_plural = 'Specialties'

    def __str__(self):
        return self.name


class AgentTestimonial(models.Model):
    agent       = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='testimonials')
    author      = models.CharField(max_length=100)
    text        = models.TextField()
    order       = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        verbose_name = 'Testimonial'
        verbose_name_plural = 'Testimonials'

    def __str__(self):
        return f"{self.agent.first_name} — {self.author}"
    


    #______________________________________________________________________
    #   LEGAL CODUMENTS UPLOAD
    #______________________________________________________________________

def legal_doc_upload_path(instance, filename):
    return f'legal_docs/{filename}'

class LegalDocument(models.Model):
    DOC_TYPES = [
        ('privacy',  'Privacy Statement'),
        ('trec',     'TREC Information'),
        ('iabs',     'IABS Notice'),
        ('other',    'Other'),
    ]
    title       = models.CharField(max_length=200)
    doc_type    = models.CharField(max_length=20, choices=DOC_TYPES, default='other')
    file        = models.FileField(upload_to=legal_doc_upload_path)
    description = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True)
    order       = models.PositiveIntegerField(default=0)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'title']

    def __str__(self):
        return self.title
    
    #_____________________________________________________________________________

