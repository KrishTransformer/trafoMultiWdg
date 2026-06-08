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
    get_stray_loss,
    get_stray_loss_for_disc,
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
        "gapField": gap_field,
        "gapToPrevious": safe_float(getattr(radial_gaps, gap_field, 0.0) if radial_gaps is not None else 0.0, 0.0),
    }


def build_geometry_snapshot(winding_name, inner_diameter, radial_thickness, outer_diameter, winding_length, source):
    return {
        "name": winding_name,
        "innerDiameter": safe_float(inner_diameter, 0.0),
        "radialThickness": safe_float(radial_thickness, 0.0),
        "outerDiameter": safe_float(outer_diameter, 0.0),
        "windingLength": safe_float(winding_length, 0.0),
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


def _next_even_integer(value):
    even_value = int(math.ceil(value))
    if even_value % 2 != 0:
        even_value += 1
    return even_value


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
    no_of_discs = _next_even_integer(
        winding_length / max((breadth_insulated * axial_parallel) + disc_duct_size, 0.1)
    )
    original_no_of_discs = no_of_discs
    turns_per_disc_rough = turns / max(no_of_discs, 1)

    while two_digit_decimal_part(turns_per_disc_rough) < 0.7:
        no_of_discs += 2
        turns_per_disc_rough = turns / max(no_of_discs, 1)
        if two_digit_decimal_part(turns_per_disc_rough) >= 0.7:
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
            while no_of_discs > 2 and two_digit_decimal_part(turns_per_disc_rough) < 0.7:
                no_of_discs -= 2
                turns_per_disc_rough = turns / max(no_of_discs, 1)
                if two_digit_decimal_part(turns_per_disc_rough) >= 0.7:
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
    current_density_override=None,
):
    winding_type = _normalize_winding_type(winding_type)
    raw_winding = safe_winding(winding)
    user_cond_breadth = raw_winding.condBreadth
    user_cond_height = raw_winding.condHeight
    user_conductor_diameter = raw_winding.conductorDiameter
    user_current_density = raw_winding.currentDensity
    winding = seed_section_winding(winding, hv_source, winding_type)
    allocated_turns = safe_float(allocated_turns, 0.0)
    if allocated_turns <= 0:
        allocated_turns = safe_float(getattr(winding, "turnsPerPhase", None), 0.0)
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
    axial_parallel = max(1, axial_parallel)
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

    base_winding_length = safe_float(
        seed_dimensions.get("previousWindingLength"),
        safe_float(hv_source.get("hvWindingLength"), 0.0),
    )
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
        disc_geometry = _select_disc_conductor_geometry(
            allocated_turns,
            base_winding_length,
            cross_sec_per_conductor,
            conductor_insulation,
            axial_parallel,
            disc_duct_size,
            winding.condBreadth,
            winding.condHeight,
        )
        breadth = disc_geometry["breadth"]
        height = disc_geometry["height"]
        breadth_insulated = disc_geometry["breadthInsulated"]
        height_insulated = get_height_insulated(height, conductor_insulation)
        turns_per_layer = float(disc_geometry["noOfDiscs"])
        number_of_layers = float(disc_geometry["turnsPerDisc"])
        winding_length = get_disc_winding_length(
            breadth,
            conductor_insulation,
            INSULATION_COMPRESSION,
            int(turns_per_layer),
            disc_duct_size,
        )
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
        turns_per_layer = safe_float(winding.turnsPerLayer, safe_float(hv_source.get("hvTurnsPerLayer"), 1.0))
        turns_per_layer = max(1.0, turns_per_layer)
        number_of_layers = _safe_layers(allocated_turns, turns_per_layer)
        winding_length = base_winding_length
        inter_layer_insulation = safe_float(
            winding.interLayerInsulation,
            safe_float(hv_source.get("hvInterLayerInsulation"), 0.0),
        )
        no_of_ducts = (
            winding.ducts
            if winding.ducts is not None
            else max(0, int(round(safe_float(hv_source.get("hvNoOfDuct"), 0.0) * turn_share)))
        )
        no_of_ducts = max(0, no_of_ducts)
        duct_thickness = (
            winding.ductSize
            if winding.ductSize is not None
            else int(round(safe_float(hv_source.get("hvDuctThickness"), 0.0))) if no_of_ducts > 0 else 0
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
            0,
            is_round,
        )

    previous_outer_diameter = safe_float(seed_dimensions.get("previousOuterDiameter"), 0.0)
    gap_to_previous = safe_float(seed_dimensions.get("gapToPrevious"), 0.0)
    inner_diameter = previous_outer_diameter + (2 * gap_to_previous)
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
    gradient = get_hv_gradient(load_loss, (no_of_ducts * 2) + 2, winding_length, 0, lmt, dry_type)
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
        "endClearance": safe_float(winding.endClearances, safe_float(hv_source.get("hvEndClearance"), 0.0)),
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
