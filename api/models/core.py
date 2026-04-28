from django.db import models


class Core(models.Model):
    coreType = models.CharField(max_length=255, blank=True, default="0")
    coreDia = models.IntegerField(null=True, blank=True)
    limbHt = models.FloatField(null=True, blank=True)
    cenDist = models.FloatField(default=0.0)
    area = models.FloatField(default=0.0)
    blade = models.CharField(max_length=255, blank=True, default="0")
    wKgGrade = models.FloatField(default=0.0)
    fluxDensity = models.FloatField(default=0.0)
    coreWeight = models.FloatField(default=0.0)
    coreMaterial = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return f"Core {self.coreType or self.pk or 'unsaved'}"
