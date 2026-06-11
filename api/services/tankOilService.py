import math

from api.services.numberUtils import next_integer, one_digit_decimal, two_digit_decimal
from api.services.windingFormulae import (
    COPPER,
    ECONOMIC,
    RADIATOR,
    get_bushing_current,
    get_bushing_voltage_and_height,
    get_channel_weight,
    get_conservator_capacity,
    get_conservator_dia,
    get_conservator_length,
    get_conservator_oil,
    get_connection_gap,
    get_connection_weight,
    get_corrugation_area,
    get_corrugation_slits,
    get_depth_of_corrugation,
    get_frame_thickness,
    get_heat_dis_by_tank_wall,
    get_insulation_wt,
    get_kw55,
    get_kw55_for_multiple_windings,
    get_largest_blade,
    get_lid_thickness,
    get_lifting_lugs,
    get_oltc_spec,
    get_procurement_weight,
    get_radiator_area,
    get_radiator_height,
    get_radiator_section,
    get_radiator_width,
    get_tank_capacity,
    get_tank_height,
    get_tank_length,
    get_tank_wall_thickness,
    get_tank_width,
    get_tap_ins_weight,
    get_tap_lead_weight,
    get_top_oil_temperature,
    get_top_yoke_to_cover,
    get_total_radiator_weight,
    get_total_steel_weight,
    get_wdg_to_tank_gap,
    get_yoke_insulation,
    get_tank_bottom_thickness,
    displacement_volume,
)


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    try:
        if value is None:
            return default
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _section_float(section, *keys, default=0.0):
    if not section:
        return default
    for key in keys:
        if key in section and section[key] is not None:
            return _safe_float(section[key], default)
    return default


def _section_int(section, *keys, default=0):
    if not section:
        return default
    for key in keys:
        if key in section and section[key] is not None:
            return _safe_int(section[key], default)
    return default


def _normalize_upper(value):
    return "" if value is None else str(value).strip().upper()


def _is_copper(material):
    return _normalize_upper(material) == COPPER


def _get_material_cost(multi_winding, material):
    copper_cost = _safe_float(getattr(multi_winding, "copperCostPerKg", None), 850.0)
    aluminium_cost = _safe_float(getattr(multi_winding, "aluminiumCostPerKg", None), 235.0)
    return copper_cost if _is_copper(material) else aluminium_cost


def _get_cost_defaults(multi_winding):
    return {
        "copperCostPerKg": _safe_float(getattr(multi_winding, "copperCostPerKg", None), 850.0),
        "aluminiumCostPerKg": _safe_float(getattr(multi_winding, "aluminiumCostPerKg", None), 235.0),
        "coreCostPerKg": _safe_float(getattr(multi_winding, "coreCostPerKg", None), 250.0),
        "steelCostPerKg": _safe_float(getattr(multi_winding, "steelCostPerKg", None), 90.0),
        "oilCostPerKg": _safe_float(getattr(multi_winding, "oilCostPerKg", None), 80.0),
        "insulationCostPerKg": _safe_float(getattr(multi_winding, "insulationCostPerKg", None), 170.0),
        "radiatorCostPerKg": _safe_float(getattr(multi_winding, "radiatorCostPerKg", None), 200.0),
    }


def _high_side_material(multi_winding, winding_name):
    if winding_name == "corse":
        return getattr(multi_winding, "corseConductorMaterial", None) or getattr(multi_winding, "hvConductorMaterial", COPPER)
    if winding_name == "fine":
        return getattr(multi_winding, "fineConductorMaterial", None) or getattr(multi_winding, "hvConductorMaterial", COPPER)
    if winding_name == "outer":
        return getattr(multi_winding, "outerConductorMaterial", None) or getattr(multi_winding, "hvConductorMaterial", COPPER)
    return getattr(multi_winding, "hvConductorMaterial", COPPER)


def _section_procurement_weight(section):
    if not section:
        return 0.0
    no_of_conductors = max(1, _section_int(section, "noOfConductors", "hvNoOfConductors", default=1))
    insulated_weight = _section_float(section, "insulatedWeight", "hvInsulatedWeight", default=0.0)
    if insulated_weight <= 0:
        return 0.0
    return get_procurement_weight(insulated_weight, no_of_conductors)


def _iter_high_side_sections(hv_results, corse_results, fine_results, outer_results):
    return (
        ("hv", hv_results),
        ("corse", corse_results),
        ("fine", fine_results),
        ("outer", outer_results),
    )


