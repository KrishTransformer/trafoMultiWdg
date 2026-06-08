from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0005_radialgaps_hvtoouter"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="radialgaps",
            name="lvToOuter",
        ),
    ]
