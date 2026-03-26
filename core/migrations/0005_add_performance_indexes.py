from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_alter_systemlog_action"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="fuelrecord",
            index=models.Index(
                fields=["historical_region", "filled_at"],
                name="fuel_historic_reg_fill_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="systemlog",
            index=models.Index(
                fields=["created_at"],
                name="syslog_created_at_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="systemlog",
            index=models.Index(
                fields=["action", "created_at"],
                name="syslog_action_created_idx",
            ),
        ),
    ]