def _collect_multi_winding_kw55_inputs(lv_results, section_results):
    winding_load_losses = [_safe_float(lv_results.get("lvLoadLoss"), 0.0)]
    winding_gradients = [_safe_float(lv_results.get("lvGradient"), 0.0)]

    for _, section in section_results:
        if not section:
            continue
        winding_load_losses.append(_section_float(section, "loadLoss", "hvLoadLossAtNormal", default=0.0))
        winding_gradients.append(_section_float(section, "gradient", "tempGradDegC", "hvGradient", default=0.0))

    return winding_load_losses, winding_gradients


def _get_kw55_value(multi_winding, lv_results, raw_hv_results, high_side_sections, core_loss, tank_loss):
    if multi_winding.windings == "2 Wdg (LV and HV-Main)":
        return get_kw55(
            core_loss,
            _safe_float(lv_results.get("lvLoadLoss"), 0.0),
            _safe_float(raw_hv_results.get("hvLoadLossAtLowest", raw_hv_results.get("hvLoadLossAtNormal", 0.0)), 0.0),
            tank_loss,
            _safe_float(lv_results.get("lvGradient"), 0.0),
            _safe_float(raw_hv_results.get("hvGradient"), 0.0),
        )

    winding_load_losses, winding_gradients = _collect_multi_winding_kw55_inputs(lv_results, high_side_sections)
    return get_kw55_for_multiple_windings(core_loss, winding_load_losses, tank_loss, winding_gradients)


def _get_outermost_section_name(coil_dimensions):
    outermost = getattr(coil_dimensions, "outermostWinding", None)
    return outermost if outermost in {"hv", "corse", "fine", "outer"} else "hv"


def _get_outermost_section_result(coil_dimensions, hv_results, corse_results, fine_results, outer_results):
    section_by_name = {
        "hv": hv_results,
        "corse": corse_results,
        "fine": fine_results,
        "outer": outer_results,
    }
    return section_by_name.get(_get_outermost_section_name(coil_dimensions)) or hv_results


def _sum_high_side_procurement_weights(high_side_sections):
    return sum(_section_procurement_weight(section) for _, section in high_side_sections if section)


def _sum_high_side_bare_weights(high_side_sections):
    return sum(_section_float(section, "bareWeight", "hvBareWeight", default=0.0) for _, section in high_side_sections if section)


def _max_high_side_gradient(high_side_sections):
    gradients = [
        _section_float(section, "gradient", "tempGradDegC", "hvGradient", default=0.0)
        for _, section in high_side_sections
        if section
    ]
    return max(gradients) if gradients else 0.0


def _sum_high_side_material_cost(multi_winding, high_side_sections):
    total_cost = 0
    for winding_name, section in high_side_sections:
        if not section:
            continue
        total_cost += _get_material_cost(multi_winding, _high_side_material(multi_winding, winding_name)) * _section_procurement_weight(section)
    return total_cost


def _sum_tap_ins_weight(multi_winding, raw_hv_results, high_side_distribution, hv_results, corse_results, fine_results, outer_results):
    if multi_winding.windings == "2 Wdg (LV and HV-Main)":
        return get_tap_ins_weight(
            _safe_float(raw_hv_results.get("hvBareWeight"), 0.0),
            _safe_float(raw_hv_results.get("hvInsulatedWeight"), 0.0),
            _safe_float(raw_hv_results.get("hvTurnsAtHighest"), 0.0),
            _safe_float(raw_hv_results.get("hvTurnsAtLowest"), 0.0),
        )

    section_by_name = {
        "hv": hv_results,
        "corse": corse_results,
        "fine": fine_results,
        "outer": outer_results,
    }
    tap_ins_weight = 0.0
    for winding_name in ("corse", "fine", "outer"):
        taps = _safe_float((high_side_distribution.get(winding_name) or {}).get("taps"), 0.0)
        section = section_by_name.get(winding_name)
        if taps <= 0 or not section:
            continue
        tap_ins_weight += max(
            _section_float(section, "insulatedWeight", "hvInsulatedWeight", default=0.0)
            - _section_float(section, "bareWeight", "hvBareWeight", default=0.0),
            0.0,
        )
    return one_digit_decimal(tap_ins_weight)


