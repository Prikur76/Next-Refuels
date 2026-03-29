from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0015_car_is_fuel_tanker"),
    ]

    operations = [
        migrations.AddField(
            model_name="fuelrecord",
            name="reporting_status",
            field=models.CharField(
                choices=[
                    ("ACTIVE", "Учитывается"),
                    ("EXCLUDED_DUPLICATE", "Исключена (дубликат)"),
                    ("EXCLUDED_DELETION", "На удаление"),
                ],
                default="ACTIVE",
                max_length=32,
                verbose_name="Статус учёта в отчётах",
            ),
        ),
    ]
