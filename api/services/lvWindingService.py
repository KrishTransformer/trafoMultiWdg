import math

from api.models import Windings
from api.services.windingFormulae import (
    CLASS_B,
    ECONOMIC,
    COPPER,
    get_actual_conductor_x_sec,
    get_axial_parallel_conductors,
    get_bare_weight,
    get_conductor_cross_section,
    get_conductor_insulation,
    get_core_diameter,
    get_core_lv_gap,
    get_current_density,
    get_current_per_phase,
    get_duct_size,
    get_end_clearance,
    get_gross_core_area,
    get_height,
    get_height_insulated,
    get_id,
    get_insulated_weight,
    get_inter_layer_insulation,
    get_load_loss,
    get_lmt,
    get_lv_gradient,
    get_lv_end_clearance,
    get_lv_hv_gap,
    get_lv_volts_per_phase,
    get_net_area,
    get_number_of_conductors,
    get_perma_wood_ring,
    get_procurement_weight,
    get_radial_parallel_conductors,
    get_radial_thickness,
    get_r26,
    get_r75,
    get_revised_conductor_cross_section,
    get_revised_flux_density,
    get_revised_volts_per_turn,
    get_round_cond_dia,
    get_stray_loss,
    get_turns_per_phase,
    get_volts_per_turn,
    get_window_height,
    get_winding_length,
    get_wire_length,
    get_x_sec_per_conductor,
    get_od,
    is_conductor_round,
    one_digit_decimal,
    three_digit_decimal,
    two_digit_decimal,
)


def _safe_winding(winding):
    return winding if winding is not None else Windings()


def _safe_positive(value, fallback):
    if value is None:
        return fallback
    return value if value > 0 else fallback


def _dry_type(multi_winding):
    return bool(getattr(multi_winding, "dryType", False))


def _dry_temp_class(multi_winding):
    return getattr(multi_winding, "dryTempClass", CLASS_B)


def _trans_cost_type(multi_winding):
    return getattr(multi_winding, "transCostType", ECONOMIC)


def _lv_material(multi_winding):
    return (multi_winding.lvConductorMaterial or COPPER).upper()


