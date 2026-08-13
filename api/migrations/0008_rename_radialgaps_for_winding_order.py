from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0007_rename_radialgaps_lvtohv"),
    ]

    operations = [
        migrations.RenameField(
            model_name="radialgaps",
            old_name="lvToFine",
            new_name="hvToFine",
        ),
        migrations.RenameField(
            model_name="radialgaps",
            old_name="lvToCoarse",
            new_name="hvToCorse",
        ),
        migrations.RenameField(
            model_name="radialgaps",
            old_name="fineToCoarse",
            new_name="corseToFine",
        ),
        migrations.RenameField(
            model_name="radialgaps",
            old_name="coarseToOuter",
            new_name="corseToOuter",
        ),
    ]
