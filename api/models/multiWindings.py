from django.db import models


class MultiWindings(models.Model):
    designId = models.CharField(max_length=255, blank=True, default="")
    windings = models.CharField(max_length=255, blank=True, default="")
    kVA = models.FloatField(default=0.0)
    kValue = models.FloatField(default=0.0)
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
    lvWindings = models.OneToOneField(
        "Windings",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lvMultiWindings",
    )
    hvWindings = models.OneToOneField(
        "Windings",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hvMultiWindings",
    )
    fineWindings = models.OneToOneField(
        "Windings",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fineMultiWindings",
    )
    corseWindings = models.OneToOneField(
        "Windings",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="corseMultiWindings",
    )
    outerWindings = models.OneToOneField(
        "Windings",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outerMultiWindings",
    )

    radialGaps = models.ForeignKey("RadialGaps", on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"MultiWindings {self.pk or 'unsaved'}"

    def winding_formula_context(self):
        from api.services.windingFormulae import build_winding_formula_context

        return build_winding_formula_context(self)

    def winding_formulae(self):
        from api.services.windingFormulae import calculate_winding_formulae

        return calculate_winding_formulae(self)
