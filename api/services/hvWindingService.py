import math

from api.models import Windings
from api.services.windingFormulae import (
    CLASS_B,
    ECONOMIC,
    COPPER,
    get_actual_conductor_x_sec,
    get_axial_parallel_conductors,
    get_bare_weight,
    get_center_distance,
    get_conductor_cross_section,
    get_conductor_insulation,
    get_core_length,
    get_core_loss,
    get_core_weight,
    get_current_density,
    get_current_per_phase,
    get_disc_duct_size,
    get_duct_size,
    get_end_clearance,
    get_gradient_limit,
    get_gap_between_coils,
    get_height,
    get_height_insulated,
    get_hv_gradient,
    get_hv_hv_gap,
    get_hv_volts_per_phase,
    get_id,
    get_insulated_weight,
    get_inter_layer_insulation,
    get_kw55,
    get_load_loss,
    get_lmt,
    get_lv_hv_gap,
    get_no_of_coils,
    get_od,
    get_number_of_conductors,
    get_procurement_weight,
    get_radial_parallel_conductors,
    get_radial_thickness,
    get_r26,
    get_r75,
    get_revised_conductor_cross_section,
    get_round_cond_dia,
    get_stray_loss,
    get_stray_loss_for_x_over,
    get_tank_loss,
    get_tap_currents,
    get_tap_voltages,
    get_turns_at_tap,
    get_turns_per_phase,
    get_winding_length,
    get_winding_length_per_coil,
    get_wire_length,
    get_x_sec_per_conductor,
    hv_step_voltage,
    is_conductor_round,
    next_integer,
    one_digit_decimal,
    three_digit_decimal,
    two_digit_decimal,
)


def _safe_winding(winding):
    return winding if winding is not None else Windings()


def _dry_type(multi_winding):
    return bool(getattr(multi_winding, "dryType", False))


def _dry_temp_class(multi_winding):
    return getattr(multi_winding, "dryTempClass", CLASS_B)


def _trans_cost_type(multi_winding):
    return getattr(multi_winding, "transCostType", ECONOMIC)


def _hv_material(multi_winding):
    return (multi_winding.hvConductorMaterial or COPPER).upper()


def _adjust_helical_hv_layers(hv_turns_at_highest, turns_per_layer):
    adjusted_turns_per_layer = max(1, int(math.floor(turns_per_layer)))
    number_of_layers_rough = hv_turns_at_highest / adjusted_turns_per_layer

    # Match the Java service: reduce T/L until the last layer exceeds 50%.
    while adjusted_turns_per_layer > 1 and (number_of_layers_rough % 1) <= 0.5:
        adjusted_turns_per_layer -= 1
        number_of_layers_rough = hv_turns_at_highest / adjusted_turns_per_layer
        if (number_of_layers_rough % 1) > 0.5:
            break

    return adjusted_turns_per_layer, two_digit_decimal(number_of_layers_rough)


def _two_digit_decimal_part(value):
    return abs(value - int(value))


def _half_up(value):
    return int(math.ceil(value)) if _two_digit_decimal_part(value) >= 0.5 else int(math.floor(value))


def _adjust_xover_hv_layers(hv_turns_per_coil, turns_per_layer):
    adjusted_turns_per_layer = max(1, int(math.floor(turns_per_layer)))
    number_of_layers_rough = hv_turns_per_coil / adjusted_turns_per_layer

    while adjusted_turns_per_layer > 1 and _two_digit_decimal_part(number_of_layers_rough) < 0.5:
        adjusted_turns_per_layer -= 1
        number_of_layers_rough = hv_turns_per_coil / adjusted_turns_per_layer

    return adjusted_turns_per_layer, int(math.ceil(number_of_layers_rough))


