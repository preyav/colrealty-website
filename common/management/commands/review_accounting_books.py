import json
from django.core.management.base import BaseCommand,CommandError
from accounting.book_models import AccountingEntity,PropertyBooks
from accounting.book_reports import coverage,owner_funds

class Command(BaseCommand):
    help='Read-only accounting readiness review. Does not import, alter or post historical records.'
    def add_arguments(self,parser):
        parser.add_argument('--entity',type=int)
        parser.add_argument('--output')
    def handle(self,*args,**options):
        configs=PropertyBooks.objects.all()
        if options['entity']:configs=configs.filter(entity_id=options['entity'])
        rows=[]
        for config in configs.select_related('entity','property'):
            status=coverage(config)
            rows.append({'entity_id':config.entity_id,'entity':str(config.entity),'property_id':config.property_id,'property':str(config.property),'enabled':config.enabled,**status})
        from accounting.journal_models import JournalEntry
        unassigned=list(JournalEntry.objects.filter(book_posting__isnull=True).values('id','date','memo','property_id'))
        result={'unassigned_journals':unassigned,'entities':list(AccountingEntity.objects.values('id','name','default_basis','is_active')),'properties':rows,'warning':'Existing unassigned journals must be matched to sources before importing those sources. No automatic matching or opening balance conversion is performed.'}
        payload=json.dumps(result,indent=2,default=str)
        if options['output']:
            try:
                with open(options['output'],'x',encoding='utf-8') as output:output.write(payload+'\n')
            except OSError as exc:raise CommandError(str(exc)) from exc
        self.stdout.write(payload)
