import math

from api.models import Windings
from api.services.numberUtils import (
    next_integer,
    one_digit_decimal,
    three_digit_decimal,
    two_digit_decimal,
    two_digit_decimal_part,
)
from api.services.windingFormulae import (
    COPPER,
    get_actual_conductor_x_sec,
    get_bare_weight,
    get_conductor_cross_section,
    get_disc_radial_thickness,
    get_disc_winding_length,
    get_duct_size,
    get_gradient_limit,
    get_height,
    get_height_insulated,
    get_hv_gradient,
    get_insulated_weight,
    get_load_loss,
    get_lmt,
    get_od,
    get_radial_thickness,
    get_r26,
    get_r75,
    get_revised_conductor_cross_section,
    get_spacers_and_width,
    get_stray_loss,
    get_stray_loss_for_disc,
    get_psi,
    get_rw,
    get_v0,
    get_wire_length,
)

INSULATION_COMPRESSION = 0.93
INSULATION_EXPANSION = 1.07


def safe_winding(winding):
    return winding if winding is not None else Windings()


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _positive_or_fallback(value, fallback):
    numeric_value = safe_float(value, 0.0)
    if numeric_value > 0:
        return numeric_value
    return safe_float(fallback, 0.0)


def resolve_axial_parallel_for_winding(winding_type, axial_parallel):
    if _normalize_winding_type(winding_type) == "DISC":
        return 1
    return max(1, int(round(safe_float(axial_parallel, 1.0))))


def seed_section_winding(winding, hv_source, winding_type=None):
    winding = safe_winding(winding)
    winding_type = _normalize_winding_type(winding_type)

    winding.turnsPerLayer = _positive_or_fallback(winding.turnsPerLayer, hv_source.get("hvTurnsPerLayer"))
    winding.endClearances = _positive_or_fallback(winding.endClearances, hv_source.get("hvEndClearance"))

    if winding.condInsulation is None:
        winding.condInsulation = safe_float(hv_source.get("hvConductorInsulation"), 0.0)
    if winding.interLayerInsulation is None:
        winding.interLayerInsulation = safe_float(hv_source.get("hvInterLayerInsulation"), 0.0)
    if winding.radialParallelCond is None:
        winding.radialParallelCond = int(round(safe_float(hv_source.get("hvRadialParallelConductors"), 1.0)))
    if winding.axialParallelCond is None:
        winding.axialParallelCond = int(round(safe_float(hv_source.get("hvAxialParallelConductors"), 1.0)))
    winding.axialParallelCond = resolve_axial_parallel_for_winding(winding_type, winding.axialParallelCond)
    if winding.condBreadth is None and winding_type != "DISC":
        winding.condBreadth = safe_float(hv_source.get("hvBreadth"), 0.0)
    if winding.condHeight is None and winding_type != "DISC":
        winding.condHeight = safe_float(hv_source.get("hvHeight"), 0.0)
    if winding.conductorDiameter is None and winding_type != "DISC":
        winding.conductorDiameter = safe_float(hv_source.get("hvBreadth"), 0.0)
    if winding.isConductorRound is None:
        winding.isConductorRound = hv_source.get("hvIsConductorRound")
    if winding.isEnamel is None:
        winding.isEnamel = hv_source.get("hvIsEnamel")

    return winding


def estimate_winding_radial_thickness(winding):
    winding = safe_winding(winding)
    no_of_layers = max(0.0, safe_float(winding.noOfLayers, 0.0))
    conductor_height = safe_float(winding.condHeight, 0.0)
    conductor_diameter = safe_float(winding.conductorDiameter, 0.0)
    conductor_insulation = safe_float(winding.condInsulation, 0.0)
    inter_layer = safe_float(winding.interLayerInsulation, 0.0)
    ducts = max(0.0, safe_float(winding.ducts, 0.0))
    duct_size = max(0.0, safe_float(winding.ductSize, 0.0))

    base_height = conductor_height if conductor_height > 0 else conductor_diameter
    if base_height <= 0 and no_of_layers <= 0:
        return 0.0

    if no_of_layers <= 0:
        no_of_layers = 1.0

    insulated_height = base_height + (2 * conductor_insulation if conductor_insulation > 0 else 0.0)
    radial_thickness = insulated_height * no_of_layers
    if no_of_layers > 1 and inter_layer > 0:
        radial_thickness += inter_layer * (no_of_layers - 1)
    if ducts > 0 and duct_size > 0:
        radial_thickness += ducts * duct_size
    return radial_thickness


