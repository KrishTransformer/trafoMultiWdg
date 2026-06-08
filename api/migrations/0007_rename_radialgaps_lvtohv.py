from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0006_remove_radialgaps_lvtoouter"),
    ]

    operations = [
        migrations.RenameField(
            model_name="radialgaps",
            old_name="LvtoHV",
            new_name="lvToHv",
        ),
    ]
