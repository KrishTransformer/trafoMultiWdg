import json

from django.forms.models import model_to_dict
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from api.models import MultiWindings, RadialGaps, Windings
from api.services.windingFormulae import calculate_winding_formulae


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


def _serialize_model(instance):
    if instance is None:
        return None
    return model_to_dict(instance, fields=[field.name for field in instance._meta.fields if field.name != "id"])


def _serialize_formula_payload(payload):
    inputs = payload.get("inputs", {})
    winding_models = inputs.get("windingModels", {})

    serialized_inputs = {
        **inputs,
        "windingModels": {
            name: _serialize_model(model)
            for name, model in winding_models.items()
        },
        "radialGaps": _serialize_model(inputs.get("radialGaps")),
    }

    return {
        **payload,
        "inputs": serialized_inputs,
    }


def _build_multi_winding(payload):
    multi_winding = _build_model_instance(MultiWindings, payload)
    if multi_winding is None:
        raise ValueError("Request body must be a JSON object.")

    multi_winding.lvWindings = _build_model_instance(Windings, payload.get("lvWindings"))
    multi_winding.hvWindings = _build_model_instance(Windings, payload.get("hvWindings"))
    multi_winding.fineWindings = _build_model_instance(Windings, payload.get("fineWindings"))
    multi_winding.corseWindings = _build_model_instance(Windings, payload.get("corseWindings"))
    multi_winding.outerWindings = _build_model_instance(Windings, payload.get("outerWindings"))
    multi_winding.radialGaps = _build_model_instance(RadialGaps, payload.get("radialGaps"))

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

    formula_payload = calculate_winding_formulae(multi_winding)
    return JsonResponse(_serialize_formula_payload(formula_payload), status=200)
