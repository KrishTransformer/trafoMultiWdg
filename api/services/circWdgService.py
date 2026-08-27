import math

from api.models import CoilDimensions, Core, Windings
from api.services.numberUtils import next_integer, two_digit_decimal
from api.services._windingServiceSupport import (
    build_geometry_snapshot,
    build_hv_section_results,
    build_section_turns,
    build_seed_dimensions,
    safe_float,
)
from api.services.corseWindingService import calculate_corse_windings
from api.services.fineWindingService import calculate_fine_windings
from api.services.hvWindingService import calculate_hv_windings, get_effective_limb_height
from api.services.impedanceVbService import calculate_vb_multi_impedance
from api.services.lvWindingService import calculate_lv_windings
from api.services.outerWindingService import calculate_outer_windings
from api.services.tankOilService import calculate_tank_and_oil
from api.services.windingFormulae import (
    CLASS_B,
    COPPER,
    ECONOMIC,
    ampere_turns,
    build_winding_formula_context,
    ek,
    er,
    ex,
    get_build_factor,
    get_core_lv_ins,
    get_core_material,
    get_core_type,
    get_core_length,
    get_core_loss,
    get_core_weight,
    get_current_density,
    get_center_distance,
    get_efficiency_percentage,
    get_flux_density,
    get_frequency,
    get_high_voltage,
    get_hv_hv_ins,
    get_k_value,
    # get_kw55_for_multiple_windings,
    get_limit_ez,
    get_loss_at_100_percent,
    get_loss_at_50_percent,
    get_low_voltage,
    get_lv_hv_ins,
    get_modified_limb_ht_for_impedance,
    get_nl_current_percentage,
    get_specific_loss,
    get_tank_loss,
    get_test_and_imp_test,
    get_vector_group,
    get_voltage_regulation,
    h1h2,
    is_ez_within_range,
    ls,
)

DEFAULT_WINDING_SELECTION = "2 Wdg (LV and HV-Main)"
IMPEDANCE_MAX_ITERATIONS = 20
WINDING_SEQUENCE = ("lv", "hv", "corse", "fine", "outer")
WINDING_SELECTION_CODES = {
    DEFAULT_WINDING_SELECTION: "2_WDG",
    "3 Wdg (LV, HV-Main and Outer)": "3_WDG",
    "4 Wdg (LV, HV-Main, Corse and Outer)": "4_WDG_C",
    "4 Wdg (LV, HV-Main, Fine and Outer)": "4_WDG_F",
    "5 Wdg (LV, HV-Main, Corse, Fine and Outer)": "5_WDG",
}
WINDING_SELECTION_LABELS_BY_CODE = {
    code: label
    for label, code in WINDING_SELECTION_CODES.items()
}
WINDING_SELECTIONS = {
    DEFAULT_WINDING_SELECTION: frozenset(("lv", "hv")),
    "3 Wdg (LV, HV-Main and Outer)": frozenset(("lv", "hv", "outer")),
    "4 Wdg (LV, HV-Main, Corse and Outer)": frozenset(("lv", "hv", "corse", "outer")),
    "4 Wdg (LV, HV-Main, Fine and Outer)": frozenset(("lv", "hv", "fine", "outer")),
    "5 Wdg (LV, HV-Main, Corse, Fine and Outer)": frozenset(("lv", "hv", "corse", "fine", "outer")),
}
WINDING_MODEL_ATTRS = {
    "lv": "lvWindings",
    "hv": "hvWindings",
    "fine": "fineWindings",
    "corse": "corseWindings",
    "outer": "outerWindings",
}
WINDING_TYPE_ATTRS = {
    "lv": "lvWindingType",
    "hv": "hvWindingType",
    "corse": "corseWindingType",
    "fine": "fineWindingType",
    "outer": "outerWindingType",
}
WINDING_TYPE_OPTIONS = {
    "lv": ("FOIL", "HELICAL", "DISC", "LAYER_DISC"),
    "hv": ("HELICAL", "XOVER", "DISC"),
    "corse": ("HELICAL",),
    "fine": ("HELICAL",),
    "outer": ("HELICAL", "DISC"),
}
WINDING_TYPE_DEFAULTS = {
    "lv": "HELICAL",
    "hv": "HELICAL",
    "corse": "HELICAL",
    "fine": "HELICAL",
    "outer": "HELICAL",
}
WINDING_SELECTION_ALIASES = {
    "": DEFAULT_WINDING_SELECTION,
    "2 WDG": DEFAULT_WINDING_SELECTION,
    "2WDG": DEFAULT_WINDING_SELECTION,
    "LV HV": DEFAULT_WINDING_SELECTION,
    "LV-HV": DEFAULT_WINDING_SELECTION,
    "LV AND HV-MAIN": DEFAULT_WINDING_SELECTION,
    "3 WDG": "3 Wdg (LV, HV-Main and Outer)",
    "3WDG": "3 Wdg (LV, HV-Main and Outer)",
    "LV HV-MAIN OUTER": "3 Wdg (LV, HV-Main and Outer)",
    "4 WDG CORSE OUTER": "4 Wdg (LV, HV-Main, Corse and Outer)",
    "4WDG CORSE OUTER": "4 Wdg (LV, HV-Main, Corse and Outer)",
    "LV HV-MAIN CORSE OUTER": "4 Wdg (LV, HV-Main, Corse and Outer)",
    "4 WDG COURSE OUTER": "4 Wdg (LV, HV-Main, Corse and Outer)",
    "4WDG COURSE OUTER": "4 Wdg (LV, HV-Main, Corse and Outer)",
    "LV HV-MAIN COURSE OUTER": "4 Wdg (LV, HV-Main, Corse and Outer)",
    "4 WDG FINE OUTER": "4 Wdg (LV, HV-Main, Fine and Outer)",
    "4WDG FINE OUTER": "4 Wdg (LV, HV-Main, Fine and Outer)",
    "LV HV-MAIN FINE OUTER": "4 Wdg (LV, HV-Main, Fine and Outer)",
    "5 WDG": "5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
    "5WDG": "5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
    "LV HV-MAIN CORSE FINE OUTER": "5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
    "LV HV-MAIN COURSE FINE OUTER": "5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
    "2_WDG": DEFAULT_WINDING_SELECTION,
    "3_WDG": "3 Wdg (LV, HV-Main and Outer)",
    "4_WDG_C": "4 Wdg (LV, HV-Main, Corse and Outer)",
    "4_WDG_F": "4 Wdg (LV, HV-Main, Fine and Outer)",
    "5_WDG": "5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
}
WINDING_TYPE_ALIASES = {
    "LAYER DISC": "LAYER_DISC",
    "LAYERDISC": "LAYER_DISC",
    "LAYER_DISC": "LAYER_DISC",
    "X OVER": "XOVER",
    "X-OVER": "XOVER",
}
COIL_SCALE_GAP_LAYOUTS = {
    "3 Wdg (LV, HV-Main and Outer)": (
        {"winding": "outer", "gapField": "hvToOuter", "inner": "hv", "outer": "outer"},
    ),
    "4 Wdg (LV, HV-Main, Corse and Outer)": (
        {"winding": "corse", "gapField": "hvToCorse", "inner": "hv", "outer": "corse"},
        {"winding": "outer", "gapField": "corseToOuter", "inner": "corse", "outer": "outer"},
    ),
    "4 Wdg (LV, HV-Main, Fine and Outer)": (
        {"winding": "fine", "gapField": "hvToFine", "inner": "hv", "outer": "fine"},
        {"winding": "outer", "gapField": "fineToOuter", "inner": "fine", "outer": "outer"},
    ),
    "5 Wdg (LV, HV-Main, Corse, Fine and Outer)": (
        {"winding": "corse", "gapField": "hvToCorse", "inner": "hv", "outer": "corse"},
        {"winding": "fine", "gapField": "corseToFine", "inner": "corse", "outer": "fine"},
        {"winding": "outer", "gapField": "fineToOuter", "inner": "fine", "outer": "outer"},
    ),
}
EXTRA_WINDING_SERVICE_MAP = {
    "corse": calculate_corse_windings,
    "fine": calculate_fine_windings,
    "outer": calculate_outer_windings,
}


def _default_core(multi_winding):
    core = getattr(multi_winding, "core", None)
    if core is None:
        core = Core()
        multi_winding.core = core
    return core


def _default_winding(multi_winding, attr_name):
    winding = getattr(multi_winding, attr_name, None)
    if winding is None:
        winding = Windings()
        setattr(multi_winding, attr_name, winding)
    return winding


def _snapshot_model_fields(model):
    """Keep request values separate from calculated values written onto the models."""
    if model is None:
        return None
    if not hasattr(model, "_meta"):
        return {
            name: value
            for name, value in vars(model).items()
            if name != "_state"
        }
    return {
        field.name: getattr(model, field.name)
        for field in model._meta.fields
        if field.name != "id"
    }


def _restore_model_fields(model, values):
    if model is None or values is None:
        return
    for name, value in values.items():
        setattr(model, name, value)


def _snapshot_impedance_inputs(multi_winding):
    active_windings = set(_get_active_windings(multi_winding.windings))
    return {
        "core": _snapshot_model_fields(_default_core(multi_winding)),
        "coilDimensions": _snapshot_model_fields(_default_coil_dimensions(multi_winding)),
        "windings": {
            attr_name: _snapshot_model_fields(_default_winding(multi_winding, attr_name))
            for winding_name, attr_name in WINDING_MODEL_ATTRS.items()
            if winding_name in active_windings
        },
    }


def _restore_impedance_inputs(multi_winding, snapshot):
    _restore_model_fields(_default_core(multi_winding), snapshot["core"])
    _restore_model_fields(_default_coil_dimensions(multi_winding), snapshot["coilDimensions"])
    for attr_name, values in snapshot["windings"].items():
        _restore_model_fields(_default_winding(multi_winding, attr_name), values)


def _has_impedance_locked_input(snapshot):
    core = snapshot["core"] or {}
    windings = snapshot["windings"]
    lv = windings.get("lvWindings") or {}
    hv = windings.get("hvWindings") or {}
    return (
        core.get("limbHt") is not None
        or lv.get("condBreadth") is not None
        or lv.get("condHeight") is not None
        or hv.get("condBreadth") is not None
        or hv.get("condHeight") is not None
    )


def _default_coil_dimensions(multi_winding):
    coil_dimensions = getattr(multi_winding, "coilDimensions", None)
    if coil_dimensions is None:
        coil_dimensions = CoilDimensions()
        multi_winding.coilDimensions = coil_dimensions
    return coil_dimensions


def _resolve_optional_current_density(multi_winding, winding_name, active_windings, trans_cost_type, dry_type, dry_temp_class):
    if winding_name not in active_windings:
        return None

    current_density_attr = f"{winding_name}CurrentDensity"
    conductor_material_attr = f"{winding_name}ConductorMaterial"
    current_density_value = getattr(multi_winding, current_density_attr, None)
    current_density_override = (
        current_density_value
        if current_density_value is not None and current_density_value > 0
        else multi_winding.hvCurrentDensity
    )

    return get_current_density(
        getattr(multi_winding, conductor_material_attr),
        trans_cost_type,
        dry_type,
        dry_temp_class,
        False,
        current_density_override,
    )


def _normalize_winding_type(multi_winding, attr_name, default_value):
    value = getattr(multi_winding, attr_name, None)
    return value if value else default_value


def _normalize_winding_type_value(winding_name, value):
    if value is None or str(value).strip() == "":
        return WINDING_TYPE_DEFAULTS[winding_name]

    normalized_value = "_".join(str(value).strip().upper().replace("-", " ").split())
    normalized_value = WINDING_TYPE_ALIASES.get(normalized_value.replace("_", " "), normalized_value)
    if normalized_value in WINDING_TYPE_OPTIONS[winding_name]:
        return normalized_value

    supported_values = ", ".join(WINDING_TYPE_OPTIONS[winding_name])
    raise ValueError(
        f"Unsupported {winding_name}WindingType. Supported values are: {supported_values}"
    )


