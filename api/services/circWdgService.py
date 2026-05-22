from api.models import CoilDimensions, Core, Windings
from api.services.hvWindingService import calculate_hv_windings
from api.services.lvWindingService import calculate_lv_windings
from api.services.windingFormulae import (
    CLASS_B,
    COPPER,
    ECONOMIC,
    ampere_turns,
    build_winding_formula_context,
    ek,
    er,
    ex,
    get_build_factor,
    get_core_lv_ins,
    get_core_material,
    get_core_type,
    get_current_density,
    get_efficiency_percentage,
    get_flux_density,
    get_frequency,
    get_high_voltage,
    get_hv_hv_ins,
    get_k_value,
    get_limit_ez,
    get_loss_at_100_percent,
    get_loss_at_50_percent,
    get_low_voltage,
    get_lv_hv_ins,
    get_nl_current_percentage,
    get_test_and_imp_test,
    get_vector_group,
    get_voltage_regulation,
    h1h2,
    is_ez_within_range,
    ls,
)


def _default_core(multi_winding):
    core = getattr(multi_winding, "core", None)
    if core is None:
        core = Core()
        multi_winding.core = core
    return core


def _default_winding(multi_winding, attr_name):
    winding = getattr(multi_winding, attr_name, None)
    if winding is None:
        winding = Windings()
        setattr(multi_winding, attr_name, winding)
    return winding


def _default_coil_dimensions(multi_winding):
    coil_dimensions = getattr(multi_winding, "coilDimensions", None)
    if coil_dimensions is None:
        coil_dimensions = CoilDimensions()
        multi_winding.coilDimensions = coil_dimensions
    return coil_dimensions


def _normalize_winding_type(multi_winding, attr_name, default_value):
    value = getattr(multi_winding, attr_name, None)
    return value if value else default_value


def _apply_defaults(multi_winding):
    dry_type = bool(getattr(multi_winding, "dryType", False))
    dry_temp_class = getattr(multi_winding, "dryTempClass", CLASS_B)
    trans_cost_type = getattr(multi_winding, "transCostType", ECONOMIC)

    multi_winding.frequency = get_frequency(multi_winding.frequency)
    multi_winding.vectorGroup = get_vector_group(multi_winding.vectorGroup)
    multi_winding.lowVoltage = get_low_voltage(multi_winding.lowVoltage)
    multi_winding.highVoltage = get_high_voltage(multi_winding.highVoltage)
    multi_winding.fluxDensity = get_flux_density(multi_winding.fluxDensity, dry_type)
    multi_winding.lvConductorMaterial = (multi_winding.lvConductorMaterial or COPPER).upper()
    multi_winding.hvConductorMaterial = (multi_winding.hvConductorMaterial or COPPER).upper()
    multi_winding.kValue = get_k_value(
        multi_winding.kVA,
        multi_winding.kValue if multi_winding.kValue > 0 else None,
        multi_winding.lvConductorMaterial,
        trans_cost_type,
    )
    multi_winding.lvCurrentDensity = get_current_density(
        multi_winding.lvConductorMaterial,
        trans_cost_type,
        dry_type,
        dry_temp_class,
        True,
        multi_winding.lvCurrentDensity if multi_winding.lvCurrentDensity > 0 else None,
    )
    multi_winding.hvCurrentDensity = get_current_density(
        multi_winding.hvConductorMaterial,
        trans_cost_type,
        dry_type,
        dry_temp_class,
        False,
        multi_winding.hvCurrentDensity if multi_winding.hvCurrentDensity > 0 else None,
    )
    multi_winding.buildFactor = get_build_factor(
        multi_winding.kVA,
        getattr(_default_core(multi_winding), "coreType", None) or get_core_type(None),
        getattr(multi_winding, "buildFactor", None),
    )
    _default_core(multi_winding).coreMaterial = get_core_material(getattr(_default_core(multi_winding), "coreMaterial", None))
    multi_winding.lvWindingType = _normalize_winding_type(multi_winding, "lvWindingType", "HELICAL")
    multi_winding.hvWindingType = _normalize_winding_type(multi_winding, "hvWindingType", "HELICAL")
    multi_winding.limitEz = get_limit_ez(multi_winding.kVA, getattr(multi_winding, "limitEz", None))
    _default_coil_dimensions(multi_winding)
    _default_winding(multi_winding, "lvWindings")
    _default_winding(multi_winding, "hvWindings")
    return multi_winding


