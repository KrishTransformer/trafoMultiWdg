from django.db import models

class MultiWindings(models.Model):
    designId = models.CharField(max_length=255, blank=True, default="")
    windings = models.CharField(max_length=255, blank=True, default="")
    kVA = models.FloatField(default=0.0)
    kValue = models.FloatField(default=0.0)
    frequency = models.IntegerField(default=50)
    fluxDensity = models.FloatField(default=1.7333)
    vectorGroup = models.CharField(max_length=255, blank=True, default="")
    lowVoltage = models.FloatField(default=0.0)
    highVoltage = models.FloatField(default=0.0)

    # All the Current Density fields
    lvCurrentDensity = models.FloatField(default=0.0)
    hvCurrentDensity = models.FloatField(default=0.0)
    fineCurrentDensity = models.FloatField(default=0.0)
    corseCurrentDensity = models.FloatField(default=0.0)
    outerCurrentDensity = models.FloatField(default=0.0)

    # Conductor Materials
    lvConductorMaterial = models.CharField(max_length=255, blank=True, default="")
    hvConductorMaterial = models.CharField(max_length=255, blank=True, default="") 
    fineConductorMaterial = models.CharField(max_length=255, blank=True, default="")
    corseConductorMaterial = models.CharField(max_length=255, blank=True, default="")
    outerConductorMaterial = models.CharField(max_length=255, blank=True, default="")

    # Tap Steps
    tapStepsPercentage = models.FloatField(null=True, blank=True)
    tapStepPositive = models.IntegerField(null=True, blank=True)
    tapStepNegative = models.IntegerField(null=True, blank=True)

    # Windings
    lvWindings = models.OneToOneField("Windings", on_delete=models.SET_NULL, null=True, blank=True, related_name="lv_multi_winding",)
    hvWindings = models.OneToOneField("Windings", on_delete=models.SET_NULL, null=True, blank=True, related_name="hv_multi_winding",)
    fineWindings = models.OneToOneField("Windings", on_delete=models.SET_NULL, null=True, blank=True, related_name="fine_multi_winding",)
    corseWindings = models.OneToOneField("Windings", on_delete=models.SET_NULL, null=True, blank=True, related_name="corse_multi_winding",)
    outerWindings = models.OneToOneField("Windings", on_delete=models.SET_NULL, null=True, blank=True, related_name="outer_multi_winding",)

    radialGaps = models.ForeignKey("RadialGaps", on_delete=models.SET_NULL, null=True, blank=True)


    def __str__(self):
        return f"MultiWindings {self.pk or 'unsaved'}"