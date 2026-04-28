from django.db import models


class RadialGaps(models.Model):
    coreToLv = models.FloatField(default=0.0)
    LvtoHV = models.FloatField(default=0.0)

    lvToFine = models.FloatField(default=0.0)
    lvToCoarse = models.FloatField(default=0.0)
    lvToOuter = models.FloatField(default=0.0)

    fineToCoarse = models.FloatField(default=0.0)
    fineToOuter = models.FloatField(default=0.0)

    coarseToOuter = models.FloatField(default=0.0)

    def __str__(self):
        return f"RadialGaps {self.pk or 'unsaved'}"
