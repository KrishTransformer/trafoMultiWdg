import math

from api.models import Windings
from api.services.windingFormulae import (
    CLASS_B,
    ECONOMIC,
    COPPER,
    get_actual_conductor_x_sec,
    get_axial_parallel_conductors,
    get_bare_weight,
    get_bi,
    get_breadth,
    get_conductor_cross_section,
    get_conductor_insulation,
    get_core_diameter,
    get_core_lv_gap,
    get_current_density,
    get_current_per_phase,
    get_disc_duct_size,
    get_disc_radial_thickness,
    get_disc_winding_length,
    get_duct_size,
    get_gross_core_area,
    get_height,
    get_height_insulated,
    get_id,
    get_insulated_weight,
    get_inter_layer_insulation,
    get_gradient_limit,
    get_load_loss,
    get_lmt,
    get_lv_end_clearance,
    get_lv_gradient,
    get_lv_hv_gap,
    get_lv_volts_per_phase,
    get_net_area,
    get_number_of_conductors,
    get_od,
    get_perma_wood_ring,
    get_procurement_weight,
    get_psi,
    get_radial_parallel_conductors,
    get_radial_thickness,
    get_r26,
    get_r75,
    get_revised_conductor_cross_section,
    get_revised_flux_density,
    get_revised_volts_per_turn,
    get_round_cond_dia,
    get_rw,
    get_spacers_and_width,
    get_stray_loss,
    get_stray_loss_for_disc,
    get_stray_loss_for_foil,
    get_turns_per_phase,
    get_transposition,
    get_v0,
    get_volts_per_turn,
    get_winding_length,
    get_window_height,
    get_wire_length,
    get_x_sec_per_conductor,
    get_foil_end_strip,
    get_foil_length,
    is_conductor_round,
    next_integer,
    one_digit_decimal,
    one_digit_decimal_floor,
    three_digit_decimal,
    two_digit_decimal,
    two_digit_decimal_part,
)


INSULATION_COMPRESSION = 0.93
INSULATION_EXPANSION = 1.07


def _safe_winding(winding):
    return winding if winding is not None else Windings()


def _dry_type(multi_winding):
    return bool(getattr(multi_winding, "dryType", False))


def _dry_temp_class(multi_winding):
    return getattr(multi_winding, "dryTempClass", CLASS_B)


def _trans_cost_type(multi_winding):
    return getattr(multi_winding, "transCostType", ECONOMIC)


def _lv_material(multi_winding):
    return (multi_winding.lvConductorMaterial or COPPER).upper()


def _normalize_winding_type(winding_type):
    normalized = str(winding_type or "HELICAL").upper().replace("-", "_").replace(" ", "_")
    if normalized == "LAYERDISC":
        return "LAYER_DISC"
    return normalized


def _half_up(value):
    floor_value = math.floor(value)
    return int(math.ceil(value)) if (value - floor_value) >= 0.5 else int(floor_value)


def _next_even_integer(value):
    even_value = int(math.ceil(value))
    if even_value % 2 != 0:
        even_value += 1
    return even_value


def _round_branch_layers(lv_turns_per_phase, turns_per_layer):
    adjusted_turns_per_layer = max(1, int(math.floor(turns_per_layer)))
    number_of_layers_rough = lv_turns_per_phase / adjusted_turns_per_layer

    # Match the Java service: reduce T/L once if the last layer is <= 50%.
    if adjusted_turns_per_layer > 1 and (number_of_layers_rough % 1) <= 0.5:
        adjusted_turns_per_layer -= 1
        number_of_layers_rough = lv_turns_per_phase / adjusted_turns_per_layer

    return adjusted_turns_per_layer, two_digit_decimal(number_of_layers_rough)


def _coerce_ducts(no_of_ducts, number_of_layers):
    if no_of_ducts > int(number_of_layers) - 1:
        return max(0, int(number_of_layers) - 1)
    return max(0, no_of_ducts)


def _build_base_context(multi_winding, winding):
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
    core_gap = get_core_lv_gap(
        multi_winding.kVA,
        multi_winding.lowVoltage,
        getattr(getattr(multi_winding, "radialGaps", None), "coreToLv", None),
        dry_type,
    )
    lv_hv_gap = get_lv_hv_gap(
        multi_winding.kVA,
        multi_winding.highVoltage,
        vector_group,
        getattr(getattr(multi_winding, "radialGaps", None), "LvtoHV", None),
        dry_type,
    )

    return {
        "kVA": multi_winding.kVA,
        "lowVoltage": multi_winding.lowVoltage,
        "highVoltage": multi_winding.highVoltage,
        "lvConductorFlag": getattr(multi_winding, "lvConductorFlag", 0),
        "dryType": dry_type,
        "dryTempClass": dry_temp_class,
        "transCostType": trans_cost_type,
        "vectorGroup": vector_group,
        "material": material,
        "voltsPerTurn": volts_per_turn,
        "revisedVoltsPerTurn": revised_volts_per_turn,
        "revisedFluxDensity": revised_flux_density,
        "lvVoltsPerPhase": lv_volts_per_phase,
        "lvTurnsPerPhase": lv_turns_per_phase,
        "netArea": net_area,
        "grossArea": gross_area,
        "coreDiameter": core_diameter,
        "lvCurrentPerPhase": lv_current_per_phase,
        "currentDensity": current_density,
        "windowHeight": window_height,
        "lvEndClearance": end_clearance,
        "permaWoodRing": perma_wood_ring,
        "lvWindingLength": winding_length,
        "coreGap": core_gap,
        "lvHvGap": lv_hv_gap,
        "gradientLimit": get_gradient_limit(dry_type, dry_temp_class),
        "windingType": _normalize_winding_type(getattr(multi_winding, "lvWindingType", "HELICAL")),
        "ambientTemp": getattr(multi_winding, "ambientTemp", 50) or 50,
        "windingTemp": getattr(multi_winding, "windingTemp", 55) or 55,
    }


