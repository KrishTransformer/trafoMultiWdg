from django.db import models


class Windings(models.Model):
    turnsPerPhase = models.FloatField(null=True, blank=True)
    phaseCurrent = models.FloatField(default=0.0)
    currentDensity = models.FloatField(default=0.0)
    condCrossSec = models.FloatField(default=0.0)
    conductorSizes = models.CharField(max_length=255, blank=True, default="")
    condInsulation = models.FloatField(null=True, blank=True)
    noInParallel = models.CharField(max_length=255, blank=True, default="")
    windingLength = models.FloatField(default=0.0)
    noOfLayers = models.FloatField(null=True, blank=True)
    turnsPerLayer = models.FloatField(default=0.0)
    terminal = models.FloatField(default=0.0)
    endClearances = models.FloatField(default=0.0)
    eddyStrayLoss = models.FloatField(default=0.0)
    tempGradDegC = models.FloatField(default=0.0)
    ducts = models.IntegerField(null=True, blank=True)
    ductSize = models.IntegerField(null=True, blank=True)
    insulatedWeight = models.FloatField(default=0.0)
    bareWeight = models.FloatField(default=0.0)
    loadLoss = models.FloatField(default=0.0)
    commRawCond = models.FloatField(default=0.0)
    interLayerInsulation = models.FloatField(null=True, blank=True)
    noOfDuctsWidth = models.CharField(max_length=255, blank=True, default="")
    turnsLayers = models.TextField(null=True, blank=True)
    weightBareInsulated = models.CharField(max_length=255, blank=True, default="")
    radialParallelCond = models.IntegerField(null=True, blank=True)
    axialParallelCond = models.IntegerField(null=True, blank=True)
    condBreadth = models.FloatField(null=True, blank=True)
    condHeight = models.FloatField(null=True, blank=True)
    conductorDiameter = models.FloatField(null=True, blank=True)
    isConductorRound = models.BooleanField(null=True, blank=True)
    isEnamel = models.BooleanField(null=True, blank=True)

    def __str__(self):
        return f"Windings {self.pk or 'unsaved'}"