def _sum_tap_lead_weight(multi_winding, high_side_distribution, core, coil_dimensions, hv_results, corse_results, fine_results, outer_results):
    section_by_name = {
        "hv": hv_results,
        "corse": corse_results,
        "fine": fine_results,
        "outer": outer_results,
    }
    total_tap_lead_weight = 0

    if multi_winding.windings == "2 Wdg (LV and HV-Main)":
        sections_to_sum = ("hv",)
    else:
        sections_to_sum = ("corse", "fine", "outer")

    for winding_name in sections_to_sum:
        allocation = high_side_distribution.get(winding_name) or {}
        tap_count = _safe_int(allocation.get("taps"), 0)
        section = section_by_name.get(winding_name)
        if tap_count <= 0 or not section:
            continue

        total_tap_lead_weight += get_tap_lead_weight(
            _section_float(section, "condCrossSec", "hvTotalCondCrossSection", default=0.0),
            _high_side_material(multi_winding, winding_name),
            bool(getattr(multi_winding, "isOLTC", False)),
            _safe_float(core.cenDist, 0.0),
            _safe_float(core.limbHt, 0.0),
            _section_float(section, "outerDiameter", "hvOd", default=_safe_float(coil_dimensions.outermostOD, 0.0)),
            _safe_float(core.coreDia, 0.0),
            tap_count,
            0,
            _section_float(section, "conductorInsulation", "hvConductorInsulation", default=0.0),
        )

    return total_tap_lead_weight


def _get_radiator_type(multi_winding):
    return _normalize_upper(
        getattr(multi_winding, "radiatorType", None)
        or getattr(multi_winding, "eRadiatorType", None)
        or RADIATOR
    )


def _build_tank_inputs_payload(multi_winding):
    return {
        "isOLTC": bool(getattr(multi_winding, "isOLTC", False)),
        "isCSP": bool(getattr(multi_winding, "isCSP", False)),
        "radiatorType": _get_radiator_type(multi_winding),
        "lvTerminalType": getattr(multi_winding, "lvTerminalType", None),
        "hvTerminalType": getattr(multi_winding, "hvTerminalType", None),
        "topOilTemp": getattr(multi_winding, "topOilTemp", None),
        "radiatorWidth": getattr(multi_winding, "radiatorWidth", None),
        "tankLoss": getattr(multi_winding, "tankLoss", None),
        "wdgToTankGap": getattr(multi_winding, "wdgToTankGap", None),
        "connectionGap": getattr(multi_winding, "connectionGap", None),
        "topYokeToCoverGap": getattr(multi_winding, "topYokeToCoverGap", None),
    }


