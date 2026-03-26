from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0012_alter_systemlog_google_sheets_actions"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="fuelrecord",
            name="fuel_record_approve_99ad49_idx",
        ),
        migrations.RemoveField(
            model_name="fuelrecord",
            name="approved",
        ),
    ]