def _normalize_winding_selection(value):
    if value in WINDING_SELECTIONS:
        return value
    if value in WINDING_SELECTION_LABELS_BY_CODE:
        return WINDING_SELECTION_LABELS_BY_CODE[value]

    normalized_value = " ".join(str(value or "").strip().upper().replace(",", " ").split())
    if normalized_value in WINDING_SELECTION_ALIASES:
        return WINDING_SELECTION_ALIASES[normalized_value]

    supported_values = ", ".join(
        [
            f"{code} ({label})"
            for label, code in WINDING_SELECTION_CODES.items()
        ]
    )
    raise ValueError(f"Unsupported windingSelection. Supported values are: {supported_values}")


def _get_active_windings(selection):
    selected_windings = WINDING_SELECTIONS[selection]
    return tuple(
        winding_name
        for winding_name in WINDING_SEQUENCE
        if winding_name in selected_windings
    )


def _configure_winding_models(multi_winding, selection):
    active_windings = set(_get_active_windings(selection))
    for winding_name, attr_name in WINDING_MODEL_ATTRS.items():
        if winding_name in active_windings:
            _default_winding(multi_winding, attr_name)
        else:
            setattr(multi_winding, attr_name, None)


def _build_winding_type_payload(multi_winding):
    return {
        winding_name: getattr(multi_winding, WINDING_TYPE_ATTRS[winding_name], None)
        for winding_name in _get_active_windings(multi_winding.windings)
    }


def _round_dimension(value):
    return int(round(safe_float(value, 0.0)))


def _get_gap_layout(selection):
    return COIL_SCALE_GAP_LAYOUTS.get(selection, ())


def _get_post_hv_gap_for_voltage(kva, section_voltage, vector_group):
    voltage = safe_float(section_voltage, 0.0)
    rating = safe_float(kva, 0.0)
    connection = str(vector_group or "").strip().upper()[:1]

    if voltage <= 0:
        return 0.0
    if voltage <= 1100:
        return 5.0 if rating <= 500 else 6.0
    if voltage <= 6600:
        return 6.0 if rating <= 1000 else 7.0
    if voltage <= 11000:
        if rating <= 100:
            return 7.0
        if rating <= 2500:
            return 8.0
        return 9.0
    if voltage <= 33000:
        return 18.0
    if voltage <= 66000:
        return 28.0
    return 54.0 if connection == "D" else 43.0


def _resolve_post_hv_gap_to_previous(multi_winding, winding_name, gap_field, radial_gaps, section_allocations, lv_results):
    explicit_gap = safe_float(
        getattr(radial_gaps, gap_field, 0.0) if radial_gaps is not None else 0.0,
        0.0,
    )
    if explicit_gap > 0:
        return explicit_gap

    allocated_turns = safe_float((section_allocations.get(winding_name) or {}).get("turns"), 0.0)
    if allocated_turns <= 0:
        winding = getattr(multi_winding, WINDING_MODEL_ATTRS[winding_name], None)
        allocated_turns = safe_float(getattr(winding, "turnsPerPhase", None), 0.0) if winding is not None else 0.0
    if allocated_turns <= 0:
        return explicit_gap

    section_voltage = safe_float(lv_results.get("revisedVoltsPerTurn"), 0.0) * allocated_turns * 2
    return _get_post_hv_gap_for_voltage(
        getattr(multi_winding, "kVA", 0.0),
        section_voltage,
        getattr(multi_winding, "vectorGroup", ""),
    )


def _build_finalized_hv_source(raw_hv_results, hv_section_results):
    if not hv_section_results:
        return raw_hv_results

    finalized_hv_source = dict(raw_hv_results)
    finalized_hv_source.update(
        {
            "hvTurnsPerPhase": safe_float(
                hv_section_results.get("turnsPerPhase"),
                raw_hv_results.get("hvTurnsPerPhase", 0.0),
            ),
            "hvTurnsAtHighest": safe_float(
                hv_section_results.get("turnsPerPhase"),
                raw_hv_results.get("hvTurnsAtHighest", 0.0),
            ),
            "hvTurnsAtLowest": safe_float(
                hv_section_results.get("turnsPerPhase"),
                raw_hv_results.get("hvTurnsAtLowest", 0.0),
            ),
            "hvVoltsPerPhase": safe_float(
                hv_section_results.get("voltsPerPhase"),
                raw_hv_results.get("hvVoltsPerPhase", 0.0),
            ),
            "hvCurrentPerPhase": safe_float(
                hv_section_results.get("phaseCurrent"),
                raw_hv_results.get("hvCurrentPerPhase", 0.0),
            ),
            "hVRevisedCurrDenAtNormal": safe_float(
                hv_section_results.get("currentDensity"),
                raw_hv_results.get("hVRevisedCurrDenAtNormal", 0.0),
            ),
            "hVRevisedCurrDenAtLowest": safe_float(
                hv_section_results.get("currentDensity"),
                raw_hv_results.get("hVRevisedCurrDenAtLowest", 0.0),
            ),
            "hvConductorCrossSection": safe_float(
                hv_section_results.get("conductorCrossSection"),
                raw_hv_results.get("hvConductorCrossSection", 0.0),
            ),
            "hvTotalCondCrossSection": safe_float(
                hv_section_results.get("condCrossSec"),
                raw_hv_results.get("hvTotalCondCrossSection", 0.0),
            ),
            "hvConductorInsulation": safe_float(
                hv_section_results.get("conductorInsulation"),
                raw_hv_results.get("hvConductorInsulation", 0.0),
            ),
            "hvInterLayerInsulation": safe_float(
                hv_section_results.get("interLayerInsulation"),
                raw_hv_results.get("hvInterLayerInsulation", 0.0),
            ),
            "hvRadialParallelConductors": safe_float(
                hv_section_results.get("radialParallelCond"),
                raw_hv_results.get("hvRadialParallelConductors", 1.0),
            ),
            "hvAxialParallelConductors": safe_float(
                hv_section_results.get("axialParallelCond"),
                raw_hv_results.get("hvAxialParallelConductors", 1.0),
            ),
            "hvNoOfConductors": safe_float(
                hv_section_results.get("noOfConductors"),
                raw_hv_results.get("hvNoOfConductors", 0.0),
            ),
            "hvBreadth": safe_float(
                hv_section_results.get("breadth"),
                raw_hv_results.get("hvBreadth", 0.0),
            ),
            "hvHeight": safe_float(
                hv_section_results.get("height"),
                raw_hv_results.get("hvHeight", 0.0),
            ),
            "hvBreadthInsulated": safe_float(
                hv_section_results.get("breadthInsulated"),
                raw_hv_results.get("hvBreadthInsulated", 0.0),
            ),
            "hvHeightInsulated": safe_float(
                hv_section_results.get("heightInsulated"),
                raw_hv_results.get("hvHeightInsulated", 0.0),
            ),
            "hvTurnsPerLayer": safe_float(
                hv_section_results.get("turnsPerLayer"),
                raw_hv_results.get("hvTurnsPerLayer", 0.0),
            ),
            "hvNumberOfLayers": safe_float(
                hv_section_results.get("noOfLayers"),
                raw_hv_results.get("hvNumberOfLayers", 0.0),
            ),
            "hvWindingLength": safe_float(
                hv_section_results.get("windingLength"),
                raw_hv_results.get("hvWindingLength", 0.0),
            ),
            "hvEndClearance": safe_float(
                hv_section_results.get("endClearance"),
                raw_hv_results.get("hvEndClearance", 0.0),
            ),
            "hvNoOfDuct": safe_float(
                hv_section_results.get("ducts"),
                raw_hv_results.get("hvNoOfDuct", 0.0),
            ),
            "hvDuctThickness": safe_float(
                hv_section_results.get("ductSize"),
                raw_hv_results.get("hvDuctThickness", 0.0),
            ),
            "hvRadialThickness": safe_float(
                hv_section_results.get("radialThickness"),
                raw_hv_results.get("hvRadialThickness", 0.0),
            ),
            "hvId": safe_float(
                hv_section_results.get("innerDiameter"),
                raw_hv_results.get("hvId", 0.0),
            ),
            "hvOd": safe_float(
                hv_section_results.get("outerDiameter"),
                raw_hv_results.get("hvOd", 0.0),
            ),
            "hvLmt": safe_float(
                hv_section_results.get("lmt"),
                raw_hv_results.get("hvLmt", 0.0),
            ),
            "hvWireLength": safe_float(
                hv_section_results.get("wireLength"),
                raw_hv_results.get("hvWireLength", 0.0),
            ),
            "hvR75": safe_float(
                hv_section_results.get("r75"),
                raw_hv_results.get("hvR75", 0.0),
            ),
            "hvR26": safe_float(
                hv_section_results.get("r26"),
                raw_hv_results.get("hvR26", 0.0),
            ),
            "hvBareWeight": safe_float(
                hv_section_results.get("bareWeight"),
                raw_hv_results.get("hvBareWeight", 0.0),
            ),
            "hvInsulatedWeight": safe_float(
                hv_section_results.get("insulatedWeight"),
                raw_hv_results.get("hvInsulatedWeight", 0.0),
            ),
            "hvLoadLossAtNormal": safe_float(
                hv_section_results.get("loadLoss"),
                raw_hv_results.get("hvLoadLossAtNormal", 0.0),
            ),
            "hvLoadLossAtLowest": safe_float(
                hv_section_results.get("loadLoss"),
                raw_hv_results.get("hvLoadLossAtLowest", 0.0),
            ),
            "%hvStrayLoss": safe_float(
                hv_section_results.get("strayLoss"),
                raw_hv_results.get("%hvStrayLoss", 0.0),
            ),
            "hvGradient": safe_float(
                hv_section_results.get("gradient"),
                raw_hv_results.get("hvGradient", 0.0),
            ),
            "hvDiscDuctsSize": safe_float(
                hv_section_results.get("discDuctSize"),
                raw_hv_results.get("hvDiscDuctsSize", 0.0),
            ),
            "hvNoOfSpacers": hv_section_results.get(
                "noOfSpacers",
                raw_hv_results.get("hvNoOfSpacers", 0),
            ),
            "hvWidthOfSpacer": hv_section_results.get(
                "widthOfSpacer",
                raw_hv_results.get("hvWidthOfSpacer", 0),
            ),
            "hvExcessTurns": hv_section_results.get(
                "excessTurns",
                raw_hv_results.get("hvExcessTurns", 0),
            ),
            "hvSpacersToBeRemoved": hv_section_results.get(
                "spacersToBeRemoved",
                raw_hv_results.get("hvSpacersToBeRemoved", 0),
            ),
            "hvFullDisc": hv_section_results.get(
                "fullDisc",
                raw_hv_results.get("hvFullDisc", 0),
            ),
            "hvHalfDisc": hv_section_results.get(
                "halfDisc",
                raw_hv_results.get("hvHalfDisc", 0),
            ),
            "hvPartialDisc": hv_section_results.get(
                "partialDisc",
                raw_hv_results.get("hvPartialDisc", 0),
            ),
            "hvBalanceSpacersInLastDisc": hv_section_results.get(
                "balanceSpacersInLastDisc",
                raw_hv_results.get("hvBalanceSpacersInLastDisc", 0),
            ),
            "hvDiscArrangement": hv_section_results.get(
                "discArrangement",
                raw_hv_results.get("hvDiscArrangement", ""),
            ),
            "hvIsConductorRound": hv_section_results.get(
                "isConductorRound",
                raw_hv_results.get("hvIsConductorRound"),
            ),
            "hvIsEnamel": hv_section_results.get(
                "isEnamel",
                raw_hv_results.get("hvIsEnamel"),
            ),
        }
    )
    return finalized_hv_source


