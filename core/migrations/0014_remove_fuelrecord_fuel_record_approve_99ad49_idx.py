from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0013_remove_fuelrecord_approved"),
    ]

    # Индекс удален в миграции 0013 (до удаления колонки approved),
    # поэтому здесь оставляем no-op.
    operations = []

