def build_winding_formula_context(multi_winding):
    return {
        "designId": multi_winding.designId,
        "windings": multi_winding.windings,
        "ratings": {
            "kVA": multi_winding.kVA,
            "kValue": multi_winding.kValue,
            "lowVoltage": multi_winding.lowVoltage,
            "highVoltage": multi_winding.highVoltage,
        },
        "currentDensity": {
            "lv": multi_winding.lvCurrentDensity,
            "hv": multi_winding.hvCurrentDensity,
            "fine": multi_winding.fineCurrentDensity,
            "corse": multi_winding.corseCurrentDensity,
            "outer": multi_winding.outerCurrentDensity,
        },
        "conductorMaterial": {
            "lv": multi_winding.lvConductorMaterial,
            "hv": multi_winding.hvConductorMaterial,
            "fine": multi_winding.fineConductorMaterial,
            "corse": multi_winding.corseConductorMaterial,
            "outer": multi_winding.outerConductorMaterial,
        },
        "tapSteps": {
            "percentage": multi_winding.tapStepsPercentage,
            "positive": multi_winding.tapStepPositive,
            "negative": multi_winding.tapStepNegative,
        },
        "windingModels": {
            "lv": multi_winding.lvWindings,
            "hv": multi_winding.hvWindings,
            "fine": multi_winding.fineWindings,
            "corse": multi_winding.corseWindings,
            "outer": multi_winding.outerWindings,
        },
        "radialGaps": multi_winding.radialGaps,
    }


def calculate_winding_formulae(multi_winding):
    context = build_winding_formula_context(multi_winding)
    return {
        "inputs": context,
        "results": {},
        "notes": [
            "Start adding winding formulae in api/services/windingFormulae.py.",
            "Use the context dict to read model values and populate results.",
        ],
    }