def _build_extra_winding_results(
    multi_winding,
    selection,
    hv_source,
    section_allocations,
    previous_geometry,
    lv_results,
    limb_height=None,
    perma_wood_ring=0.0,
):
    radial_gaps = getattr(multi_winding, "radialGaps", None)
    allow_turns_fallback = _get_total_taps(multi_winding) <= 0
    extra_results = {
        "corse": None,
        "fine": None,
        "outer": None,
    }

    for gap_layout in _get_gap_layout(selection):
        winding_name = gap_layout["winding"]
        gap_field = gap_layout["gapField"]
        seed_dimensions = build_seed_dimensions(previous_geometry, gap_field, radial_gaps)
        seed_dimensions["gapToPrevious"] = _resolve_post_hv_gap_to_previous(
            multi_winding,
            winding_name,
            gap_field,
            radial_gaps,
            section_allocations,
            lv_results,
        )
        service = EXTRA_WINDING_SERVICE_MAP[winding_name]
        result = service(
            multi_winding,
            hv_source,
            seed_dimensions,
            (section_allocations.get(winding_name) or {}).get("turns", 0.0),
            (section_allocations.get(winding_name) or {}).get("voltsPerPhase", 0.0),
            allow_turns_fallback=allow_turns_fallback,
            limb_height=limb_height,
            perma_wood_ring=perma_wood_ring,
        )
        extra_results[winding_name] = result
        previous_geometry = build_geometry_snapshot(
            winding_name,
            result.get("estimatedInnerDiameter", 0.0),
            result.get("estimatedRadialThickness", 0.0),
            result.get("estimatedOuterDiameter", 0.0),
            result.get("estimatedWindingLength", 0.0),
            "estimated",
            end_clearance=result.get("endClearance", 0.0),
        )

    return extra_results


def _build_coil_dimension_scale(
    selection,
    lv_results,
    hv_results,
    extra_winding_results,
    limb_height=None,
):
    radial_build = [
        {
            "name": "lv",
            "innerDiameter": _round_dimension(lv_results["lvId"]),
            "radialThickness": _round_dimension(lv_results["lvRadialThickness"]),
            "outerDiameter": _round_dimension(lv_results["lvOd"]),
            "gapFromPrevious": safe_float(lv_results["coreGap"], 0.0),
            "gapField": "coreToLv",
            "source": "calculated",
        },
        {
            "name": "hv",
            "innerDiameter": _round_dimension(hv_results["hvId"] if "hvId" in hv_results else hv_results["innerDiameter"]),
            "radialThickness": _round_dimension(hv_results["hvRadialThickness"] if "hvRadialThickness" in hv_results else hv_results["radialThickness"]),
            "outerDiameter": _round_dimension(hv_results["hvOd"] if "hvOd" in hv_results else hv_results["outerDiameter"]),
            "gapFromPrevious": safe_float(hv_results["lvHvGap"] if "lvHvGap" in hv_results else 0.0, 0.0),
            "gapField": "lvToHv",
            "source": "calculated",
        },
    ]

    previous_outer_diameter = safe_float(hv_results["hvOd"] if "hvOd" in hv_results else hv_results["outerDiameter"], 0.0)
    for gap_layout in _get_gap_layout(selection):
        winding_name = gap_layout["winding"]
        result = extra_winding_results.get(winding_name) or {}
        seed_dimensions = result.get("seedDimensions", {})
        inner_diameter = safe_float(result.get("estimatedInnerDiameter"), 0.0)
        outer_diameter = safe_float(result.get("estimatedOuterDiameter"), 0.0)
        radial_thickness = safe_float(result.get("estimatedRadialThickness"), 0.0)
        if inner_diameter <= 0.0:
            inner_diameter = previous_outer_diameter + (2 * safe_float(seed_dimensions.get("gapToPrevious"), 0.0))
        if outer_diameter <= 0.0:
            outer_diameter = inner_diameter + (2 * radial_thickness)
        radial_build.append(
            {
                "name": winding_name,
                "innerDiameter": _round_dimension(inner_diameter),
                "radialThickness": _round_dimension(radial_thickness),
                "outerDiameter": _round_dimension(outer_diameter),
                "gapFromPrevious": safe_float(seed_dimensions.get("gapToPrevious"), 0.0),
                "gapField": seed_dimensions.get("gapField"),
                "seededFrom": seed_dimensions.get("previousWinding"),
                "source": "estimated",
            }
        )
        previous_outer_diameter = outer_diameter

    scaled_outer_od = _round_dimension(previous_outer_diameter)
    scaled_gap = safe_float(hv_results["hvHvGap"], 0.0)
    scaled_center_distance = _round_dimension(previous_outer_diameter + scaled_gap)
    finalized_limb_height = lv_results["windowHeight"] if limb_height is None else limb_height
    scaled_active_part_height = _round_dimension((2 * lv_results["coreDiameter"]) + finalized_limb_height)
    scaled_active_part_length = _round_dimension((2 * scaled_center_distance) + previous_outer_diameter)
    winding_dimensions = {
        winding_name: None
        for winding_name in WINDING_MODEL_ATTRS.keys()
    }
    for item in radial_build:
        winding_dimensions[item["name"]] = {
            "innerDiameter": item["innerDiameter"],
            "radialThickness": item["radialThickness"],
            "outerDiameter": item["outerDiameter"],
            "gapFromPrevious": item["gapFromPrevious"],
            "gapField": item["gapField"],
            "seededFrom": item.get("seededFrom"),
            "source": item["source"],
        }

    return {
        "radialBuild": radial_build,
        "windingDimensions": winding_dimensions,
        "outermostWinding": radial_build[-1]["name"],
        "outermostOD": scaled_outer_od,
        "centerDistance": scaled_center_distance,
        "activePartSize": f"{scaled_active_part_length} L X {scaled_outer_od} W X {scaled_active_part_height} H mm",
    }


def _get_er_tank_loss_factor(low_voltage, phase_current):
    if low_voltage <= 1100:
        if phase_current <= 300:
            return 0.8
        if phase_current <= 700:
            return 1
        if phase_current <= 2000:
            return 1.5
        if phase_current <= 4000:
            return 2
        return 3
    return 0.4 if low_voltage <= 33000 else 0.3


def _get_winding_order(selection):
    return list(_get_active_windings(selection))


def _vb_int(value):
    return int(math.floor(safe_float(value, 0.0)))


def _vb_round1(value):
    numeric_value = safe_float(value, 0.0)
    return math.floor((numeric_value * 10) + 0.5) / 10


def _build_section_allocation(turns=0.0, volts_per_phase=0.0, taps=0.0, turns_per_tap=0.0):
    return {
        "turns": safe_float(turns, 0.0),
        "voltsPerPhase": safe_float(volts_per_phase, 0.0),
        "taps": safe_float(taps, 0.0),
        "turnsPerTap": safe_float(turns_per_tap, 0.0),
    }


def _get_total_taps(multi_winding):
    return max(0, int((multi_winding.tapStepPositive or 0) + (multi_winding.tapStepNegative or 0)))


def _get_supported_taps_for_winding(multi_winding, winding_name, turns_per_tap):
    if safe_float(turns_per_tap, 0.0) <= 0:
        return None

    winding = getattr(multi_winding, WINDING_MODEL_ATTRS[winding_name], None)
    winding_turns = safe_float(getattr(winding, "turnsPerPhase", None), 0.0) if winding is not None else 0.0
    if winding_turns <= 0:
        return None

    return max(0, int(math.floor(winding_turns / turns_per_tap)))


def _build_tap_turns(tap_count, turns_per_tap):
    return two_digit_decimal(safe_float(tap_count, 0.0) * safe_float(turns_per_tap, 0.0))


def _allocate_from_turn_share(total_turns, total_taps, share, volts_per_turn, turns_per_tap, total_voltage=None):
    allocated_turns = two_digit_decimal(safe_float(total_turns, 0.0) * safe_float(share, 0.0))
    allocated_taps = two_digit_decimal(safe_float(total_taps, 0.0) * safe_float(share, 0.0))
    inferred_turns_per_tap = safe_float(turns_per_tap, 0.0)
    if inferred_turns_per_tap <= 0 and safe_float(total_taps, 0.0) > 0:
        inferred_turns_per_tap = two_digit_decimal(safe_float(total_turns, 0.0) / safe_float(total_taps, 1.0))
    allocated_voltage = safe_float(total_voltage, 0.0) * safe_float(share, 0.0)
    if allocated_voltage <= 0:
        allocated_voltage = allocated_turns * safe_float(volts_per_turn, 0.0)
    return _build_section_allocation(
        turns=allocated_turns,
        volts_per_phase=_vb_int(allocated_voltage),
        taps=allocated_taps,
        turns_per_tap=inferred_turns_per_tap,
    )


def _allocate_outer_first_taps(multi_winding, turns_per_tap):
    total_taps = _get_total_taps(multi_winding)
    outer_supported_taps = _get_supported_taps_for_winding(multi_winding, "outer", turns_per_tap)
    outer_taps = total_taps if outer_supported_taps is None else min(total_taps, outer_supported_taps)
    remaining_taps = max(total_taps - outer_taps, 0)
    return outer_taps, remaining_taps


def _apply_section_allocation_fallbacks(multi_winding, allocations, volts_per_turn):
    if _get_total_taps(multi_winding) > 0:
        return

    for winding_name in ("corse", "fine", "outer"):
        allocation = allocations[winding_name]
        if allocation["turns"] > 0:
            continue
        winding = getattr(multi_winding, WINDING_MODEL_ATTRS[winding_name], None)
        fallback_turns = safe_float(getattr(winding, "turnsPerPhase", None), 0.0) if winding is not None else 0.0
        if fallback_turns <= 0:
            continue
        allocation["turns"] = fallback_turns
        allocation["voltsPerPhase"] = _vb_int(fallback_turns * volts_per_turn)


def _seed_hv_main_winding(winding, hv_results, winding_type=None):
    hv_winding = winding if winding is not None else Windings()
    normalized_winding_type = str(winding_type or "HELICAL").upper()

    if safe_float(getattr(hv_winding, "turnsPerLayer", None), 0.0) <= 0:
        hv_winding.turnsPerLayer = safe_float(hv_results.get("hvTurnsPerLayer"), 0.0)
    if safe_float(getattr(hv_winding, "endClearances", None), 0.0) <= 0:
        hv_winding.endClearances = safe_float(hv_results.get("hvEndClearance"), 0.0)
    if getattr(hv_winding, "ducts", None) is None:
        hv_winding.ducts = int(round(safe_float(hv_results.get("hvNoOfDuct"), 0.0)))
    if getattr(hv_winding, "ductSize", None) is None:
        hv_winding.ductSize = int(round(safe_float(hv_results.get("hvDuctThickness"), 0.0)))
    if getattr(hv_winding, "condInsulation", None) is None:
        hv_winding.condInsulation = safe_float(hv_results.get("hvConductorInsulation"), 0.0)
    if getattr(hv_winding, "interLayerInsulation", None) is None:
        hv_winding.interLayerInsulation = safe_float(hv_results.get("hvInterLayerInsulation"), 0.0)
    if getattr(hv_winding, "radialParallelCond", None) is None:
        hv_winding.radialParallelCond = int(round(safe_float(hv_results.get("hvRadialParallelConductors"), 1.0)))
    if getattr(hv_winding, "axialParallelCond", None) is None:
        hv_winding.axialParallelCond = int(round(safe_float(hv_results.get("hvAxialParallelConductors"), 1.0)))
    if normalized_winding_type != "DISC" and getattr(hv_winding, "condBreadth", None) is None:
        hv_winding.condBreadth = safe_float(hv_results.get("hvBreadth"), 0.0)
    if normalized_winding_type != "DISC" and getattr(hv_winding, "condHeight", None) is None:
        hv_winding.condHeight = safe_float(hv_results.get("hvHeight"), 0.0)
    if normalized_winding_type != "DISC" and getattr(hv_winding, "conductorDiameter", None) is None:
        hv_winding.conductorDiameter = safe_float(hv_results.get("hvBreadth"), 0.0)
    if getattr(hv_winding, "isConductorRound", None) is None:
        hv_winding.isConductorRound = hv_results.get("hvIsConductorRound")
    if getattr(hv_winding, "isEnamel", None) is None:
        hv_winding.isEnamel = hv_results.get("hvIsEnamel")

    return hv_winding


