import uuid
from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError


def immutable_error():
    from .general_ledger import wording
    return ValidationError(wording()['immutable'])


class JournalEntry(models.Model):
    entry_token=models.UUIDField(default=uuid.uuid4,unique=True,editable=False)
    date=models.DateField(db_index=True)
    memo=models.TextField()
    property=models.ForeignKey('properties.Property',null=True,blank=True,on_delete=models.PROTECT,related_name='journal_entries')
    unit=models.ForeignKey('properties.PropertyUnit',null=True,blank=True,on_delete=models.PROTECT,related_name='journal_entries')
    fund_type=models.CharField(max_length=40,blank=True)
    reversal_of=models.OneToOneField('self',null=True,blank=True,on_delete=models.PROTECT,related_name='reversal')
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering=['date','pk']

    def save(self,*args,**kwargs):
        if not self._state.adding:raise immutable_error()
        return super().save(*args,**kwargs)

    def delete(self,*args,**kwargs):raise immutable_error()


class JournalLine(models.Model):
    journal=models.ForeignKey(JournalEntry,on_delete=models.PROTECT,related_name='lines')
    account=models.ForeignKey('accounting.ChartAccount',on_delete=models.PROTECT,related_name='journal_lines')
    debit=models.DecimalField(max_digits=14,decimal_places=2,default=0)
    credit=models.DecimalField(max_digits=14,decimal_places=2,default=0)

    class Meta:
        ordering=['journal__date','journal_id','pk']
        constraints=[models.CheckConstraint(condition=(models.Q(debit__gt=0,credit=0)|models.Q(credit__gt=0,debit=0)),name='journal_line_one_positive_side')]

    def save(self,*args,**kwargs):
        if not self._state.adding:raise immutable_error()
        return super().save(*args,**kwargs)

    def delete(self,*args,**kwargs):raise immutable_error()
