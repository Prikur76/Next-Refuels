from django.db import migrations, models


def migrate_duplicate_to_deletion(apps, schema_editor):
    FuelRecord = apps.get_model("core", "FuelRecord")
    FuelRecord.objects.filter(
        reporting_status="EXCLUDED_DUPLICATE",
    ).update(reporting_status="EXCLUDED_DELETION")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_fuelrecord_reporting_status_filled_at_idx"),
    ]

    operations = [
        migrations.RunPython(
            migrate_duplicate_to_deletion,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="fuelrecord",
            name="reporting_status",
            field=models.CharField(
                choices=[
                    ("ACTIVE", "Учитывается"),
                    ("EXCLUDED_DELETION", "На удаление"),
                ],
                default="ACTIVE",
                max_length=32,
                verbose_name="Статус учёта в отчётах",
            ),
        ),
    ]