def _get_high_side_distribution(multi_winding, lv_results, hv_results):
    selection = multi_winding.windings
    volts_per_turn = safe_float(lv_results.get("revisedVoltsPerTurn"), 0.0)
    highest_turns = safe_float(hv_results.get("hvTurnsAtHighest"), 0.0)
    lowest_turns = safe_float(hv_results.get("hvTurnsAtLowest"), safe_float(hv_results.get("hvTurnsPerPhase"), 0.0))
    highest_voltage = safe_float(hv_results.get("hvHighestTapVoltage"), safe_float(hv_results.get("hvVoltsPerPhase"), 0.0))
    lowest_voltage = safe_float(hv_results.get("hvLowestTapVoltage"), safe_float(hv_results.get("hvVoltsPerPhase"), 0.0))
    turns_per_tap = safe_float(hv_results.get("hvTurnsPerTap"), 0.0)
    total_taps = _get_total_taps(multi_winding)

    allocations = {
        "lv": _build_section_allocation(
            turns=lv_results.get("lvTurnsPerPhase", 0.0),
            volts_per_phase=_vb_int(lv_results.get("lvVoltsPerPhase", 0.0)),
        ),
        "hv": _build_section_allocation(
            turns=highest_turns if selection == DEFAULT_WINDING_SELECTION else lowest_turns,
            volts_per_phase=_vb_int(highest_voltage if selection == DEFAULT_WINDING_SELECTION else lowest_voltage),
        ),
        "corse": _build_section_allocation(),
        "fine": _build_section_allocation(),
        "outer": _build_section_allocation(),
    }

    if selection == DEFAULT_WINDING_SELECTION:
        return allocations

    tap_range_turns = max(highest_turns - lowest_turns, 0.0)
    tap_range_voltage = max(highest_voltage - lowest_voltage, 0.0)

    if selection == "3 Wdg (LV, HV-Main and Outer)":
        allocations["outer"] = _allocate_from_turn_share(
            tap_range_turns,
            total_taps,
            1.0,
            volts_per_turn,
            turns_per_tap,
            total_voltage=tap_range_voltage,
        )
    elif selection == "4 Wdg (LV, HV-Main, Corse and Outer)":
        allocations["corse"] = _allocate_from_turn_share(
            tap_range_turns,
            total_taps,
            0.5,
            volts_per_turn,
            turns_per_tap,
            total_voltage=tap_range_voltage,
        )
        allocations["outer"] = _allocate_from_turn_share(
            tap_range_turns,
            total_taps,
            0.5,
            volts_per_turn,
            turns_per_tap,
            total_voltage=tap_range_voltage,
        )
    elif selection == "4 Wdg (LV, HV-Main, Fine and Outer)":
        allocations["fine"] = _allocate_from_turn_share(
            tap_range_turns,
            total_taps,
            0.5,
            volts_per_turn,
            turns_per_tap,
            total_voltage=tap_range_voltage,
        )
        allocations["outer"] = _allocate_from_turn_share(
            tap_range_turns,
            total_taps,
            0.5,
            volts_per_turn,
            turns_per_tap,
            total_voltage=tap_range_voltage,
        )
    elif selection == "5 Wdg (LV, HV-Main, Corse, Fine and Outer)":
        allocations["corse"] = _allocate_from_turn_share(
            tap_range_turns,
            total_taps,
            0.5,
            volts_per_turn,
            turns_per_tap,
            total_voltage=tap_range_voltage,
        )
        allocations["fine"] = _allocate_from_turn_share(
            tap_range_turns,
            total_taps,
            0.25,
            volts_per_turn,
            turns_per_tap,
            total_voltage=tap_range_voltage,
        )
        allocations["outer"] = _allocate_from_turn_share(
            tap_range_turns,
            total_taps,
            0.25,
            volts_per_turn,
            turns_per_tap,
            total_voltage=tap_range_voltage,
        )

    _apply_section_allocation_fallbacks(multi_winding, allocations, volts_per_turn)
    return allocations


def _build_hv_main_results(multi_winding, lv_results, hv_results, allocation):
    if multi_winding.windings == DEFAULT_WINDING_SELECTION:
        return hv_results

    hv_winding = _seed_hv_main_winding(
        getattr(multi_winding, "hvWindings", None),
        hv_results,
        getattr(multi_winding, "hvWindingType", "HELICAL"),
    )
    hv_seed_dimensions = {
        "previousWinding": "lv",
        "previousOuterDiameter": safe_float(lv_results["lvOd"], 0.0),
        "previousRadialThickness": safe_float(lv_results["lvRadialThickness"], 0.0),
        "previousWindingLength": safe_float(hv_results["hvWindingLength"], 0.0),
        "gapField": "lvToHv",
        "gapToPrevious": safe_float(hv_results["lvHvGap"], 0.0),
    }
    section_results = build_hv_section_results(
        section_name="hv",
        winding_type=getattr(multi_winding, "hvWindingType", "HELICAL"),
        winding=hv_winding,
        hv_source=hv_results,
        material=multi_winding.hvConductorMaterial,
        allocated_turns=allocation.get("turns", safe_float(hv_results.get("hvTurnsPerPhase"), 0.0)),
        allocated_voltage=allocation.get("voltsPerPhase", safe_float(hv_results.get("hvVoltsPerPhase"), 0.0)),
        seed_dimensions=hv_seed_dimensions,
        dry_type=bool(getattr(multi_winding, "dryType", False)),
        ambient_temp=getattr(multi_winding, "ambientTemp", 50) or 50,
        winding_temp=getattr(multi_winding, "windingTemp", 55) or 55,
        limb_height=safe_float(getattr(getattr(multi_winding, "core", None), "limbHt", None), safe_float(lv_results["windowHeight"], 0.0)),
        perma_wood_ring=safe_float(lv_results["permaWoodRing"], 0.0),
    )
    section_results["endClearance"] = max(
        0.0,
        safe_float(getattr(getattr(multi_winding, "core", None), "limbHt", None), safe_float(lv_results["windowHeight"], 0.0))
        - safe_float(section_results.get("windingLength"), 0.0)
        - safe_float(lv_results["permaWoodRing"], 0.0),
    )
    section_results["hvTurnsPerTap"] = hv_results.get("hvTurnsPerTap", 0.0)
    section_results["hvHighestTapVoltage"] = hv_results.get("hvHighestTapVoltage", 0.0)
    section_results["hvLowestTapVoltage"] = hv_results.get("hvLowestTapVoltage", 0.0)
    section_results["tapVoltages"] = hv_results.get("tapVoltages")
    section_results["tapCurrent"] = hv_results.get("tapCurrent")
    section_results["hvCurrentAtLowest"] = hv_results.get("hvCurrentAtLowest", 0.0)
    section_results["hVRevisedCurrDenAtNormal"] = hv_results.get("hVRevisedCurrDenAtNormal", 0.0)
    section_results["hVRevisedCurrDenAtLowest"] = hv_results.get("hVRevisedCurrDenAtLowest", 0.0)
    section_results["hvLoadLossAtNormal"] = hv_results.get("hvLoadLossAtNormal", 0.0)
    section_results["hvLoadLossAtLowest"] = hv_results.get("hvLoadLossAtLowest", 0.0)
    section_results["hvDiscDuctsSize"] = hv_results.get("hvDiscDuctsSize", 0.0)
    section_results["hvNoOfSpacers"] = hv_results.get("hvNoOfSpacers", section_results.get("noOfSpacers", 0))
    section_results["hvWidthOfSpacer"] = hv_results.get("hvWidthOfSpacer", section_results.get("widthOfSpacer", 0))
    section_results["hvExcessTurns"] = hv_results.get("hvExcessTurns", section_results.get("excessTurns", 0))
    section_results["hvSpacersToBeRemoved"] = hv_results.get("hvSpacersToBeRemoved", section_results.get("spacersToBeRemoved", 0))
    section_results["hvFullDisc"] = hv_results.get("hvFullDisc", section_results.get("fullDisc", 0))
    section_results["hvHalfDisc"] = hv_results.get("hvHalfDisc", section_results.get("halfDisc", 0))
    section_results["hvPartialDisc"] = hv_results.get("hvPartialDisc", section_results.get("partialDisc", 0))
    section_results["hvBalanceSpacersInLastDisc"] = hv_results.get(
        "hvBalanceSpacersInLastDisc",
        section_results.get("balanceSpacersInLastDisc", 0),
    )
    section_results["hvDiscArrangement"] = hv_results.get("hvDiscArrangement", section_results.get("discArrangement", ""))
    section_results["coreLoss"] = hv_results.get("coreLoss", 0.0)
    section_results["lvHvGap"] = hv_results.get("lvHvGap", 0.0)
    section_results["hvVoltsPerPhase"] = allocation.get("voltsPerPhase", hv_results.get("hvVoltsPerPhase", 0.0))
    section_results["sourceHvVoltsPerPhase"] = hv_results.get("hvVoltsPerPhase", 0.0)
    section_results["hvHvGap"] = hv_results.get("hvHvGap", 0.0)
    return section_results


def _safe_positive_number(value, fallback):
    numeric_value = safe_float(value, fallback)
    return numeric_value if numeric_value > 0 else fallback


def _estimate_breadth_insulated_from_model(winding):
    cond_ins = safe_float(getattr(winding, "condInsulation", None), 0.0)
    breadth = safe_float(getattr(winding, "condBreadth", None), 0.0)
    if breadth <= 0:
        breadth = safe_float(getattr(winding, "condHeight", None), 0.0)
    if breadth <= 0:
        breadth = safe_float(getattr(winding, "conductorDiameter", None), 0.0)
    if breadth <= 0:
        return max(cond_ins, 0.1)
    return max(breadth + (2 * cond_ins), 0.1)


def _build_impedance_winding_data(multi_winding, lv_results, hv_results, coil_dimension_scale):
    winding_dimensions = coil_dimension_scale["windingDimensions"]
    winding_order = _get_winding_order(multi_winding.windings)
    winding_data = []

    for winding_name in winding_order:
        if winding_name == "lv":
            winding_data.append(
                {
                    "name": "lv",
                    "windingType": multi_winding.lvWindingType,
                    "turnsPerPhase": safe_float(lv_results["lvTurnsPerPhase"], 0.0),
                    "phaseCurrent": safe_float(lv_results["lvCurrentPerPhase"], 0.0),
                    "loadLoss": safe_float(lv_results["lvLoadLoss"], 0.0),
                    "condIns": safe_float(lv_results["lvConductorInsulation"], 0.0),
                    "radialThickness": safe_float(lv_results["lvRadialThickness"], 0.0),
                    "innerDiameter": safe_float(lv_results["lvId"], 0.0),
                    "outerDiameter": safe_float(lv_results["lvOd"], 0.0),
                    "breadthInsulated": _safe_positive_number(lv_results["lvBreadthInsulated"], 0.1),
                    "breadth": safe_float(lv_results["lvBreadth"], 0.0),
                    "turnsPerLayer": _safe_positive_number(lv_results["lvTurnsPerLayer"], 1.0),
                    "axialParallel": max(1, int(round(safe_float(lv_results["lvAxialParallelConductors"], 1.0)))),
                    "windingLength": _safe_positive_number(lv_results["lvWindingLength"], 1.0),
                    "endClearance": safe_float(lv_results["lvEndClearance"], 0.0),
                    "gapFromPrevious": safe_float(lv_results["coreGap"], 0.0),
                    "ducts": max(0, int(round(safe_float(lv_results["lvNoOfDuct"], 0.0)))),
                    "ductSize": safe_float(lv_results["lvDuctThickness"], 0.0),
                    "transposition": 0,
                    "noOfCoils": 0,
                }
            )
            continue

        winding = getattr(multi_winding, WINDING_MODEL_ATTRS[winding_name], None)
        winding_type = getattr(multi_winding, WINDING_TYPE_ATTRS[winding_name], WINDING_TYPE_DEFAULTS[winding_name])
        dimensions = winding_dimensions.get(winding_name) or {}
        winding_data.append(
            {
                "name": winding_name,
                "windingType": winding_type,
                "turnsPerPhase": safe_float(getattr(winding, "turnsPerPhase", None), 0.0),
                "phaseCurrent": safe_float(getattr(winding, "phaseCurrent", None), 0.0),
                "loadLoss": safe_float(getattr(winding, "loadLoss", None), 0.0),
                "condIns": safe_float(getattr(winding, "condInsulation", None), 0.0),
                "radialThickness": safe_float(dimensions.get("radialThickness"), 0.0),
                "innerDiameter": safe_float(dimensions.get("innerDiameter"), 0.0),
                "outerDiameter": safe_float(dimensions.get("outerDiameter"), 0.0),
                "breadthInsulated": _estimate_breadth_insulated_from_model(winding),
                "breadth": safe_float(getattr(winding, "condBreadth", None), 0.0),
                "turnsPerLayer": _safe_positive_number(getattr(winding, "turnsPerLayer", None), 1.0),
                "axialParallel": max(1, int(round(safe_float(getattr(winding, "axialParallelCond", None), 1.0)))),
                "windingLength": _safe_positive_number(getattr(winding, "windingLength", None), 1.0),
                "endClearance": safe_float(getattr(winding, "endClearances", None), 0.0),
                "gapFromPrevious": safe_float(dimensions.get("gapFromPrevious"), 0.0),
                "ducts": max(0, int(round(safe_float(getattr(winding, "ducts", None), 0.0)))),
                "ductSize": safe_float(getattr(winding, "ductSize", None), 0.0),
                "transposition": max(0, int(round(safe_float(hv_results.get("hvTransposition", 0), 0.0)))) if winding_name == "hv" else 0,
                "noOfCoils": max(0, int(round(safe_float(hv_results.get("hvNoOfCoils", 0), 0.0)))) if winding_name == "hv" else 0,
            }
        )

    return winding_data