def calculate_lv_windings(multi_winding):
    winding = _safe_winding(getattr(multi_winding, "lvWindings", None))
    dry_type = _dry_type(multi_winding)
    dry_temp_class = _dry_temp_class(multi_winding)
    trans_cost_type = _trans_cost_type(multi_winding)
    vector_group = multi_winding.vectorGroup
    material = _lv_material(multi_winding)

    k_value = multi_winding.kValue
    volts_per_turn = get_volts_per_turn(k_value, multi_winding.kVA) if k_value and multi_winding.kVA else None
    lv_volts_per_phase = get_lv_volts_per_phase(multi_winding.lowVoltage, vector_group)
    lv_turns_per_phase = get_turns_per_phase(
        lv_volts_per_phase,
        volts_per_turn,
        winding.turnsPerPhase,
        vector_group,
        True,
    )
    revised_volts_per_turn = get_revised_volts_per_turn(lv_volts_per_phase, lv_turns_per_phase)
    net_area = get_net_area(revised_volts_per_turn, multi_winding.frequency, multi_winding.fluxDensity)
    gross_area = get_gross_core_area(net_area, get_core_diameter(net_area))
    core_diameter = int(math.ceil(get_core_diameter(gross_area)))
    revised_flux_density = get_revised_flux_density(revised_volts_per_turn, multi_winding.frequency, net_area)

    lv_current_per_phase = get_current_per_phase(multi_winding.kVA, lv_volts_per_phase)
    current_density = get_current_density(
        material,
        trans_cost_type,
        dry_type,
        dry_temp_class,
        True,
        multi_winding.lvCurrentDensity if multi_winding.lvCurrentDensity > 0 else None,
    )
    window_height = get_window_height(
        k_value,
        core_diameter,
        material,
        getattr(getattr(multi_winding, "core", None), "limbHt", None),
        dry_type,
    )
    end_clearance = get_lv_end_clearance(
        multi_winding.kVA,
        vector_group,
        winding.endClearances if winding.endClearances > 0 else None,
        dry_type,
        multi_winding.lowVoltage,
        multi_winding.highVoltage,
    )
    perma_wood_ring = get_perma_wood_ring(multi_winding.kVA, multi_winding.lowVoltage, dry_type)
    winding_length = get_winding_length(window_height, end_clearance, perma_wood_ring)

    conductor_cross_section = get_conductor_cross_section(lv_current_per_phase, current_density)
    number_of_conductors = get_number_of_conductors(conductor_cross_section, material)
    conductor_flag = getattr(multi_winding, "lvConductorFlag", 0)
    radial_parallel = get_radial_parallel_conductors(number_of_conductors, conductor_flag, winding.radialParallelCond)
    axial_parallel = get_axial_parallel_conductors(number_of_conductors, radial_parallel, winding.axialParallelCond)
    number_of_conductors = radial_parallel * axial_parallel
    cross_sec_per_conductor = get_x_sec_per_conductor(conductor_cross_section, number_of_conductors)

    user_round = winding.isConductorRound
    is_round = user_round if user_round is not None else is_conductor_round(cross_sec_per_conductor)
    is_enamel = bool(winding.isEnamel)
    conductor_insulation = get_conductor_insulation(
        multi_winding.kVA,
        multi_winding.lowVoltage,
        is_round,
        vector_group,
        is_enamel,
        winding.condInsulation,
        dry_type,
    )

    if is_round:
        breadth = get_round_cond_dia(cross_sec_per_conductor, winding.conductorDiameter or winding.condBreadth, material)
        height = breadth
        revised_cond_cross_section = two_digit_decimal(math.pi * math.pow(breadth, 2) / 4)
    else:
        user_height = winding.condHeight if winding.condHeight is not None else 1.6
        breadth = winding.condBreadth if winding.condBreadth is not None else one_digit_decimal(max(2.0, math.sqrt(cross_sec_per_conductor * 4)))
        height = user_height if winding.condHeight is not None else get_height(cross_sec_per_conductor, breadth)
        if winding.condBreadth is None and winding.condHeight is None:
            while breadth > 6 * height:
                height = one_digit_decimal(height + 0.1)
                breadth = get_height(cross_sec_per_conductor, height)
                if breadth <= 6 * height:
                    break
        revised_cond_cross_section = get_revised_conductor_cross_section(breadth, height)

    breadth_insulated = get_height_insulated(breadth, conductor_insulation)
    height_insulated = get_height_insulated(height, conductor_insulation)
    turns_per_layer = max(1, int(math.floor((winding_length or 1) / max(breadth_insulated * axial_parallel, 0.1))))
    number_of_layers = two_digit_decimal(lv_turns_per_phase / turns_per_layer)
    revised_current_density = three_digit_decimal(lv_current_per_phase / (revised_cond_cross_section * number_of_conductors))
    total_cond_cross_section = get_actual_conductor_x_sec(revised_cond_cross_section, number_of_conductors)
    inter_layer_insulation = get_inter_layer_insulation(
        revised_volts_per_turn,
        turns_per_layer,
        conductor_insulation,
        is_enamel,
        winding.interLayerInsulation,
        dry_type,
    )
    no_of_ducts = max(0, winding.ducts or 0)
    duct_thickness = get_duct_size(multi_winding.kVA, winding_length, winding.ductSize, dry_type)
    radial_thickness = get_radial_thickness(
        height_insulated,
        radial_parallel,
        number_of_layers,
        inter_layer_insulation,
        no_of_ducts,
        duct_thickness,
        True,
    )
    core_gap = get_core_lv_gap(
        multi_winding.kVA,
        multi_winding.lowVoltage,
        getattr(getattr(multi_winding, "radialGaps", None), "coreToLv", None),
        dry_type,
    )
    lv_id = get_id(core_diameter, core_gap)
    lv_od = get_od(lv_id, radial_thickness)
    lv_lmt = get_lmt(lv_id, lv_od)
    wire_length = get_wire_length(lv_lmt, lv_turns_per_phase, 3, number_of_conductors)
    r75 = get_r75(material, lv_lmt, lv_turns_per_phase, total_cond_cross_section)
    r26 = get_r26(r75, material)
    bare_weight = get_bare_weight(lv_lmt, lv_turns_per_phase, total_cond_cross_section, material)
    insulated_weight = get_insulated_weight(
        breadth_insulated,
        height_insulated,
        breadth,
        height,
        material,
        bare_weight,
        is_enamel,
    )
    procurement_weight = get_procurement_weight(insulated_weight, number_of_conductors)
    stray_loss = get_stray_loss(
        breadth,
        breadth_insulated,
        height,
        turns_per_layer,
        radial_parallel,
        axial_parallel,
        conductor_insulation,
        material,
        number_of_layers,
        0,
        is_round,
    )
    load_loss = get_load_loss(material, bare_weight, revised_current_density, stray_loss)
    gradient = get_lv_gradient(
        load_loss,
        (no_of_ducts * 2) + 2,
        winding_length,
        0,
        lv_lmt,
        dry_type,
        True,
    )
    lv_hv_gap = get_lv_hv_gap(
        multi_winding.kVA,
        multi_winding.highVoltage,
        vector_group,
        getattr(getattr(multi_winding, "radialGaps", None), "LvtoHV", None),
        dry_type,
    )

    return {
        "revisedFluxDensity": revised_flux_density,
        "lvVoltsPerPhase": lv_volts_per_phase,
        "lvTurnsPerPhase": lv_turns_per_phase,
        "revisedVoltsPerTurn": revised_volts_per_turn,
        "netArea": net_area,
        "grossArea": gross_area,
        "coreDiameter": core_diameter,
        "lvCurrentPerPhase": lv_current_per_phase,
        "windowHeight": window_height,
        "lvEndClearance": end_clearance,
        "permaWoodRing": perma_wood_ring,
        "lvWindingLength": winding_length,
        "lvNumberOfLayers": number_of_layers,
        "lvTurnsPerLayer": turns_per_layer,
        "lvConductorCrossSection": conductor_cross_section,
        "lvCrossSecPerConductor": cross_sec_per_conductor,
        "lvNumberOfConductors": number_of_conductors,
        "lvRadialParallelConductors": radial_parallel,
        "lvAxialParallelConductors": axial_parallel,
        "lvConductorInsulation": conductor_insulation,
        "lvIsConductorRound": is_round,
        "lvIsEnamel": is_enamel,
        "lvBreadth": breadth,
        "lvHeight": height,
        "lvBreadthInsulated": breadth_insulated,
        "lvHeightInsulated": height_insulated,
        "lvRevisedCondCrossSection": revised_cond_cross_section,
        "lvTotalCondCrossSection": total_cond_cross_section,
        "lVRevisedCurrentDensity": revised_current_density,
        "lvInterLayerInsulation": inter_layer_insulation,
        "lvRadialThickness": radial_thickness,
        "coreGap": core_gap,
        "lvId": lv_id,
        "lvOd": lv_od,
        "lvLmt": lv_lmt,
        "lvWireLength": wire_length,
        "lvR75": r75,
        "lvR26": r26,
        "lvBareWeight": bare_weight,
        "lvInsulatedWeight": insulated_weight,
        "lvProcurementWeight": procurement_weight,
        "%lvStrayLoss": stray_loss,
        "lvLoadLoss": load_loss,
        "lvGradient": gradient,
        "lvHvGap": lv_hv_gap,
        "lvNoOfDuct": no_of_ducts,
        "lvDuctThickness": duct_thickness,
    }