def _finalize_result(ctx, values):
    result = dict(ctx)
    result.update(values)
    return result


def _apply_gradient_loop_helical(ctx, values, user_ducts):
    if user_ducts is not None:
        return values

    while values["lvGradient"] >= ctx["gradientLimit"] and values["lvNoOfDuct"] < values["lvNumberOfLayers"] - 1:
        values["lvNoOfDuct"] += 1
        values["lvRadialThickness"] = get_radial_thickness(
            values["lvHeightInsulated"],
            values["lvRadialParallelConductors"],
            values["lvNumberOfLayers"],
            values["lvInterLayerInsulation"],
            values["lvNoOfDuct"],
            values["lvDuctThickness"],
            True,
        )
        values["lvId"] = get_id(ctx["coreDiameter"], ctx["coreGap"])
        values["lvOd"] = get_od(values["lvId"], values["lvRadialThickness"])
        values["lvLmt"] = get_lmt(values["lvId"], values["lvOd"])
        values["lvWireLength"] = get_wire_length(values["lvLmt"], ctx["lvTurnsPerPhase"], 3, values["lvNumberOfConductors"])
        values["lvR75"] = get_r75(ctx["material"], values["lvLmt"], ctx["lvTurnsPerPhase"], values["lvTotalCondCrossSection"])
        values["lvR26"] = get_r26(values["lvR75"], ctx["material"])
        values["lvBareWeight"] = get_bare_weight(values["lvLmt"], ctx["lvTurnsPerPhase"], values["lvTotalCondCrossSection"], ctx["material"])
        values["lvInsulatedWeight"] = get_insulated_weight(
            values["lvBreadthInsulated"],
            values["lvHeightInsulated"],
            values["lvBreadth"],
            values["lvHeight"],
            ctx["material"],
            values["lvBareWeight"],
            values["lvIsEnamel"],
        )
        values["lvProcurementWeight"] = get_procurement_weight(values["lvInsulatedWeight"], values["lvNumberOfConductors"])
        values["%lvStrayLoss"] = get_stray_loss(
            values["lvBreadth"],
            values["lvBreadthInsulated"],
            values["lvHeight"],
            values["lvTurnsPerLayer"],
            values["lvRadialParallelConductors"],
            values["lvAxialParallelConductors"],
            values["lvConductorInsulation"],
            ctx["material"],
            values["lvNumberOfLayers"],
            values["lvTransposition"],
            values["lvIsConductorRound"],
        )
        current_density_for_loss = values.get("lvLoadLossCurrentDensity", values["lVRevisedCurrentDensity"])
        values["lvLoadLoss"] = get_load_loss(ctx["material"], values["lvBareWeight"], current_density_for_loss, values["%lvStrayLoss"])
        values["lvGradient"] = get_lv_gradient(
            values["lvLoadLoss"],
            (values["lvNoOfDuct"] * 2) + 2,
            values["lvWindingLength"],
            values["lvTransposition"],
            values["lvLmt"],
            ctx["dryType"],
            True,
        )
    return values


def _calculate_helical_round(ctx, winding):
    conductor_cross_section = get_conductor_cross_section(ctx["lvCurrentPerPhase"], ctx["currentDensity"])
    number_of_conductors = get_number_of_conductors(conductor_cross_section, ctx["material"])
    cross_sec_per_conductor = get_x_sec_per_conductor(conductor_cross_section, number_of_conductors)
    breadth = get_round_cond_dia(cross_sec_per_conductor, winding.conductorDiameter or winding.condBreadth, ctx["material"])
    height = breadth
    conductor_insulation = get_conductor_insulation(
        ctx["kVA"],
        ctx["lowVoltage"],
        True,
        ctx["vectorGroup"],
        bool(winding.isEnamel),
        winding.condInsulation,
        ctx["dryType"],
    )
    breadth_insulated = get_height_insulated(breadth, conductor_insulation)
    height_insulated = get_height_insulated(height, conductor_insulation)
    turns_per_layer = math.floor(ctx["lvWindingLength"] / max(breadth_insulated, 0.1))
    turns_per_layer, number_of_layers = _round_branch_layers(ctx["lvTurnsPerPhase"], turns_per_layer)
    winding_length = next_integer(breadth_insulated * (turns_per_layer + 1))
    end_clearance = ctx["windowHeight"] - winding_length
    revised_cond_cross_section = two_digit_decimal(math.pi * math.pow(breadth, 2) / 4)
    revised_current_density = three_digit_decimal(ctx["lvCurrentPerPhase"] / (revised_cond_cross_section * number_of_conductors))
    total_cond_cross_section = get_actual_conductor_x_sec(revised_cond_cross_section, number_of_conductors)
    inter_layer_insulation = get_inter_layer_insulation(
        ctx["voltsPerTurn"],
        turns_per_layer,
        conductor_insulation,
        bool(winding.isEnamel),
        winding.interLayerInsulation,
        ctx["dryType"],
    )
    no_of_ducts = _coerce_ducts(max(0, winding.ducts or 0), number_of_layers)
    duct_thickness = get_duct_size(ctx["kVA"], winding_length, winding.ductSize, ctx["dryType"])
    radial_thickness = get_radial_thickness(
        height_insulated,
        1,
        number_of_layers,
        inter_layer_insulation,
        no_of_ducts,
        duct_thickness,
        True,
    )
    lv_id = get_id(ctx["coreDiameter"], ctx["coreGap"])
    lv_od = get_od(lv_id, radial_thickness)
    lv_lmt = get_lmt(lv_id, lv_od)
    wire_length = get_wire_length(lv_lmt, ctx["lvTurnsPerPhase"], 3, number_of_conductors)
    r75 = get_r75(ctx["material"], lv_lmt, ctx["lvTurnsPerPhase"], total_cond_cross_section)
    r26 = get_r26(r75, ctx["material"])
    bare_weight = get_bare_weight(lv_lmt, ctx["lvTurnsPerPhase"], total_cond_cross_section, ctx["material"])
    insulated_weight = get_insulated_weight(
        breadth_insulated,
        height_insulated,
        breadth,
        height,
        ctx["material"],
        bare_weight,
        bool(winding.isEnamel),
    )
    procurement_weight = get_procurement_weight(insulated_weight, number_of_conductors)
    stray_loss = get_stray_loss(
        breadth,
        breadth_insulated,
        height,
        turns_per_layer,
        1,
        1,
        conductor_insulation,
        ctx["material"],
        number_of_layers,
        0,
        True,
    )
    load_loss = get_load_loss(ctx["material"], bare_weight, ctx["currentDensity"], stray_loss)
    gradient = get_lv_gradient(load_loss, (no_of_ducts * 2) + 2, winding_length, 0, lv_lmt, ctx["dryType"], True)

    values = {
        "lvWindingLength": winding_length,
        "lvEndClearance": end_clearance,
        "lvNumberOfLayers": number_of_layers,
        "lvTurnsPerLayer": turns_per_layer,
        "lvConductorCrossSection": conductor_cross_section,
        "lvCrossSecPerConductor": cross_sec_per_conductor,
        "lvNumberOfConductors": number_of_conductors,
        "lvRadialParallelConductors": 1,
        "lvAxialParallelConductors": 1,
        "lvConductorInsulation": conductor_insulation,
        "lvIsConductorRound": True,
        "lvIsEnamel": bool(winding.isEnamel),
        "lvBreadth": breadth,
        "lvHeight": height,
        "lvBreadthInsulated": breadth_insulated,
        "lvHeightInsulated": height_insulated,
        "lvRevisedCondCrossSection": revised_cond_cross_section,
        "lvTotalCondCrossSection": total_cond_cross_section,
        "lVRevisedCurrentDensity": revised_current_density,
        "lvLoadLossCurrentDensity": ctx["currentDensity"],
        "lvInterLayerInsulation": inter_layer_insulation,
        "lvRadialThickness": radial_thickness,
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
        "lvNoOfDuct": no_of_ducts,
        "lvDuctThickness": duct_thickness,
        "lvTransposition": 0,
        "lvDiscDuctsSize": 0,
    }
    return _apply_gradient_loop_helical(ctx, values, winding.ducts)


