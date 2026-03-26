from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_remove_user_zone"),
    ]

    operations = [
        migrations.DeleteModel(
            name="Zone",
        ),
    ]
