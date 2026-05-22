from api.utils.number_format import round_to_next_5or0


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

def getLvVoltsPerPhase(vectorGroup, lowVoltage):
    return vectorGroup[0] == "y" and lowVoltage / (3 ** 0.5) or lowVoltage

def getLvVoltsPerTurn(kValue, kVA):
    return round(kValue * kVA, 3)

def getLvTurnsPerPhase(voltsPerPhase, voltsPerTurn):
    return voltsPerPhase / voltsPerTurn

def getLvCurrentPerPhase(kVA, lowVoltage):
    return kVA * 1000 / (3 ** 0.5 * lowVoltage)

def getRevisedVoltsPerPhase(voltsPerPhase, turnsPerPhase):
    return round(voltsPerPhase / turnsPerPhase, 3)

def getNetArea(revisedVoltsPerPhase, frequency, fluxDensity):
    return round(revisedVoltsPerPhase / (4.44 * frequency * fluxDensity * (10 ** -6)), 3)

def grossArea(netArea, coreDia):
    factor = 1
    if coreDia <= 100:
        factor = 0.88
    elif coreDia <= 150:
        factor = 0.9
    elif coreDia <= 200:
        factor = 0.91
    elif coreDia <= 250:
        factor = 0.92
    elif coreDia > 300:
        factor = 0.93
    return round_to_next_5or0(netArea / factor)

def getRevisedFluxDensity(revisedVoltsPerPhase, frequency, netArea):
    return round(revisedVoltsPerPhase / (4.44 * frequency * netArea * (10 ** -6)), 4)