def _calculate_helical_rectangular(ctx, winding):
    conductor_cross_section = get_conductor_cross_section(ctx["lvCurrentPerPhase"], ctx["currentDensity"])
    number_of_conductors = get_number_of_conductors(conductor_cross_section, ctx["material"])
    conductor_flag = ctx["lvConductorFlag"]
    radial_parallel = get_radial_parallel_conductors(number_of_conductors, conductor_flag, winding.radialParallelCond)
    axial_parallel = get_axial_parallel_conductors(number_of_conductors, radial_parallel, winding.axialParallelCond)
    number_of_conductors = radial_parallel * axial_parallel
    cross_sec_per_conductor = get_x_sec_per_conductor(conductor_cross_section, number_of_conductors)
    transposition = 30 if radial_parallel > 1 else 0
    window_height = ctx["windowHeight"]
    end_clearance = ctx["lvEndClearance"]
    winding_length = ctx["lvWindingLength"]
    conductor_insulation = get_conductor_insulation(
        ctx["kVA"],
        ctx["lowVoltage"],
        False,
        ctx["vectorGroup"],
        bool(winding.isEnamel),
        winding.condInsulation,
        ctx["dryType"],
    )

    if winding.noOfLayers and winding.noOfLayers > 0:
        number_of_layers = winding.noOfLayers
        turns_per_layer = ctx["lvTurnsPerPhase"] / number_of_layers
    elif winding.turnsPerLayer and winding.turnsPerLayer > 0:
        turns_per_layer = winding.turnsPerLayer
        number_of_layers = two_digit_decimal(ctx["lvTurnsPerPhase"] / turns_per_layer)
    else:
        initial_breadth = one_digit_decimal(max(2.0, math.sqrt(cross_sec_per_conductor * 4)))
        initial_breadth_insulated = get_height_insulated(initial_breadth, conductor_insulation)
        turns_per_layer = max(
            1,
            int(math.floor((ctx["lvWindingLength"] - transposition) / max((initial_breadth_insulated * axial_parallel), 0.1))),
        )
        number_of_layers = two_digit_decimal(ctx["lvTurnsPerPhase"] / turns_per_layer)

    breadth_insulated = get_bi(winding_length, turns_per_layer, axial_parallel, transposition, radial_parallel)

    if winding.condBreadth is not None:
        breadth = winding.condBreadth
        breadth_insulated = breadth + conductor_insulation
        winding_length = next_integer(breadth_insulated * axial_parallel * (turns_per_layer + 1))
        window_height = winding_length + transposition + end_clearance + ctx["permaWoodRing"]
    else:
        breadth = get_breadth(breadth_insulated, conductor_insulation, radial_parallel)
        breadth_insulated = breadth + conductor_insulation

    if (
        winding.radialParallelCond is None
        and winding.axialParallelCond is None
        and winding.condBreadth is None
    ):
        while breadth_insulated > 14.5:
            if 14.2 <= breadth_insulated <= 15:
                window_height = next_integer(
                    window_height - ((breadth_insulated - 14.4) * (turns_per_layer + 1) * axial_parallel)
                )
                winding_length = get_winding_length(window_height, end_clearance, ctx["permaWoodRing"])
                breadth_insulated = get_bi(winding_length, turns_per_layer, axial_parallel, transposition, radial_parallel)
                breadth = get_breadth(breadth_insulated, conductor_insulation, radial_parallel)
                breadth_insulated = breadth + conductor_insulation
            elif breadth_insulated > 15:
                axial_parallel += 1
                number_of_conductors = axial_parallel * radial_parallel
                cross_sec_per_conductor = get_x_sec_per_conductor(conductor_cross_section, number_of_conductors)
                breadth_insulated = get_bi(winding_length, turns_per_layer, axial_parallel, transposition, radial_parallel)
                breadth = get_breadth(breadth_insulated, conductor_insulation, radial_parallel)
                breadth_insulated = breadth + conductor_insulation

            if breadth_insulated <= 14.5:
                break

    if winding.condHeight is not None:
        height = winding.condHeight
        if winding.condBreadth is None:
            breadth = get_height(cross_sec_per_conductor, height)
            breadth_insulated = breadth + conductor_insulation
    else:
        height = get_height(cross_sec_per_conductor, breadth)

    height_insulated = get_height_insulated(height, conductor_insulation)
    revised_cond_cross_section = get_revised_conductor_cross_section(breadth, height)
    revised_current_density = three_digit_decimal(ctx["lvCurrentPerPhase"] / (revised_cond_cross_section * number_of_conductors))
    if winding.condBreadth is None:
        while revised_current_density > ctx["currentDensity"] and breadth < 14.4:
            breadth = one_digit_decimal(breadth + 0.1)
            revised_cond_cross_section = get_revised_conductor_cross_section(breadth, height)
            revised_current_density = three_digit_decimal(
                ctx["lvCurrentPerPhase"] / (revised_cond_cross_section * number_of_conductors)
            )
            breadth_insulated = breadth + conductor_insulation
            end_clearance_candidate = int(
                math.floor(
                    (window_height - (breadth_insulated * (turns_per_layer + 1) * axial_parallel)) / 2
                )
            )
            if (end_clearance - end_clearance_candidate) > 3 or breadth > 14.4:
                break
            end_clearance = end_clearance_candidate

    winding_length = window_height - end_clearance - ctx["permaWoodRing"] - transposition

    if winding.condHeight is None:
        while revised_current_density > ctx["currentDensity"] and height < 4.5:
            height = one_digit_decimal(height + 0.1)
            revised_cond_cross_section = get_revised_conductor_cross_section(breadth, height)
            revised_current_density = three_digit_decimal(ctx["lvCurrentPerPhase"] / revised_cond_cross_section)
            height_insulated = get_height_insulated(height, conductor_insulation)
            if height > 4.5:
                break

    total_cond_cross_section = get_actual_conductor_x_sec(revised_cond_cross_section, number_of_conductors)
    transposition = get_transposition(
        breadth_insulated,
        winding_length,
        transposition,
        turns_per_layer,
        radial_parallel,
        axial_parallel,
    )
    revised_cond_cross_section = get_revised_conductor_cross_section(breadth, height)
    revised_current_density = three_digit_decimal(
        ctx["lvCurrentPerPhase"] / (revised_cond_cross_section * number_of_conductors)
    )
    total_cond_cross_section = get_actual_conductor_x_sec(revised_cond_cross_section, number_of_conductors)
    inter_layer_insulation = get_inter_layer_insulation(
        ctx["voltsPerTurn"],
        turns_per_layer,
        conductor_insulation,
        bool(winding.isEnamel),
        winding.interLayerInsulation,
        ctx["dryType"],
    )
    no_of_ducts = _coerce_ducts(max(0, winding.ducts or 0), number_of_layers)
    duct_thickness = get_duct_size(ctx["kVA"], winding_length, winding.ductSize, ctx["dryType"])
    radial_thickness = get_radial_thickness(
        height_insulated,
        radial_parallel,
        number_of_layers,
        inter_layer_insulation,
        no_of_ducts,
        duct_thickness,
        True,
    )
    winding_length = next_integer(breadth_insulated * (turns_per_layer + 1) * axial_parallel)
    end_clearance = window_height - winding_length - transposition - ctx["permaWoodRing"]
    lv_id = get_id(ctx["coreDiameter"], ctx["coreGap"])
    lv_od = get_od(lv_id, radial_thickness)
    lv_lmt = get_lmt(lv_id, lv_od)
    wire_length = get_wire_length(lv_lmt, ctx["lvTurnsPerPhase"], 3, number_of_conductors)
    r75 = get_r75(ctx["material"], lv_lmt, ctx["lvTurnsPerPhase"], total_cond_cross_section)
    r26 = get_r26(r75, ctx["material"])
    bare_weight = get_bare_weight(lv_lmt, ctx["lvTurnsPerPhase"], total_cond_cross_section, ctx["material"])
    insulated_weight = get_insulated_weight(
        breadth_insulated,
        height_insulated,
        breadth,
        height,
        ctx["material"],
        bare_weight,
        bool(winding.isEnamel),
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
        ctx["material"],
        number_of_layers,
        transposition,
        False,
    )

    if winding.radialParallelCond is None and winding.axialParallelCond is None:
        while stray_loss > 10:
            radial_parallel += 1
            transposition = 20
            number_of_conductors = axial_parallel * radial_parallel
            cross_sec_per_conductor = get_x_sec_per_conductor(total_cond_cross_section, number_of_conductors)
            breadth_insulated = get_bi(winding_length, turns_per_layer, axial_parallel, transposition, radial_parallel)
            breadth = get_breadth(breadth_insulated, conductor_insulation, radial_parallel)
            breadth_insulated = breadth + conductor_insulation
            height = get_height(cross_sec_per_conductor, breadth)
            height_insulated = get_height_insulated(height, conductor_insulation)
            revised_cond_cross_section = get_revised_conductor_cross_section(breadth, height)
            revised_current_density = three_digit_decimal(
                ctx["lvCurrentPerPhase"] / (revised_cond_cross_section * number_of_conductors)
            )
            transposition = get_transposition(
                breadth_insulated,
                winding_length,
                transposition,
                turns_per_layer,
                radial_parallel,
                axial_parallel,
            )
            revised_cond_cross_section = get_revised_conductor_cross_section(breadth, height)
            revised_current_density = three_digit_decimal(
                ctx["lvCurrentPerPhase"] / (revised_cond_cross_section * number_of_conductors)
            )
            total_cond_cross_section = get_actual_conductor_x_sec(revised_cond_cross_section, number_of_conductors)
            inter_layer_insulation = get_inter_layer_insulation(
                ctx["voltsPerTurn"],
                turns_per_layer,
                conductor_insulation,
                bool(winding.isEnamel),
                winding.interLayerInsulation,
                ctx["dryType"],
            )
            radial_thickness = get_radial_thickness(
                height_insulated,
                radial_parallel,
                number_of_layers,
                inter_layer_insulation,
                no_of_ducts,
                duct_thickness,
                True,
            )
            winding_length = next_integer(breadth_insulated * (turns_per_layer + 1) * axial_parallel)
            end_clearance = window_height - winding_length - transposition - ctx["permaWoodRing"]
            lv_id = get_id(ctx["coreDiameter"], ctx["coreGap"])
            lv_od = get_od(lv_id, radial_thickness)
            lv_lmt = get_lmt(lv_id, lv_od)
            wire_length = get_wire_length(lv_lmt, ctx["lvTurnsPerPhase"], 3, number_of_conductors)
            r75 = get_r75(ctx["material"], lv_lmt, ctx["lvTurnsPerPhase"], total_cond_cross_section)
            r26 = get_r26(r75, ctx["material"])
            bare_weight = get_bare_weight(lv_lmt, ctx["lvTurnsPerPhase"], total_cond_cross_section, ctx["material"])
            insulated_weight = get_insulated_weight(
                breadth_insulated,
                height_insulated,
                breadth,
                height,
                ctx["material"],
                bare_weight,
                bool(winding.isEnamel),
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
                ctx["material"],
                number_of_layers,
                transposition,
                False,
            )
            if radial_parallel > 6:
                break

    load_loss = get_load_loss(ctx["material"], bare_weight, revised_current_density, stray_loss)
    gradient = get_lv_gradient(
        load_loss,
        (no_of_ducts * 2) + 2,
        winding_length,
        transposition,
        lv_lmt,
        ctx["dryType"],
        True,
    )

    values = {
        "lvWindingLength": winding_length,
        "lvEndClearance": end_clearance,
        "lvNumberOfLayers": number_of_layers,
        "lvTurnsPerLayer": turns_per_layer,
        "lvConductorCrossSection": conductor_cross_section,
        "lvCrossSecPerConductor": cross_sec_per_conductor,
        "lvNumberOfConductors": number_of_conductors,
        "lvRadialParallelConductors": radial_parallel,
        "lvAxialParallelConductors": axial_parallel,
        "lvConductorInsulation": conductor_insulation,
        "lvIsConductorRound": False,
        "lvIsEnamel": bool(winding.isEnamel),
        "lvBreadth": breadth,
        "lvHeight": height,
        "lvBreadthInsulated": breadth_insulated,
        "lvHeightInsulated": height_insulated,
        "lvRevisedCondCrossSection": revised_cond_cross_section,
        "lvTotalCondCrossSection": total_cond_cross_section,
        "lVRevisedCurrentDensity": revised_current_density,
        "lvInterLayerInsulation": inter_layer_insulation,
        "lvRadialThickness": radial_thickness,
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
        "lvNoOfDuct": no_of_ducts,
        "lvDuctThickness": duct_thickness,
        "lvTransposition": transposition,
        "lvDiscDuctsSize": 0,
    }
    return _apply_gradient_loop_helical(ctx, values, winding.ducts)


