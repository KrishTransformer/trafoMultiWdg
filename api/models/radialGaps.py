from django.db import models


class RadialGaps(models.Model):
    coreToLv = models.FloatField(default=0.0)
    lvToHv = models.FloatField(default=0.0)

    hvToFine = models.FloatField(default=0.0)
    hvToCorse = models.FloatField(default=0.0)
    hvToOuter = models.FloatField(default=0.0)

    corseToFine = models.FloatField(default=0.0)
    fineToOuter = models.FloatField(default=0.0)

    corseToOuter = models.FloatField(default=0.0)

    def __str__(self):
        return f"RadialGaps {self.pk or 'unsaved'}"