def build_seed_dimensions(previous_geometry, gap_field, radial_gaps):
    return {
        "previousWinding": previous_geometry["name"],
        "previousOuterDiameter": safe_float(previous_geometry["outerDiameter"], 0.0),
        "previousRadialThickness": safe_float(previous_geometry["radialThickness"], 0.0),
        "previousWindingLength": safe_float(previous_geometry["windingLength"], 0.0),
        "previousEndClearance": safe_float(previous_geometry.get("endClearance"), 0.0),
        "gapField": gap_field,
        "gapToPrevious": safe_float(getattr(radial_gaps, gap_field, 0.0) if radial_gaps is not None else 0.0, 0.0),
    }


def build_geometry_snapshot(winding_name, inner_diameter, radial_thickness, outer_diameter, winding_length, source, end_clearance=0.0):
    return {
        "name": winding_name,
        "innerDiameter": safe_float(inner_diameter, 0.0),
        "radialThickness": safe_float(radial_thickness, 0.0),
        "outerDiameter": safe_float(outer_diameter, 0.0),
        "windingLength": safe_float(winding_length, 0.0),
        "endClearance": safe_float(end_clearance, 0.0),
        "source": source,
    }


def serialize_winding_inputs(winding):
    winding = safe_winding(winding)
    return {
        "turnsPerPhase": winding.turnsPerPhase,
        "noOfLayers": winding.noOfLayers,
        "turnsPerLayer": winding.turnsPerLayer,
        "windingLength": winding.windingLength,
        "endClearances": winding.endClearances,
        "loadLoss": winding.loadLoss,
        "ducts": winding.ducts,
        "ductSize": winding.ductSize,
        "condInsulation": winding.condInsulation,
        "interLayerInsulation": winding.interLayerInsulation,
        "radialParallelCond": winding.radialParallelCond,
        "axialParallelCond": winding.axialParallelCond,
        "condBreadth": winding.condBreadth,
        "condHeight": winding.condHeight,
        "conductorDiameter": winding.conductorDiameter,
        "isConductorRound": winding.isConductorRound,
        "isEnamel": winding.isEnamel,
    }


def build_section_turns(total_turns, ratios):
    if total_turns <= 0:
        return [0.0 for _ in ratios]

    allocated = []
    running_total = 0.0
    for index, ratio in enumerate(ratios):
        if index == len(ratios) - 1:
            section_turns = two_digit_decimal(total_turns - running_total)
        else:
            section_turns = two_digit_decimal(total_turns * ratio)
            running_total += section_turns
        allocated.append(section_turns)
    return allocated


def _select_material(multi_winding, attr_name, fallback_attr):
    material = getattr(multi_winding, attr_name, None) or getattr(multi_winding, fallback_attr, None) or COPPER
    return str(material).upper()


def _normalize_winding_type(winding_type):
    return str(winding_type or "HELICAL").upper().replace("-", "_").replace(" ", "_")


def _safe_layers(turns, turns_per_layer):
    return max(1.0, two_digit_decimal(turns / max(turns_per_layer, 1.0)))


def _adjust_helical_section_layers(turns_per_phase, turns_per_layer):
    adjusted_turns_per_layer = max(1, int(math.floor(safe_float(turns_per_layer, 1.0))))
    number_of_layers_rough = safe_float(turns_per_phase, 0.0) / max(adjusted_turns_per_layer, 1)

    while number_of_layers_rough % 1 <= 0.5 and adjusted_turns_per_layer > 1:
        adjusted_turns_per_layer -= 1
        number_of_layers_rough = safe_float(turns_per_phase, 0.0) / max(adjusted_turns_per_layer, 1)
        if number_of_layers_rough % 1 > 0.5:
            break

    return adjusted_turns_per_layer, two_digit_decimal(number_of_layers_rough)


def _next_even_integer(value):
    even_value = int(math.ceil(value))
    if even_value % 2 != 0:
        even_value += 1
    return even_value