def _calculate_disc(ctx, winding):
    conductor_cross_section = get_conductor_cross_section(ctx["lvCurrentPerPhase"], ctx["currentDensity"])
    number_of_conductors = get_number_of_conductors(conductor_cross_section, ctx["material"])
    conductor_insulation = get_conductor_insulation(
        ctx["kVA"],
        ctx["lowVoltage"],
        False,
        ctx["vectorGroup"],
        bool(winding.isEnamel),
        winding.condInsulation,
        ctx["dryType"],
    )
    radial_parallel = winding.radialParallelCond if winding.radialParallelCond is not None else number_of_conductors
    axial_parallel = get_axial_parallel_conductors(number_of_conductors, radial_parallel, winding.axialParallelCond)
    number_of_conductors = radial_parallel * axial_parallel
    cross_sec_per_conductor = get_x_sec_per_conductor(conductor_cross_section, number_of_conductors)
    disc_duct_size = get_disc_duct_size(ctx["lowVoltage"], True, ctx["vectorGroup"], None)

    if winding.condBreadth is not None:
        breadth = winding.condBreadth
        breadth_insulated = breadth + conductor_insulation
    else:
        breadth = 14
        breadth_insulated = breadth + conductor_insulation

    if winding.condHeight is not None:
        height = winding.condHeight
        if winding.condBreadth is None:
            breadth = get_height(cross_sec_per_conductor, height)
            breadth_insulated = breadth + conductor_insulation
    else:
        height = get_height(cross_sec_per_conductor, breadth)

    if winding.condBreadth is None and winding.condHeight is None:
        while breadth > 6 * height:
            breadth = one_digit_decimal(breadth - 0.1)
            height = get_height(cross_sec_per_conductor, breadth)
            breadth_insulated = breadth + conductor_insulation
            if breadth <= 6 * height:
                break

    no_of_discs = _next_even_integer(ctx["lvWindingLength"] / max((breadth_insulated * axial_parallel) + disc_duct_size, 0.1))
    turns_per_disc = ctx["lvTurnsPerPhase"] / max(no_of_discs, 1)
    while two_digit_decimal_part(turns_per_disc) < 0.7:
        no_of_discs += 2
        turns_per_disc = ctx["lvTurnsPerPhase"] / no_of_discs
        if two_digit_decimal_part(turns_per_disc) >= 0.7:
            break
    turns_per_disc = int(math.ceil(turns_per_disc))

    if winding.condHeight is None and winding.condBreadth is None:
        breadth_insulated = one_digit_decimal(((ctx["lvWindingLength"] / no_of_discs) - (disc_duct_size * INSULATION_COMPRESSION)) / axial_parallel)
        breadth = one_digit_decimal_floor(breadth_insulated - (conductor_insulation * INSULATION_COMPRESSION))
        breadth_insulated = breadth + conductor_insulation
        height = get_height(cross_sec_per_conductor, breadth)

    height_insulated = get_height_insulated(height, conductor_insulation)
    revised_cond_cross_section = get_revised_conductor_cross_section(breadth, height)
    total_cond_cross_section = two_digit_decimal(revised_cond_cross_section * number_of_conductors)
    revised_current_density = three_digit_decimal(ctx["lvCurrentPerPhase"] / (revised_cond_cross_section * number_of_conductors))
    winding_length = get_disc_winding_length(breadth, conductor_insulation, INSULATION_COMPRESSION, no_of_discs, disc_duct_size)
    end_clearance = math.floor(ctx["windowHeight"] - (winding_length + ctx["permaWoodRing"]))
    no_of_ducts = max(0, winding.ducts or 0)
    duct_thickness = get_duct_size(ctx["kVA"], winding_length, winding.ductSize, ctx["dryType"])
    radial_thickness = get_disc_radial_thickness(height, radial_parallel, conductor_insulation, INSULATION_EXPANSION, turns_per_disc, no_of_ducts, duct_thickness)

    if radial_thickness >= 70 and winding.ducts is None:
        no_of_ducts = 1
        default_disc_duct = 3 if ctx["kVA"] <= 5000 else 4
        duct_thickness = max(winding.ductSize or default_disc_duct, default_disc_duct)
        radial_thickness = get_disc_radial_thickness(height, radial_parallel, conductor_insulation, INSULATION_EXPANSION, turns_per_disc, no_of_ducts, duct_thickness)

    lv_id = get_id(ctx["coreDiameter"], ctx["coreGap"])
    lv_od = get_od(lv_id, radial_thickness)
    lv_lmt = get_lmt(lv_id, lv_od)
    wire_length = get_wire_length(lv_lmt, ctx["lvTurnsPerPhase"], 3, number_of_conductors)
    r75 = get_r75(ctx["material"], lv_lmt, ctx["lvTurnsPerPhase"], total_cond_cross_section)
    r26 = get_r26(r75, ctx["material"])
    bare_weight = get_bare_weight(lv_lmt, ctx["lvTurnsPerPhase"], total_cond_cross_section, ctx["material"])
    insulated_weight = get_insulated_weight(
        breadth_insulated,
        height_insulated,
        breadth,
        height,
        ctx["material"],
        bare_weight,
        bool(winding.isEnamel),
    )
    procurement_weight = get_procurement_weight(insulated_weight, number_of_conductors)
    stray_loss = get_stray_loss_for_disc(
        breadth,
        height,
        no_of_discs,
        radial_parallel,
        axial_parallel,
        conductor_insulation,
        ctx["material"],
        turns_per_disc,
        winding_length,
    )
    load_loss = get_load_loss(ctx["material"], bare_weight, revised_current_density, stray_loss)
    v0 = get_v0(revised_current_density, revised_cond_cross_section, stray_loss, height_insulated, ctx["windingTemp"], ctx["ambientTemp"])
    psi = get_psi(breadth_insulated, radial_thickness, duct_thickness, no_of_ducts)
    rw = get_rw(v0, psi, conductor_insulation)
    gradient = one_digit_decimal(v0 * psi * rw)
    excess_turns = max(0, int((turns_per_disc * no_of_discs) - ctx["lvTurnsPerPhase"]))
    if excess_turns > 0:
        no_of_spacers, width_of_spacer = get_spacers_and_width(lv_id, no_of_discs, excess_turns)
    else:
        no_of_spacers, width_of_spacer = 0, 0

    return {
        "lvWindingLength": winding_length,
        "lvEndClearance": end_clearance,
        "lvNumberOfLayers": turns_per_disc,
        "lvTurnsPerLayer": no_of_discs,
        "lvConductorCrossSection": conductor_cross_section,
        "lvCrossSecPerConductor": cross_sec_per_conductor,
        "lvNumberOfConductors": number_of_conductors,
        "lvRadialParallelConductors": radial_parallel,
        "lvAxialParallelConductors": axial_parallel,
        "lvConductorInsulation": conductor_insulation,
        "lvIsConductorRound": False,
        "lvIsEnamel": bool(winding.isEnamel),
        "lvBreadth": breadth,
        "lvHeight": height,
        "lvBreadthInsulated": breadth_insulated,
        "lvHeightInsulated": height_insulated,
        "lvRevisedCondCrossSection": revised_cond_cross_section,
        "lvTotalCondCrossSection": total_cond_cross_section,
        "lVRevisedCurrentDensity": revised_current_density,
        "lvInterLayerInsulation": 0,
        "lvRadialThickness": radial_thickness,
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
        "lvNoOfDuct": no_of_ducts,
        "lvDuctThickness": duct_thickness,
        "lvTransposition": 0,
        "lvDiscDuctsSize": disc_duct_size,
        "lvNoOfSpacers": no_of_spacers,
        "lvWidthOfSpacer": width_of_spacer,
    }