def _parallel_label(radial_parallel, axial_parallel, total_conductors):
    if total_conductors > 1:
        return f"Rad {radial_parallel} X Axi {axial_parallel} = {total_conductors}"
    return str(total_conductors)


def _conductor_size_label(breadth, height, is_round):
    if is_round:
        return f"Round {breadth}"
    return f"{breadth} X {height}"


def _apply_lv_results_to_model(winding, lv_results, winding_type):
    winding.turnsPerPhase = lv_results["lvTurnsPerPhase"]
    winding.phaseCurrent = lv_results["lvCurrentPerPhase"]
    winding.currentDensity = lv_results["lVRevisedCurrentDensity"]
    winding.condCrossSec = lv_results["lvTotalCondCrossSection"]
    winding.conductorSizes = _conductor_size_label(
        lv_results["lvBreadth"],
        lv_results["lvHeight"],
        lv_results["lvIsConductorRound"],
    )
    winding.condInsulation = lv_results["lvConductorInsulation"]
    winding.noInParallel = _parallel_label(
        lv_results["lvRadialParallelConductors"],
        lv_results["lvAxialParallelConductors"],
        lv_results["lvNumberOfConductors"],
    )
    winding.windingLength = lv_results["lvWindingLength"]
    winding.noOfLayers = lv_results["lvNumberOfLayers"]
    winding.turnsPerLayer = lv_results["lvTurnsPerLayer"]
    winding.endClearances = lv_results["lvEndClearance"]
    winding.eddyStrayLoss = lv_results["%lvStrayLoss"]
    winding.tempGradDegC = lv_results["lvGradient"]
    winding.ducts = lv_results["lvNoOfDuct"]
    winding.ductSize = lv_results["lvDuctThickness"]
    winding.insulatedWeight = lv_results["lvInsulatedWeight"]
    winding.bareWeight = lv_results["lvBareWeight"]
    winding.loadLoss = lv_results["lvLoadLoss"]
    winding.interLayerInsulation = lv_results["lvInterLayerInsulation"]
    winding.noOfDuctsWidth = f'{lv_results["lvNoOfDuct"]} / {lv_results["lvDuctThickness"]}'
    if winding_type == "DISC":
        winding.turnsLayers = str(lv_results.get("lvDiscArrangement", ""))
    else:
        winding.turnsLayers = str(lv_results["lvTurnsPerLayer"])
    winding.weightBareInsulated = f'{lv_results["lvBareWeight"]} / {lv_results["lvInsulatedWeight"]}'
    winding.radialParallelCond = lv_results["lvRadialParallelConductors"]
    winding.axialParallelCond = lv_results["lvAxialParallelConductors"]
    winding.condBreadth = lv_results["lvBreadth"]
    winding.condHeight = lv_results["lvHeight"]
    winding.conductorDiameter = lv_results["lvBreadth"]
    winding.isConductorRound = lv_results["lvIsConductorRound"]
    winding.isEnamel = lv_results["lvIsEnamel"]