def build_disc_arrangement(winding_id, no_of_discs, turns_per_disc, total_turns):
    no_of_discs = max(int(round(safe_float(no_of_discs, 0.0))), 0)
    turns_per_disc = max(int(math.ceil(safe_float(turns_per_disc, 0.0))), 0)
    total_turns = max(int(round(safe_float(total_turns, 0.0))), 0)
    if no_of_discs <= 0:
        return {
            "noOfSpacers": 0,
            "widthOfSpacer": 0,
            "excessTurns": 0,
            "spacersToBeRemoved": 0,
            "fullDisc": 0,
            "halfDisc": 0,
            "partialDisc": 0,
            "balanceSpacersInLastDisc": 0,
            "discArrangement": "",
        }

    total_turns_possible = turns_per_disc * no_of_discs
    excess_turns = max(total_turns_possible - total_turns, 0)
    if excess_turns > 0:
        no_of_spacers, width_of_spacer = get_spacers_and_width(winding_id, no_of_discs, excess_turns)
    else:
        no_of_spacers, width_of_spacer = 0, 0

    spacers_to_be_removed = max((no_of_spacers * excess_turns) - no_of_discs, 0) if no_of_spacers > 0 else 0
    half_disc = 0
    if spacers_to_be_removed > 0 and no_of_spacers > 2:
        removable_per_half_disc = max(int((no_of_spacers / 2) - 1), 1)
        half_disc = int(math.floor(spacers_to_be_removed / removable_per_half_disc))
        spacers_to_be_removed -= half_disc * removable_per_half_disc

    if spacers_to_be_removed == 0:
        partial_disc = 0
        full_disc = no_of_discs - half_disc
        balance_spacers_in_last_disc = 0
    else:
        partial_disc = 1
        full_disc = no_of_discs - half_disc - partial_disc
        balance_spacers_in_last_disc = max(no_of_spacers - spacers_to_be_removed - 1, 0)

    partial_disc_str = (
        f" + {partial_disc}({balance_spacers_in_last_disc}/{no_of_spacers})"
        if partial_disc > 0 and no_of_spacers > 0
        else ""
    )
    return {
        "noOfSpacers": no_of_spacers,
        "widthOfSpacer": width_of_spacer,
        "excessTurns": excess_turns,
        "spacersToBeRemoved": spacers_to_be_removed,
        "fullDisc": full_disc,
        "halfDisc": half_disc,
        "partialDisc": partial_disc,
        "balanceSpacersInLastDisc": balance_spacers_in_last_disc,
        "discArrangement": f"{full_disc}F + {half_disc}H{partial_disc_str}",
    }


def _select_disc_conductor_geometry(
    turns,
    winding_length,
    cross_sec_per_conductor,
    conductor_insulation,
    axial_parallel,
    disc_duct_size,
    user_breadth,
    user_height,
):
    breadth = safe_float(user_breadth, 0.0) if user_breadth is not None else 14.0
    if user_height is not None:
        height = safe_float(user_height, 0.0)
        if user_breadth is None:
            breadth = get_height(cross_sec_per_conductor, height)
    else:
        height = get_height(cross_sec_per_conductor, breadth)

    if user_breadth is None and user_height is None:
        while breadth > 6 * height:
            breadth = one_digit_decimal(breadth - 0.1)
            height = get_height(cross_sec_per_conductor, breadth)
            if breadth <= 6 * height:
                break

    breadth = one_digit_decimal(breadth)
    breadth_insulated = breadth + conductor_insulation
    max_even_discs = max(2, int(math.floor(max(turns, 0.0))))
    if max_even_discs % 2 != 0:
        max_even_discs -= 1
    max_even_discs = max(2, max_even_discs)
    no_of_discs = _next_even_integer(
        winding_length / max((breadth_insulated * axial_parallel) + disc_duct_size, 0.1)
    )
    no_of_discs = min(no_of_discs, max_even_discs)
    original_no_of_discs = no_of_discs
    turns_per_disc_rough = turns / max(no_of_discs, 1)

    while (
        no_of_discs < max_even_discs
        and (two_digit_decimal_part(turns_per_disc_rough) < 0.7 or two_digit_decimal_part(turns_per_disc_rough) >= 0.95)
    ):
        no_of_discs += 2
        turns_per_disc_rough = turns / max(no_of_discs, 1)
        if 0.68 <= two_digit_decimal_part(turns_per_disc_rough) < 0.95:
            break

    turns_per_disc = int(math.ceil(turns_per_disc_rough))
    if user_breadth is None and user_height is None:
        breadth_insulated = (
            (winding_length / max(no_of_discs, 1)) - (disc_duct_size * INSULATION_COMPRESSION)
        ) / max(axial_parallel, 1)
        breadth = one_digit_decimal(breadth_insulated - (conductor_insulation * INSULATION_COMPRESSION))
        breadth_insulated = breadth + conductor_insulation
        height = get_height(cross_sec_per_conductor, breadth)

        if breadth < 5 and height > 1.7:
            no_of_discs = original_no_of_discs
            turns_per_disc_rough = turns / max(no_of_discs, 1)
            while no_of_discs > 2 and (
                two_digit_decimal_part(turns_per_disc_rough) < 0.7
                or two_digit_decimal_part(turns_per_disc_rough) >= 0.95
            ):
                no_of_discs -= 2
                turns_per_disc_rough = turns / max(no_of_discs, 1)
                if 0.68 <= two_digit_decimal_part(turns_per_disc_rough) < 0.95:
                    break

            turns_per_disc = int(math.ceil(turns_per_disc_rough))
            breadth_insulated = (
                (winding_length / max(no_of_discs, 1)) - (disc_duct_size * INSULATION_COMPRESSION)
            ) / max(axial_parallel, 1)
            breadth = one_digit_decimal(breadth_insulated - (conductor_insulation * INSULATION_COMPRESSION))
            height = get_height(cross_sec_per_conductor, breadth)
            breadth_insulated = one_digit_decimal(breadth + conductor_insulation)

    return {
        "breadth": breadth,
        "height": height,
        "breadthInsulated": breadth_insulated,
        "noOfDiscs": no_of_discs,
        "turnsPerDisc": turns_per_disc,
    }


