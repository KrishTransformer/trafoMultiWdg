from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0003_core_radialgaps_multiwindings"),
    ]

    operations = [
        migrations.AddField(
            model_name="coildimensions",
            name="coilCoilGap",
            field=models.FloatField(blank=True, null=True),
        ),
    ]