def _apply_hv_results_to_model(winding, hv_results, winding_type):
    winding.turnsPerPhase = hv_results["hvTurnsPerPhase"]
    winding.phaseCurrent = hv_results["hvCurrentPerPhase"]
    winding.currentDensity = hv_results["hVRevisedCurrDenAtNormal"]
    winding.condCrossSec = hv_results["hvTotalCondCrossSection"]
    winding.conductorSizes = _conductor_size_label(
        hv_results["hvBreadth"],
        hv_results["hvHeight"],
        hv_results["hvIsConductorRound"],
    )
    winding.condInsulation = hv_results["hvConductorInsulation"]
    winding.noInParallel = _parallel_label(
        hv_results["hvRadialParallelConductors"],
        hv_results["hvAxialParallelConductors"],
        hv_results["hvNoOfConductors"],
    )
    winding.windingLength = hv_results["hvWindingLength"]
    winding.noOfLayers = hv_results["hvNumberOfLayers"]
    winding.turnsPerLayer = hv_results["hvTurnsPerLayer"]
    winding.endClearances = hv_results["hvEndClearance"]
    winding.eddyStrayLoss = hv_results["%hvStrayLoss"]
    winding.tempGradDegC = hv_results["hvGradient"]
    winding.ducts = hv_results["hvNoOfDuct"]
    winding.ductSize = hv_results["hvDuctThickness"]
    winding.insulatedWeight = hv_results["hvInsulatedWeight"]
    winding.bareWeight = hv_results["hvBareWeight"]
    winding.loadLoss = hv_results["hvLoadLossAtNormal"]
    winding.interLayerInsulation = hv_results["hvInterLayerInsulation"]
    winding.noOfDuctsWidth = f'{hv_results["hvNoOfDuct"]} / {hv_results["hvDuctThickness"]}'
    if winding_type in {"DISC", "DOUBLE_DISC"}:
        winding.turnsLayers = str(hv_results.get("hvDiscArrangement", ""))
    elif winding_type == "XOVER":
        winding.turnsLayers = str(hv_results.get("hvXOverTurnsLayers", ""))
    else:
        winding.turnsLayers = str(hv_results["hvTurnsPerLayer"])
    winding.weightBareInsulated = f'{hv_results["hvBareWeight"]} / {hv_results["hvInsulatedWeight"]}'
    winding.radialParallelCond = hv_results["hvRadialParallelConductors"]
    winding.axialParallelCond = hv_results["hvAxialParallelConductors"]
    winding.condBreadth = hv_results["hvBreadth"]
    winding.condHeight = hv_results["hvHeight"]
    winding.conductorDiameter = hv_results["hvBreadth"]
    winding.isConductorRound = hv_results["hvIsConductorRound"]
    winding.isEnamel = hv_results["hvIsEnamel"]


