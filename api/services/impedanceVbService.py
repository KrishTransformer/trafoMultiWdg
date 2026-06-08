import math

from api.services.numberUtils import two_digit_decimal
from api.services.windingFormulae import ek


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


def _vb_rdc(section):
    no_of_ducts = max(0.0, _safe_float(section.get("ducts"), 0.0))
    return (1 - (1 / (no_of_ducts + 1))) / 2 if no_of_ducts >= 0 else 0.0


def _vb_insulated_height(section):
    radial_thickness = _safe_float(section.get("radialThickness"), 0.0)
    conductor_insulation = _safe_float(section.get("condIns"), 0.0)
    duct_size = _safe_float(section.get("ductSize"), 0.0)
    return (radial_thickness - conductor_insulation - (_vb_rdc(section) * (duct_size + conductor_insulation))) / 10


def _vb_gap_cm(inner_section, outer_section):
    return (
        _safe_float(outer_section.get("gapFromPrevious"), 0.0)
        + _safe_float(inner_section.get("condIns"), 0.0)
        + _safe_float(outer_section.get("condIns"), 0.0)
    ) / 20


def _vb_mean_diameter_cm(inner_diameter, outer_diameter):
    return (_safe_float(inner_diameter, 0.0) + _safe_float(outer_diameter, 0.0)) / 20


def _gamma(value, sigma_hv):
    return _safe_float(value, 0.0) / max(sigma_hv, 1.0)


def _alpha(gamma_value):
    return 1 - gamma_value + ((gamma_value * gamma_value) / 3)


