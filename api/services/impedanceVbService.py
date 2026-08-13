import math

from api.services.numberUtils import two_digit_decimal
from api.services.windingFormulae import ek, ex as winding_ex, h1h2, ls as winding_ls


DISC_TYPES = {"DISC", "LAYER_DISC"}


def _safe_float(value, fallback=0.0):
    try:
        if value is None:
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _normalize_winding_type(value):
    return str(value or "").strip().upper().replace("-", "_")


def _is_disc_like(winding_type):
    return _normalize_winding_type(winding_type) in DISC_TYPES


def _build_section_map(winding_data):
    return {
        winding["name"]: winding
        for winding in winding_data
    }


def _active_sections(winding_data):
    return [
        winding
        for winding in winding_data
        if _safe_float(winding.get("turnsPerPhase"), 0.0) > 0
    ]


def _vb_axial_length(section):
    turns_per_phase = _safe_float(section.get("turnsPerPhase"), 0.0)
    if turns_per_phase <= 0:
        return 0.0

    winding_type = _normalize_winding_type(section.get("windingType"))
    conductor_insulation = _safe_float(section.get("condIns"), 0.0)
    winding_length = _safe_float(section.get("windingLength"), 0.0)
    end_clearance = _safe_float(section.get("endClearance"), 0.0)

    if _is_disc_like(winding_type):
        return max(winding_length - end_clearance - conductor_insulation, 0.0)

    breadth = _safe_float(section.get("breadth"), 0.0)
    turns_per_layer = _safe_float(section.get("turnsPerLayer"), 0.0)
    axial_parallel = max(1.0, _safe_float(section.get("axialParallel"), 1.0))
    if winding_type == "XOVER":
        no_of_coils = max(1.0, _safe_float(section.get("noOfCoils"), 1.0))
        axial = (turns_per_layer * no_of_coils * axial_parallel * breadth) - conductor_insulation
        axial += _safe_float(section.get("transposition"), 0.0)
        return max(axial, 0.0)

    axial = (turns_per_layer * axial_parallel * breadth) - conductor_insulation
    return max(axial, 0.0)


def _tap_h(section):
    return max(
        h1h2(
            _safe_float(section.get("radialThickness"), 0.0),
            int(round(_safe_float(section.get("ducts"), 0.0))),
            _safe_float(section.get("ductSize"), 0.0),
            _safe_float(section.get("condIns"), 0.0),
        ),
        0.0,
    )


def _section_turns(section):
    return _safe_float(section.get("turnsPerPhase"), 0.0)


def _hv_main_normal_load_loss(section_map, hv_results):
    hv = section_map.get("hv", {})
    return _safe_float(
        hv_results.get("hvLoadLossAtNormal", hv.get("hvLoadLossAtNormal", hv.get("loadLoss", 0.0))),
        0.0,
    )


def _hv_main_lowest_load_loss(section_map, hv_results):
    hv = section_map.get("hv", {})
    return _safe_float(
        hv_results.get("hvLoadLossAtLowest", hv.get("hvLoadLossAtLowest", hv.get("loadLoss", 0.0))),
        0.0,
    )


def _normal_tap_turns(multi_winding, tap_sections):
    total_extra_turns = sum(_section_turns(section) for section in tap_sections)
    total_taps = max(
        int(getattr(multi_winding, "tapStepPositive", 0) or 0)
        + int(getattr(multi_winding, "tapStepNegative", 0) or 0),
        0,
    )
    if total_extra_turns <= 0:
        return 0.0
    if total_taps <= 0:
        return total_extra_turns
    return total_extra_turns * max(int(getattr(multi_winding, "tapStepNegative", 0) or 0), 0) / total_taps


def _normal_tap_usage(tap_sections, normal_turns):
    remaining_turns = max(normal_turns, 0.0)
    usage = {}
    for section in tap_sections:
        turns = _section_turns(section)
        if turns <= 0 or remaining_turns <= 0:
            included_turns = 0.0
        else:
            included_turns = min(turns, remaining_turns)
        fraction = (included_turns / turns) if turns > 0 else 0.0
        usage[section["name"]] = {
            "includedTurns": included_turns,
            "fraction": fraction,
            "included": fraction >= 0.5,
        }
        remaining_turns = max(remaining_turns - included_turns, 0.0)
    return usage


