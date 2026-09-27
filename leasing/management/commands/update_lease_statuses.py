from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from leasing.models import Lease


class Command(BaseCommand):
    help = "Expire Active leases whose end date has passed and sync unit occupancy."

    def handle(self, *args, **options):
        today = timezone.localdate()

        expired_count = 0
        vacated_unit_count = 0

        expired_leases = list(
            Lease.objects.filter(
                status="active",
                end_date__lt=today,
            )
            .select_related("unit")
            .order_by("end_date")
        )

        with transaction.atomic():
            for lease in expired_leases:
                lease.status = "expired"
                lease.save(update_fields=["status", "updated_at"])
                expired_count += 1

                unit = lease.unit

                has_current_active_lease = (
                    Lease.objects.filter(
                        unit=unit,
                        status="active",
                        start_date__lte=today,
                        end_date__gte=today,
                    )
                    .exclude(pk=lease.pk)
                    .exists()
                )

                if not has_current_active_lease and unit.status != "vacant":
                    unit.status = "vacant"
                    unit.save(update_fields=["status", "updated_at"])
                    vacated_unit_count += 1

        if expired_count:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Expired {expired_count} lease(s); "
                    f"marked {vacated_unit_count} unit(s) vacant."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "No Active leases needed expiration."
                )
            )