def calculate_circ_wdg(multi_winding):
    multi_winding = _apply_defaults(multi_winding)
    core = _default_core(multi_winding)
    coil_dimensions = _default_coil_dimensions(multi_winding)
    lv_winding_model = _default_winding(multi_winding, "lvWindings")
    hv_winding_model = _default_winding(multi_winding, "hvWindings")

    lv_results = calculate_lv_windings(multi_winding)
    hv_results = calculate_hv_windings(multi_winding, lv_results)
    _apply_lv_results_to_model(lv_winding_model, lv_results, multi_winding.lvWindingType)
    _apply_hv_results_to_model(hv_winding_model, hv_results, multi_winding.hvWindingType)

    ampere_turn_value = ampere_turns(lv_results["lvTurnsPerPhase"], lv_results["lvCurrentPerPhase"])
    h1 = h1h2(
        lv_results["lvRadialThickness"],
        lv_results["lvNoOfDuct"],
        lv_results["lvDuctThickness"],
        lv_results["lvConductorInsulation"],
    )
    h2 = h1h2(
        hv_results["hvRadialThickness"],
        hv_results["hvNoOfDuct"],
        hv_results["hvDuctThickness"],
        hv_results["hvConductorInsulation"],
    )
    ls_values = ls(
        lv_results["lvBreadthInsulated"],
        hv_results["hvBreadthInsulated"],
        lv_results["lvTurnsPerLayer"],
        hv_results["hvTurnsPerLayer"],
        lv_results["lvAxialParallelConductors"],
        hv_results["hvAxialParallelConductors"],
        hv_results["hvOd"],
        lv_results["lvId"],
        lv_results["lvConductorInsulation"],
        hv_results["hvConductorInsulation"],
        lv_results["lvWindingLength"],
        hv_results["hvWindingLength"],
        multi_winding.lvWindingType,
        multi_winding.hvWindingType,
        0,
        hv_results["hvTransposition"] if "hvTransposition" in hv_results else 0,
        hv_results["hvNoOfCoils"] if "hvNoOfCoils" in hv_results else 0,
    )
    ex_values = ex(
        lv_results["revisedVoltsPerTurn"],
        lv_results["lvHvGap"],
        lv_results["lvConductorInsulation"],
        hv_results["hvConductorInsulation"],
        h1,
        h2,
        ampere_turn_value,
        ls_values[0],
        lv_results["lvOd"],
        multi_winding.frequency / 50 if multi_winding.frequency != 50 else 1,
    )
    er_value = er(
        lv_results["lvLoadLoss"],
        hv_results["hvLoadLossAtNormal"],
        multi_winding.kVA,
        lv_results["lvCurrentPerPhase"],
        multi_winding.lowVoltage,
    )
    ek_value = ek(er_value, ex_values[3])

    coil_dimensions.coreDia = lv_results["coreDiameter"]
    coil_dimensions.coreGap = lv_results["coreGap"]
    coil_dimensions.lVID = lv_results["lvId"]
    coil_dimensions.lVRadial = lv_results["lvRadialThickness"]
    coil_dimensions.lVOD = lv_results["lvOd"]
    coil_dimensions.lVHVGap = hv_results["lvHvGap"]
    coil_dimensions.hVID = hv_results["hvId"]
    coil_dimensions.hVRadial = hv_results["hvRadialThickness"]
    coil_dimensions.hVOD = hv_results["hvOd"]
    coil_dimensions.hVHVGap = hv_results["hvHvGap"]
    coil_dimensions.activePartSize = hv_results["activePartSize"]

    core.coreDia = lv_results["coreDiameter"]
    core.limbHt = lv_results["windowHeight"]
    core.area = lv_results["netArea"]
    core.cenDist = hv_results["centerDistance"]
    core.fluxDensity = lv_results["revisedFluxDensity"]
    core.coreWeight = hv_results["coreWeight"]
    core.coreType = get_core_type(core.coreType)

    inputs = build_winding_formula_context(multi_winding)
    inputs["core"] = core
    inputs["coilDimensions"] = coil_dimensions

    common = {
        "frequency": multi_winding.frequency,
        "buildFactor": multi_winding.buildFactor,
        "fluxDensity": multi_winding.fluxDensity,
        "coreMaterial": core.coreMaterial,
        "lowVoltage": multi_winding.lowVoltage,
        "highVoltage": multi_winding.highVoltage,
        "vectorGroup": multi_winding.vectorGroup,
        "kValue": multi_winding.kValue,
        "lVCurrentDensity": multi_winding.lvCurrentDensity,
        "hVCurrentDensity": multi_winding.hvCurrentDensity,
        "ampereTurns": ampere_turn_value,
        "h1": h1,
        "h2": h2,
        "ls": ls_values[0],
        "l": ls_values[1],
        "b": ls_values[2],
        "kR": ls_values[3],
        "delta": ex_values[0],
        "delta1": ex_values[1],
        "ds": ex_values[2],
        "ex": ex_values[3],
        "er": er_value,
        "ek": ek_value,
    }

    losses_at_50 = get_loss_at_50_percent(
        hv_results["coreLoss"],
        hv_results["tankLoss"],
        lv_results["lvLoadLoss"],
        hv_results["hvLoadLossAtNormal"],
    )
    losses_at_100 = get_loss_at_100_percent(
        hv_results["coreLoss"],
        hv_results["tankLoss"],
        lv_results["lvLoadLoss"],
        hv_results["hvLoadLossAtNormal"],
    )

    return {
        "inputs": inputs,
        "results": {
            "voltsPerTurn": multi_winding.kValue and round(multi_winding.kValue * (multi_winding.kVA ** 0.5), 3) or None,
            "revisedVoltsPerTurn": lv_results["revisedVoltsPerTurn"],
            "lvVoltsPerPhase": lv_results["lvVoltsPerPhase"],
            "hvVoltsPerPhase": hv_results["hvVoltsPerPhase"],
            "lvTurnsPerPhase": lv_results["lvTurnsPerPhase"],
            "hvTurnsPerPhase": hv_results["hvTurnsPerPhase"],
            "lvCurrentPerPhase": lv_results["lvCurrentPerPhase"],
            "hvCurrentPerPhase": hv_results["hvCurrentPerPhase"],
            "lvEndClearance": lv_results["lvEndClearance"],
            "hvEndClearance": hv_results["hvEndClearance"],
            "lvWinding": lv_results,
            "hvWinding": hv_results,
            "common": common,
            "core": {
                "coreDia": core.coreDia,
                "limbHt": core.limbHt,
                "area": core.area,
                "cenDist": core.cenDist,
                "fluxDensity": core.fluxDensity,
                "coreWeight": core.coreWeight,
                "coreType": core.coreType,
                "coreMaterial": core.coreMaterial,
            },
            "coilDimensions": {
                "coreDia": coil_dimensions.coreDia,
                "coreGap": coil_dimensions.coreGap,
                "lVID": coil_dimensions.lVID,
                "lVRadial": coil_dimensions.lVRadial,
                "lVOD": coil_dimensions.lVOD,
                "lVHVGap": coil_dimensions.lVHVGap,
                "hVID": coil_dimensions.hVID,
                "hVRadial": coil_dimensions.hVRadial,
                "hVOD": coil_dimensions.hVOD,
                "hVHVGap": coil_dimensions.hVHVGap,
                "activePartSize": coil_dimensions.activePartSize,
            },
            "ez": {
                "value": ek_value,
                "limit": multi_winding.limitEz,
                "withinRange": is_ez_within_range(
                    multi_winding.limitEz,
                    ek_value,
                    20 if multi_winding.kVA <= 10 else 5,
                ),
            },
            "efficiencyAndVr": {
                "efficiencyAtUnity100": get_efficiency_percentage(multi_winding.kVA, hv_results["totalLoadLoss"], hv_results["coreLoss"], 1.0, 1.0),
                "efficiencyAtUnity75": get_efficiency_percentage(multi_winding.kVA, hv_results["totalLoadLoss"], hv_results["coreLoss"], 0.75, 1.0),
                "efficiencyAtUnity50": get_efficiency_percentage(multi_winding.kVA, hv_results["totalLoadLoss"], hv_results["coreLoss"], 0.5, 1.0),
                "voltageRegulation100": get_voltage_regulation(er_value, ex_values[3], 1.0),
                "voltageRegulation80": get_voltage_regulation(er_value, ex_values[3], 0.8),
            },
            "testVoltages": {
                "lv": {
                    "test": get_test_and_imp_test(multi_winding.lowVoltage)[0],
                    "impulse": get_test_and_imp_test(multi_winding.lowVoltage)[1],
                },
                "hv": {
                    "test": get_test_and_imp_test(multi_winding.highVoltage)[0],
                    "impulse": get_test_and_imp_test(multi_winding.highVoltage)[1],
                },
            },
            "insulation": {
                "coreLv": get_core_lv_ins(multi_winding.lvWindingType, coil_dimensions.coreGap or 0),
                "lvHv": get_lv_hv_ins(multi_winding.lvWindingType, multi_winding.hvWindingType, coil_dimensions.lVHVGap or 0),
                "hvHv": get_hv_hv_ins(multi_winding.lvWindingType, multi_winding.hvWindingType, coil_dimensions.hVHVGap or 0),
            },
            "lossesAt50Percent": losses_at_50,
            "lossesAt100Percent": losses_at_100,
            "nlCurrentPercentage": get_nl_current_percentage(core.coreWeight, hv_results["coreLoss"], multi_winding.kVA) if multi_winding.kVA else 0,
        },
    }