def calculate_hv_windings(multi_winding, lv_results):
    winding = _safe_winding(getattr(multi_winding, "hvWindings", None))
    dry_type = _dry_type(multi_winding)
    dry_temp_class = _dry_temp_class(multi_winding)
    trans_cost_type = _trans_cost_type(multi_winding)
    vector_group = multi_winding.vectorGroup
    material = _hv_material(multi_winding)

    volts_per_turn = lv_results["revisedVoltsPerTurn"]
    hv_volts_per_phase = get_hv_volts_per_phase(multi_winding.highVoltage, vector_group)
    tap_step_percent = multi_winding.tapStepsPercentage or 0
    tap_positive = multi_winding.tapStepPositive or 0
    tap_negative = multi_winding.tapStepNegative or 0
    hv_step = hv_step_voltage(hv_volts_per_phase, tap_step_percent)
    hv_turns_per_tap = two_digit_decimal(hv_step / volts_per_turn) if volts_per_turn else 0
    hv_highest_tap_voltage = hv_volts_per_phase + (hv_step * tap_positive)
    hv_lowest_tap_voltage = hv_volts_per_phase - (hv_step * tap_negative)
    hv_turns_per_phase = get_turns_per_phase(
        hv_volts_per_phase,
        volts_per_turn,
        winding.turnsPerPhase,
        vector_group,
        False,
    )
    hv_turns_at_highest = int(math.floor(hv_turns_per_phase + (hv_turns_per_tap * tap_positive)))
    hv_turns_at_lowest = int(math.floor(hv_turns_per_phase - (hv_turns_per_tap * tap_negative)))

    hv_current_per_phase = get_current_per_phase(multi_winding.kVA, hv_volts_per_phase)
    hv_current_at_lowest = get_current_per_phase(multi_winding.kVA, max(hv_lowest_tap_voltage, 1))
    current_density = get_current_density(
        material,
        trans_cost_type,
        dry_type,
        dry_temp_class,
        False,
        multi_winding.hvCurrentDensity if multi_winding.hvCurrentDensity > 0 else None,
    )
    end_clearance = get_end_clearance(
        multi_winding.kVA,
        multi_winding.highVoltage,
        vector_group,
        winding.endClearances if winding.endClearances > 0 else None,
        dry_type,
        False,
    )
    winding_length = get_winding_length(lv_results["windowHeight"], end_clearance, lv_results["permaWoodRing"])
    duct_thickness = get_duct_size(multi_winding.kVA, winding_length, winding.ductSize, dry_type)
    conductor_cross_section = get_conductor_cross_section(hv_current_at_lowest, current_density)
    no_of_conductors = get_number_of_conductors(conductor_cross_section, material)
    conductor_flag = getattr(multi_winding, "hvConductorFlag", 0)
    radial_parallel = get_radial_parallel_conductors(no_of_conductors, conductor_flag, winding.radialParallelCond)
    axial_parallel = get_axial_parallel_conductors(no_of_conductors, radial_parallel, winding.axialParallelCond)
    no_of_conductors = radial_parallel * axial_parallel
    cross_sec_per_conductor = get_x_sec_per_conductor(conductor_cross_section, no_of_conductors)

    user_round = winding.isConductorRound
    is_round = user_round if user_round is not None else is_conductor_round(cross_sec_per_conductor)
    is_enamel = bool(winding.isEnamel)
    conductor_insulation = get_conductor_insulation(
        multi_winding.kVA,
        multi_winding.highVoltage,
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
    winding_type = str(getattr(multi_winding, "hvWindingType", "HELICAL") or "HELICAL").upper()
    transposition = 20 if radial_parallel > 1 else 0
    hv_no_of_coils = 0
    hv_gap_bw_coil = 0
    hv_wdg_length_per_coil = 0

    if winding_type == "XOVER":
        hv_no_of_coils = get_no_of_coils(multi_winding.highVoltage, None)
        hv_turns_per_coil = _half_up(hv_turns_at_highest / max(hv_no_of_coils, 1))
        hv_turns_at_highest = hv_turns_per_coil * hv_no_of_coils
        hv_gap_bw_coil = get_gap_between_coils(multi_winding.kVA, multi_winding.highVoltage, dry_type)
        hv_wdg_length_per_coil = get_winding_length_per_coil(winding_length, hv_gap_bw_coil, hv_no_of_coils)
        duct_thickness = get_duct_size(multi_winding.kVA, hv_wdg_length_per_coil, winding.ductSize, dry_type)
        turns_per_layer = max(1, int(math.floor(hv_wdg_length_per_coil / max(breadth_insulated * axial_parallel, 0.1))) - 1)
        turns_per_layer, number_of_layers = _adjust_xover_hv_layers(hv_turns_per_coil, turns_per_layer)
        hv_wdg_length_per_coil = next_integer(breadth_insulated * axial_parallel * (turns_per_layer + 1))
        hv_gap_bw_coil = int(math.floor((winding_length - (hv_wdg_length_per_coil * hv_no_of_coils)) / max(hv_no_of_coils, 1)))
        winding_length = (hv_wdg_length_per_coil * hv_no_of_coils) + (hv_gap_bw_coil * (hv_no_of_coils - 1))
        end_clearance = max(0, lv_results["windowHeight"] - winding_length)
    else:
        turns_per_layer = max(1, int(math.floor((winding_length - transposition) / max(breadth_insulated * axial_parallel, 0.1))))
        turns_per_layer, number_of_layers = _adjust_helical_hv_layers(hv_turns_at_highest, turns_per_layer)
        winding_length = next_integer((turns_per_layer + 1) * (breadth_insulated * axial_parallel))
        end_clearance = max(0, lv_results["windowHeight"] - winding_length - transposition)
    revised_curr_den_normal = three_digit_decimal(hv_current_per_phase / (revised_cond_cross_section * no_of_conductors))
    revised_curr_den_lowest = three_digit_decimal(hv_current_at_lowest / (revised_cond_cross_section * no_of_conductors))
    total_cond_cross_section = get_actual_conductor_x_sec(revised_cond_cross_section, no_of_conductors)
    inter_layer_insulation = get_inter_layer_insulation(
        volts_per_turn,
        turns_per_layer,
        conductor_insulation,
        is_enamel,
        winding.interLayerInsulation,
        dry_type,
    )
    no_of_ducts = max(0, winding.ducts or 0)
    if no_of_ducts > number_of_layers - 1:
        no_of_ducts = max(0, int(number_of_layers) - 1)
    hv_id = get_id(lv_results["lvOd"], lv_results["lvHvGap"])
    radial_thickness = get_radial_thickness(
        height_insulated,
        radial_parallel,
        number_of_layers,
        inter_layer_insulation,
        no_of_ducts,
        duct_thickness,
        False,
    )
    hv_od = get_od(hv_id, radial_thickness)
    hv_lmt = get_lmt(hv_id, hv_od)
    wire_length = get_wire_length(hv_lmt, hv_turns_at_highest, 3, no_of_conductors)
    r75 = get_r75(material, hv_lmt, hv_turns_per_phase, total_cond_cross_section)
    r26 = get_r26(r75, material)
    bare_weight = get_bare_weight(hv_lmt, hv_turns_at_highest, total_cond_cross_section, material)
    insulated_weight = get_insulated_weight(
        breadth_insulated,
        height_insulated,
        breadth,
        height,
        material,
        bare_weight,
        is_enamel,
    )
    procurement_weight = get_procurement_weight(insulated_weight, no_of_conductors)
    if winding_type == "XOVER":
        stray_loss = get_stray_loss_for_x_over(
            breadth,
            height,
            turns_per_layer,
            hv_no_of_coils,
            radial_parallel,
            axial_parallel,
            conductor_insulation,
            material,
            number_of_layers,
            winding_length,
            is_round,
        )
    else:
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
            transposition,
            is_round,
        )
    load_loss_normal = next_integer(get_load_loss(material, bare_weight, revised_curr_den_normal, stray_loss) * (hv_turns_per_phase / max(hv_turns_at_highest, 1)))
    load_loss_lowest = next_integer(get_load_loss(material, bare_weight, revised_curr_den_lowest, stray_loss) * (hv_turns_at_lowest / max(hv_turns_at_highest, 1)))
    gradient = get_hv_gradient(load_loss_lowest, (no_of_ducts * 2) + 2, winding_length, transposition, hv_lmt, dry_type)

    no_of_steps = tap_positive + tap_negative + 1
    turns_per_tap = get_turns_at_tap(multi_winding.highVoltage, no_of_steps, tap_negative, tap_step_percent, volts_per_turn, vector_group)
    tap_voltages = get_tap_voltages(multi_winding.highVoltage, tap_negative, tap_positive, tap_step_percent)
    tap_current = get_tap_currents(no_of_steps, tap_voltages, multi_winding.kVA)

    hv_hv_gap = get_hv_hv_gap(
        multi_winding.kVA,
        multi_winding.lowVoltage,
        multi_winding.highVoltage,
        vector_group,
        None,
        dry_type,
    )
    center_distance = get_center_distance(hv_od, hv_hv_gap)
    hv_hv_gap = center_distance - hv_od
    core_length = get_core_length(lv_results["coreDiameter"], lv_results["windowHeight"], center_distance)
    core_weight = get_core_weight(core_length, lv_results["netArea"])
    specific_loss = 0.0
    core_loss = get_core_loss(core_weight, getattr(multi_winding, "buildFactor", 1.25), specific_loss)
    tank_loss = get_tank_loss(multi_winding.kVA, lv_results["lvCurrentPerPhase"], multi_winding.lowVoltage, None, dry_type)
    total_load_loss = next_integer(lv_results["lvLoadLoss"] + load_loss_normal + tank_loss)
    kw55 = get_kw55(core_loss, lv_results["lvLoadLoss"], load_loss_lowest, tank_loss, lv_results["lvGradient"], gradient)
    gradient_limit = get_gradient_limit(dry_type, dry_temp_class)
    active_part_length = (2 * center_distance) + hv_od
    active_part_height = int((2 * lv_results["coreDiameter"]) + lv_results["windowHeight"])
    active_part_size = f"{active_part_length} L X {hv_od} W X {active_part_height} H mm"

    return {
        "lvHvGap": lv_results["lvHvGap"],
        "hvVoltsPerPhase": hv_volts_per_phase,
        "hvStepVoltage": hv_step,
        "hvTurnsPerTap": hv_turns_per_tap,
        "hvHighestTapVoltage": hv_highest_tap_voltage,
        "hvLowestTapVoltage": hv_lowest_tap_voltage,
        "hvTurnsPerPhase": hv_turns_per_phase,
        "hvTurnsAtHighest": hv_turns_at_highest,
        "hvTurnsAtLowest": hv_turns_at_lowest,
        "hvCurrentPerPhase": hv_current_per_phase,
        "hvCurrentAtLowest": hv_current_at_lowest,
        "hVRevisedCurrDenAtNormal": revised_curr_den_normal,
        "hVRevisedCurrDenAtLowest": revised_curr_den_lowest,
        "hvEndClearance": end_clearance,
        "hvWindingLength": winding_length,
        "hvConductorCrossSection": conductor_cross_section,
        "hvCrossSecPerConductor": cross_sec_per_conductor,
        "hvNoOfConductors": no_of_conductors,
        "hvRadialParallelConductors": radial_parallel,
        "hvAxialParallelConductors": axial_parallel,
        "hvConductorInsulation": conductor_insulation,
        "hvIsConductorRound": is_round,
        "hvIsEnamel": is_enamel,
        "hvBreadth": breadth,
        "hvHeight": height,
        "hvBreadthInsulated": breadth_insulated,
        "hvHeightInsulated": height_insulated,
        "hvTurnsPerLayer": turns_per_layer,
        "hvNumberOfLayers": number_of_layers,
        "hvNoOfCoils": hv_no_of_coils,
        "hvGapBwCoil": hv_gap_bw_coil,
        "hvWdgLengthPerCoil": hv_wdg_length_per_coil,
        "hvRevisedCondCrossSection": revised_cond_cross_section,
        "hvTotalCondCrossSection": total_cond_cross_section,
        "hvInterLayerInsulation": inter_layer_insulation,
        "hvNoOfDuct": no_of_ducts,
        "hvDuctThickness": duct_thickness,
        "hvRadialThickness": radial_thickness,
        "hvId": hv_id,
        "hvOd": hv_od,
        "hvLmt": hv_lmt,
        "hvWireLength": wire_length,
        "hvR75": r75,
        "hvR26": r26,
        "hvBareWeight": bare_weight,
        "hvInsulatedWeight": insulated_weight,
        "hvProcurementWeight": procurement_weight,
        "%hvStrayLoss": stray_loss,
        "hvLoadLossAtNormal": load_loss_normal,
        "hvLoadLossAtLowest": load_loss_lowest,
        "hvGradient": gradient,
        "turnsPerTap": turns_per_tap,
        "tapVoltages": tap_voltages,
        "tapCurrent": tap_current,
        "hvHvGap": hv_hv_gap,
        "centerDistance": center_distance,
        "coreLength": core_length,
        "coreWeight": core_weight,
        "coreLoss": core_loss,
        "tankLoss": tank_loss,
        "totalLoadLoss": total_load_loss,
        "kW55": kw55,
        "gradientLimit": gradient_limit,
        "activePartSize": active_part_size,
        "hvDiscDuctsSize": get_disc_duct_size(multi_winding.highVoltage, False, vector_group, None),
    }