def _included_hv_sections(hv_section, tap_sections, normal_usage, condition):
    sections = []
    if hv_section:
        sections.append(hv_section)
    if condition == "lowest":
        return sections
    if condition == "highest":
        return sections + tap_sections
    return sections + [
        section
        for section in tap_sections
        if normal_usage.get(section["name"], {}).get("included", False)
    ]


def _pair_ls_values(lv_section, hv_section):
    return winding_ls(
        _safe_float(lv_section.get("breadthInsulated"), 0.0),
        _safe_float(hv_section.get("breadthInsulated"), 0.0),
        _safe_float(lv_section.get("turnsPerLayer"), 1.0),
        _safe_float(hv_section.get("turnsPerLayer"), 1.0),
        max(1, int(round(_safe_float(lv_section.get("axialParallel"), 1.0)))),
        max(1, int(round(_safe_float(hv_section.get("axialParallel"), 1.0)))),
        _safe_float(hv_section.get("outerDiameter"), 0.0),
        _safe_float(lv_section.get("innerDiameter"), 0.0),
        _safe_float(lv_section.get("condIns"), 0.0),
        _safe_float(hv_section.get("condIns"), 0.0),
        _safe_float(lv_section.get("windingLength"), 0.0),
        _safe_float(hv_section.get("windingLength"), 0.0),
        lv_section.get("windingType"),
        hv_section.get("windingType"),
        _safe_float(lv_section.get("transposition"), 0.0),
        _safe_float(hv_section.get("transposition"), 0.0),
        max(0, int(round(_safe_float(hv_section.get("noOfCoils"), 0.0)))),
    )


def _average_l_value(lv_section, hv_sections):
    if not hv_sections:
        return 0.0
    return sum(_pair_ls_values(lv_section, section)[1] for section in hv_sections) / len(hv_sections)


def _tap_geometry(lv_section, hv_sections, volts_per_turn, ampere_turn_value, frequency_factor):
    hv_main = hv_sections[0] if hv_sections else {}
    outermost_hv = hv_sections[-1] if hv_sections else {}
    h1_value = _tap_h(lv_section)
    h2_value = max(sum(_tap_h(section) for section in hv_sections), 0.0)
    l_value = _average_l_value(lv_section, hv_sections) if hv_sections else 0.0
    b_value = (
        _safe_float(outermost_hv.get("outerDiameter"), 0.0)
        - _safe_float(lv_section.get("innerDiameter"), 0.0)
        - _safe_float(outermost_hv.get("condIns"), 0.0)
        - _safe_float(lv_section.get("condIns"), 0.0)
    ) / 2
    b_value = max(b_value, 0.001)
    power = math.pi * l_value / b_value if b_value else 0.0
    k_ratio = 1 - ((1 - math.exp(-power)) / power) if power else 1.0
    ls_value = l_value / k_ratio if k_ratio else l_value
    ex_values = winding_ex(
        volts_per_turn,
        _safe_float(hv_main.get("gapFromPrevious"), 0.0),
        _safe_float(lv_section.get("condIns"), 0.0),
        _safe_float(hv_main.get("condIns"), 0.0),
        h1_value,
        h2_value,
        ampere_turn_value,
        max(ls_value, 0.001),
        _safe_float(lv_section.get("outerDiameter"), 0.0),
        frequency_factor,
    )
    return {
        "h1": two_digit_decimal(h1_value),
        "h2": two_digit_decimal(h2_value),
        "delta": two_digit_decimal(ex_values[0]),
        "delta1": two_digit_decimal(ex_values[1]),
        "ds": two_digit_decimal(ex_values[2]),
        "l": two_digit_decimal(l_value),
        "b": two_digit_decimal(b_value),
        "kR": two_digit_decimal(k_ratio),
        "ls": two_digit_decimal(ls_value),
        "ex": two_digit_decimal(ex_values[3]),
        "includedHvWindings": [section["name"] for section in hv_sections],
        "outermostHvWinding": outermost_hv.get("name"),
    }