def _calculate_foil(ctx, winding):
    conductor_cross_section = get_conductor_cross_section(ctx["lvCurrentPerPhase"], ctx["currentDensity"])
    turns_per_layer = 1
    number_of_layers = ctx["lvTurnsPerPhase"]
    end_strip = get_foil_end_strip(ctx["lvWindingLength"])
    breadth = get_foil_length(ctx["lvWindingLength"], winding.condBreadth, end_strip)
    winding_length = breadth + (end_strip * 2)
    breadth_insulated = breadth
    if winding.condHeight is not None:
        height = winding.condHeight
    else:
        height = one_digit_decimal(conductor_cross_section / max(breadth, 0.1))
    height_insulated = height
    radial_parallel = 1
    axial_parallel = 1
    number_of_conductors = 1
    if winding.radialParallelCond is None:
        while height > 2:
            radial_parallel += 1
            number_of_conductors = radial_parallel * axial_parallel
            height = one_digit_decimal(conductor_cross_section / max((breadth * radial_parallel), 0.1))
            if height <= 2:
                break
    else:
        radial_parallel = winding.radialParallelCond
        number_of_conductors = radial_parallel * axial_parallel
        if winding.condHeight is None:
            height = one_digit_decimal(conductor_cross_section / max((breadth * radial_parallel), 0.1))

    height_insulated = height
    conductor_insulation = 0.0
    revised_cond_cross_section = two_digit_decimal(breadth * height)
    total_cond_cross_section = revised_cond_cross_section * number_of_conductors
    revised_current_density = three_digit_decimal(ctx["lvCurrentPerPhase"] / max(total_cond_cross_section, 0.1))
    inter_layer_insulation = winding.interLayerInsulation if winding.interLayerInsulation is not None else 0.1
    no_of_ducts = max(0, winding.ducts or 0)
    duct_thickness = get_duct_size(ctx["kVA"], winding_length, winding.ductSize, ctx["dryType"])
    radial_thickness = get_radial_thickness(height_insulated, radial_parallel, number_of_layers, inter_layer_insulation, no_of_ducts, duct_thickness, False)
    radial_thickness = _half_up(radial_thickness * 1.05)
    lv_id = get_id(ctx["coreDiameter"], ctx["coreGap"])
    lv_od = get_od(lv_id, radial_thickness)
    lv_lmt = get_lmt(lv_id, lv_od)
    bare_weight = get_bare_weight(lv_lmt, ctx["lvTurnsPerPhase"], total_cond_cross_section, ctx["material"])
    wire_length = get_wire_length(lv_lmt, ctx["lvTurnsPerPhase"], 3, number_of_conductors)
    r75 = get_r75(ctx["material"], lv_lmt, ctx["lvTurnsPerPhase"], total_cond_cross_section)
    r26 = get_r26(r75, ctx["material"])
    insulated_weight = bare_weight
    procurement_weight = get_procurement_weight(insulated_weight, number_of_conductors)
    stray_loss = get_stray_loss_for_foil(height, radial_parallel, ctx["material"], number_of_layers)
    load_loss = get_load_loss(ctx["material"], bare_weight, revised_current_density, stray_loss)
    gradient = get_lv_gradient(load_loss, (no_of_ducts * 2) + 2, breadth, 0, lv_lmt, ctx["dryType"], True)

    return {
        "lvWindingLength": winding_length,
        "lvEndClearance": ctx["lvEndClearance"],
        "lvNumberOfLayers": number_of_layers,
        "lvTurnsPerLayer": turns_per_layer,
        "lvConductorCrossSection": conductor_cross_section,
        "lvCrossSecPerConductor": revised_cond_cross_section,
        "lvNumberOfConductors": number_of_conductors,
        "lvRadialParallelConductors": radial_parallel,
        "lvAxialParallelConductors": axial_parallel,
        "lvConductorInsulation": conductor_insulation,
        "lvIsConductorRound": False,
        "lvIsEnamel": bool(winding.isEnamel),
        "lvBreadth": breadth,
        "lvHeight": height,
        "lvBreadthInsulated": breadth_insulated,
        "lvHeightInsulated": height_insulated,
        "lvRevisedCondCrossSection": revised_cond_cross_section,
        "lvTotalCondCrossSection": total_cond_cross_section,
        "lVRevisedCurrentDensity": revised_current_density,
        "lvInterLayerInsulation": inter_layer_insulation,
        "lvRadialThickness": radial_thickness,
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
        "lvNoOfDuct": no_of_ducts,
        "lvDuctThickness": duct_thickness,
        "lvTransposition": 0,
        "lvDiscDuctsSize": 0,
    }