def build_hv_section_results(
    section_name,
    winding_type,
    winding,
    hv_source,
    material,
    allocated_turns,
    allocated_voltage,
    seed_dimensions,
    dry_type,
    ambient_temp=50,
    winding_temp=55,
    current_density_override=None,
    allow_turns_fallback=True,
    limb_height=None,
    perma_wood_ring=0.0,
    kva=0.0,
):
    winding_type = _normalize_winding_type(winding_type)
    raw_winding = safe_winding(winding)
    user_cond_breadth = raw_winding.condBreadth
    user_cond_height = raw_winding.condHeight
    user_conductor_diameter = raw_winding.conductorDiameter
    user_current_density = raw_winding.currentDensity
    user_turns_per_layer = raw_winding.turnsPerLayer
    user_no_of_layers = raw_winding.noOfLayers
    winding = seed_section_winding(winding, hv_source, winding_type)
    allocated_turns = safe_float(allocated_turns, 0.0)
    if allocated_turns <= 0 and allow_turns_fallback:
        allocated_turns = safe_float(getattr(winding, "turnsPerPhase", None), 0.0)
    previous_outer_diameter = safe_float(seed_dimensions.get("previousOuterDiameter"), 0.0)
    gap_to_previous = safe_float(seed_dimensions.get("gapToPrevious"), 0.0)
    inner_diameter = previous_outer_diameter + (2 * gap_to_previous)
    if winding_type == "DISC" and allocated_turns <= 0:
        return {
            "windingName": section_name,
            "windingType": winding_type,
            "implemented": True,
            "status": "calculated",
            "seedDimensions": {
                **seed_dimensions,
                "estimatedInnerDiameter": inner_diameter,
            },
            "turnsPerPhase": 0.0,
            "voltsPerPhase": safe_float(allocated_voltage, 0.0),
            "phaseCurrent": 0.0,
            "currentDensity": 0.0,
            "condCrossSec": 0.0,
            "conductorCrossSection": 0.0,
            "conductorInsulation": safe_float(winding.condInsulation, safe_float(hv_source.get("hvConductorInsulation"), 0.0)),
            "breadth": 0.0,
            "height": 0.0,
            "breadthInsulated": 0.0,
            "heightInsulated": 0.0,
            "turnsPerLayer": 0.0,
            "noOfLayers": 0.0,
            "windingLength": 0.0,
            "endClearance": safe_float(winding.endClearances, safe_float(hv_source.get("hvEndClearance"), 0.0)),
            "radialParallelCond": 0,
            "axialParallelCond": 0,
            "noOfConductors": 0,
            "interLayerInsulation": 0.0,
            "ducts": 0,
            "ductSize": 0,
            "radialThickness": 0.0,
            "innerDiameter": inner_diameter,
            "outerDiameter": inner_diameter,
            "estimatedRadialThickness": 0.0,
            "estimatedInnerDiameter": inner_diameter,
            "estimatedOuterDiameter": inner_diameter,
            "estimatedWindingLength": 0.0,
            "lmt": 0.0,
            "wireLength": 0.0,
            "r75": 0.0,
            "r26": 0.0,
            "bareWeight": 0.0,
            "insulatedWeight": 0.0,
            "strayLoss": 0.0,
            "loadLoss": 0.0,
            "gradient": 0.0,
            "discDuctSize": safe_float(hv_source.get("hvDiscDuctsSize"), 0.0),
            "noOfSpacers": 0,
            "widthOfSpacer": 0,
            "excessTurns": 0,
            "spacersToBeRemoved": 0,
            "fullDisc": 0,
            "halfDisc": 0,
            "partialDisc": 0,
            "balanceSpacersInLastDisc": 0,
            "discArrangement": "",
            "isConductorRound": False,
            "isEnamel": bool(winding.isEnamel),
            "model": serialize_winding_inputs(winding),
        }
    turn_base = max(safe_float(hv_source.get("hvTurnsAtHighest"), 0.0), 1.0)
    turn_share = allocated_turns / turn_base if turn_base else 0.0

    current_per_phase = safe_float(hv_source.get("hvCurrentPerPhase"), 0.0)
    target_current_density = safe_float(current_density_override, 0.0)
    if target_current_density <= 0:
        target_current_density = safe_float(user_current_density, 0.0)
    is_round = (
        winding.isConductorRound
        if winding.isConductorRound is not None
        else bool(hv_source.get("hvIsConductorRound"))
    )
    is_enamel = winding.isEnamel if winding.isEnamel is not None else bool(hv_source.get("hvIsEnamel"))
    radial_parallel = (
        winding.radialParallelCond
        if winding.radialParallelCond is not None
        else int(round(safe_float(hv_source.get("hvRadialParallelConductors"), 1.0)))
    )
    axial_parallel = (
        winding.axialParallelCond
        if winding.axialParallelCond is not None
        else int(round(safe_float(hv_source.get("hvAxialParallelConductors"), 1.0)))
    )
    radial_parallel = max(1, radial_parallel)
    axial_parallel = resolve_axial_parallel_for_winding(winding_type, axial_parallel)
    no_of_conductors = radial_parallel * axial_parallel
    target_total_cond_cross_section = (
        get_conductor_cross_section(current_per_phase, target_current_density)
        if target_current_density > 0
        else 0.0
    )
    cross_sec_per_conductor = (
        target_total_cond_cross_section / max(no_of_conductors, 1)
        if target_total_cond_cross_section > 0
        else safe_float(
            hv_source.get("hvCrossSecPerConductor"),
            safe_float(hv_source.get("hvConductorCrossSection"), 0.0) / max(no_of_conductors, 1),
        )
    )

    if (
        target_current_density > 0
        and user_cond_breadth is None
        and user_cond_height is None
        and user_conductor_diameter is None
    ):
        if is_round:
            breadth = two_digit_decimal(math.sqrt((4 * cross_sec_per_conductor) / math.pi)) if cross_sec_per_conductor > 0 else 0.0
            height = breadth
        else:
            breadth = one_digit_decimal(max(2.0, math.sqrt(cross_sec_per_conductor * 4))) if cross_sec_per_conductor > 0 else 0.0
            height = get_height(cross_sec_per_conductor, breadth) if breadth > 0 else 0.0
            while height > 0 and breadth > 6 * height:
                height = one_digit_decimal(height + 0.1)
                breadth = get_height(cross_sec_per_conductor, height)
                if breadth <= 6 * height:
                    break
            breadth = one_digit_decimal(breadth)
    else:
        breadth = safe_float(winding.condBreadth, safe_float(hv_source.get("hvBreadth"), 0.0))
        height = safe_float(winding.condHeight, safe_float(hv_source.get("hvHeight"), breadth))
        if is_round and breadth <= 0:
            breadth = safe_float(hv_source.get("hvBreadth"), 0.0)
            height = breadth

    conductor_insulation = safe_float(winding.condInsulation, safe_float(hv_source.get("hvConductorInsulation"), 0.0))
    breadth_insulated = get_height_insulated(breadth, conductor_insulation)
    height_insulated = get_height_insulated(height, conductor_insulation)

    previous_end_clearance = safe_float(
        seed_dimensions.get("previousEndClearance"),
        safe_float(hv_source.get("hvEndClearance"), 0.0),
    )
    section_end_clearance = previous_end_clearance + 20.0
    base_winding_length = safe_float(
        seed_dimensions.get("previousWindingLength"),
        safe_float(hv_source.get("hvWindingLength"), 0.0),
    )
    available_winding_length = base_winding_length
    if limb_height is not None:
        available_winding_length = max(
            1.0,
            safe_float(limb_height, 0.0)
            - section_end_clearance
            - safe_float(perma_wood_ring, 0.0),
        )
    transposition = 20 if winding_type == "HELICAL" and radial_parallel > 1 else 0
    revised_cond_cross_section = (
        two_digit_decimal(math.pi * math.pow(breadth, 2) / 4)
        if is_round
        else get_revised_conductor_cross_section(breadth, height)
    )
    total_cond_cross_section = get_actual_conductor_x_sec(revised_cond_cross_section, no_of_conductors)
    current_density = (
        three_digit_decimal(current_per_phase / total_cond_cross_section)
        if total_cond_cross_section > 0
        else 0.0
    )
    conductor_cross_section = get_conductor_cross_section(current_per_phase, current_density) if current_density > 0 else 0.0
    if winding_type == "DISC":
        is_round = False
        disc_duct_size = safe_float(hv_source.get("hvDiscDuctsSize"), 0.0)
        user_disc_dimensions_provided = user_cond_breadth is not None or user_cond_height is not None
        disc_geometry = _select_disc_conductor_geometry(
            allocated_turns,
            available_winding_length,
            cross_sec_per_conductor,
            conductor_insulation,
            axial_parallel,
            disc_duct_size,
            user_cond_breadth,
            user_cond_height,
        )
        breadth = disc_geometry["breadth"]
        height = disc_geometry["height"]
        breadth_insulated = disc_geometry["breadthInsulated"]
        turns_per_layer = float(disc_geometry["noOfDiscs"])
        number_of_layers = float(disc_geometry["turnsPerDisc"])
        winding_length = get_disc_winding_length(
            breadth,
            conductor_insulation,
            INSULATION_COMPRESSION,
            int(turns_per_layer),
            disc_duct_size,
        )
        if not user_disc_dimensions_provided:
            while winding_length > available_winding_length and breadth > 0.1:
                breadth = one_digit_decimal(breadth - 0.1)
                height = get_height(cross_sec_per_conductor, breadth)
                breadth_insulated = one_digit_decimal(breadth + conductor_insulation)
                winding_length = get_disc_winding_length(
                    breadth,
                    conductor_insulation,
                    INSULATION_COMPRESSION,
                    int(turns_per_layer),
                    disc_duct_size,
                )
        winding_length = get_disc_winding_length(
            breadth,
            conductor_insulation,
            INSULATION_COMPRESSION,
            int(turns_per_layer),
            disc_duct_size,
        )
        height_insulated = get_height_insulated(height, conductor_insulation)
        revised_cond_cross_section = get_revised_conductor_cross_section(breadth, height)
        total_cond_cross_section = get_actual_conductor_x_sec(revised_cond_cross_section, no_of_conductors)
        current_density = (
            three_digit_decimal(current_per_phase / total_cond_cross_section)
            if total_cond_cross_section > 0
            else 0.0
        )
        conductor_cross_section = (
            get_conductor_cross_section(current_per_phase, current_density)
            if current_density > 0
            else 0.0
        )
        end_clearance = section_end_clearance
        inter_layer_insulation = 0.0
        no_of_ducts = max(0, winding.ducts or 0)
        duct_thickness = (
            winding.ductSize
            if winding.ductSize is not None
            else int(round(safe_float(hv_source.get("hvDuctThickness"), 0.0))) if no_of_ducts > 0 else 0
        )
        duct_thickness = max(0, duct_thickness or 0)
        radial_thickness = get_disc_radial_thickness(
            height,
            radial_parallel,
            conductor_insulation,
            INSULATION_EXPANSION,
            number_of_layers,
            no_of_ducts,
            duct_thickness,
        )
        stray_loss = get_stray_loss_for_disc(
            breadth,
            height,
            turns_per_layer,
            radial_parallel,
            axial_parallel,
            conductor_insulation,
            material,
            number_of_layers,
            winding_length,
        )
    else:
        if safe_float(user_no_of_layers, 0.0) > 0:
            number_of_layers = safe_float(user_no_of_layers, 0.0)
            turns_per_layer = max(1.0, two_digit_decimal(allocated_turns / max(number_of_layers, 1.0)))
        elif safe_float(user_turns_per_layer, 0.0) > 0:
            turns_per_layer = max(1.0, safe_float(user_turns_per_layer, 1.0))
            number_of_layers = _safe_layers(allocated_turns, turns_per_layer)
        else:
            turns_per_layer = max(
                1,
                int(
                    math.floor(
                        (available_winding_length - transposition)
                        / max(breadth_insulated * axial_parallel, 0.1)
                    )
                ),
            )
            turns_per_layer, number_of_layers = _adjust_helical_section_layers(
                allocated_turns,
                turns_per_layer,
            )
        winding_length = next_integer((turns_per_layer + 1) * (breadth_insulated * axial_parallel))
        while winding_length > available_winding_length and turns_per_layer > 1:
            turns_per_layer -= 1
            turns_per_layer, number_of_layers = _adjust_helical_section_layers(
                allocated_turns,
                turns_per_layer,
            )
            winding_length = next_integer((turns_per_layer + 1) * (breadth_insulated * axial_parallel))
        end_clearance = section_end_clearance
        inter_layer_insulation = safe_float(
            winding.interLayerInsulation,
            safe_float(hv_source.get("hvInterLayerInsulation"), 0.0),
        )
        no_of_ducts = winding.ducts if winding.ducts is not None else 0
        no_of_ducts = max(0, no_of_ducts)
        duct_thickness = (
            winding.ductSize
            if winding.ductSize is not None
            else 0
        )
        duct_thickness = max(0, duct_thickness or 0)
        radial_thickness = get_radial_thickness(
            height_insulated,
            radial_parallel,
            number_of_layers,
            inter_layer_insulation,
            no_of_ducts,
            duct_thickness,
            False,
        )
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

    disc_arrangement = (
        build_disc_arrangement(inner_diameter, turns_per_layer, number_of_layers, allocated_turns)
        if winding_type == "DISC"
        else None
    )
    outer_diameter = get_od(inner_diameter, radial_thickness)
    lmt = get_lmt(inner_diameter, outer_diameter)
    wire_length = get_wire_length(lmt, allocated_turns, 3, no_of_conductors)
    bare_weight = get_bare_weight(lmt, allocated_turns, total_cond_cross_section, material)
    insulated_weight = get_insulated_weight(
        breadth_insulated,
        height_insulated,
        breadth,
        height,
        material,
        bare_weight,
        is_enamel,
    )
    load_loss = next_integer(get_load_loss(material, bare_weight, current_density, stray_loss))
    if winding_type == "DISC":
        if allocated_turns > 0 and load_loss > 0 and cross_sec_per_conductor > 0:
            v0 = get_v0(current_density, cross_sec_per_conductor, stray_loss, height_insulated, winding_temp, ambient_temp)
            psi = get_psi(breadth_insulated, radial_thickness, duct_thickness, no_of_ducts)
            if v0 > 0 and psi > 0:
                rw = get_rw(v0, psi, conductor_insulation)
                gradient = one_digit_decimal(v0 * psi * rw)
            else:
                gradient = 0.0
        else:
            gradient = 0.0

        gradient_limit = get_gradient_limit(dry_type, "CLASS_B")
        if winding.ducts is None and allocated_turns > 0:
            while gradient >= gradient_limit:
                if no_of_ducts > 1:
                    break
                no_of_ducts += 1
                duct_thickness = get_duct_size(
                    0.0,
                    399.0 if base_winding_length <= 499.0 else 499.0,
                    winding.ductSize if winding.ductSize is not None else duct_thickness,
                    dry_type,
                )
                radial_thickness = get_disc_radial_thickness(
                    height,
                    radial_parallel,
                    conductor_insulation,
                    INSULATION_EXPANSION,
                    number_of_layers,
                    no_of_ducts,
                    duct_thickness,
                )
                outer_diameter = get_od(inner_diameter, radial_thickness)
                lmt = get_lmt(inner_diameter, outer_diameter)
                wire_length = get_wire_length(lmt, allocated_turns, 3, no_of_conductors)
                bare_weight = get_bare_weight(lmt, allocated_turns, total_cond_cross_section, material)
                insulated_weight = get_insulated_weight(
                    breadth_insulated,
                    height_insulated,
                    breadth,
                    height,
                    material,
                    bare_weight,
                    is_enamel,
                )
                load_loss = next_integer(get_load_loss(material, bare_weight, current_density, stray_loss))
                v0 = get_v0(current_density, cross_sec_per_conductor, stray_loss, height_insulated, winding_temp, ambient_temp)
                psi = get_psi(breadth_insulated, radial_thickness, duct_thickness, no_of_ducts)
                if v0 > 0 and psi > 0:
                    rw = get_rw(v0, psi, conductor_insulation)
                    gradient = one_digit_decimal(v0 * psi * rw)
                else:
                    gradient = 0.0
                    break
    else:
        gradient = get_hv_gradient(load_loss, (no_of_ducts * 2) + 2, winding_length, transposition, lmt, dry_type)
        gradient_limit = get_gradient_limit(dry_type, "CLASS_B")
        if winding.ducts is None and allocated_turns > 0:
            while gradient >= gradient_limit:
                if no_of_ducts > number_of_layers:
                    break
                no_of_ducts += 1
                if duct_thickness <= 0:
                    duct_thickness = get_duct_size(
                        safe_float(kva, 0.0),
                        399.0 if base_winding_length <= 499.0 else 499.0,
                        winding.ductSize,
                        dry_type,
                    )
                radial_thickness = get_radial_thickness(
                    height_insulated,
                    radial_parallel,
                    number_of_layers,
                    inter_layer_insulation,
                    no_of_ducts,
                    duct_thickness,
                    False,
                )
                outer_diameter = get_od(inner_diameter, radial_thickness)
                lmt = get_lmt(inner_diameter, outer_diameter)
                wire_length = get_wire_length(lmt, allocated_turns, 3, no_of_conductors)
                bare_weight = get_bare_weight(lmt, allocated_turns, total_cond_cross_section, material)
                insulated_weight = get_insulated_weight(
                    breadth_insulated,
                    height_insulated,
                    breadth,
                    height,
                    material,
                    bare_weight,
                    is_enamel,
                )
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
                load_loss = next_integer(get_load_loss(material, bare_weight, current_density, stray_loss))
                gradient = get_hv_gradient(
                    load_loss,
                    (no_of_ducts * 2) + 2,
                    winding_length,
                    transposition,
                    lmt,
                    dry_type,
                )
    r75 = get_r75(material, lmt, allocated_turns, total_cond_cross_section) if total_cond_cross_section > 0 else 0.0
    r26 = get_r26(r75, material) if r75 else 0.0

    return {
        "windingName": section_name,
        "windingType": winding_type,
        "implemented": True,
        "status": "calculated",
        "seedDimensions": {
            **seed_dimensions,
            "estimatedInnerDiameter": inner_diameter,
        },
        "turnsPerPhase": allocated_turns,
        "voltsPerPhase": safe_float(allocated_voltage, 0.0),
        "phaseCurrent": current_per_phase,
        "currentDensity": current_density,
        "condCrossSec": total_cond_cross_section,
        "conductorCrossSection": conductor_cross_section,
        "conductorInsulation": conductor_insulation,
        "breadth": breadth,
        "height": height,
        "breadthInsulated": breadth_insulated,
        "heightInsulated": height_insulated,
        "turnsPerLayer": turns_per_layer,
        "noOfLayers": number_of_layers,
        "windingLength": winding_length,
        "endClearance": end_clearance,
        "radialParallelCond": radial_parallel,
        "axialParallelCond": axial_parallel,
        "noOfConductors": no_of_conductors,
        "interLayerInsulation": inter_layer_insulation,
        "ducts": no_of_ducts,
        "ductSize": duct_thickness,
        "radialThickness": radial_thickness,
        "innerDiameter": inner_diameter,
        "outerDiameter": outer_diameter,
        "estimatedRadialThickness": radial_thickness,
        "estimatedInnerDiameter": inner_diameter,
        "estimatedOuterDiameter": outer_diameter,
        "estimatedWindingLength": winding_length,
        "lmt": lmt,
        "wireLength": wire_length,
        "r75": r75,
        "r26": r26,
        "bareWeight": bare_weight,
        "insulatedWeight": insulated_weight,
        "strayLoss": stray_loss,
        "loadLoss": load_loss,
        "gradient": gradient,
        "discDuctSize": disc_duct_size if winding_type == "DISC" else 0,
        "noOfSpacers": (disc_arrangement or {}).get("noOfSpacers", 0),
        "widthOfSpacer": (disc_arrangement or {}).get("widthOfSpacer", 0),
        "excessTurns": (disc_arrangement or {}).get("excessTurns", 0),
        "spacersToBeRemoved": (disc_arrangement or {}).get("spacersToBeRemoved", 0),
        "fullDisc": (disc_arrangement or {}).get("fullDisc", 0),
        "halfDisc": (disc_arrangement or {}).get("halfDisc", 0),
        "partialDisc": (disc_arrangement or {}).get("partialDisc", 0),
        "balanceSpacersInLastDisc": (disc_arrangement or {}).get("balanceSpacersInLastDisc", 0),
        "discArrangement": (disc_arrangement or {}).get("discArrangement", ""),
        "isConductorRound": is_round,
        "isEnamel": is_enamel,
        "model": serialize_winding_inputs(winding),
    }


