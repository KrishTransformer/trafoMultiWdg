from api.formulae.windingFormulae import getLvCurrentPerPhase, getLvTurnsPerPhase, getLvVoltsPerTurn, getLvVoltsPerPhase, build_winding_formula_context, getNetArea, getRevisedVoltsPerPhase, grossArea, getRevisedFluxDensity
from api.models.multiWindings import MultiWinding
from api.utils.number_format import circle_dia


def calculate_lv_windings(multi_winding):
    lvVoltsPerTurn = getLvVoltsPerTurn(multi_winding.kValue, multi_winding.kVA)
    lvVoltsPerPhase = getLvVoltsPerPhase(multi_winding.vectorGroup, multi_winding.lowVoltage)
    lvTurnsPerPhase = getLvTurnsPerPhase(lvVoltsPerPhase, lvVoltsPerTurn)
    lvCurrentPerPhase = getLvCurrentPerPhase(multi_winding.kVA, multi_winding.lowVoltage)
    lvRevisedVoltsPerPhase = getRevisedVoltsPerPhase(lvVoltsPerPhase, lvTurnsPerPhase)
    lvNetArea = getNetArea(lvRevisedVoltsPerPhase, multi_winding.frequency, multi_winding.fluxDensity)
    lvGrossArea = grossArea(lvNetArea, circle_dia(lvNetArea))
    
    coreDia = circle_dia(lvGrossArea)
    revisedFluxDensity = getRevisedFluxDensity(lvRevisedVoltsPerPhase, multi_winding.frequency, lvNetArea)
    windowHeight = 1.5 * coreDia
    
