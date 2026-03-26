from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0009_user_must_change_password"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="zone",
        ),
    ]
