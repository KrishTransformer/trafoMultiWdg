from decimal import Decimal, ROUND_HALF_UP
from math import sqrt


def two_digit_decimal(value):
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def has_star_connection(vector_group):
    vector_group_name = (vector_group or "").strip()
    return (
        (len(vector_group_name) > 1 and vector_group_name[1] == "y")
        or (len(vector_group_name) > 0 and vector_group_name[0] == "Y")
    )

def get_lv_volts_per_phase(voltage_value, vector_group):
    if voltage_value is None:
        return None

    vector_group_name = (vector_group or "").strip()
    use_star_connection = len(vector_group_name) > 1 and vector_group_name[1] == "y"
    volts_per_phase = voltage_value / sqrt(3) if use_star_connection else voltage_value
    return two_digit_decimal(volts_per_phase)

def get_hv_volts_per_phase(voltage_value, vector_group):
    if voltage_value is None:
        return None

    vector_group_name = (vector_group or "").strip()
    use_star_connection = len(vector_group_name) > 0 and vector_group_name[0] == "Y"
    volts_per_phase = voltage_value / sqrt(3) if use_star_connection else voltage_value
    return two_digit_decimal(volts_per_phase)

def get_end_clearance(kva, voltage, vector_group, end_clr=None, dry_type=False):
    kva_value = 0.0 if kva is None else kva
    voltage_value = 0.0 if voltage is None else voltage
    end_clearance = 8 * 2

    if voltage_value <= 1100:
        if kva_value <= 25:
            end_clearance = 8 * 2
        elif kva_value <= 100:
            end_clearance = 10 * 2
        else:
            end_clearance = 15 * 2
    elif voltage_value <= 11000:
        if kva_value <= 25:
            end_clearance = 20 * 2
        elif kva_value <= 1000:
            end_clearance = 25 * 2
        else:
            end_clearance = 30 * 2
    elif voltage_value <= 22000:
        if kva_value <= 100:
            end_clearance = 30 * 2
        else:
            end_clearance = 35 * 2
    elif voltage_value <= 33000:
        if kva_value <= 100:
            end_clearance = 35 * 2
        else:
            end_clearance = 45 * 2
    elif voltage_value <= 66000:
        if has_star_connection(vector_group):
            end_clearance = 80
            if kva_value <= 500:
                end_clearance += 35
            elif kva_value <= 2500:
                end_clearance += 50
            else:
                end_clearance += 60
        else:
            end_clearance = 80 * 2
    elif voltage_value <= 132000:
        if has_star_connection(vector_group):
            end_clearance = 115
            if kva_value <= 500:
                end_clearance += 35
            elif kva_value <= 2500:
                end_clearance += 50
            else:
                end_clearance += 60
        else:
            end_clearance = 115 * 2
    else:
        if has_star_connection(vector_group):
            end_clearance = 115
            if kva_value <= 500:
                end_clearance += 35
            elif kva_value <= 2500:
                end_clearance += 50
            else:
                end_clearance += 60
        else:
            end_clearance = 115 * 2

    if dry_type:
        if voltage_value <= 1100:
            end_clearance = 2 * 40 if kva_value <= 100 else 2 * 60
        elif voltage_value <= 11000:
            end_clearance = 2 * 140
        elif voltage_value <= 22000:
            end_clearance = 2 * 200
        elif voltage_value <= 33000:
            end_clearance = 2 * 240

    if end_clr is not None and end_clr >= 0.25 * end_clearance:
        return end_clr

    return float(end_clearance)

def _get_winding_value(winding, field_name):
    if winding is None:
        return None
    return getattr(winding, field_name, None)

def build_winding_formula_context(multi_winding):
    return {
        "designId": multi_winding.designId,
        "windings": multi_winding.windings,
        "vectorGroup": multi_winding.vectorGroup,
        "ratings": {
            "kVA": multi_winding.kVA,
            "kValue": multi_winding.kValue,
            "frequency": multi_winding.frequency,
            "fluxDensity": multi_winding.fluxDensity,
            "lowVoltage": multi_winding.lowVoltage,
            "highVoltage": multi_winding.highVoltage,
        },
        "currentDensity": {
            "lv": multi_winding.lvCurrentDensity,
            "hv": multi_winding.hvCurrentDensity,
            "fine": multi_winding.fineCurrentDensity,
            "corse": multi_winding.corseCurrentDensity,
            "outer": multi_winding.outerCurrentDensity,
        },
        "conductorMaterial": {
            "lv": multi_winding.lvConductorMaterial,
            "hv": multi_winding.hvConductorMaterial,
            "fine": multi_winding.fineConductorMaterial,
            "corse": multi_winding.corseConductorMaterial,
            "outer": multi_winding.outerConductorMaterial,
        },
        "tapSteps": {
            "percentage": multi_winding.tapStepsPercentage,
            "positive": multi_winding.tapStepPositive,
            "negative": multi_winding.tapStepNegative,
        },
        "windingModels": {
            "lv": multi_winding.lvWindings,
            "hv": multi_winding.hvWindings,
            "fine": multi_winding.fineWindings,
            "corse": multi_winding.corseWindings,
            "outer": multi_winding.outerWindings,
        },
        "radialGaps": multi_winding.radialGaps,
    }

def calculate_winding_formulae(multi_winding):
    context = build_winding_formula_context(multi_winding)
    vector_group = context["vectorGroup"]
    kva = context["ratings"]["kVA"]
    dry_type = getattr(multi_winding, "dryType", False)
    lv_winding = context["windingModels"]["lv"]
    hv_winding = context["windingModels"]["hv"]

    return {
        "inputs": context,
        "results": {
            "lvVoltsPerPhase": get_lv_volts_per_phase(
                context["ratings"]["lowVoltage"],
                vector_group,
            ),
            "hvVoltsPerPhase": get_hv_volts_per_phase(
                context["ratings"]["highVoltage"],
                vector_group,
            ),
            "lvEndClearance": get_end_clearance(
                kva,
                context["ratings"]["lowVoltage"],
                vector_group,
                _get_winding_value(lv_winding, "endClearances"),
                dry_type,
            ),
            "hvEndClearance": get_end_clearance(
                kva,
                context["ratings"]["highVoltage"],
                vector_group,
                _get_winding_value(hv_winding, "endClearances"),
                dry_type,
            ),
        },
    }