def _calculate_layer_disc(ctx, winding):
    conductor_cross_section = get_conductor_cross_section(ctx["lvCurrentPerPhase"], ctx["currentDensity"])
    number_of_layers = 1
    no_of_ducts = 0
    duct_thickness = 0
    turns_per_layer = ctx["lvTurnsPerPhase"]
    conductor_insulation = get_conductor_insulation(
        ctx["kVA"],
        ctx["lowVoltage"],
        False,
        ctx["vectorGroup"],
        bool(winding.isEnamel),
        winding.condInsulation,
        ctx["dryType"],
    )
    number_of_conductors = get_number_of_conductors(conductor_cross_section, ctx["material"])
    radial_parallel = winding.radialParallelCond if winding.radialParallelCond is not None else number_of_conductors
    axial_parallel = get_axial_parallel_conductors(number_of_conductors, radial_parallel, winding.axialParallelCond)
    number_of_conductors = radial_parallel * axial_parallel
    cross_sec_per_conductor = get_x_sec_per_conductor(conductor_cross_section, number_of_conductors)
    disc_duct_size = get_disc_duct_size(ctx["lowVoltage"], True, ctx["vectorGroup"], None)

    if winding.condBreadth is not None:
        breadth = winding.condBreadth
        breadth_insulated = breadth + conductor_insulation
    else:
        breadth_insulated = one_digit_decimal(((ctx["lvWindingLength"] / turns_per_layer) - (disc_duct_size * INSULATION_COMPRESSION)) / axial_parallel)
        breadth = one_digit_decimal_floor(breadth_insulated - (conductor_insulation * INSULATION_COMPRESSION))
        breadth_insulated = breadth + conductor_insulation

    if winding.condHeight is not None:
        height = winding.condHeight
        if winding.condBreadth is None:
            breadth_insulated = one_digit_decimal(((ctx["lvWindingLength"] / turns_per_layer) - (disc_duct_size * INSULATION_COMPRESSION)) / axial_parallel)
            breadth = one_digit_decimal_floor(breadth_insulated - (conductor_insulation * INSULATION_COMPRESSION))
            breadth_insulated = breadth + conductor_insulation
    else:
        height = get_height(cross_sec_per_conductor, breadth)

    height_insulated = get_height_insulated(height, conductor_insulation)
    revised_cond_cross_section = get_revised_conductor_cross_section(breadth, height)
    total_cond_cross_section = two_digit_decimal(revised_cond_cross_section * number_of_conductors)
    revised_current_density = three_digit_decimal(ctx["lvCurrentPerPhase"] / (revised_cond_cross_section * number_of_conductors))
    winding_length = get_disc_winding_length(breadth, conductor_insulation, INSULATION_COMPRESSION, int(turns_per_layer), disc_duct_size)
    end_clearance = math.floor(ctx["windowHeight"] - (winding_length + ctx["permaWoodRing"]))
    radial_thickness = get_disc_radial_thickness(height, radial_parallel, conductor_insulation, INSULATION_EXPANSION, int(number_of_layers), no_of_ducts, duct_thickness)
    lv_id = get_id(ctx["coreDiameter"], ctx["coreGap"])
    lv_od = get_od(lv_id, radial_thickness)
    lv_lmt = get_lmt(lv_id, lv_od)
    wire_length = get_wire_length(lv_lmt, ctx["lvTurnsPerPhase"], 3, number_of_conductors)
    r75 = get_r75(ctx["material"], lv_lmt, ctx["lvTurnsPerPhase"], total_cond_cross_section)
    r26 = get_r26(r75, ctx["material"])
    bare_weight = get_bare_weight(lv_lmt, ctx["lvTurnsPerPhase"], total_cond_cross_section, ctx["material"])
    insulated_weight = get_insulated_weight(
        breadth_insulated,
        height_insulated,
        breadth,
        height,
        ctx["material"],
        bare_weight,
        bool(winding.isEnamel),
    )
    procurement_weight = get_procurement_weight(insulated_weight, number_of_conductors)
    stray_loss = get_stray_loss_for_disc(
        breadth,
        height,
        turns_per_layer,
        radial_parallel,
        axial_parallel,
        conductor_insulation,
        ctx["material"],
        number_of_layers,
        winding_length,
    )
    load_loss = get_load_loss(ctx["material"], bare_weight, revised_current_density, stray_loss)
    v0 = get_v0(revised_current_density, revised_cond_cross_section, stray_loss, height_insulated, ctx["windingTemp"], ctx["ambientTemp"])
    psi = get_psi(breadth_insulated, radial_thickness, 0, 0)
    rw = get_rw(v0, psi, conductor_insulation)
    gradient = one_digit_decimal(v0 * psi * rw)

    return {
        "lvWindingLength": winding_length,
        "lvEndClearance": end_clearance,
        "lvNumberOfLayers": number_of_layers,
        "lvTurnsPerLayer": turns_per_layer,
        "lvConductorCrossSection": conductor_cross_section,
        "lvCrossSecPerConductor": cross_sec_per_conductor,
        "lvNumberOfConductors": number_of_conductors,
        "lvRadialParallelConductors": radial_parallel,
        "lvAxialParallelConductors": axial_parallel,
        "lvConductorInsulation": conductor_insulation,
        "lvIsConductorRound": False,
        "lvIsEnamel": bool(winding.isEnamel),
        "lvBreadth": breadth,
        "lvHeight": height,
        "lvBreadthInsulated": breadth_insulated,
        "lvHeightInsulated": height_insulated,
        "lvRevisedCondCrossSection": revised_cond_cross_section,
        "lvTotalCondCrossSection": total_cond_cross_section,
        "lVRevisedCurrentDensity": revised_current_density,
        "lvInterLayerInsulation": 0,
        "lvRadialThickness": radial_thickness,
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
        "lvNoOfDuct": no_of_ducts,
        "lvDuctThickness": duct_thickness,
        "lvTransposition": 0,
        "lvDiscDuctsSize": disc_duct_size,
    }