def _build_multi_impedance(multi_winding, lv_results, hv_results, coil_dimension_scale):
    winding_data = _build_impedance_winding_data(multi_winding, lv_results, hv_results, coil_dimension_scale)
    active_winding_data = [
        winding
        for winding in winding_data
        if safe_float(winding.get("turnsPerPhase"), 0.0) > 0
    ]
    radial_build = {
        item["name"]: item
        for item in coil_dimension_scale["radialBuild"]
    }
    frequency_factor = multi_winding.frequency / 50 if multi_winding.frequency != 50 else 1
    pair_breakdown = []
    total_ex = 0.0

    for previous_winding, current_winding in zip(active_winding_data, active_winding_data[1:]):
        current_dimensions = radial_build.get(current_winding["name"], {})
        gap_value = safe_float(current_dimensions.get("gapFromPrevious"), 0.0)
        h_previous = h1h2(
            previous_winding["radialThickness"],
            previous_winding["ducts"],
            previous_winding["ductSize"],
            previous_winding["condIns"],
        )
        h_current = h1h2(
            current_winding["radialThickness"],
            current_winding["ducts"],
            current_winding["ductSize"],
            current_winding["condIns"],
        )
        ampere_turn_value = ampere_turns(
            previous_winding["turnsPerPhase"],
            previous_winding["phaseCurrent"],
        )
        ls_values = ls(
            previous_winding["breadthInsulated"],
            current_winding["breadthInsulated"],
            previous_winding["turnsPerLayer"],
            current_winding["turnsPerLayer"],
            previous_winding["axialParallel"],
            current_winding["axialParallel"],
            current_winding["outerDiameter"],
            previous_winding["innerDiameter"],
            previous_winding["condIns"],
            current_winding["condIns"],
            previous_winding["windingLength"],
            current_winding["windingLength"],
            previous_winding["windingType"],
            current_winding["windingType"],
            previous_winding["transposition"],
            current_winding["transposition"],
            current_winding["noOfCoils"],
        )
        ls_value = _safe_positive_number(ls_values[0], 0.1)
        ex_values = ex(
            lv_results["revisedVoltsPerTurn"],
            gap_value,
            previous_winding["condIns"],
            current_winding["condIns"],
            h_previous,
            h_current,
            ampere_turn_value,
            ls_value,
            previous_winding["outerDiameter"],
            frequency_factor,
        )
        total_ex += safe_float(ex_values[3], 0.0)
        pair_breakdown.append(
            {
                "pair": f'{previous_winding["name"]}-{current_winding["name"]}',
                "innerWinding": previous_winding["name"],
                "outerWinding": current_winding["name"],
                "gap": gap_value,
                "h1": h_previous,
                "h2": h_current,
                "ampereTurns": ampere_turn_value,
                "ls": ls_values[0],
                "l": ls_values[1],
                "b": ls_values[2],
                "kR": ls_values[3],
                "delta": ex_values[0],
                "delta1": ex_values[1],
                "ds": ex_values[2],
                "ex": ex_values[3],
            }
        )

    total_load_loss = sum(winding["loadLoss"] for winding in active_winding_data)
    tank_loss_factor = _get_er_tank_loss_factor(multi_winding.lowVoltage, lv_results["lvCurrentPerPhase"])
    tank_loss_component = tank_loss_factor * multi_winding.kVA
    kva_base = max(multi_winding.kVA * math.pow(10, 3), 1)
    total_er = two_digit_decimal(((total_load_loss + tank_loss_component) / kva_base) * 100)
    total_ex = two_digit_decimal(total_ex)
    total_ek = ek(total_er, total_ex)
    primary_pair = pair_breakdown[0] if pair_breakdown else {
        "h1": 0.0,
        "h2": 0.0,
        "ls": 0.0,
        "l": 0.0,
        "b": 0.0,
        "kR": 0.0,
        "delta": 0.0,
        "delta1": 0.0,
        "ds": 0.0,
    }

    return {
        "h1": primary_pair["h1"],
        "h2": primary_pair["h2"],
        "ls": primary_pair["ls"],
        "l": primary_pair["l"],
        "b": primary_pair["b"],
        "kR": primary_pair["kR"],
        "delta": primary_pair["delta"],
        "delta1": primary_pair["delta1"],
        "ds": primary_pair["ds"],
        "ex": total_ex,
        "er": total_er,
        "ek": total_ek,
        "breakdown": {
            "activeWindingOrder": [winding["name"] for winding in active_winding_data],
            "pairs": pair_breakdown,
            "totals": {
                "loadLoss": two_digit_decimal(total_load_loss),
                "tankLossComponent": two_digit_decimal(tank_loss_component),
                "ex": total_ex,
                "er": total_er,
                "ek": total_ek,
            },
        },
    }


def _build_impedance_summary(multi_winding, lv_results, hv_results, coil_dimension_scale):
    pairwise_summary = _build_multi_impedance(multi_winding, lv_results, hv_results, coil_dimension_scale)
    if multi_winding.windings == DEFAULT_WINDING_SELECTION:
        pairwise_summary["breakdown"]["method"] = "pairwise"
        return pairwise_summary

    winding_data = _build_impedance_winding_data(multi_winding, lv_results, hv_results, coil_dimension_scale)
    return calculate_vb_multi_impedance(
        multi_winding,
        winding_data,
        lv_results,
        hv_results,
        pairwise_summary,
    )


def _apply_defaults(multi_winding):
    dry_type = bool(getattr(multi_winding, "dryType", False))
    dry_temp_class = getattr(multi_winding, "dryTempClass", CLASS_B)
    trans_cost_type = getattr(multi_winding, "transCostType", ECONOMIC)
    multi_winding.windings = _normalize_winding_selection(getattr(multi_winding, "windings", None))
    active_windings = WINDING_SELECTIONS.get(multi_winding.windings, WINDING_SELECTIONS[DEFAULT_WINDING_SELECTION])

    multi_winding.frequency = get_frequency(multi_winding.frequency)
    multi_winding.vectorGroup = get_vector_group(multi_winding.vectorGroup)
    multi_winding.lowVoltage = get_low_voltage(multi_winding.lowVoltage)
    multi_winding.highVoltage = get_high_voltage(multi_winding.highVoltage)
    multi_winding.fluxDensity = get_flux_density(multi_winding.fluxDensity, dry_type)
    multi_winding.lvConductorMaterial = (multi_winding.lvConductorMaterial or COPPER).upper()
    multi_winding.hvConductorMaterial = (multi_winding.hvConductorMaterial or COPPER).upper()
    multi_winding.corseConductorMaterial = (getattr(multi_winding, "corseConductorMaterial", None) or multi_winding.hvConductorMaterial).upper()
    multi_winding.fineConductorMaterial = (getattr(multi_winding, "fineConductorMaterial", None) or multi_winding.hvConductorMaterial).upper()
    multi_winding.outerConductorMaterial = (getattr(multi_winding, "outerConductorMaterial", None) or multi_winding.hvConductorMaterial).upper()
    multi_winding.kValue = get_k_value(
        multi_winding.kVA,
        multi_winding.kValue if multi_winding.kValue > 0 else None,
        multi_winding.lvConductorMaterial,
        trans_cost_type,
    )
    multi_winding.lvCurrentDensity = get_current_density(
        multi_winding.lvConductorMaterial,
        trans_cost_type,
        dry_type,
        dry_temp_class,
        True,
        multi_winding.lvCurrentDensity if multi_winding.lvCurrentDensity > 0 else None,
    )
    multi_winding.hvCurrentDensity = get_current_density(
        multi_winding.hvConductorMaterial,
        trans_cost_type,
        dry_type,
        dry_temp_class,
        False,
        multi_winding.hvCurrentDensity if multi_winding.hvCurrentDensity > 0 else None,
    )
    multi_winding.corseCurrentDensity = _resolve_optional_current_density(
        multi_winding,
        "corse",
        active_windings,
        trans_cost_type,
        dry_type,
        dry_temp_class,
    )
    multi_winding.fineCurrentDensity = _resolve_optional_current_density(
        multi_winding,
        "fine",
        active_windings,
        trans_cost_type,
        dry_type,
        dry_temp_class,
    )
    multi_winding.outerCurrentDensity = _resolve_optional_current_density(
        multi_winding,
        "outer",
        active_windings,
        trans_cost_type,
        dry_type,
        dry_temp_class,
    )
    multi_winding.buildFactor = get_build_factor(
        multi_winding.kVA,
        get_core_type(getattr(_default_core(multi_winding), "coreType", None)),
        getattr(multi_winding, "buildFactor", None),
    )
    _default_core(multi_winding).coreMaterial = get_core_material(getattr(_default_core(multi_winding), "coreMaterial", None))
    for winding_name, attr_name in WINDING_TYPE_ATTRS.items():
        setattr(
            multi_winding,
            attr_name,
            _normalize_winding_type_value(winding_name, getattr(multi_winding, attr_name, None)),
        )
    multi_winding.limitEz = get_limit_ez(multi_winding.kVA, getattr(multi_winding, "limitEz", None))
    _default_coil_dimensions(multi_winding)
    _configure_winding_models(multi_winding, multi_winding.windings)
    return multi_winding


def _parallel_label(radial_parallel, axial_parallel, total_conductors):
    return f"Rad {radial_parallel} X Axi {axial_parallel} = {total_conductors}"


def _conductor_size_label(breadth, height, is_round):
    if is_round:
        return f"Round {breadth}"
    return f"{breadth} L X {height} B"


