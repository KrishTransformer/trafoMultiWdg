from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0004_coildimensions_coilcoilgap"),
    ]

    operations = [
        migrations.AddField(
            model_name="radialgaps",
            name="hvToOuter",
            field=models.FloatField(default=0.0),
        ),
    ]
