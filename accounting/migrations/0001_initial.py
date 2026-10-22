from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="ChartAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=20, unique=True)),
                ("name", models.CharField(max_length=150)),
                ("account_type", models.CharField(choices=[("asset", "Asset"), ("liability", "Liability"), ("equity", "Equity"), ("income", "Income"), ("expense", "Expense")], db_index=True, max_length=20)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["code", "name"]},
        ),
        migrations.CreateModel(
            name="FinancialAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150, unique=True)),
                ("kind", models.CharField(choices=[("bank", "Bank Account"), ("trust", "Trust Account"), ("cash", "Cash / Petty Cash"), ("credit_card", "Credit Card"), ("other", "Other")], max_length=20)),
                ("institution_name", models.CharField(blank=True, max_length=150)),
                ("account_last_four", models.CharField(blank=True, max_length=4)),
                ("opening_balance", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("opening_balance_date", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("ledger_account", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="financial_account", to="accounting.chartaccount")),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddConstraint(
            model_name="chartaccount",
            constraint=models.UniqueConstraint(fields=("name", "account_type"), name="accounting_unique_chart_name_per_type"),
        ),
    ]