def calculate_tank_and_oil(
    multi_winding,
    lv_results,
    raw_hv_results,
    hv_results,
    corse_results,
    fine_results,
    outer_results,
    core,
    coil_dimensions,
    recomputed_core_loss,
    recomputed_tank_loss,
    high_side_distribution,
):
    high_side_sections = list(_iter_high_side_sections(hv_results, corse_results, fine_results, outer_results))
    outermost_section = _get_outermost_section_result(coil_dimensions, hv_results, corse_results, fine_results, outer_results)

    largest_blade = get_largest_blade(_safe_float(core.coreDia, 0.0))
    yoke_insulation = get_yoke_insulation(multi_winding.kVA)
    is_csp = bool(getattr(multi_winding, "isCSP", False))
    is_oltc = bool(getattr(multi_winding, "isOLTC", False))
    trans_cost_type = getattr(multi_winding, "transCostType", ECONOMIC)
    radiator_type = _get_radiator_type(multi_winding)
    top_oil_temp_user = _safe_float(getattr(multi_winding, "topOilTemp", None), 50.0)

    connection_gap = get_connection_gap(multi_winding.highVoltage, getattr(multi_winding, "connectionGap", None))
    wdg_tank_gap = get_wdg_to_tank_gap(multi_winding.highVoltage, multi_winding.kVA, getattr(multi_winding, "wdgToTankGap", None))
    top_yoke_cover_gap = get_top_yoke_to_cover(
        multi_winding.kVA,
        multi_winding.highVoltage,
        is_oltc,
        getattr(multi_winding, "topYokeToCoverGap", None),
    )

    outermost_od = _safe_float(coil_dimensions.outermostOD, _safe_float(raw_hv_results.get("hvOd"), 0.0))
    center_distance = _safe_float(core.cenDist, _safe_float(coil_dimensions.centerDistance, 0.0))
    tank_length = get_tank_length(
        outermost_od,
        center_distance,
        multi_winding.highVoltage,
        multi_winding.kVA,
        is_oltc,
        getattr(multi_winding, "wdgToTankGap", None),
    )
    tank_width = get_tank_width(
        outermost_od,
        multi_winding.highVoltage,
        multi_winding.kVA,
        getattr(multi_winding, "connectionGap", None),
        getattr(multi_winding, "wdgToTankGap", None),
    )
    tank_height = get_tank_height(
        _safe_float(core.limbHt, 0.0),
        largest_blade,
        multi_winding.kVA,
        multi_winding.highVoltage,
        is_oltc,
        _safe_float(multi_winding.tapStepsPercentage, 0.0),
        _safe_int(getattr(multi_winding, "topYokeToCoverGap", 0), 0),
    )
    tank_capacity = get_tank_capacity(tank_length, tank_width, tank_height)
    tank_weight = tank_capacity * 0.6

    tank_wall_thickness = get_tank_wall_thickness(multi_winding.kVA)
    tank_lid_thickness = get_lid_thickness(multi_winding.kVA)
    tank_bottom_thickness = get_tank_bottom_thickness(multi_winding.kVA)
    frame_thickness = get_frame_thickness(multi_winding.kVA)

    lv_procurement_weight = _safe_float(lv_results.get("lvProcurementWeight"), 0.0)
    total_high_side_procurement_weight = _sum_high_side_procurement_weights(high_side_sections)
    weight_core = next_integer(_safe_float(core.coreWeight, 0.0) * 1.02)
    lv_connection_weight = get_connection_weight(
        _safe_float(lv_results.get("lvTotalCondCrossSection"), 0.0),
        getattr(multi_winding, "lvConductorMaterial", COPPER),
        300,
    )
    hv_connection_weight = get_connection_weight(
        _section_float(hv_results, "condCrossSec", "hvTotalCondCrossSection", default=_safe_float(raw_hv_results.get("hvTotalCondCrossSection"), 0.0)),
        getattr(multi_winding, "hvConductorMaterial", COPPER),
        1000,
    )
    tap_ins_weight = _sum_tap_ins_weight(
        multi_winding,
        raw_hv_results,
        high_side_distribution,
        hv_results,
        corse_results,
        fine_results,
        outer_results,
    )
    tap_lead_weight = _sum_tap_lead_weight(
        multi_winding,
        high_side_distribution,
        core,
        coil_dimensions,
        hv_results,
        corse_results,
        fine_results,
        outer_results,
    )
    total_connection_weight = next_integer(tap_ins_weight + tap_lead_weight + lv_connection_weight + hv_connection_weight)
    channel_weight = get_channel_weight(largest_blade, tank_length / 1000.0)
    insulation_weight = get_insulation_wt(multi_winding.kVA, multi_winding.highVoltage, multi_winding.vectorGroup)
    total_conductor_weight = next_integer(lv_procurement_weight + total_high_side_procurement_weight + lv_connection_weight + hv_connection_weight)

    volume_lv_cond = displacement_volume(
        _safe_float(lv_results.get("lvBareWeight"), 0.0),
        8.89 if _is_copper(getattr(multi_winding, "lvConductorMaterial", COPPER)) else 2.703,
    )
    hv_bare_density_total = 0.0
    for winding_name, section in high_side_sections:
        if not section:
            continue
        hv_bare_density_total += displacement_volume(
            _section_float(section, "bareWeight", "hvBareWeight", default=0.0),
            8.89 if _is_copper(_high_side_material(multi_winding, winding_name)) else 2.703,
        )
    volume_core = displacement_volume(weight_core, 7.65)
    volume_lv_connection_weight = displacement_volume(
        lv_connection_weight,
        8.89 if _is_copper(getattr(multi_winding, "lvConductorMaterial", COPPER)) else 2.703,
    )
    volume_hv_connection_weight = displacement_volume(
        hv_connection_weight,
        8.89 if _is_copper(getattr(multi_winding, "hvConductorMaterial", COPPER)) else 2.703,
    )
    volume_connection_weight = two_digit_decimal(volume_lv_connection_weight + volume_hv_connection_weight)
    volume_channel = displacement_volume(channel_weight, 7.85)
    volume_insulation = displacement_volume(insulation_weight, 1)
    displacement_volume_total = math.floor(
        volume_core
        + volume_lv_cond
        + hv_bare_density_total
        + volume_connection_weight
        + volume_channel
        + volume_insulation
    )

    kw55 = _get_kw55_value(
        multi_winding,
        lv_results,
        raw_hv_results,
        high_side_sections,
        recomputed_core_loss,
        recomputed_tank_loss,
    )

    heat_dis_by_tank_walls = 0.0
    heat_to_be_dissipated = float(kw55)
    top_oil_temperature = 0.0
    radiator_area = 0.0
    radiator_height = 0
    radiator_width = 0
    radiator_section = 0
    area_per_fin = 0.0
    no_of_fins = 0
    no_of_radiators = 0
    corrugation_area = get_corrugation_area(kw55, trans_cost_type)
    corrugation_slits_on_length = 0
    corrugation_slits_on_width = 0
    total_corrugation_slits = 0
    pipe_area = 0.0
    pipe_length = 0.0
    cooling_statement = ""
    oil_in_radiators = 0.0
    total_radiator_weight = 0.0
    no_of_fins_per_radiator = 0

    if radiator_type == "RADIATOR":
        heat_dis_by_tank_walls = get_heat_dis_by_tank_wall(tank_length, tank_width, tank_height)
        heat_to_be_dissipated -= heat_dis_by_tank_walls
        top_oil_temperature = get_top_oil_temperature(
            _safe_float(lv_results.get("lvGradient"), 0.0),
            _max_high_side_gradient(high_side_sections),
        )
        radiator_area = get_radiator_area(heat_to_be_dissipated, top_oil_temperature, top_oil_temp_user)
        radiator_height = get_radiator_height(tank_height, largest_blade, yoke_insulation)
        radiator_width = get_radiator_width(radiator_height, getattr(multi_winding, "radiatorWidth", None))
        area_per_fin = radiator_width * radiator_height * 2 * math.pow(10, -6)
        no_of_fins = next_integer(radiator_area / max(area_per_fin, 0.1))
        if no_of_fins % 2 != 0:
            no_of_fins += 1
        radiator_section, no_of_radiators, no_of_fins = get_radiator_section(no_of_fins)
        oil_in_radiators = next_integer(no_of_fins * radiator_height * radiator_width * math.pow(10, -4) * 0.1)
        total_radiator_weight = next_integer(
            get_total_radiator_weight(radiator_height, radiator_width, radiator_section, no_of_radiators)
        )
        cooling_statement = f"L X W = {radiator_height} X {radiator_width} : {no_of_radiators} X {radiator_section}"
        no_of_fins_per_radiator = int(no_of_fins / max(no_of_radiators, 1))
    elif radiator_type == "PIPES":
        pipe_area = math.pi * math.pow(38.1, 2) / 4
        pipe_length = one_digit_decimal(corrugation_area / max(pipe_area, 0.1))
        oil_in_radiators = next_integer((math.pow(33.33, 2) * math.pi / 4) * pipe_length * math.pow(10, -5))
        total_radiator_weight = next_integer(279.61 * pipe_length * 7.85 * math.pow(10, -6))
        cooling_statement = f"38.1mm Pipe or  56.2 mm elliptic pipe of Length {pipe_length}Mtrs"
    elif radiator_type == "CORRUGATION":
        corrugation_slits_on_length = get_corrugation_slits(tank_length)
        corrugation_slits_on_width = get_corrugation_slits(tank_width)
        total_corrugation_slits = corrugation_slits_on_length + corrugation_slits_on_width
        area_per_fin = corrugation_area / max(total_corrugation_slits, 1)
        radiator_height = get_radiator_height(tank_height, largest_blade, yoke_insulation)
        radiator_width = get_depth_of_corrugation(area_per_fin, radiator_height, max(total_corrugation_slits, 1))
        no_of_fins = total_corrugation_slits
        oil_in_radiators = next_integer(no_of_fins * area_per_fin * 0.1)
        total_radiator_weight = next_integer(
            radiator_height * radiator_width * total_corrugation_slits * 2 * 1.25 * 7.85 * math.pow(10, -6)
        )
        cooling_statement = (
            f"L X W = {radiator_height} X {radiator_width}\n"
            f"No. Corrugation on Length X 2 = {corrugation_slits_on_length}\n"
            f"No. Corrugation on Width X 2 = {corrugation_slits_on_width}"
        )

    oltc_spec = get_oltc_spec(
        multi_winding.highVoltage,
        _safe_int(multi_winding.tapStepPositive, 0),
        _safe_int(multi_winding.tapStepNegative, 0),
    )
    oltc_weight = _safe_float(oltc_spec[0], 0.0)
    oltc_current = _safe_float(oltc_spec[1], 0.0)
    oltc_oil = _safe_float(oltc_spec[2], 0.0)
    oltc_length = _safe_float(oltc_spec[3], 0.0)
    oltc_breadth = _safe_float(oltc_spec[4], 0.0)
    oltc_height = _safe_float(oltc_spec[5], 0.0)

    oil_in_tank = next_integer(tank_capacity - displacement_volume_total)
    oil_in_conservator = 0 if is_csp else get_conservator_oil(oil_in_tank, oil_in_radiators)
    total_oil = oil_in_radiators + oil_in_conservator + oil_in_tank

    conservator_capacity = 0
    conservator_dia = 0
    conservator_length = 0
    if not is_csp:
        conservator_capacity = get_conservator_capacity(multi_winding.kVA, total_oil)
        conservator_dia = get_conservator_dia(conservator_capacity)
        conservator_length = get_conservator_length(conservator_capacity, conservator_dia)

    total_steel_weight = next_integer(get_total_steel_weight(multi_winding.highVoltage, multi_winding.kVA, multi_winding.vectorGroup))
    total_oil = total_oil + (oltc_oil if is_oltc else 0)
    oil_weight = next_integer(total_oil * 0.89)

    lv_bushing_voltage, lv_bushing_height = get_bushing_voltage_and_height(multi_winding.lowVoltage)
    hv_bushing_voltage, hv_bushing_height = get_bushing_voltage_and_height(multi_winding.highVoltage)
    lv_bushing_current = get_bushing_current(_safe_float(lv_results.get("lvCurrentPerPhase"), 0.0), multi_winding.vectorGroup, True)
    hv_bushing_current = get_bushing_current(_section_float(hv_results, "phaseCurrent", "hvCurrentPerPhase", default=0.0), multi_winding.vectorGroup, False)

    conservator_height = (420 if multi_winding.highVoltage > 11000 else 300) + (conservator_dia * 0.5) + 70
    rollers = 0
    lifting_lugs = get_lifting_lugs(multi_winding.kVA)

    csp_tank_height = 0
    if is_csp:
        csp_tank_height = 150 if multi_winding.kVA > 25000 else 100
        tank_height += csp_tank_height
        tank_capacity = get_tank_capacity(tank_length, tank_width, tank_height)
        tank_weight = tank_capacity * 0.6

    overall_length = next_integer(tank_length + lifting_lugs + conservator_dia + oltc_breadth)
    overall_width = next_integer(tank_width + ((((radiator_section - 1) * 50) + 100) * 2))
    overall_height = next_integer(tank_height + (conservator_dia / 2) + hv_bushing_height + largest_blade + 100 + rollers)

    weights_of_active_part = next_integer(weight_core + total_conductor_weight + channel_weight + insulation_weight)
    weight_of_tank_and_acc = next_integer(total_steel_weight + oltc_weight + oil_weight + total_radiator_weight)
    transformer_weight = next_integer(weights_of_active_part + weight_of_tank_and_acc)

    cost_defaults = _get_cost_defaults(multi_winding)
    lv_conductor_cost = math.ceil(
        _get_material_cost(multi_winding, getattr(multi_winding, "lvConductorMaterial", COPPER))
        * (lv_procurement_weight + lv_connection_weight)
    )
    hv_conductor_cost = math.ceil(
        _sum_high_side_material_cost(multi_winding, high_side_sections)
        + (_get_material_cost(multi_winding, getattr(multi_winding, "hvConductorMaterial", COPPER)) * hv_connection_weight)
    )
    conductor_cost = int(lv_conductor_cost + hv_conductor_cost)
    core_cost = int(math.ceil(cost_defaults["coreCostPerKg"] * weight_core))
    insulation_cost = int(math.ceil(cost_defaults["insulationCostPerKg"] * insulation_weight))
    steel_cost = int(math.ceil(cost_defaults["steelCostPerKg"] * total_steel_weight))
    oil_cost = int(math.ceil(cost_defaults["oilCostPerKg"] * total_oil))
    radiator_cost = int(math.ceil(cost_defaults["radiatorCostPerKg"] * total_radiator_weight))
    capital_cost = conductor_cost + core_cost + insulation_cost + steel_cost + oil_cost + radiator_cost

    return {
        "tankLoss": recomputed_tank_loss,
        "tankLength": tank_length,
        "tankWidth": tank_width,
        "tankHeight": tank_height,
        "tankWeight": tank_weight,
        "wdgTankGap": wdg_tank_gap,
        "connectionGap": connection_gap,
        "topYokeCoverGap": top_yoke_cover_gap,
        "tankCapacity": tank_capacity,
        "tankWallThickness": tank_wall_thickness,
        "tankLidThickness": tank_lid_thickness,
        "tankBottomThickness": tank_bottom_thickness,
        "frameThickness": frame_thickness,
        "weightCore": weight_core,
        "totalConductorWeight": total_conductor_weight,
        "channelWeight": channel_weight,
        "insulationWeight": insulation_weight,
        "lvConnectionWeight": lv_connection_weight,
        "hvConnectionWeight": hv_connection_weight,
        "tapInsWeight": tap_ins_weight,
        "tapLeadWeight": tap_lead_weight,
        "totalConnectionWeight": total_connection_weight,
        "volumeCore": volume_core,
        "volumeChannel": volume_channel,
        "volumeInsulation": volume_insulation,
        "volumeLvCond": volume_lv_cond,
        "volumeHvCond": two_digit_decimal(hv_bare_density_total),
        "volumeConnectionWeight": volume_connection_weight,
        "displacementVolume": displacement_volume_total,
        "radiator": f"{radiator_height} X {radiator_width}: {radiator_section} X {no_of_radiators}",
        "noOfFins": no_of_fins,
        "radiatorArea": radiator_area,
        "noOfRadiators": no_of_radiators,
        "noOfFinsPerRadiator": no_of_fins_per_radiator,
        "totalRadiatorWeight": total_radiator_weight,
        "conservatorDia": conservator_dia,
        "conservatorLength": conservator_length,
        "conservatorCapacity": conservator_capacity,
        "conservatorHeight": conservator_height,
        "oilInTank": oil_in_tank,
        "oilInRadiators": oil_in_radiators,
        "oilInConservator": oil_in_conservator,
        "totalOil": total_oil,
        "oilWeight": oil_weight,
        "totalSteelWeight": total_steel_weight,
        "coolingStatement": cooling_statement,
        "radiatorHeight": radiator_height,
        "radiatorWidth": radiator_width,
        "radiatorSection": radiator_section,
        "heatDisByTankWalls": heat_dis_by_tank_walls,
        "heatToBeDissipated": heat_to_be_dissipated,
        "topOilTemperature": top_oil_temperature,
        "corrugationArea": corrugation_area,
        "corrugationSlitsOnLength": corrugation_slits_on_length,
        "corrugationSlitsOnWidth": corrugation_slits_on_width,
        "totalCorrugationSlits": total_corrugation_slits,
        "pipeArea": pipe_area,
        "pipeLength": pipe_length,
        "kw55": kw55,
        "lvBushingVoltage": lv_bushing_voltage,
        "lvBushingCurrent": lv_bushing_current,
        "lvBushingHeight": lv_bushing_height,
        "hvBushingVoltage": hv_bushing_voltage,
        "hvBushingCurrent": hv_bushing_current,
        "hvBushingHeight": hv_bushing_height,
        "overallLength": overall_length,
        "overallWidth": overall_width,
        "overallHeight": overall_height,
        "tankDimension": f"{tank_length} L X {tank_width} W X {tank_height} H mm",
        "overallDimension": f"{overall_length} L X {overall_width} W X {overall_height} H mm",
        "weightsOfActivePart": weights_of_active_part,
        "weightOfTankAndAcc": weight_of_tank_and_acc,
        "transformerWeight": transformer_weight,
        "conductorCost": conductor_cost,
        "coreCost": core_cost,
        "insulationCost": insulation_cost,
        "steelCost": steel_cost,
        "oilCost": oil_cost,
        "radiatorCost": radiator_cost,
        "capitalCost": capital_cost,
        "oltcWeight": oltc_weight,
        "oltcCurrent": oltc_current,
        "oltcOil": oltc_oil,
        "oltcLength": oltc_length,
        "oltcBreadth": oltc_breadth,
        "oltcHeight": oltc_height,
        "cspTankHeight": csp_tank_height,
        "outermostWinding": _get_outermost_section_name(coil_dimensions),
        "outermostOuterDiameter": _section_float(outermost_section, "outerDiameter", "hvOd", default=outermost_od),
    }
