from django.db import models


class FormFieldSetting(models.Model):
    form_key = models.CharField(max_length=100)
    field_key = models.CharField(max_length=100)
    label = models.CharField(max_length=255)
    help_text = models.TextField(blank=True)
    option_labels = models.JSONField(default=dict, blank=True)
    error_messages = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['form_key', 'field_key']
        constraints = [models.UniqueConstraint(fields=['form_key', 'field_key'], name='unique_form_field_setting')]

    def __str__(self):
        return f'{self.form_key}: {self.label}'