def build_pending_winding_result(winding_name, winding_type, winding, depends_on, seed_dimensions=None):
    estimated_radial_thickness = estimate_winding_radial_thickness(winding)
    seed_dimensions = seed_dimensions or {}
    previous_outer_diameter = safe_float(seed_dimensions.get("previousOuterDiameter"), 0.0)
    gap_to_previous = safe_float(seed_dimensions.get("gapToPrevious"), 0.0)
    estimated_inner_diameter = previous_outer_diameter + (2 * gap_to_previous) if previous_outer_diameter > 0 else 0.0
    estimated_outer_diameter = (
        estimated_inner_diameter + (2 * estimated_radial_thickness)
        if estimated_inner_diameter > 0
        else 0.0
    )
    return {
        "windingName": winding_name,
        "windingType": winding_type,
        "implemented": False,
        "status": "pending_formula_port",
        "message": f"{winding_name.title()} winding service is scaffolded and ready for formula porting.",
        "dependsOn": list(depends_on),
        "seedDimensions": {
            **seed_dimensions,
            "estimatedInnerDiameter": estimated_inner_diameter,
        },
        "estimatedRadialThickness": estimated_radial_thickness,
        "estimatedInnerDiameter": estimated_inner_diameter,
        "estimatedOuterDiameter": estimated_outer_diameter,
        "estimatedWindingLength": safe_float(seed_dimensions.get("previousWindingLength"), 0.0),
        "model": serialize_winding_inputs(winding),
    }
