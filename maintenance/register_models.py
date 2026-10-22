"""Property inspection and inventory registers; independent of financial postings."""
from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from common.models import FormFieldSetting


class PropertyRegister(models.Model):
    property=models.ForeignKey('properties.Property',on_delete=models.PROTECT)
    unit=models.ForeignKey('properties.PropertyUnit',null=True,blank=True,on_delete=models.PROTECT)
    title=models.CharField(max_length=180)
    status=models.CharField(max_length=40)
    notes=models.TextField(blank=True)
    document_link=models.URLField(max_length=1500,blank=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    class Meta:
        abstract=True
        ordering=['property__street_address','title','pk']

    def clean(self):
        if self.unit_id and self.property_id and self.unit.property_id!=self.property_id:
            row=FormFieldSetting.objects.filter(form_key='property_registers',field_key='ui').first()
            raise ValidationError({'unit':row.option_labels.get('unit_mismatch','') if row else 'Unit/property mismatch.'})

    def __str__(self):return self.title


class PropertyInspection(PropertyRegister):
    scheduled_on=models.DateField()
    completed_on=models.DateField(null=True,blank=True)
    inspection_type=models.CharField(max_length=40)
    assigned_to=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.PROTECT,related_name='+')

    def clean(self):
        super().clean()
        if self.status=='completed' and not self.completed_on:
            row=FormFieldSetting.objects.filter(form_key='property_registers',field_key='ui').first()
            raise ValidationError({'completed_on':row.option_labels.get('completed_required','') if row else 'Completion date required.'})


class PropertyAsset(PropertyRegister):
    quantity=models.PositiveIntegerField(default=1)
    manufacturer=models.CharField(max_length=120,blank=True)
    model_number=models.CharField(max_length=120,blank=True)
    serial_number=models.CharField(max_length=120,blank=True)
    installed_on=models.DateField(null=True,blank=True)
    warranty_until=models.DateField(null=True,blank=True)

    def clean(self):
        super().clean()
        if self.quantity is not None and self.quantity<1:
            row=FormFieldSetting.objects.filter(form_key='property_registers',field_key='ui').first()
            raise ValidationError({'quantity':row.option_labels.get('quantity_positive','') if row else 'Quantity must be positive.'})