def calculate_vb_multi_impedance(multi_winding, winding_data, lv_results, hv_results, pairwise_summary):
    sections = _build_section_map(winding_data)
    lv = sections.get("lv", {})
    hv = sections.get("hv", {})
    active_sections = _active_sections(winding_data)
    active_order = [winding["name"] for winding in active_sections]
    winding_count = len(active_sections)

    axial_cm = sum(_vb_axial_length(section) for section in active_sections) / max(winding_count * 10, 10)
    innermost = active_sections[0] if active_sections else {}
    outermost = active_sections[-1] if active_sections else {}
    radial_cm = (
        _safe_float(outermost.get("outerDiameter"), 0.0)
        - _safe_float(innermost.get("innerDiameter"), 0.0)
        - (_safe_float(innermost.get("condIns"), 0.0) - _safe_float(outermost.get("condIns"), 0.0))
    ) / 20

    radial_cm = max(radial_cm, 0.001)
    power = math.pi * axial_cm / radial_cm if radial_cm else 0.0
    k_ratio = 1 - ((1 - math.exp(-power)) / power) if power else 1.0
    ls_ez = axial_cm / k_ratio if k_ratio else axial_cm

    insulated_heights = {
        winding["name"]: _vb_insulated_height(winding)
        for winding in active_sections
    }
    gap_terms = {}
    diameter_terms = {}
    for previous_section, current_section in zip(active_sections, active_sections[1:]):
        current_name = current_section["name"]
        gap_terms[current_name] = _vb_gap_cm(previous_section, current_section)
        diameter_terms[current_name] = (
            _safe_float(previous_section.get("outerDiameter"), 0.0)
            + _safe_float(current_section.get("innerDiameter"), 0.0)
        ) / 20

    lv_ins_ht = insulated_heights.get("lv", 0.0)
    hv_ins_ht = insulated_heights.get("hv", 0.0)
    legacy_reference_section = active_sections[2] if len(active_sections) > 2 else hv
    legacy_reference_name = legacy_reference_section.get("name")
    legacy_gap_cm = gap_terms.get(legacy_reference_name, gap_terms.get("hv", 0.0))
    legacy_ins_ht = insulated_heights.get(legacy_reference_name, hv_ins_ht)

    hv_delta1_legacy = legacy_gap_cm + ((legacy_ins_ht + lv_ins_ht + hv_ins_ht) / 3)
    ds_corse_legacy = (
        (_safe_float(lv.get("outerDiameter"), 0.0) - _safe_float(lv.get("condIns"), 0.0)) / 10
        + legacy_gap_cm
        + ((hv_ins_ht - legacy_ins_ht - lv_ins_ht) / 3)
    )

    ampere_turn_value = _safe_float(hv.get("phaseCurrent"), 0.0) * _safe_float(hv.get("turnsPerPhase"), 0.0)
    fac = 1.05 if _normalize_winding_type(lv.get("windingType")) == "HELICAL" and _normalize_winding_type(hv.get("windingType")) != "HELICAL" else 1.0
    old_ex = (1.24 * (ampere_turn_value * hv_delta1_legacy * ds_corse_legacy * math.pow(10, -3) * fac) / max(_safe_float(lv_results.get("revisedVoltsPerTurn"), 0.0), 0.001) / max(ls_ez, 0.001))

    high_side_sections = active_sections[1:]
    high_side_turns = {
        section["name"]: _safe_float(section.get("turnsPerPhase"), 0.0)
        for section in high_side_sections
    }
    sigma_hv = max(sum(high_side_turns.values()), 1.0)
    cumulative_turns = 0.0
    high_side_names = [section["name"] for section in high_side_sections]
    tail_turns = {}
    running_turns = 0.0
    for section_name in reversed(high_side_names):
        running_turns += high_side_turns.get(section_name, 0.0)
        tail_turns[section_name] = running_turns

    vb_terms = {}
    for index, section in enumerate(active_sections):
        section_name = section["name"]
        turns = _safe_float(section.get("turnsPerPhase"), 0.0)
        if index == 0:
            gamma_value = 1.0
            beta_value = 1.0
            delta_value = 0.0
            ddelta_value = 0.0
        else:
            cumulative_turns += turns
            gamma_value = _gamma(cumulative_turns, sigma_hv)
            beta_value = (tail_turns.get(section_name, 0.0) / sigma_hv) ** 2 if tail_turns.get(section_name, 0.0) > 0 else 0.0
            delta_value = gap_terms.get(section_name, 0.0)
            ddelta_value = diameter_terms.get(section_name, 0.0)

        alpha_value = _alpha(gamma_value) if index == 0 or turns > 1 else 0.0
        br_value = (_safe_float(section.get("radialThickness"), 0.0) - _safe_float(section.get("condIns"), 0.0)) / 10 if index == 0 or turns > 1 else 0.0
        d_value = _vb_mean_diameter_cm(section.get("innerDiameter"), section.get("outerDiameter")) if index == 0 or turns > 1 else 0.0
        prod_beta_value = beta_value * delta_value * ddelta_value
        prod_alpha_value = alpha_value * beta_value * br_value * d_value
        vb_terms[section_name] = {
            "gamma": gamma_value,
            "alpha": alpha_value,
            "beta": beta_value,
            "delta": delta_value,
            "br": br_value,
            "ddelta": ddelta_value,
            "d": d_value,
            "prodBeta": prod_beta_value,
            "prodAlpha": prod_alpha_value,
        }

    delta_ds = sum(term["prodBeta"] + term["prodAlpha"] for term in vb_terms.values())

    ex_value = two_digit_decimal((1.24 * (delta_ds * math.pow(10, -3)) * ampere_turn_value) / max(ls_ez, 0.001) / max(_safe_float(lv_results.get("revisedVoltsPerTurn"), 0.0), 0.001))
    copper_loss = sum(_safe_float(winding.get("loadLoss"), 0.0) for winding in active_sections)
    er_value = two_digit_decimal((copper_loss / max(_safe_float(multi_winding.kVA, 0.0), 1.0)) / 10)
    ek_value = ek(er_value, ex_value)

    return {
        "h1": pairwise_summary.get("h1", 0.0),
        "h2": pairwise_summary.get("h2", 0.0),
        "ls": two_digit_decimal(ls_ez),
        "l": two_digit_decimal(axial_cm),
        "b": two_digit_decimal(radial_cm),
        "kR": two_digit_decimal(k_ratio),
        "delta": pairwise_summary.get("delta", 0.0),
        "delta1": pairwise_summary.get("delta1", 0.0),
        "ds": pairwise_summary.get("ds", 0.0),
        "ex": ex_value,
        "er": er_value,
        "ek": ek_value,
        "breakdown": {
            "method": "vb_multi_wdg",
            "activeWindingOrder": active_order,
            "pairs": pairwise_summary.get("breakdown", {}).get("pairs", []),
            "totals": {
                "loadLoss": two_digit_decimal(copper_loss),
                "tankLossComponent": 0.0,
                "ex": ex_value,
                "er": er_value,
                "ek": ek_value,
            },
            "vb": {
                "axial": two_digit_decimal(axial_cm),
                "radial": two_digit_decimal(radial_cm),
                "kRatio": two_digit_decimal(k_ratio),
                "lsEz": two_digit_decimal(ls_ez),
                "ampereTurns": two_digit_decimal(ampere_turn_value),
                "deltaDs": two_digit_decimal(delta_ds),
                "oldEx": two_digit_decimal(old_ex),
                "fac": fac,
                "hvDelta1Legacy": two_digit_decimal(hv_delta1_legacy),
                "dsCorseLegacy": two_digit_decimal(ds_corse_legacy),
                "termOrder": active_order,
                "termBreakdown": {
                    section_name: {
                        key: two_digit_decimal(value)
                        for key, value in term.items()
                    }
                    for section_name, term in vb_terms.items()
                },
            },
        },
    }