def _apply_lv_results_to_model(winding, lv_results, winding_type):
    winding.turnsPerPhase = lv_results["lvTurnsPerPhase"]
    winding.terminal = lv_results["lvVoltsPerPhase"]
    winding.phaseCurrent = lv_results["lvCurrentPerPhase"]
    winding.currentDensity = lv_results["lVRevisedCurrentDensity"]
    winding.condCrossSec = lv_results["lvTotalCondCrossSection"]
    winding.conductorSizes = _conductor_size_label(
        lv_results["lvBreadth"],
        lv_results["lvHeight"],
        lv_results["lvIsConductorRound"],
    )
    winding.condInsulation = lv_results["lvConductorInsulation"]
    winding.noInParallel = _parallel_label(
        lv_results["lvRadialParallelConductors"],
        lv_results["lvAxialParallelConductors"],
        lv_results["lvNumberOfConductors"],
    )
    winding.windingLength = lv_results["lvWindingLength"]
    winding.noOfLayers = lv_results["lvNumberOfLayers"]
    winding.turnsPerLayer = lv_results["lvTurnsPerLayer"]
    winding.endClearances = lv_results["lvEndClearance"]
    winding.eddyStrayLoss = lv_results["%lvStrayLoss"]
    winding.tempGradDegC = lv_results["lvGradient"]
    winding.ducts = lv_results["lvNoOfDuct"]
    winding.ductSize = lv_results["lvDuctThickness"]
    winding.insulatedWeight = lv_results["lvInsulatedWeight"]
    winding.bareWeight = lv_results["lvBareWeight"]
    winding.loadLoss = lv_results["lvLoadLoss"]
    winding.interLayerInsulation = lv_results["lvInterLayerInsulation"]
    winding.noOfDuctsWidth = f'{lv_results["lvNoOfDuct"]} / {lv_results["lvDuctThickness"]}'
    if winding_type == "DISC":
        winding.turnsLayers = str(lv_results.get("lvDiscArrangement", ""))
    else:
        winding.turnsLayers = str(lv_results["lvTurnsPerLayer"])
    winding.weightBareInsulated = f'{lv_results["lvBareWeight"]} / {lv_results["lvInsulatedWeight"]}'
    winding.radialParallelCond = lv_results["lvRadialParallelConductors"]
    winding.axialParallelCond = lv_results["lvAxialParallelConductors"]
    winding.condBreadth = lv_results["lvBreadth"]
    winding.condHeight = lv_results["lvHeight"]
    winding.conductorDiameter = lv_results["lvBreadth"]
    winding.isConductorRound = lv_results["lvIsConductorRound"]
    winding.isEnamel = lv_results["lvIsEnamel"]


def _apply_hv_results_to_model(winding, hv_results, winding_type):
    winding.turnsPerPhase = hv_results["hvTurnsPerPhase"]
    winding.terminal = hv_results["hvVoltsPerPhase"]
    winding.phaseCurrent = hv_results["hvCurrentPerPhase"]
    winding.currentDensity = hv_results["hVRevisedCurrDenAtNormal"]
    winding.condCrossSec = hv_results["hvTotalCondCrossSection"]
    winding.conductorSizes = _conductor_size_label(
        hv_results["hvBreadth"],
        hv_results["hvHeight"],
        hv_results["hvIsConductorRound"],
    )
    winding.condInsulation = hv_results["hvConductorInsulation"]
    winding.noInParallel = _parallel_label(
        hv_results["hvRadialParallelConductors"],
        hv_results["hvAxialParallelConductors"],
        hv_results["hvNoOfConductors"],
    )
    winding.windingLength = hv_results["hvWindingLength"]
    winding.noOfLayers = hv_results["hvNumberOfLayers"]
    winding.turnsPerLayer = hv_results["hvTurnsPerLayer"]
    winding.endClearances = hv_results["hvEndClearance"]
    winding.eddyStrayLoss = hv_results["%hvStrayLoss"]
    winding.tempGradDegC = hv_results["hvGradient"]
    winding.ducts = hv_results["hvNoOfDuct"]
    winding.ductSize = hv_results["hvDuctThickness"]
    winding.insulatedWeight = hv_results["hvInsulatedWeight"]
    winding.bareWeight = hv_results["hvBareWeight"]
    winding.loadLoss = hv_results["hvLoadLossAtNormal"]
    winding.interLayerInsulation = hv_results["hvInterLayerInsulation"]
    winding.noOfDuctsWidth = f'{hv_results["hvNoOfDuct"]} / {hv_results["hvDuctThickness"]}'
    if winding_type in {"DISC", "DOUBLE_DISC"}:
        winding.turnsLayers = str(hv_results.get("hvDiscArrangement", ""))
    elif winding_type == "XOVER":
        winding.turnsLayers = str(hv_results.get("hvXOverTurnsLayers", ""))
    else:
        winding.turnsLayers = str(hv_results["hvTurnsPerLayer"])
    winding.weightBareInsulated = f'{hv_results["hvBareWeight"]} / {hv_results["hvInsulatedWeight"]}'
    winding.radialParallelCond = hv_results["hvRadialParallelConductors"]
    winding.axialParallelCond = hv_results["hvAxialParallelConductors"]
    winding.condBreadth = hv_results["hvBreadth"]
    winding.condHeight = hv_results["hvHeight"]
    winding.conductorDiameter = hv_results["hvBreadth"]
    winding.isConductorRound = hv_results["hvIsConductorRound"]
    winding.isEnamel = hv_results["hvIsEnamel"]


def _apply_section_results_to_model(winding, section_results):
    if winding is None or not section_results:
        return

    winding.turnsPerPhase = section_results.get("turnsPerPhase")
    winding.terminal = section_results.get("voltsPerPhase", 0.0)
    winding.phaseCurrent = section_results.get("phaseCurrent")
    winding.currentDensity = section_results.get("currentDensity")
    winding.condCrossSec = section_results.get("condCrossSec")
    winding.windingLength = section_results.get("windingLength", winding.windingLength)
    winding.noOfLayers = section_results.get("noOfLayers")
    winding.turnsPerLayer = section_results.get("turnsPerLayer", 0.0)
    winding.endClearances = section_results.get("endClearance", winding.endClearances)
    winding.condInsulation = section_results.get("conductorInsulation")
    winding.interLayerInsulation = section_results.get("interLayerInsulation")
    winding.ducts = section_results.get("ducts")
    winding.ductSize = section_results.get("ductSize")
    winding.radialParallelCond = section_results.get("radialParallelCond")
    winding.axialParallelCond = section_results.get("axialParallelCond")
    winding.condBreadth = section_results.get("breadth")
    winding.condHeight = section_results.get("height")
    winding.conductorDiameter = section_results.get("breadth")
    winding.isConductorRound = section_results.get("isConductorRound")
    winding.isEnamel = section_results.get("isEnamel")
    winding.insulatedWeight = section_results.get("insulatedWeight", 0.0)
    winding.bareWeight = section_results.get("bareWeight", 0.0)
    winding.loadLoss = section_results.get("loadLoss", 0.0)
    winding.eddyStrayLoss = section_results.get("strayLoss", 0.0)
    winding.tempGradDegC = section_results.get("gradient", 0.0)
    winding.noOfDuctsWidth = f'{section_results.get("ducts", 0)} / {section_results.get("ductSize", 0)}'
    winding.noInParallel = _parallel_label(
        section_results.get("radialParallelCond"),
        section_results.get("axialParallelCond"),
        section_results.get("noOfConductors", 0),
    )
    winding.turnsLayers = (
        str(section_results.get("discArrangement", ""))
        if section_results.get("windingType") == "DISC"
        else str(section_results.get("turnsPerLayer", 0.0))
    )
    winding.conductorSizes = _conductor_size_label(
        section_results.get("breadth", 0.0),
        section_results.get("height", 0.0),
        section_results.get("isConductorRound", False),
    )
    winding.weightBareInsulated = f'{section_results.get("bareWeight", 0.0)} / {section_results.get("insulatedWeight", 0.0)}'


def _build_phase_voltage_division(section_allocations):
    return {
        "lv": _vb_int((section_allocations.get("lv") or {}).get("voltsPerPhase", 0.0)),
        "hvMain": _vb_int((section_allocations.get("hv") or {}).get("voltsPerPhase", 0.0)),
        "corse": _vb_int((section_allocations.get("corse") or {}).get("voltsPerPhase", 0.0)),
        "fine": _vb_int((section_allocations.get("fine") or {}).get("voltsPerPhase", 0.0)),
        "outer": _vb_int((section_allocations.get("outer") or {}).get("voltsPerPhase", 0.0)),
    }


def _build_post_hv_filling_gaps(corse_results, fine_results, outer_results):
    return {
        "corse": safe_float((corse_results or {}).get("fillingGap"), 0.0),
        "fine": safe_float((fine_results or {}).get("fillingGap"), 0.0),
        "outer": safe_float((outer_results or {}).get("fillingGap"), 0.0),
    }


def _build_calculated_radial_gaps(radial_build):
    return {
        item["gapField"]: safe_float(item.get("gapFromPrevious"), 0.0)
        for item in radial_build
        if item.get("gapField")
    }


def _winding_type_name(multi_winding, winding_name):
    attr_name = WINDING_TYPE_ATTRS[winding_name]
    return getattr(multi_winding, attr_name, WINDING_TYPE_DEFAULTS[winding_name])


def _gap_insulation_label(multi_winding, inner_winding, outer_winding, gap_value):
    inner_type = _winding_type_name(multi_winding, inner_winding)
    outer_type = _winding_type_name(multi_winding, outer_winding)
    if inner_winding == "lv":
        return get_lv_hv_ins(inner_type, outer_type, gap_value)
    return get_hv_hv_ins(inner_type, outer_type, gap_value)


def _build_insulation_payload(multi_winding, coil_dimensions):
    outermost_winding_name = coil_dimensions.outermostWinding or "hv"
    outermost_winding_type = _winding_type_name(multi_winding, outermost_winding_name)
    insulation = {
        "coreLv": get_core_lv_ins(multi_winding.lvWindingType, coil_dimensions.coreGap or 0),
        "lvHv": get_lv_hv_ins(
            multi_winding.lvWindingType,
            multi_winding.hvWindingType,
            coil_dimensions.lVHVGap or 0,
        ),
        "coilCoil": get_hv_hv_ins(
            outermost_winding_type,
            outermost_winding_type,
            coil_dimensions.coilCoilGap or coil_dimensions.hVHVGap or 0,
        ),
    }

    winding_dimensions = {
        "corse": {
            "gap": coil_dimensions.corseGap,
        },
        "fine": {
            "gap": coil_dimensions.fineGap,
        },
        "outer": {
            "gap": coil_dimensions.outerGap,
        },
    }

    for gap_layout in _get_gap_layout(multi_winding.windings):
        winding_name = gap_layout["winding"]
        gap_field = gap_layout["gapField"]
        gap_value = (winding_dimensions.get(winding_name) or {}).get("gap")
        insulation[gap_field] = _gap_insulation_label(
            multi_winding,
            gap_layout["inner"],
            gap_layout["outer"],
            gap_value or 0,
        )

    return insulation


def _build_test_voltage_entry(voltage):
    test_voltage, impulse_voltage = get_test_and_imp_test(safe_float(voltage, 0.0))
    return {
        "test": test_voltage,
        "impulse": impulse_voltage,
    }


def _build_test_voltages_payload(
    multi_winding,
    corse_winding_model,
    fine_winding_model,
    outer_winding_model,
):
    return {
        "lv": _build_test_voltage_entry(multi_winding.lowVoltage),
        "hv": _build_test_voltage_entry(multi_winding.highVoltage),
    }


# def _build_multi_winding_kw55(load_losses, gradients, core_loss, tank_loss):
#     return get_kw55_for_multiple_windings(core_loss, load_losses, tank_loss, gradients)


def _collect_multi_winding_thermal_inputs(
    lv_results,
    hv_winding_model,
    corse_winding_model,
    fine_winding_model,
    outer_winding_model,
):
    load_losses = [safe_float(lv_results.get("lvLoadLoss"), 0.0)]
    gradients = [safe_float(lv_results.get("lvGradient"), 0.0)]

    for winding_model in (hv_winding_model, corse_winding_model, fine_winding_model, outer_winding_model):
        if winding_model is None:
            continue
        load_losses.append(safe_float(getattr(winding_model, "loadLoss", None), 0.0))
        gradients.append(safe_float(getattr(winding_model, "tempGradDegC", None), 0.0))

    return load_losses, gradients


def _with_named_volts_per_phase(payload, voltage_field_name, voltage_value):
    normalized_payload = dict(payload)
    normalized_payload["voltsPerPhase"] = voltage_value
    if voltage_field_name not in normalized_payload:
        normalized_payload[voltage_field_name] = voltage_value
    return normalized_payload


