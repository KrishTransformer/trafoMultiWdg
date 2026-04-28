from django.db import models


class CoilDimensions(models.Model):
    coreDia = models.IntegerField(default=0)
    coreGap = models.FloatField(null=True, blank=True)
    lVID = models.IntegerField(default=0)
    lVRadial = models.IntegerField(default=0)
    lVOD = models.IntegerField(default=0)
    lVHVGap = models.FloatField(null=True, blank=True)
    hVID = models.IntegerField(default=0)
    hVRadial = models.IntegerField(default=0)
    hVOD = models.IntegerField(default=0)
    hVHVGap = models.FloatField(null=True, blank=True)
    activePartSize = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return f"CoilDimensions {self.pk or 'unsaved'}"
