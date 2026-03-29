from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0016_fuelrecord_reporting_status"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="fuelrecord",
            index=models.Index(
                fields=["reporting_status", "filled_at"],
                name="fuel_reporting_fill_idx",
            ),
        ),
    ]