def _tap_resistance(load_loss, kva):
    return two_digit_decimal(_safe_float(load_loss, 0.0) / max(_safe_float(kva, 0.0), 1.0) / 10)


def calculate_vb_multi_impedance(multi_winding, winding_data, lv_results, hv_results, pairwise_summary):
    sections = _build_section_map(winding_data)
    lv = sections.get("lv", {})
    active_sections = _active_sections(winding_data)
    active_order = [winding["name"] for winding in active_sections]
    hv = sections.get("hv", {})
    tap_sections = active_sections[2:]
    normal_turns = _normal_tap_turns(multi_winding, tap_sections)
    normal_usage = _normal_tap_usage(tap_sections, normal_turns)
    ampere_turn_value = _safe_float(lv.get("phaseCurrent"), 0.0) * _safe_float(lv.get("turnsPerPhase"), 0.0)
    volts_per_turn = max(_safe_float(lv_results.get("revisedVoltsPerTurn"), 0.0), 0.001)
    frequency_factor = _safe_float(getattr(multi_winding, "frequency", 50), 50.0) / 50 if _safe_float(getattr(multi_winding, "frequency", 50), 50.0) else 1.0
    hv_main_normal_loss = _hv_main_normal_load_loss(sections, hv_results)
    hv_main_lowest_loss = _hv_main_lowest_load_loss(sections, hv_results)
    extra_loss_total = sum(_safe_float(section.get("loadLoss"), 0.0) for section in tap_sections)

    tap_results = {}
    for condition in ("lowest", "normal", "highest"):
        hv_sections = _included_hv_sections(hv, tap_sections, normal_usage, condition)
        geometry = _tap_geometry(lv, hv_sections, volts_per_turn, ampere_turn_value, frequency_factor)
        if condition == "lowest":
            load_loss = _safe_float(lv.get("loadLoss"), 0.0) + hv_main_lowest_loss
        else:
            load_loss = _safe_float(lv.get("loadLoss"), 0.0) + hv_main_normal_loss + extra_loss_total
        er_value = _tap_resistance(load_loss, getattr(multi_winding, "kVA", 0.0))
        tap_results[condition] = {
            **geometry,
            "loadLoss": two_digit_decimal(load_loss),
            "er": er_value,
            "ek": ek(er_value, geometry["ex"]),
        }

    normal_result = tap_results["normal"]

    return {
        "h1": normal_result["h1"],
        "h2": normal_result["h2"],
        "ls": normal_result["ls"],
        "l": normal_result["l"],
        "b": normal_result["b"],
        "kR": normal_result["kR"],
        "delta": normal_result["delta"],
        "delta1": normal_result["delta1"],
        "ds": normal_result["ds"],
        "ex": normal_result["ex"],
        "er": normal_result["er"],
        "ek": normal_result["ek"],
        "breakdown": {
            "method": "tap_condition_multi_wdg",
            "activeWindingOrder": active_order,
            "pairs": pairwise_summary.get("breakdown", {}).get("pairs", []),
            "selectedTap": "normal",
            "normalTapTurnsAboveLowest": two_digit_decimal(normal_turns),
            "normalTapUsage": {
                section_name: {
                    key: two_digit_decimal(value) if key != "included" else value
                    for key, value in usage.items()
                }
                for section_name, usage in normal_usage.items()
            },
            "tapConditions": tap_results,
            "totals": {
                "ampereTurns": two_digit_decimal(ampere_turn_value),
                "loadLossAtLowest": tap_results["lowest"]["loadLoss"],
                "loadLossAtNormal": tap_results["normal"]["loadLoss"],
                "loadLossAtHighest": tap_results["highest"]["loadLoss"],
                "ex": normal_result["ex"],
                "er": normal_result["er"],
                "ek": normal_result["ek"],
            },
        },
    }