def calculate_lv_windings(multi_winding):
    winding = _safe_winding(getattr(multi_winding, "lvWindings", None))
    ctx = _build_base_context(multi_winding, winding)

    if ctx["windingType"] == "FOIL":
        values = _calculate_foil(ctx, winding)
    elif ctx["windingType"] == "DISC":
        values = _calculate_disc(ctx, winding)
    elif ctx["windingType"] == "LAYER_DISC":
        values = _calculate_layer_disc(ctx, winding)
    else:
        conductor_cross_section = get_conductor_cross_section(ctx["lvCurrentPerPhase"], ctx["currentDensity"])
        number_of_conductors = get_number_of_conductors(conductor_cross_section, ctx["material"])
        cross_sec_per_conductor = get_x_sec_per_conductor(conductor_cross_section, number_of_conductors)
        user_round = winding.isConductorRound
        is_round = user_round if user_round is not None else is_conductor_round(cross_sec_per_conductor)
        values = _calculate_helical_round(ctx, winding) if is_round else _calculate_helical_rectangular(ctx, winding)

    rounded_window_height = values["lvWindingLength"] + values["lvEndClearance"] + ctx["permaWoodRing"] + values["lvTransposition"]
    if rounded_window_height % 5 != 0:
        window_height_round_off = 5 - (rounded_window_height % 5)
        ctx["windowHeight"] = rounded_window_height + window_height_round_off
        values["lvEndClearance"] += window_height_round_off
    else:
        ctx["windowHeight"] = rounded_window_height

    values.setdefault("lvUnpressedWindingLength", 0)
    return _finalize_result(ctx, values)