def _build_impedance_response(impedance_summary):
    response = {
        "h1": impedance_summary.get("h1", 0.0),
        "h2": impedance_summary.get("h2", 0.0),
        "ls": impedance_summary.get("ls", 0.0),
        "l": impedance_summary.get("l", 0.0),
        "b": impedance_summary.get("b", 0.0),
        "kR": impedance_summary.get("kR", 0.0),
        "delta": impedance_summary.get("delta", 0.0),
        "delta1": impedance_summary.get("delta1", 0.0),
        "ds": impedance_summary.get("ds", 0.0),
        "ex": impedance_summary.get("ex", 0.0),
        "er": impedance_summary.get("er", 0.0),
        "ek": impedance_summary.get("ek", 0.0),
    }
    tap_conditions = (
        impedance_summary.get("breakdown", {}).get("tapConditions", {})
        if isinstance(impedance_summary.get("breakdown"), dict)
        else {}
    )
    if tap_conditions:
        response["lowestTap"] = tap_conditions.get("lowest", {})
        response["normalTap"] = tap_conditions.get("normal", {})
        response["highestTap"] = tap_conditions.get("highest", {})
    return response


def calculate_circ_wdg(
    multi_winding,
    _impedance_iteration=0,
    _impedance_inputs=None,
    _last_valid_limb_height=None,
    _finalize_impedance=False,
):
    multi_winding = _apply_defaults(multi_winding)
    if _impedance_inputs is None:
        _impedance_inputs = _snapshot_impedance_inputs(multi_winding)
    core = _default_core(multi_winding)
    coil_dimensions = _default_coil_dimensions(multi_winding)
    active_windings = set(_get_active_windings(multi_winding.windings))
    lv_winding_model = _default_winding(multi_winding, "lvWindings")
    hv_winding_model = _default_winding(multi_winding, "hvWindings")
    corse_winding_model = _default_winding(multi_winding, "corseWindings") if "corse" in active_windings else None
    fine_winding_model = _default_winding(multi_winding, "fineWindings") if "fine" in active_windings else None
    outer_winding_model = _default_winding(multi_winding, "outerWindings") if "outer" in active_windings else None

    lv_results = calculate_lv_windings(multi_winding)
    raw_hv_results = calculate_hv_windings(multi_winding, lv_results)
    effective_limb_height = get_effective_limb_height(
        lv_results["windowHeight"],
        raw_hv_results["hvWindingLength"],
        raw_hv_results["hvEndClearance"],
        lv_results["permaWoodRing"],
    )
    high_side_distribution = _get_high_side_distribution(multi_winding, lv_results, raw_hv_results)
    hv_results = _build_hv_main_results(
        multi_winding,
        lv_results,
        raw_hv_results,
        high_side_distribution.get("hv", _build_section_allocation(
            turns=safe_float(raw_hv_results.get("hvTurnsPerPhase"), 0.0),
            volts_per_phase=safe_float(raw_hv_results.get("hvVoltsPerPhase"), 0.0),
        )),
    )
    finalized_hv_source = (
        raw_hv_results
        if multi_winding.windings == DEFAULT_WINDING_SELECTION
        else _build_finalized_hv_source(raw_hv_results, hv_results)
    )
    hv_results_for_calc = raw_hv_results if multi_winding.windings == DEFAULT_WINDING_SELECTION else hv_results
    hv_main_geometry = build_geometry_snapshot(
        "hv",
        hv_results_for_calc["hvId"] if "hvId" in hv_results_for_calc else hv_results_for_calc["innerDiameter"],
        hv_results_for_calc["hvRadialThickness"] if "hvRadialThickness" in hv_results_for_calc else hv_results_for_calc["radialThickness"],
        hv_results_for_calc["hvOd"] if "hvOd" in hv_results_for_calc else hv_results_for_calc["outerDiameter"],
        hv_results_for_calc["hvWindingLength"] if "hvWindingLength" in hv_results_for_calc else hv_results_for_calc["windingLength"],
        "calculated",
        end_clearance=hv_results_for_calc["hvEndClearance"] if "hvEndClearance" in hv_results_for_calc else hv_results_for_calc["endClearance"],
    )
    extra_winding_results = _build_extra_winding_results(
        multi_winding,
        multi_winding.windings,
        finalized_hv_source,
        high_side_distribution,
        hv_main_geometry,
        lv_results,
        limb_height=effective_limb_height,
        perma_wood_ring=safe_float(lv_results["permaWoodRing"], 0.0),
    )
    corse_results = extra_winding_results["corse"] if "corse" in active_windings else None
    fine_results = extra_winding_results["fine"] if "fine" in active_windings else None
    outer_results = extra_winding_results["outer"] if "outer" in active_windings else None
    _apply_lv_results_to_model(lv_winding_model, lv_results, multi_winding.lvWindingType)
    if multi_winding.windings == DEFAULT_WINDING_SELECTION:
        _apply_hv_results_to_model(hv_winding_model, raw_hv_results, multi_winding.hvWindingType)
    else:
        _apply_section_results_to_model(hv_winding_model, hv_results)
    _apply_section_results_to_model(corse_winding_model, corse_results)
    _apply_section_results_to_model(fine_winding_model, fine_results)
    _apply_section_results_to_model(outer_winding_model, outer_results)

    ampere_turn_value = ampere_turns(lv_results["lvTurnsPerPhase"], lv_results["lvCurrentPerPhase"])
    h1 = h1h2(
        lv_results["lvRadialThickness"],
        lv_results["lvNoOfDuct"],
        lv_results["lvDuctThickness"],
        lv_results["lvConductorInsulation"],
    )
    h2 = h1h2(
        hv_results_for_calc["radialThickness"] if "radialThickness" in hv_results_for_calc else hv_results_for_calc["hvRadialThickness"],
        hv_results_for_calc["ducts"] if "ducts" in hv_results_for_calc else hv_results_for_calc["hvNoOfDuct"],
        hv_results_for_calc["ductSize"] if "ductSize" in hv_results_for_calc else hv_results_for_calc["hvDuctThickness"],
        hv_results_for_calc["conductorInsulation"] if "conductorInsulation" in hv_results_for_calc else hv_results_for_calc["hvConductorInsulation"],
    )
    ls_values = ls(
        lv_results["lvBreadthInsulated"],
        hv_results_for_calc["breadthInsulated"] if "breadthInsulated" in hv_results_for_calc else hv_results_for_calc["hvBreadthInsulated"],
        lv_results["lvTurnsPerLayer"],
        hv_results_for_calc["turnsPerLayer"] if "turnsPerLayer" in hv_results_for_calc else hv_results_for_calc["hvTurnsPerLayer"],
        lv_results["lvAxialParallelConductors"],
        hv_results_for_calc["axialParallelCond"] if "axialParallelCond" in hv_results_for_calc else hv_results_for_calc["hvAxialParallelConductors"],
        hv_results_for_calc["outerDiameter"] if "outerDiameter" in hv_results_for_calc else hv_results_for_calc["hvOd"],
        lv_results["lvId"],
        lv_results["lvConductorInsulation"],
        hv_results_for_calc["conductorInsulation"] if "conductorInsulation" in hv_results_for_calc else hv_results_for_calc["hvConductorInsulation"],
        lv_results["lvWindingLength"],
        hv_results_for_calc["windingLength"] if "windingLength" in hv_results_for_calc else hv_results_for_calc["hvWindingLength"],
        multi_winding.lvWindingType,
        multi_winding.hvWindingType,
        0,
        raw_hv_results["hvTransposition"] if "hvTransposition" in raw_hv_results else 0,
        raw_hv_results["hvNoOfCoils"] if "hvNoOfCoils" in raw_hv_results else 0,
    )
    coil_dimension_scale = _build_coil_dimension_scale(
        multi_winding.windings,
        lv_results,
        hv_results_for_calc,
        extra_winding_results,
        effective_limb_height,
    )
    impedance_summary = _build_impedance_summary(
        multi_winding,
        lv_results,
        hv_results_for_calc,
        coil_dimension_scale,
    )
    er_value = impedance_summary["er"]
    ek_value = impedance_summary["ek"]

    coil_dimensions.coreDia = lv_results["coreDiameter"]
    coil_dimensions.coreGap = lv_results["coreGap"]
    coil_dimensions.lVID = lv_results["lvId"]
    coil_dimensions.lVRadial = lv_results["lvRadialThickness"]
    coil_dimensions.lVOD = lv_results["lvOd"]
    coil_dimensions.lVHVGap = raw_hv_results["lvHvGap"]
    coil_dimensions.hVID = hv_results_for_calc["innerDiameter"] if "innerDiameter" in hv_results_for_calc else raw_hv_results["hvId"]
    coil_dimensions.hVRadial = hv_results_for_calc["radialThickness"] if "radialThickness" in hv_results_for_calc else raw_hv_results["hvRadialThickness"]
    coil_dimensions.hVOD = hv_results_for_calc["outerDiameter"] if "outerDiameter" in hv_results_for_calc else raw_hv_results["hvOd"]
    coil_dimensions.hVHVGap = raw_hv_results["hvHvGap"]
    coil_dimensions.coilCoilGap = raw_hv_results["hvHvGap"]
    coil_dimensions.corseID = (coil_dimension_scale["windingDimensions"]["corse"] or {}).get("innerDiameter")
    coil_dimensions.corseRadial = (coil_dimension_scale["windingDimensions"]["corse"] or {}).get("radialThickness")
    coil_dimensions.corseOD = (coil_dimension_scale["windingDimensions"]["corse"] or {}).get("outerDiameter")
    coil_dimensions.corseGap = (coil_dimension_scale["windingDimensions"]["corse"] or {}).get("gapFromPrevious")
    coil_dimensions.fineID = (coil_dimension_scale["windingDimensions"]["fine"] or {}).get("innerDiameter")
    coil_dimensions.fineRadial = (coil_dimension_scale["windingDimensions"]["fine"] or {}).get("radialThickness")
    coil_dimensions.fineOD = (coil_dimension_scale["windingDimensions"]["fine"] or {}).get("outerDiameter")
    coil_dimensions.fineGap = (coil_dimension_scale["windingDimensions"]["fine"] or {}).get("gapFromPrevious")
    coil_dimensions.outerID = (coil_dimension_scale["windingDimensions"]["outer"] or {}).get("innerDiameter")
    coil_dimensions.outerRadial = (coil_dimension_scale["windingDimensions"]["outer"] or {}).get("radialThickness")
    coil_dimensions.outerOD = (coil_dimension_scale["windingDimensions"]["outer"] or {}).get("outerDiameter")
    coil_dimensions.outerGap = (coil_dimension_scale["windingDimensions"]["outer"] or {}).get("gapFromPrevious")
    coil_dimensions.centerDistance = coil_dimension_scale["centerDistance"]
    coil_dimensions.outermostOD = coil_dimension_scale["outermostOD"]
    coil_dimensions.outermostWinding = coil_dimension_scale["outermostWinding"]
    coil_dimensions.activePartSize = coil_dimension_scale["activePartSize"]

    core.coreDia = lv_results["coreDiameter"]
    core.limbHt = effective_limb_height
    core.area = lv_results["netArea"]
    core.cenDist = coil_dimension_scale["centerDistance"]
    core.fluxDensity = lv_results["revisedFluxDensity"]
    core.wKgGrade = get_specific_loss(
        core.coreMaterial,
        multi_winding.fluxDensity,
        multi_winding.frequency,
        getattr(core, "wKgGrade", None),
    )
    recomputed_center_distance = get_center_distance(coil_dimension_scale["outermostOD"], raw_hv_results["hvHvGap"])
    recomputed_core_length = get_core_length(lv_results["coreDiameter"], effective_limb_height, recomputed_center_distance)
    recomputed_core_weight = get_core_weight(recomputed_core_length, lv_results["netArea"])
    recomputed_core_loss = get_core_loss(
        recomputed_core_weight,
        getattr(multi_winding, "buildFactor", 1.25),
        core.wKgGrade,
    )
    recomputed_tank_loss = get_tank_loss(
        multi_winding.kVA,
        lv_results["lvCurrentPerPhase"],
        multi_winding.lowVoltage,
        getattr(multi_winding, "tankLoss", None),
        bool(getattr(multi_winding, "dryType", False)),
    )
    core.coreWeight = recomputed_core_weight
    core.coreType = get_core_type(core.coreType)

    inputs = build_winding_formula_context(multi_winding)
    inputs["core"] = core
    inputs["coilDimensions"] = coil_dimensions
    inputs["windingTypes"] = _build_winding_type_payload(multi_winding)
    inputs["tank"] = {
        "tankLoss": getattr(multi_winding, "tankLoss", None),
        "wdgToTankGap": getattr(multi_winding, "wdgToTankGap", None),
        "connectionGap": getattr(multi_winding, "connectionGap", None),
        "topYokeToCoverGap": getattr(multi_winding, "topYokeToCoverGap", None),
    }
    inputs["cost"] = {
        "copperCostPerKg": getattr(multi_winding, "copperCostPerKg", None),
        "aluminiumCostPerKg": getattr(multi_winding, "aluminiumCostPerKg", None),
        "coreCostPerKg": getattr(multi_winding, "coreCostPerKg", None),
        "steelCostPerKg": getattr(multi_winding, "steelCostPerKg", None),
        "oilCostPerKg": getattr(multi_winding, "oilCostPerKg", None),
        "insulationCostPerKg": getattr(multi_winding, "insulationCostPerKg", None),
        "radiatorCostPerKg": getattr(multi_winding, "radiatorCostPerKg", None),
    }

    common = {
        "frequency": multi_winding.frequency,
        "buildFactor": multi_winding.buildFactor,
        "fluxDensity": multi_winding.fluxDensity,
        "coreMaterial": core.coreMaterial,
        "wKgGrade": core.wKgGrade,
        "lowVoltage": multi_winding.lowVoltage,
        "highVoltage": multi_winding.highVoltage,
        "vectorGroup": multi_winding.vectorGroup,
        "kValue": multi_winding.kValue,
        "lVCurrentDensity": multi_winding.lvCurrentDensity,
        "hVCurrentDensity": multi_winding.hvCurrentDensity,
        "ampereTurns": ampere_turn_value,
        "h1": impedance_summary["h1"],
        "h2": impedance_summary["h2"],
        "ls": impedance_summary["ls"],
        "l": impedance_summary["l"],
        "b": impedance_summary["b"],
        "kR": impedance_summary["kR"],
        "delta": impedance_summary["delta"],
        "delta1": impedance_summary["delta1"],
        "ds": impedance_summary["ds"],
        "ex": impedance_summary["ex"],
        "er": er_value,
        "ek": ek_value,
    }

    losses_at_50 = get_loss_at_50_percent(
        recomputed_core_loss,
        recomputed_tank_loss,
        lv_results["lvLoadLoss"],
        hv_winding_model.loadLoss,
    )
    losses_at_100 = get_loss_at_100_percent(
        recomputed_core_loss,
        recomputed_tank_loss,
        lv_results["lvLoadLoss"],
        hv_winding_model.loadLoss,
    )
    total_high_side_load_loss = sum(
        safe_float(getattr(winding_model, "loadLoss", 0.0), 0.0)
        for winding_model in [hv_winding_model, corse_winding_model, fine_winding_model, outer_winding_model]
        if winding_model is not None
    )
    total_load_loss = next_integer(lv_results["lvLoadLoss"] + total_high_side_load_loss + recomputed_tank_loss)
    phase_voltage_division = _build_phase_voltage_division(high_side_distribution)
    calculated_radial_gaps = _build_calculated_radial_gaps(coil_dimension_scale["radialBuild"])
    filling_gaps = _build_post_hv_filling_gaps(corse_results, fine_results, outer_results)
    impedance_response = _build_impedance_response(impedance_summary)
    lv_winding_response = _with_named_volts_per_phase(
        lv_results,
        "lvVoltsPerPhase",
        lv_results["lvVoltsPerPhase"],
    )
    hv_winding_response = _with_named_volts_per_phase(
        hv_results_for_calc,
        "hvVoltsPerPhase",
        hv_results_for_calc["hvVoltsPerPhase"] if "hvVoltsPerPhase" in hv_results_for_calc else raw_hv_results["hvVoltsPerPhase"],
    )
    try:
        tank_and_oil = calculate_tank_and_oil(
            multi_winding,
            lv_results,
            raw_hv_results,
            hv_results_for_calc,
            corse_results,
            fine_results,
            outer_results,
            core,
            coil_dimensions,
            recomputed_core_loss,
            recomputed_tank_loss,
            high_side_distribution,
        )
    except ValueError as error:
        if _last_valid_limb_height is None or "Invalid KW55 thermal state" not in str(error):
            raise
        _restore_impedance_inputs(multi_winding, _impedance_inputs)
        _default_core(multi_winding).limbHt = _last_valid_limb_height
        return calculate_circ_wdg(
            multi_winding,
            _impedance_iteration=_impedance_iteration,
            _impedance_inputs=_impedance_inputs,
            _last_valid_limb_height=None,
            _finalize_impedance=True,
        )
    kw55 = safe_float(tank_and_oil.get("kw55"), 0.0)
    raw_hv_results["kW55"] = kw55
    hv_results["kW55"] = kw55
    raw_hv_results["coreLength"] = recomputed_core_length
    raw_hv_results["coreWeight"] = recomputed_core_weight
    raw_hv_results["coreLoss"] = recomputed_core_loss
    raw_hv_results["activePartSize"] = coil_dimensions.activePartSize
    hv_results["coreLength"] = recomputed_core_length
    hv_results["coreWeight"] = recomputed_core_weight
    hv_results["coreLoss"] = recomputed_core_loss
    hv_results["activePartSize"] = coil_dimensions.activePartSize
    hv_winding_response["coreLength"] = recomputed_core_length
    hv_winding_response["coreWeight"] = recomputed_core_weight
    hv_winding_response["tankLoss"] = tank_and_oil["tankLoss"]
    hv_winding_response["totalLoadLoss"] = total_load_loss
    hv_winding_response["kW55"] = kw55
    hv_winding_response["coreLoss"] = recomputed_core_loss
    hv_winding_response["activePartSize"] = coil_dimensions.activePartSize
    common["kW55"] = kw55

    ez_within_range = is_ez_within_range(
        multi_winding.limitEz,
        ek_value,
        20 if multi_winding.kVA <= 10 else 5,
    )
    can_retry_impedance = (
        not _finalize_impedance
        and not ez_within_range
        and not _has_impedance_locked_input(_impedance_inputs)
        and _impedance_iteration + 1 < IMPEDANCE_MAX_ITERATIONS
    )
    if can_retry_impedance:
        revised_limb_height = get_modified_limb_ht_for_impedance(
            ek_value,
            multi_winding.limitEz,
            effective_limb_height,
            multi_winding.kVA,
        )
        _restore_impedance_inputs(multi_winding, _impedance_inputs)
        _default_core(multi_winding).limbHt = revised_limb_height
        return calculate_circ_wdg(
            multi_winding,
            _impedance_iteration=_impedance_iteration + 1,
            _impedance_inputs=_impedance_inputs,
            _last_valid_limb_height=effective_limb_height,
        )

    return {
        "selectedCode": WINDING_SELECTION_CODES[multi_winding.windings],
        "inputs": inputs,
        "results": {
            "voltsPerTurn": multi_winding.kValue and round(multi_winding.kValue * (multi_winding.kVA ** 0.5), 3) or None,
            "revisedVoltsPerTurn": lv_results["revisedVoltsPerTurn"],
            "lvVoltsPerPhase": lv_results["lvVoltsPerPhase"],
            "hvVoltsPerPhase": raw_hv_results["hvVoltsPerPhase"],
            "lvTurnsPerPhase": lv_results["lvTurnsPerPhase"],
            "hvTurnsPerPhase": hv_winding_model.turnsPerPhase,
            "lvCurrentPerPhase": lv_results["lvCurrentPerPhase"],
            "hvCurrentPerPhase": hv_winding_model.phaseCurrent,
            "lvEndClearance": lv_results["lvEndClearance"],
            "hvEndClearance": hv_winding_model.endClearances,
            "coreLoss": recomputed_core_loss,
            "phaseVoltages": phase_voltage_division,
            "phaseVoltageDivision": phase_voltage_division,
            "calculatedRadialGaps": calculated_radial_gaps,
            "fillingGaps": filling_gaps,
            "lvWinding": lv_winding_response,
            "hvWinding": hv_winding_response,
            "corseWinding": corse_results,
            "fineWinding": fine_results,
            "outerWinding": outer_results,
            "windingTypes": _build_winding_type_payload(multi_winding),
            "kW55": kw55,
            "common": common,
            "core": {
                "coreDia": core.coreDia,
                "limbHt": core.limbHt,
                "area": core.area,
                "cenDist": core.cenDist,
                "fluxDensity": core.fluxDensity,
                "wKgGrade": core.wKgGrade,
                "coreWeight": core.coreWeight,
                "coreLoss": recomputed_core_loss,
                "coreType": core.coreType,
                "coreMaterial": core.coreMaterial,
            },
            "coilDimensions": {
                "coreDia": coil_dimensions.coreDia,
                "coreGap": coil_dimensions.coreGap,
                "lVID": coil_dimensions.lVID,
                "lVRadial": coil_dimensions.lVRadial,
                "lVOD": coil_dimensions.lVOD,
                "lVHVGap": coil_dimensions.lVHVGap,
                "hVID": coil_dimensions.hVID,
                "hVRadial": coil_dimensions.hVRadial,
                "hVOD": coil_dimensions.hVOD,
                "coilCoilGap": coil_dimensions.coilCoilGap,
                "hVHVGap": coil_dimensions.hVHVGap,
                "corseID": coil_dimensions.corseID,
                "corseRadial": coil_dimensions.corseRadial,
                "corseOD": coil_dimensions.corseOD,
                "corseGap": coil_dimensions.corseGap,
                "fineID": coil_dimensions.fineID,
                "fineRadial": coil_dimensions.fineRadial,
                "fineOD": coil_dimensions.fineOD,
                "fineGap": coil_dimensions.fineGap,
                "outerID": coil_dimensions.outerID,
                "outerRadial": coil_dimensions.outerRadial,
                "outerOD": coil_dimensions.outerOD,
                "outerGap": coil_dimensions.outerGap,
                "activePartSize": coil_dimensions.activePartSize,
                "outermostWinding": coil_dimensions.outermostWinding,
                "outermostOD": coil_dimensions.outermostOD,
                "centerDistance": coil_dimensions.centerDistance,
                "windingDimensions": coil_dimension_scale["windingDimensions"],
                "radialBuild": coil_dimension_scale["radialBuild"],
            },
            "impedance": impedance_response,
            "ez": {
                "value": ek_value,
                "limit": multi_winding.limitEz,
                "withinRange": ez_within_range,
                "iterations": _impedance_iteration + 1,
            },
            "efficiencyAndVr": {
                "efficiencyAtUnity100": get_efficiency_percentage(multi_winding.kVA, total_load_loss, recomputed_core_loss, 1.0, 1.0),
                "efficiencyAtUnity75": get_efficiency_percentage(multi_winding.kVA, total_load_loss, recomputed_core_loss, 0.75, 1.0),
                "efficiencyAtUnity50": get_efficiency_percentage(multi_winding.kVA, total_load_loss, recomputed_core_loss, 0.5, 1.0),
                "voltageRegulation100": get_voltage_regulation(er_value, impedance_summary["ex"], 1.0),
                "voltageRegulation80": get_voltage_regulation(er_value, impedance_summary["ex"], 0.8),
            },
            "testVoltages": _build_test_voltages_payload(
                multi_winding,
                corse_winding_model,
                fine_winding_model,
                outer_winding_model,
            ),
            "insulation": _build_insulation_payload(multi_winding, coil_dimensions),
            "tankAndOil": tank_and_oil,
                "lossesAt50Percent": losses_at_50,
            "lossesAt100Percent": losses_at_100,
            "nlCurrentPercentage": get_nl_current_percentage(core.coreWeight, recomputed_core_loss, multi_winding.kVA) if multi_winding.kVA else 0,
        },
    }
