import json

from django.forms.models import model_to_dict
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from api.models import CoilDimensions, Core, MultiWindings, RadialGaps, Windings
from api.services.circWdgService import calculate_circ_wdg


RADIAL_GAP_FIELDS_BY_SELECTION = {
    "2_WDG": ("coreToLv", "lvToHv"),
    "3_WDG": ("coreToLv", "lvToHv", "hvToOuter"),
    "4_WDG_C": ("coreToLv", "lvToHv", "hvToCorse", "corseToOuter"),
    "4_WDG_F": ("coreToLv", "lvToHv", "hvToFine", "fineToOuter"),
    "5_WDG": ("coreToLv", "lvToHv", "hvToCorse", "corseToFine", "fineToOuter"),
}


def _build_model_instance(model_class, payload):
    if not isinstance(payload, dict):
        return None

    field_names = {
        field.name
        for field in model_class._meta.fields
        if field.name != "id" and not field.is_relation
    }
    filtered_payload = {
        key: value
        for key, value in payload.items()
        if key in field_names
    }
    return model_class(**filtered_payload)


def _normalize_coil_dimensions_payload(payload):
    if not isinstance(payload, dict):
        return payload

    normalized_payload = dict(payload)
    if "coilCoilGap" not in normalized_payload and "hVHVGap" in normalized_payload:
        normalized_payload["coilCoilGap"] = normalized_payload["hVHVGap"]
    if "hVHVGap" not in normalized_payload and "coilCoilGap" in normalized_payload:
        normalized_payload["hVHVGap"] = normalized_payload["coilCoilGap"]
    return normalized_payload


def _normalize_radial_gaps_payload(payload):
    if not isinstance(payload, dict):
        return payload

    normalized_payload = dict(payload)
    if "lvToHv" not in normalized_payload and "LvtoHV" in normalized_payload:
        normalized_payload["lvToHv"] = normalized_payload["LvtoHV"]
    if "hvToCorse" not in normalized_payload and "lvToCoarse" in normalized_payload:
        normalized_payload["hvToCorse"] = normalized_payload["lvToCoarse"]
    if "hvToFine" not in normalized_payload and "lvToFine" in normalized_payload:
        normalized_payload["hvToFine"] = normalized_payload["lvToFine"]
    if "corseToFine" not in normalized_payload and "fineToCoarse" in normalized_payload:
        normalized_payload["corseToFine"] = normalized_payload["fineToCoarse"]
    if "corseToOuter" not in normalized_payload and "coarseToOuter" in normalized_payload:
        normalized_payload["corseToOuter"] = normalized_payload["coarseToOuter"]
    return normalized_payload


def _serialize_model(instance):
    if instance is None:
        return None
    return model_to_dict(instance, fields=[field.name for field in instance._meta.fields if field.name != "id"])


def _serialize_radial_gaps(instance, selected_code):
    serialized = _serialize_model(instance)
    if serialized is None:
        return None

    allowed_fields = RADIAL_GAP_FIELDS_BY_SELECTION.get(selected_code)
    if not allowed_fields:
        return serialized
    return {field: serialized[field] for field in allowed_fields if field in serialized}


def _serialize_formula_payload(payload):
    inputs = payload.get("inputs", {})
    winding_models = inputs.get("windingModels", {})
    selected_code = payload.get("selectedCode")

    serialized_inputs = {
        **inputs,
        "windingModels": {
            name: _serialize_model(model)
            for name, model in winding_models.items()
        },
        "radialGaps": _serialize_radial_gaps(inputs.get("radialGaps"), selected_code),
        "core": _serialize_model(inputs.get("core")),
        "coilDimensions": _serialize_model(inputs.get("coilDimensions")),
    }

    return {
        **payload,
        "inputs": serialized_inputs,
    }


def _build_multi_winding(payload):
    multi_winding = _build_model_instance(MultiWindings, payload)
    if multi_winding is None:
        raise ValueError("Request body must be a JSON object.")

    if "windingSelection" in payload:
        multi_winding.windings = payload["windingSelection"]

    multi_winding.lvWindings = _build_model_instance(Windings, payload.get("lvWindings"))
    multi_winding.hvWindings = _build_model_instance(Windings, payload.get("hvWindings"))
    multi_winding.fineWindings = _build_model_instance(Windings, payload.get("fineWindings"))
    multi_winding.corseWindings = _build_model_instance(Windings, payload.get("corseWindings"))
    multi_winding.outerWindings = _build_model_instance(Windings, payload.get("outerWindings"))
    multi_winding.radialGaps = _build_model_instance(
        RadialGaps,
        _normalize_radial_gaps_payload(payload.get("radialGaps")),
    )
    multi_winding.core = _build_model_instance(Core, payload.get("core"))
    multi_winding.coilDimensions = _build_model_instance(
        CoilDimensions,
        _normalize_coil_dimensions_payload(payload.get("coilDimensions")),
    )

    for key in [
        "dryType",
        "dryTempClass",
        "transCostType",
        "lvWindingType",
        "hvWindingType",
        "corseWindingType",
        "fineWindingType",
        "outerWindingType",
        "limitEz",
        "buildFactor",
        "lvConductorFlag",
        "hvConductorFlag",
    ]:
        if key in payload:
            setattr(multi_winding, key, payload[key])

    for key in [
        "isOLTC",
        "isCSP",
        "eRadiatorType",
        "radiatorType",
        "lvTerminalType",
        "hvTerminalType",
        "ambientTemp",
        "windingTemp",
        "topOilTemp",
        "radiatorWidth",
        "copperCostPerKg",
        "aluminiumCostPerKg",
        "coreCostPerKg",
        "steelCostPerKg",
        "oilCostPerKg",
        "insulationCostPerKg",
        "radiatorCostPerKg",
    ]:
        if key in payload:
            setattr(multi_winding, key, payload[key])

    tank_payload = payload.get("tank")
    if isinstance(tank_payload, dict):
        for source_key, attr_name in [
            ("tankLoss", "tankLoss"),
            ("wdgToTankGap", "wdgToTankGap"),
            ("connectionGap", "connectionGap"),
            ("topYokeToCoverGap", "topYokeToCoverGap"),
        ]:
            if source_key in tank_payload:
                setattr(multi_winding, attr_name, tank_payload[source_key])

    cost_payload = payload.get("cost")
    if isinstance(cost_payload, dict):
        for key in [
            "copperCostPerKg",
            "aluminiumCostPerKg",
            "coreCostPerKg",
            "steelCostPerKg",
            "oilCostPerKg",
            "insulationCostPerKg",
            "radiatorCostPerKg",
        ]:
            if key in cost_payload:
                setattr(multi_winding, key, cost_payload[key])

    return multi_winding


def home(request):
    return HttpResponse("multiWdg backend is running")


@csrf_exempt
@require_http_methods(["POST"])
def multi_wdg_calculator(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    try:
        multi_winding = _build_multi_winding(payload)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        formula_payload = calculate_circ_wdg(multi_winding)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse(_serialize_formula_payload(formula_payload), status=200)
