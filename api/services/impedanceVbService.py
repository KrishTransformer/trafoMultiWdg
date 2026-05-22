import math

from api.services.windingFormulae import ek, two_digit_decimal


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
    corse = sections.get("corse", {})
    fine = sections.get("fine", {})
    outer = sections.get("outer", {})

    active_order = [winding["name"] for winding in winding_data]
    winding_count = len(active_order)

    lv_axial = _vb_axial_length(lv)
    hv_axial = _vb_axial_length(hv)
    corse_axial = _vb_axial_length(corse)
    fine_axial = _vb_axial_length(fine)
    outer_axial = _vb_axial_length(outer)

    axial_cm = (lv_axial + hv_axial + corse_axial + fine_axial + outer_axial) / max(winding_count * 10, 10)
    if winding_count <= 2:
        radial_cm = (
            _safe_float(hv.get("outerDiameter"), 0.0)
            - _safe_float(lv.get("innerDiameter"), 0.0)
            - (_safe_float(lv.get("condIns"), 0.0) - _safe_float(hv.get("condIns"), 0.0))
        ) / 20
    else:
        radial_cm = (
            _safe_float(hv.get("outerDiameter"), 0.0)
            - _safe_float(lv.get("innerDiameter"), 0.0)
            - (_safe_float(lv.get("condIns"), 0.0) - _safe_float(outer.get("condIns"), 0.0))
        ) / 20

    radial_cm = max(radial_cm, 0.001)
    power = math.pi * axial_cm / radial_cm if radial_cm else 0.0
    k_ratio = 1 - ((1 - math.exp(-power)) / power) if power else 1.0
    ls_ez = axial_cm / k_ratio if k_ratio else axial_cm

    lv_ins_ht = _vb_insulated_height(lv)
    hv_ins_ht = _vb_insulated_height(hv)
    corse_ins_ht = _vb_insulated_height(corse) if _safe_float(corse.get("turnsPerPhase"), 0.0) > 0 else 0.0
    fine_ins_ht = _vb_insulated_height(fine) if _safe_float(fine.get("turnsPerPhase"), 0.0) > 0 else 0.0
    outer_ins_ht = _vb_insulated_height(outer) if _safe_float(outer.get("turnsPerPhase"), 0.0) > 0 else 0.0

    hv_gap_cm = _vb_gap_cm(lv, hv) if hv else 0.0
    corse_gap_cm = _vb_gap_cm(hv, corse) if corse else 0.0
    fine_gap_cm = _vb_gap_cm(corse, fine) if fine else 0.0
    outer_gap_cm = _vb_gap_cm(fine, outer) if outer else 0.0

    hv_delta1_legacy = corse_gap_cm + ((corse_ins_ht + lv_ins_ht + hv_ins_ht) / 3)
    ds_corse_legacy = (
        (_safe_float(lv.get("outerDiameter"), 0.0) - _safe_float(lv.get("condIns"), 0.0)) / 10
        + corse_gap_cm
        + ((hv_ins_ht - corse_ins_ht - lv_ins_ht) / 3)
    )

    ampere_turn_value = _safe_float(hv.get("phaseCurrent"), 0.0) * _safe_float(hv.get("turnsPerPhase"), 0.0)
    fac = 1.05 if _normalize_winding_type(lv.get("windingType")) == "HELICAL" and _normalize_winding_type(hv.get("windingType")) != "HELICAL" else 1.0
    old_ex = (1.24 * (ampere_turn_value * hv_delta1_legacy * ds_corse_legacy * math.pow(10, -3) * fac) / max(_safe_float(lv_results.get("revisedVoltsPerTurn"), 0.0), 0.001) / max(ls_ez, 0.001))

    hv_turns = _safe_float(hv.get("turnsPerPhase"), 0.0)
    corse_turns = _safe_float(corse.get("turnsPerPhase"), 0.0)
    fine_turns = _safe_float(fine.get("turnsPerPhase"), 0.0)
    outer_turns = _safe_float(outer.get("turnsPerPhase"), 0.0)
    sigma_hv = max(hv_turns + corse_turns + fine_turns + outer_turns, 1.0)
    sigma_corse = corse_turns + fine_turns + outer_turns
    sigma_fine = fine_turns + outer_turns
    sigma_outer = outer_turns

    gamma_lv = 1.0
    gamma_hv = _gamma(hv_turns, sigma_hv)
    gamma_corse = _gamma(hv_turns + corse_turns, sigma_hv)
    gamma_fine = _gamma(hv_turns + corse_turns + fine_turns, sigma_hv)
    gamma_outer = _gamma(hv_turns + corse_turns + fine_turns + outer_turns, sigma_hv)

    alpha_lv = _alpha(gamma_lv)
    alpha_hv = _alpha(gamma_hv)
    alpha_corse = _alpha(gamma_corse) if corse_turns > 1 else 0.0
    alpha_fine = _alpha(gamma_fine) if fine_turns > 1 else 0.0
    alpha_outer = _alpha(gamma_outer) if outer_turns > 1 else 0.0

    beta_lv = 1.0
    beta_hv = (sigma_hv / sigma_hv) ** 2
    beta_corse = (sigma_corse / sigma_hv) ** 2 if sigma_corse > 0 else 0.0
    beta_fine = (sigma_fine / sigma_hv) ** 2 if sigma_fine > 0 else 0.0
    beta_outer = (sigma_outer / sigma_hv) ** 2 if sigma_outer > 0 else 0.0

    delta_lv = 0.0
    delta_hv = hv_gap_cm
    delta_corse = corse_gap_cm
    delta_fine = fine_gap_cm
    delta_outer = outer_gap_cm

    br_lv = (_safe_float(lv.get("radialThickness"), 0.0) - _safe_float(lv.get("condIns"), 0.0)) / 10
    br_hv = (_safe_float(hv.get("radialThickness"), 0.0) - _safe_float(hv.get("condIns"), 0.0)) / 10
    br_corse = (_safe_float(corse.get("radialThickness"), 0.0) - _safe_float(corse.get("condIns"), 0.0)) / 10 if corse_turns > 1 else 0.0
    br_fine = (_safe_float(fine.get("radialThickness"), 0.0) - _safe_float(fine.get("condIns"), 0.0)) / 10 if fine_turns > 1 else 0.0
    br_outer = (_safe_float(outer.get("radialThickness"), 0.0) - _safe_float(outer.get("condIns"), 0.0)) / 10 if outer_turns > 1 else 0.0

    ddelta_lv = 0.0
    d_lv = _vb_mean_diameter_cm(lv.get("innerDiameter"), lv.get("outerDiameter"))
    ddelta_hv = (_safe_float(lv.get("outerDiameter"), 0.0) + _safe_float(hv.get("innerDiameter"), 0.0)) / 20
    d_hv = _vb_mean_diameter_cm(hv.get("innerDiameter"), hv.get("outerDiameter"))
    ddelta_corse = (_safe_float(hv.get("outerDiameter"), 0.0) + _safe_float(corse.get("innerDiameter"), 0.0)) / 20 if corse_turns > 1 else 0.0
    d_corse = _vb_mean_diameter_cm(corse.get("innerDiameter"), corse.get("outerDiameter")) if corse_turns > 1 else 0.0
    ddelta_fine = (_safe_float(corse.get("outerDiameter"), 0.0) + _safe_float(fine.get("innerDiameter"), 0.0)) / 20 if fine_turns > 1 else 0.0
    d_fine = _vb_mean_diameter_cm(fine.get("innerDiameter"), fine.get("outerDiameter")) if fine_turns > 1 else 0.0
    ddelta_outer = (_safe_float(fine.get("outerDiameter"), 0.0) + _safe_float(outer.get("innerDiameter"), 0.0)) / 20 if outer_turns > 1 else 0.0
    d_outer = _vb_mean_diameter_cm(outer.get("innerDiameter"), outer.get("outerDiameter")) if outer_turns > 1 else 0.0

    prod_beta_lv = beta_lv * delta_lv * ddelta_lv
    prod_alpha_lv = alpha_lv * beta_lv * br_lv * d_lv
    prod_beta_hv = beta_hv * delta_hv * ddelta_hv
    prod_alpha_hv = alpha_hv * beta_hv * br_hv * d_hv
    prod_beta_corse = beta_corse * delta_corse * ddelta_corse
    prod_alpha_corse = alpha_corse * beta_corse * br_corse * d_corse
    prod_beta_fine = beta_fine * delta_fine * ddelta_fine
    prod_alpha_fine = alpha_fine * beta_fine * br_fine * d_fine
    prod_beta_outer = beta_outer * delta_outer * ddelta_outer
    prod_alpha_outer = alpha_outer * beta_outer * br_outer * d_outer

    delta_ds = (
        prod_beta_lv
        + prod_beta_hv
        + prod_beta_corse
        + prod_beta_fine
        + prod_beta_outer
        + prod_alpha_lv
        + prod_alpha_hv
        + prod_alpha_corse
        + prod_alpha_fine
        + alpha_outer
    )

    ex_value = two_digit_decimal((1.24 * (delta_ds * math.pow(10, -3)) * ampere_turn_value) / max(ls_ez, 0.001) / max(_safe_float(lv_results.get("revisedVoltsPerTurn"), 0.0), 0.001))
    copper_loss = sum(_safe_float(winding.get("loadLoss"), 0.0) for winding in winding_data)
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
                "outerAlphaCompatibilityTerm": two_digit_decimal(alpha_outer),
                "outerProdAlphaReference": two_digit_decimal(prod_alpha_outer),
            },
        },
    }
