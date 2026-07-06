import json
from types import SimpleNamespace

from django.test import Client, TestCase

from api.models import MultiWindings, Windings
from api.services import (
    calculate_winding_formulae,
    calculate_circ_wdg,
    calculate_corse_windings,
    calculate_fine_windings,
    calculate_hv_windings,
    calculate_lv_windings,
    calculate_outer_windings,
)
from api.services.circWdgService import _get_high_side_distribution
from api.services.impedanceVbService import calculate_vb_multi_impedance
from api.services.windingFormulae import get_specific_loss, select_radiators


class MultiWdgCalculatorEndpointTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_multi_wdg_calculator_returns_formula_results(self):
        payload = {
            "designId": "D-1001",
            "windings": "LV-HV",
            "kVA": 100,
            "kValue": 0.45,
            "frequency": 50,
            "fluxDensity": 1.7,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
            "lvWindingType": "Layer Disc",
            "hvWindingType": "X-Over",
            "lvWindings": {
                "endClearances": 40,
            },
            "hvWindings": {
                "endClearances": 60,
            },
            "radialGaps": {
                "coreToLv": 5,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["selectedCode"], "2_WDG")
        self.assertNotIn("windingSelection", response.json()["inputs"])
        self.assertNotIn("windingSelection", response.json()["results"])
        results = response.json()["results"]
        self.assertEqual(results["voltsPerTurn"], 4.5)
        self.assertEqual(results["lvVoltsPerPhase"], 249.99)
        self.assertEqual(results["hvVoltsPerPhase"], 11000.0)
        self.assertEqual(results["lvTurnsPerPhase"], 56)
        self.assertEqual(results["hvTurnsPerPhase"], 2465)
        self.assertEqual(results["lvCurrentPerPhase"], 133.34)
        self.assertEqual(results["hvCurrentPerPhase"], 3.03)
        self.assertEqual(results["lvEndClearance"], 46.0)
        self.assertEqual(results["hvEndClearance"], 64.0)
        self.assertEqual(results["lvWinding"]["lvTurnsPerPhase"], 56)
        self.assertEqual(results["lvWinding"]["lvTurnsPerLayer"], 56)
        self.assertEqual(results["lvWinding"]["lvNumberOfLayers"], 1)
        self.assertEqual(results["hvWinding"]["hvTurnsPerPhase"], 2465)
        self.assertEqual(results["hvWinding"]["hvTurnsPerLayer"], 45)
        self.assertEqual(results["hvWinding"]["hvNumberOfLayers"], 14)
        self.assertEqual(results["lvWinding"]["voltsPerPhase"], 249.99)
        self.assertEqual(results["hvWinding"]["voltsPerPhase"], 11000.0)
        self.assertIn("common", results)
        self.assertIn("core", results)
        self.assertIn("coilDimensions", results)
        self.assertEqual(response.json()["inputs"]["windingModels"]["lv"]["turnsPerPhase"], 56)
        self.assertEqual(response.json()["inputs"]["windingModels"]["lv"]["phaseCurrent"], 133.34)
        self.assertEqual(response.json()["inputs"]["windingModels"]["lv"]["endClearances"], 46)
        self.assertEqual(response.json()["inputs"]["windingModels"]["lv"]["terminal"], 249.99)
        self.assertEqual(
            response.json()["inputs"]["windingModels"]["lv"]["noInParallel"],
            "Rad 1 X Axi 1 = 1",
        )
        self.assertEqual(response.json()["inputs"]["windingModels"]["hv"]["turnsPerPhase"], 2465)
        self.assertEqual(response.json()["inputs"]["windingModels"]["hv"]["terminal"], 11000.0)
        self.assertEqual(
            response.json()["inputs"]["windingModels"]["hv"]["noInParallel"],
            "Rad 1 X Axi 1 = 1",
        )
        self.assertEqual(response.json()["inputs"]["radialGaps"]["coreToLv"], 5)
        self.assertEqual(
            response.json()["inputs"]["radialGaps"],
            {"coreToLv": 5, "lvToHv": 0.0},
        )
        self.assertEqual(response.json()["inputs"]["core"]["wKgGrade"], 1.3)
        self.assertEqual(response.json()["results"]["core"]["wKgGrade"], 1.3)
        self.assertGreater(response.json()["results"]["hvWinding"]["coreLoss"], 0)
        self.assertEqual(
            response.json()["inputs"]["windingTypes"]["lv"],
            "LAYER_DISC",
        )
        self.assertEqual(
            response.json()["inputs"]["windingTypes"]["hv"],
            "XOVER",
        )
        self.assertNotIn("outer", response.json()["inputs"]["windingTypes"])
        self.assertIn("ex", response.json()["results"]["impedance"])
        self.assertIn("er", response.json()["results"]["impedance"])
        self.assertIn("ek", response.json()["results"]["impedance"])
        self.assertEqual(
            response.json()["results"]["impedance"]["ek"],
            response.json()["results"]["ez"]["value"],
        )
        self.assertEqual(
            response.json()["results"]["phaseVoltages"],
            {"lv": 249, "hvMain": 11000, "corse": 0, "fine": 0, "outer": 0},
        )
        self.assertEqual(
            response.json()["results"]["phaseVoltageDivision"],
            {"lv": 249, "hvMain": 11000, "corse": 0, "fine": 0, "outer": 0},
        )
        self.assertEqual(
            response.json()["results"]["testVoltages"],
            {
                "lv": {"test": 3, "impulse": 0},
                "hv": {"test": 28, "impulse": 75},
            },
        )
        self.assertEqual(
            response.json()["results"]["coilDimensions"]["windingDimensions"]["lv"]["innerDiameter"],
            response.json()["results"]["coilDimensions"]["lVID"],
        )
        self.assertEqual(
            response.json()["results"]["coilDimensions"]["windingDimensions"]["hv"]["outerDiameter"],
            response.json()["results"]["coilDimensions"]["hVOD"],
        )
        self.assertIsNone(response.json()["results"]["coilDimensions"]["windingDimensions"]["outer"])
        self.assertIsNone(response.json()["results"]["coilDimensions"]["outerID"])
        self.assertIsNone(response.json()["inputs"]["coilDimensions"]["outerID"])

    def test_multi_wdg_calculator_defaults_to_2wdg_selection(self):
        payload = {
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["selectedCode"], "2_WDG")
        self.assertEqual(list(response.json().keys())[0], "selectedCode")
        self.assertNotIn("windingSelection", response.json()["inputs"])
        self.assertNotIn("windingSelection", response.json()["results"])
        self.assertIsNone(response.json()["inputs"]["windingModels"]["outer"])
        self.assertEqual(
            response.json()["inputs"]["windingTypes"],
            {"lv": "HELICAL", "hv": "HELICAL"},
        )

    def test_two_wdg_coil_dimensions_accepts_preferred_coil_coil_gap_name(self):
        payload = {
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
            "coilDimensions": {
                "coilCoilGap": 30,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["inputs"]["coilDimensions"]["coilCoilGap"], 30.0)
        self.assertEqual(response.json()["inputs"]["coilDimensions"]["hVHVGap"], 30.0)
        self.assertEqual(response.json()["results"]["coilDimensions"]["coilCoilGap"], 30)
        self.assertEqual(response.json()["results"]["coilDimensions"]["hVHVGap"], 30)

    def test_radial_gaps_accept_legacy_lvtohv_input_but_return_lv_to_hv(self):
        payload = {
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
            "radialGaps": {
                "coreToLv": 5,
                "LvtoHV": 12,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["inputs"]["radialGaps"],
            {"coreToLv": 5, "lvToHv": 12},
        )

    def test_insulation_uses_coil_coil_name_instead_of_hv_hv(self):
        payload = {
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        insulation = response.json()["results"]["insulation"]
        self.assertIn("coreLv", insulation)
        self.assertIn("lvHv", insulation)
        self.assertIn("coilCoil", insulation)
        self.assertNotIn("hvHv", insulation)

    def test_coil_coil_insulation_uses_actual_outermost_winding_type(self):
        payload = {
            "windingSelection": "3 Wdg (LV, HV-Main and Outer)",
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
            "hvWindingType": "Disc",
            "outerWindingType": "Helical",
            "radialGaps": {
                "coreToLv": 5,
                "lvToHv": 10,
                "hvToOuter": 10,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["results"]["insulation"]["coilCoil"],
            "1mm x 2 PB + rest Oil",
        )

    def test_insulation_includes_active_extra_winding_gap_keys(self):
        payload = {
            "windingSelection": "5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
            "corseWindingType": "Helical",
            "fineWindingType": "Helical",
            "outerWindingType": "Helical",
            "radialGaps": {
                "coreToLv": 5,
                "lvToHv": 10,
                "lvToCoarse": 8,
                "fineToCoarse": 6,
                "fineToOuter": 10,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        insulation = response.json()["results"]["insulation"]
        self.assertIn("coilCoil", insulation)
        self.assertIn("lvToCoarse", insulation)
        self.assertIn("fineToCoarse", insulation)
        self.assertIn("fineToOuter", insulation)
        self.assertNotIn("hvHv", insulation)

    def test_extra_winding_current_density_inputs_affect_section_sizing(self):
        base_payload = {
            "windingSelection": "5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
            "corseWindingType": "Helical",
            "fineWindingType": "Helical",
            "outerWindingType": "Helical",
            "radialGaps": {
                "coreToLv": 5,
                "lvToHv": 10,
                "lvToCoarse": 8,
                "fineToCoarse": 6,
                "fineToOuter": 10,
            },
        }

        default_response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(base_payload),
            content_type="application/json",
        )
        tuned_payload = {
            **base_payload,
            "corseCurrentDensity": 1.2,
        }
        tuned_response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(tuned_payload),
            content_type="application/json",
        )

        self.assertEqual(default_response.status_code, 200)
        self.assertEqual(tuned_response.status_code, 200)
        default_corse = default_response.json()["inputs"]["windingModels"]["corse"]
        tuned_corse = tuned_response.json()["inputs"]["windingModels"]["corse"]
        self.assertNotEqual(default_corse["condCrossSec"], tuned_corse["condCrossSec"])

    def test_test_voltages_remain_lv_and_hv_only(self):
        payload = {
            "windingSelection": "5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
            "corseWindingType": "Helical",
            "fineWindingType": "Helical",
            "outerWindingType": "Helical",
            "radialGaps": {
                "coreToLv": 5,
                "lvToHv": 10,
                "lvToCoarse": 8,
                "fineToCoarse": 6,
                "fineToOuter": 10,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        test_voltages = response.json()["results"]["testVoltages"]
        self.assertEqual(
            test_voltages,
            {
                "lv": {"test": 3, "impulse": 0},
                "hv": {"test": 28, "impulse": 75},
            },
        )

    def test_multi_wdg_calculator_activates_selected_extra_windings(self):
        payload = {
            "windingSelection": "5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
            "corseWindingType": "Helical",
            "fineWindingType": "Helical",
            "outerWindingType": "Disc",
            "corseWindings": {
                "endClearances": 65,
                "turnsPerPhase": 220,
                "phaseCurrent": 3.03,
                "turnsPerLayer": 12,
                "axialParallelCond": 1,
                "loadLoss": 60,
                "noOfLayers": 2,
                "condHeight": 3,
                "condInsulation": 0.5,
                "interLayerInsulation": 1,
                "ducts": 1,
                "ductSize": 5,
            },
            "fineWindings": {
                "endClearances": 70,
                "turnsPerPhase": 120,
                "phaseCurrent": 3.03,
                "turnsPerLayer": 10,
                "axialParallelCond": 1,
                "loadLoss": 80,
                "noOfLayers": 2,
                "condHeight": 3.5,
                "condInsulation": 0.5,
                "interLayerInsulation": 1,
                "ducts": 1,
                "ductSize": 4,
            },
            "outerWindings": {
                "endClearances": 75,
                "turnsPerPhase": 80,
                "phaseCurrent": 3.03,
                "turnsPerLayer": 8,
                "axialParallelCond": 1,
                "loadLoss": 120,
                "noOfLayers": 2,
                "condHeight": 4,
                "condInsulation": 0.5,
                "interLayerInsulation": 1,
                "ducts": 1,
                "ductSize": 6,
            },
            "radialGaps": {
                "coreToLv": 5,
                "lvToHv": 10,
                "lvToCoarse": 8,
                "fineToCoarse": 6,
                "fineToOuter": 10
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["selectedCode"], "5_WDG")
        self.assertNotIn("windingSelection", response.json()["inputs"])
        self.assertNotIn("windingSelection", response.json()["results"])
        self.assertIn("delta", response.json()["results"]["impedance"])
        self.assertIn("delta1", response.json()["results"]["impedance"])
        self.assertIn("ds", response.json()["results"]["impedance"])
        self.assertEqual(
            response.json()["results"]["phaseVoltages"],
            response.json()["results"]["phaseVoltageDivision"],
        )
        self.assertEqual(response.json()["results"]["phaseVoltageDivision"]["lv"], 249)
        self.assertEqual(response.json()["results"]["phaseVoltageDivision"]["hvMain"], 11000)
        self.assertEqual(
            response.json()["results"]["hvWinding"]["voltsPerPhase"],
            11000,
        )
        self.assertIsNotNone(response.json()["inputs"]["windingModels"]["outer"])
        self.assertEqual(response.json()["inputs"]["windingModels"]["outer"]["endClearances"], 75)
        self.assertEqual(
            response.json()["results"]["phaseVoltageDivision"]["corse"],
            int(response.json()["inputs"]["windingModels"]["corse"]["terminal"]),
        )
        self.assertEqual(
            response.json()["results"]["phaseVoltageDivision"]["fine"],
            int(response.json()["inputs"]["windingModels"]["fine"]["terminal"]),
        )
        self.assertEqual(
            response.json()["results"]["phaseVoltageDivision"]["outer"],
            int(response.json()["inputs"]["windingModels"]["outer"]["terminal"]),
        )
        self.assertEqual(
            response.json()["inputs"]["radialGaps"],
            {
                "coreToLv": 5,
                "lvToHv": 10,
                "lvToCoarse": 8,
                "fineToCoarse": 6,
                "fineToOuter": 10,
            },
        )

    def test_multi_wdg_selection_preserves_canonical_winding_sequence(self):
        payload = {
            "windingSelection": "4_WDG_F",
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["selectedCode"], "4_WDG_F")
        self.assertIn("ex", response.json()["results"]["impedance"])
        self.assertIn("er", response.json()["results"]["impedance"])
        self.assertIn("ek", response.json()["results"]["impedance"])

    def test_multi_wdg_hv_main_layers_follow_calculated_turns(self):
        payload = {
            "windingSelection": "3 Wdg (LV, HV-Main and Outer)",
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
            "hvWindingType": "Helical",
            "outerWindingType": "Helical",
            "outerWindings": {
                "turnsPerPhase": 500,
                "turnsPerLayer": 10,
                "condHeight": 4,
                "condInsulation": 0.5,
                "interLayerInsulation": 1,
                "ducts": 1,
                "ductSize": 6,
            },
            "radialGaps": {
                "coreToLv": 5,
                "lvToHv": 10,
                "hvToOuter": 10,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["inputs"]["radialGaps"],
            {
                "coreToLv": 5,
                "lvToHv": 10,
                "hvToOuter": 10,
            },
        )
        hv_model = response.json()["inputs"]["windingModels"]["hv"]
        hv_results = response.json()["results"]["hvWinding"]
        self.assertEqual(hv_model["turnsPerPhase"], 2465.0)
        self.assertEqual(hv_model["turnsPerLayer"], 197.0)
        self.assertEqual(hv_model["noOfLayers"], 12.51)
        self.assertNotEqual(hv_model["noOfLayers"], hv_model["turnsPerPhase"])
        self.assertEqual(hv_results["turnsPerLayer"], 197.0)
        self.assertEqual(hv_results["noOfLayers"], 12.51)
        self.assertEqual(hv_results["endClearance"], 57.0)
        self.assertEqual(hv_results["windingLength"], 238.0)

    def test_multi_wdg_extra_windings_layers_follow_allocated_turns(self):
        payload = {
            "windingSelection": "5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
            "tapStepsPercentage": 2.5,
            "tapStepPositive": 2,
            "tapStepNegative": 2,
            "hvWindingType": "Helical",
            "corseWindingType": "Helical",
            "fineWindingType": "Helical",
            "outerWindingType": "Helical",
            "radialGaps": {
                "coreToLv": 5,
                "lvToHv": 10,
                "lvToCoarse": 8,
                "fineToCoarse": 6,
                "fineToOuter": 10,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        for winding_name in ("corse", "fine"):
            model = response.json()["inputs"]["windingModels"][winding_name]
            result = response.json()["results"][f"{winding_name}Winding"]
            self.assertEqual(model["turnsPerLayer"], 204.0)
            self.assertEqual(model["noOfLayers"], 1.0)
            self.assertNotEqual(model["noOfLayers"], model["turnsPerPhase"])
            self.assertEqual(model["endClearances"], 49.0)
            self.assertEqual(result["turnsPerLayer"], 204.0)
            self.assertEqual(result["noOfLayers"], 1.0)
            self.assertEqual(result["endClearance"], 49.0)

        outer_model = response.json()["inputs"]["windingModels"]["outer"]
        outer_result = response.json()["results"]["outerWinding"]
        self.assertEqual(outer_model["turnsPerLayer"], 204.0)
        self.assertEqual(outer_model["endClearances"], 49.0)
        self.assertAlmostEqual(outer_model["noOfLayers"], 1.21, places=2)
        self.assertEqual(outer_result["turnsPerLayer"], 204.0)
        self.assertEqual(outer_result["endClearance"], 49.0)
        self.assertAlmostEqual(outer_result["noOfLayers"], 1.21, places=2)

    def test_multi_wdg_extra_windings_number_in_parallel_matches_lv_hv_format(self):
        payload = {
            "windingSelection": "5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
            "tapStepsPercentage": 2.5,
            "tapStepPositive": 2,
            "tapStepNegative": 2,
            "hvWindingType": "Helical",
            "corseWindingType": "Helical",
            "fineWindingType": "Helical",
            "outerWindingType": "Helical",
            "radialGaps": {
                "coreToLv": 5,
                "lvToHv": 10,
                "lvToCoarse": 8,
                "fineToCoarse": 6,
                "fineToOuter": 10,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        for winding_name in ("corse", "fine", "outer"):
            model = response.json()["inputs"]["windingModels"][winding_name]
            self.assertEqual(
                model["noInParallel"],
                (
                    f'Rad {model["radialParallelCond"]} '
                    f'X Axi {model["axialParallelCond"]} = '
                    f'{model["radialParallelCond"] * model["axialParallelCond"]}'
                ),
            )
            self.assertNotIn("Seed", model["noInParallel"])

    def test_multi_wdg_calculator_rejects_invalid_winding_selection(self):
        payload = {
            "windingSelection": "7 Wdg",
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported windingSelection", response.json()["error"])

    def test_multi_wdg_calculator_rejects_invalid_winding_type(self):
        payload = {
            "windingSelection": "3 Wdg (LV, HV-Main and Outer)",
            "outerWindingType": "XOver",
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported outerWindingType", response.json()["error"])

    def test_multi_wdg_calculator_rejects_get_requests(self):
        response = self.client.get("/api/multiWdgCalculator/")

        self.assertEqual(response.status_code, 405)

    def test_services_module_reexports_calculator(self):
        multi_winding = MultiWindings(
            kVA=100,
            kValue=0.45,
            vectorGroup="Dyn11",
            lowVoltage=433,
            highVoltage=11000,
        )

        results = calculate_winding_formulae(multi_winding)["results"]

        self.assertEqual(results["voltsPerTurn"], 4.5)
        self.assertEqual(results["lvVoltsPerPhase"], 249.99)

    def test_lv_and_hv_winding_services_return_structured_results(self):
        multi_winding = MultiWindings(
            kVA=100,
            kValue=0.45,
            frequency=50,
            fluxDensity=1.7,
            vectorGroup="Dyn11",
            lowVoltage=433,
            highVoltage=11000,
            lvCurrentDensity=2.5,
            hvCurrentDensity=2.2,
            lvConductorMaterial="COPPER",
            hvConductorMaterial="COPPER",
        )

        lv_results = calculate_lv_windings(multi_winding)
        hv_results = calculate_hv_windings(multi_winding, lv_results)

        self.assertEqual(lv_results["lvTurnsPerPhase"], 56)
        self.assertEqual(lv_results["lvCurrentPerPhase"], 133.34)
        self.assertGreater(lv_results["lvOd"], lv_results["lvId"])
        self.assertEqual(hv_results["hvTurnsPerPhase"], 2465)
        self.assertEqual(hv_results["hvCurrentPerPhase"], 3.03)
        self.assertEqual(hv_results["hvTurnsPerLayer"], 166)
        self.assertEqual(hv_results["hvNumberOfLayers"], 14.85)
        self.assertGreater(hv_results["hvOd"], hv_results["hvId"])

    def test_lv_winding_service_uses_java_type_specific_branches(self):
        expected = {
            "HELICAL": (28.0, 2),
            "DISC": (20, 3),
            "FOIL": (1, 56),
            "LAYER_DISC": (56, 1),
        }

        for winding_type, (turns_per_layer, number_of_layers) in expected.items():
            multi_winding = MultiWindings(
                kVA=100,
                kValue=0.45,
                frequency=50,
                fluxDensity=1.7,
                vectorGroup="Dyn11",
                lowVoltage=433,
                highVoltage=11000,
                lvCurrentDensity=2.5,
                lvConductorMaterial="COPPER",
            )
            multi_winding.lvWindingType = winding_type
            multi_winding.lvWindings = Windings(endClearances=40)

            lv_results = calculate_lv_windings(multi_winding)

            self.assertEqual(lv_results["lvTurnsPerLayer"], turns_per_layer)
            self.assertEqual(lv_results["lvNumberOfLayers"], number_of_layers)

    def test_lv_helical_rectangular_branch_follows_java_auto_sizing(self):
        multi_winding = MultiWindings(
            kVA=2000,
            kValue=0.45,
            frequency=50,
            fluxDensity=1.7,
            vectorGroup="Dyn11",
            lowVoltage=433,
            highVoltage=11000,
            lvCurrentDensity=2.5,
            lvConductorMaterial="COPPER",
        )
        multi_winding.lvWindingType = "HELICAL"
        multi_winding.lvWindings = Windings(endClearances=40, noOfLayers=2)

        lv_results = calculate_lv_windings(multi_winding)

        self.assertFalse(lv_results["lvIsConductorRound"])
        self.assertEqual(lv_results["lvNumberOfLayers"], 2)
        self.assertEqual(lv_results["lvTurnsPerLayer"], 6.5)
        self.assertEqual(lv_results["lvBreadthInsulated"], 5.7)
        self.assertEqual(lv_results["lvRadialParallelConductors"], 7)
        self.assertEqual(lv_results["lvAxialParallelConductors"], 10)
        self.assertEqual(lv_results["lvTransposition"], 35)
        self.assertGreater(lv_results["lvGradient"], lv_results["gradientLimit"])

    def test_hv_winding_service_uses_distinct_disc_branch(self):
        helical = MultiWindings(
            kVA=100,
            kValue=0.45,
            frequency=50,
            fluxDensity=1.7,
            vectorGroup="Dyn11",
            lowVoltage=433,
            highVoltage=11000,
            hvCurrentDensity=2.2,
            hvConductorMaterial="COPPER",
        )
        disc = MultiWindings(
            kVA=100,
            kValue=0.45,
            frequency=50,
            fluxDensity=1.7,
            vectorGroup="Dyn11",
            lowVoltage=433,
            highVoltage=11000,
            hvCurrentDensity=2.2,
            hvConductorMaterial="COPPER",
        )
        helical.hvWindingType = "HELICAL"
        disc.hvWindingType = "DISC"

        lv_helical = calculate_lv_windings(helical)
        lv_disc = calculate_lv_windings(disc)
        helical_results = calculate_hv_windings(helical, lv_helical)
        disc_results = calculate_hv_windings(disc, lv_disc)

        self.assertFalse(disc_results["hvBreadth"] < 5 and disc_results["hvHeight"] > 1.7)
        self.assertNotEqual(helical_results["hvTurnsPerLayer"], disc_results["hvTurnsPerLayer"])
        self.assertNotEqual(helical_results["hvNumberOfLayers"], disc_results["hvNumberOfLayers"])
        self.assertNotEqual(helical_results["hvWindingLength"], disc_results["hvWindingLength"])
        self.assertNotEqual(helical_results["%hvStrayLoss"], disc_results["%hvStrayLoss"])

    def test_circ_service_returns_linked_sections(self):
        multi_winding = MultiWindings(
            kVA=100,
            kValue=0.45,
            frequency=50,
            fluxDensity=1.7,
            vectorGroup="Dyn11",
            lowVoltage=433,
            highVoltage=11000,
            lvConductorMaterial="COPPER",
            hvConductorMaterial="COPPER",
        )

        payload = calculate_circ_wdg(multi_winding)
        results = payload["results"]

        self.assertIn("lvWinding", results)
        self.assertIn("hvWinding", results)
        self.assertIn("common", results)
        self.assertIn("coilDimensions", results)
        self.assertIn("ez", results)
        self.assertEqual(results["coilDimensions"]["lVID"], results["lvWinding"]["lvId"])
        self.assertEqual(payload["selectedCode"], "2_WDG")
        self.assertNotIn("windingSelection", results)
        self.assertNotIn("windingSelection", payload["inputs"])
        self.assertEqual(results["phaseVoltageDivision"]["hvMain"], 11000)
        self.assertEqual(results["windingTypes"], {"lv": "HELICAL", "hv": "HELICAL"})
        self.assertIsNone(results["outerWinding"])
        self.assertEqual(results["coilDimensions"]["outermostWinding"], "hv")
        self.assertIsNone(results["coilDimensions"]["windingDimensions"]["fine"])

    def test_extra_winding_services_return_calculated_payloads(self):
        multi_winding = MultiWindings(
            kVA=100,
            kValue=0.45,
            vectorGroup="Dyn11",
            lowVoltage=433,
            highVoltage=11000,
            windings="5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
        )
        multi_winding.outerWindingType = "DISC"
        multi_winding.fineWindingType = "HELICAL"
        multi_winding.corseWindingType = "HELICAL"
        multi_winding.outerWindings = Windings(endClearances=60, ducts=0, ductSize=0, isEnamel=False)
        multi_winding.fineWindings = Windings(endClearances=60, ducts=0, ductSize=0, isEnamel=False)
        multi_winding.corseWindings = Windings(endClearances=60, ducts=0, ductSize=0, isEnamel=False)

        lv_results = calculate_lv_windings(multi_winding)
        hv_results = calculate_hv_windings(multi_winding, lv_results)
        outer_seed = {"previousWinding": "fine", "previousOuterDiameter": 320.0, "previousRadialThickness": 12.0, "previousWindingLength": 420.0, "gapField": "fineToOuter", "gapToPrevious": 10.0}
        fine_seed = {"previousWinding": "corse", "previousOuterDiameter": 280.0, "previousRadialThickness": 10.0, "previousWindingLength": 420.0, "gapField": "fineToCoarse", "gapToPrevious": 6.0}
        corse_seed = {"previousWinding": "hv", "previousOuterDiameter": 240.0, "previousRadialThickness": 18.0, "previousWindingLength": 420.0, "gapField": "lvToCoarse", "gapToPrevious": 8.0}
        outer_results = calculate_outer_windings(multi_winding, hv_results, outer_seed, 60, 270)
        fine_results = calculate_fine_windings(multi_winding, hv_results, fine_seed, 60, 270)
        corse_results = calculate_corse_windings(multi_winding, hv_results, corse_seed, 120, 540)

        self.assertTrue(outer_results["implemented"])
        self.assertEqual(outer_results["windingType"], "DISC")
        self.assertEqual(outer_results["status"], "calculated")
        self.assertIn("estimatedRadialThickness", outer_results)
        self.assertIn("seedDimensions", outer_results)
        self.assertEqual(outer_results["voltsPerPhase"], 270)
        self.assertGreater(outer_results["loadLoss"], 0)
        self.assertTrue(fine_results["implemented"])
        self.assertEqual(fine_results["windingType"], "HELICAL")
        self.assertEqual(fine_results["voltsPerPhase"], 270)
        self.assertTrue(corse_results["implemented"])
        self.assertEqual(corse_results["windingType"], "HELICAL")
        self.assertEqual(corse_results["voltsPerPhase"], 540)

    def test_outer_winding_service_uses_distinct_disc_branch(self):
        multi_winding = MultiWindings(
            kVA=100,
            kValue=0.45,
            vectorGroup="Dyn11",
            lowVoltage=433,
            highVoltage=11000,
            windings="5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
        )
        lv_results = calculate_lv_windings(multi_winding)
        hv_results = calculate_hv_windings(multi_winding, lv_results)
        outer_seed = {
            "previousWinding": "fine",
            "previousOuterDiameter": 320.0,
            "previousRadialThickness": 12.0,
            "previousWindingLength": 420.0,
            "gapField": "fineToOuter",
            "gapToPrevious": 10.0,
        }

        multi_winding.outerWindingType = "HELICAL"
        multi_winding.outerWindings = Windings(endClearances=60, ducts=0, ductSize=0, isEnamel=False)
        helical_results = calculate_outer_windings(multi_winding, hv_results, outer_seed, 60, 270)
        multi_winding.outerWindingType = "DISC"
        multi_winding.outerWindings = Windings(endClearances=60, ducts=0, ductSize=0, isEnamel=False)
        disc_results = calculate_outer_windings(multi_winding, hv_results, outer_seed, 60, 270)

        self.assertFalse(disc_results["breadth"] < 5 and disc_results["height"] > 1.7)
        self.assertNotEqual(helical_results["turnsPerLayer"], disc_results["turnsPerLayer"])
        self.assertNotEqual(helical_results["windingLength"], disc_results["windingLength"])
        self.assertNotEqual(helical_results["strayLoss"], disc_results["strayLoss"])

    def test_api_formats_non_round_conductor_sizes_as_l_x_b(self):
        payload = {
            "windings": "LV-HV",
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
            "hvWindingType": "DISC",
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        hv_model = response.json()["inputs"]["windingModels"]["hv"]
        self.assertFalse(hv_model["isConductorRound"])
        self.assertIn(" L X ", hv_model["conductorSizes"])
        self.assertTrue(hv_model["conductorSizes"].endswith(" B"))

    def test_api_returns_tank_and_oil_results(self):
        payload = {
            "windings": "LV-HV",
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        tank_and_oil = response.json()["results"]["tankAndOil"]
        self.assertEqual(tank_and_oil["tankLength"], 685)
        self.assertEqual(tank_and_oil["tankWidth"], 285)
        self.assertEqual(tank_and_oil["tankHeight"], 615)
        self.assertEqual(tank_and_oil["radiatorHeight"], 400)
        self.assertEqual(tank_and_oil["radiatorWidth"], 226)
        self.assertEqual(tank_and_oil["radiatorSection"], 19)
        self.assertEqual(tank_and_oil["noOfRadiators"], 4)
        self.assertEqual(tank_and_oil["tankLoss"], 80)
        self.assertEqual(response.json()["results"]["hvWinding"]["tankLoss"], tank_and_oil["tankLoss"])
        self.assertEqual(tank_and_oil["capitalCost"], 151735)

    def test_api_uses_tank_override_inputs_in_tank_and_oil_results(self):
        payload = {
            "windings": "LV-HV",
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
            "tank": {
                "wdgToTankGap": 40,
                "connectionGap": 35,
                "topYokeToCoverGap": 80,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        tank_and_oil = response.json()["results"]["tankAndOil"]
        self.assertEqual(tank_and_oil["tankLength"], 715)
        self.assertEqual(tank_and_oil["tankWidth"], 325)
        self.assertEqual(tank_and_oil["tankHeight"], 635)
        self.assertEqual(tank_and_oil["wdgTankGap"], 40)
        self.assertEqual(tank_and_oil["connectionGap"], 35)
        self.assertEqual(tank_and_oil["topYokeCoverGap"], 80)

    def test_api_supports_pipe_cooling_branch_in_tank_and_oil_results(self):
        payload = {
            "windings": "LV-HV",
            "kVA": 1000,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
            "radiatorType": "PIPES",
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        tank_and_oil = response.json()["results"]["tankAndOil"]
        self.assertEqual(tank_and_oil["pipeLength"], 0.2)
        self.assertEqual(tank_and_oil["oilInRadiators"], 1)
        self.assertEqual(tank_and_oil["totalRadiatorWeight"], 1)
        self.assertIn("Pipe", tank_and_oil["coolingStatement"])

    def test_api_supports_corrugation_cooling_branch_in_tank_and_oil_results(self):
        payload = {
            "windings": "LV-HV",
            "kVA": 1000,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
            "radiatorType": "CORRUGATION",
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        tank_and_oil = response.json()["results"]["tankAndOil"]
        self.assertEqual(tank_and_oil["radiatorHeight"], 800)
        self.assertEqual(tank_and_oil["radiatorWidth"], 1)
        self.assertEqual(tank_and_oil["corrugationSlitsOnLength"], 38)
        self.assertEqual(tank_and_oil["corrugationSlitsOnWidth"], 12)
        self.assertEqual(tank_and_oil["totalRadiatorWeight"], 1)


class RadiatorSelectionTests(TestCase):
    def test_select_radiators_matches_vb_style_selection(self):
        result = select_radiators(
            kva=1000,
            cu_loss=12000,
            fe_loss=3000,
            tank_length=1500,
            tank_width=800,
            tank_height=1600,
            core_dia=500,
            temp_wdg=65,
            temp_top=50,
        )

        self.assertEqual(result["selectionText"], "1000 x 300 - 11 x 6")
        self.assertEqual(result["radiatorLength"], 1000)
        self.assertEqual(result["radiatorWidth"], 300)
        self.assertEqual(result["radiatorSections"], 11)
        self.assertEqual(result["radiatorBanks"], 6)
        self.assertEqual(result["temperatureDependenceFactor"], 280)
        self.assertEqual(result["radiatorArea"], 40.43)
        self.assertEqual(result["totalRadiatorWeight"], 412)
        self.assertEqual(result["totalRadiatorOil"], 168)

    def test_select_radiators_returns_nil_for_dry_type(self):
        result = select_radiators(
            kva=1000,
            cu_loss=12000,
            fe_loss=3000,
            tank_length=1500,
            tank_width=800,
            tank_height=1600,
            core_dia=500,
            temp_wdg=65,
            temp_top=50,
            dry_type=True,
        )

        self.assertEqual(result["selectionText"], " NIL ")
        self.assertEqual(result["radiatorSections"], 0)
        self.assertEqual(result["totalRadiatorWeight"], 0)

    def test_select_radiators_supports_pipe_cooling_branch(self):
        result = select_radiators(
            kva=1000,
            cu_loss=12000,
            fe_loss=3000,
            tank_length=1500,
            tank_width=800,
            tank_height=1600,
            core_dia=500,
            temp_wdg=65,
            temp_top=50,
            pipes_only=True,
            pipe_dia=38,
        )

        self.assertEqual(result["selectionText"], "38mm Pipes x 271.0 M ")
        self.assertEqual(result["pipeLength"], 271.0)
        self.assertEqual(result["radiatorSections"], 0)


class HighSideDistributionTests(TestCase):
    def setUp(self):
        self.lv_results = {
            "revisedVoltsPerTurn": 5.0,
            "lvTurnsPerPhase": 50.0,
            "lvVoltsPerPhase": 433.0,
        }
        self.hv_results = {
            "hvTurnsAtHighest": 140.0,
            "hvTurnsAtLowest": 100.0,
            "hvHighestTapVoltage": 11000.0,
            "hvLowestTapVoltage": 10000.0,
            "hvVoltsPerPhase": 10500.0,
            "hvTurnsPerTap": 10.0,
            "hvTurnsPerPhase": 120.0,
        }

    def test_2wdg_keeps_all_taps_in_hv_main(self):
        multi_winding = MultiWindings(
            windings="2 Wdg (LV and HV-Main)",
            tapStepPositive=2,
            tapStepNegative=2,
        )

        distribution = _get_high_side_distribution(multi_winding, self.lv_results, self.hv_results)

        self.assertEqual(distribution["hv"]["turns"], 140.0)
        self.assertEqual(distribution["hv"]["voltsPerPhase"], 11000.0)
        self.assertEqual(distribution["outer"]["turns"], 0.0)
        self.assertEqual(distribution["fine"]["turns"], 0.0)
        self.assertEqual(distribution["corse"]["turns"], 0.0)

    def test_3wdg_puts_all_taps_in_outer_only(self):
        multi_winding = MultiWindings(
            windings="3 Wdg (LV, HV-Main and Outer)",
            tapStepPositive=2,
            tapStepNegative=2,
        )

        distribution = _get_high_side_distribution(multi_winding, self.lv_results, self.hv_results)

        self.assertEqual(distribution["hv"]["turns"], 100.0)
        self.assertEqual(distribution["outer"]["turns"], 40.0)
        self.assertEqual(distribution["outer"]["taps"], 4.0)
        self.assertEqual(distribution["fine"]["turns"], 0.0)
        self.assertEqual(distribution["corse"]["turns"], 0.0)

    def test_4wdg_c_overflow_moves_remaining_taps_to_corse(self):
        multi_winding = MultiWindings(
            windings="4 Wdg (LV, HV-Main, Corse and Outer)",
            tapStepPositive=2,
            tapStepNegative=2,
        )
        multi_winding.outerWindings = Windings(turnsPerPhase=25.0)

        distribution = _get_high_side_distribution(multi_winding, self.lv_results, self.hv_results)

        self.assertEqual(distribution["outer"]["turns"], 20.0)
        self.assertEqual(distribution["outer"]["taps"], 2.0)
        self.assertEqual(distribution["corse"]["turns"], 20.0)
        self.assertEqual(distribution["corse"]["taps"], 2.0)
        self.assertEqual(distribution["fine"]["turns"], 0.0)

    def test_4wdg_f_overflow_moves_remaining_taps_to_fine(self):
        multi_winding = MultiWindings(
            windings="4 Wdg (LV, HV-Main, Fine and Outer)",
            tapStepPositive=2,
            tapStepNegative=2,
        )
        multi_winding.outerWindings = Windings(turnsPerPhase=35.0)

        distribution = _get_high_side_distribution(multi_winding, self.lv_results, self.hv_results)

        self.assertEqual(distribution["outer"]["turns"], 30.0)
        self.assertEqual(distribution["outer"]["taps"], 3.0)
        self.assertEqual(distribution["fine"]["turns"], 10.0)
        self.assertEqual(distribution["fine"]["taps"], 1.0)
        self.assertEqual(distribution["corse"]["turns"], 0.0)

    def test_5wdg_without_outer_limit_keeps_all_taps_in_outer(self):
        multi_winding = MultiWindings(
            windings="5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
            tapStepPositive=2,
            tapStepNegative=2,
        )

        distribution = _get_high_side_distribution(multi_winding, self.lv_results, self.hv_results)

        self.assertEqual(distribution["outer"]["turns"], 40.0)
        self.assertEqual(distribution["outer"]["taps"], 4.0)
        self.assertEqual(distribution["fine"]["turns"], 0.0)
        self.assertEqual(distribution["corse"]["turns"], 0.0)

    def test_5wdg_outer_overflow_moves_remaining_taps_to_fine_only(self):
        multi_winding = MultiWindings(
            windings="5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
            tapStepPositive=2,
            tapStepNegative=2,
        )
        multi_winding.outerWindings = Windings(turnsPerPhase=20.0)

        distribution = _get_high_side_distribution(multi_winding, self.lv_results, self.hv_results)

        self.assertEqual(distribution["outer"]["turns"], 20.0)
        self.assertEqual(distribution["outer"]["taps"], 2.0)
        self.assertEqual(distribution["fine"]["turns"], 20.0)
        self.assertEqual(distribution["fine"]["taps"], 2.0)
        self.assertEqual(distribution["corse"]["turns"], 0.0)


class TapDistributionIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_5wdg_disc_payload_with_high_gradients_does_not_raise_math_domain_error(self):
        payload = {
            "windingSelection": "5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
            "kVA": 1800,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 11000,
            "highVoltage": 33000,
            "tapStepsPercentage": 2.5,
            "tapStepPositive": 2,
            "tapStepNegative": 2,
            "lvWindingType": "DISC",
            "hvWindingType": "DISC",
            "corseWindingType": "Helical",
            "fineWindingType": "Helical",
            "outerWindingType": "Helical",
            "outerWindings": {
                "turnsPerPhase": 100,
            },
            "radialGaps": {
                "coreToLv": 5,
                "lvToHv": 10,
                "lvToCoarse": 8,
                "fineToCoarse": 6,
                "fineToOuter": 10,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.json()["results"]["tankAndOil"]["kw55"], 0)

    def test_5wdg_taps_do_not_backfill_corse_when_outer_overflows(self):
        payload = {
            "windingSelection": "5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
            "tapStepsPercentage": 2.5,
            "tapStepPositive": 2,
            "tapStepNegative": 2,
            "hvWindingType": "Helical",
            "corseWindingType": "Helical",
            "fineWindingType": "Helical",
            "outerWindingType": "Helical",
            "corseWindings": {
                "turnsPerPhase": 220,
            },
            "fineWindings": {
                "turnsPerPhase": 120,
            },
            "outerWindings": {
                "turnsPerPhase": 100,
            },
            "radialGaps": {
                "coreToLv": 5,
                "lvToHv": 10,
                "lvToCoarse": 8,
                "fineToCoarse": 6,
                "fineToOuter": 10,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        hv_turns_per_tap = response.json()["results"]["hvWinding"]["hvTurnsPerTap"]
        self.assertAlmostEqual(response.json()["results"]["outerWinding"]["turnsPerPhase"], hv_turns_per_tap, places=2)
        self.assertAlmostEqual(response.json()["results"]["fineWinding"]["turnsPerPhase"], hv_turns_per_tap * 3, places=2)
        self.assertEqual(response.json()["results"]["corseWinding"]["turnsPerPhase"], 0.0)


class VbMultiImpedanceTests(TestCase):
    def test_vb_multi_impedance_uses_actual_outermost_winding_for_radial_span(self):
        winding_data = [
            {
                "name": "lv",
                "windingType": "HELICAL",
                "turnsPerPhase": 10,
                "phaseCurrent": 100,
                "loadLoss": 0,
                "condIns": 1,
                "radialThickness": 11,
                "innerDiameter": 100,
                "outerDiameter": 120,
                "breadth": 10,
                "turnsPerLayer": 10,
                "axialParallel": 1,
                "windingLength": 100,
                "endClearance": 0,
                "ducts": 0,
                "ductSize": 0,
            },
            {
                "name": "hv",
                "windingType": "HELICAL",
                "turnsPerPhase": 40,
                "phaseCurrent": 10,
                "loadLoss": 0,
                "condIns": 2,
                "radialThickness": 12,
                "innerDiameter": 140,
                "outerDiameter": 160,
                "breadth": 10,
                "turnsPerLayer": 10,
                "axialParallel": 1,
                "windingLength": 100,
                "endClearance": 0,
                "gapFromPrevious": 10,
                "ducts": 0,
                "ductSize": 0,
            },
            {
                "name": "outer",
                "windingType": "HELICAL",
                "turnsPerPhase": 20,
                "phaseCurrent": 10,
                "loadLoss": 0,
                "condIns": 3,
                "radialThickness": 13,
                "innerDiameter": 200,
                "outerDiameter": 220,
                "breadth": 10,
                "turnsPerLayer": 10,
                "axialParallel": 1,
                "windingLength": 100,
                "endClearance": 0,
                "gapFromPrevious": 20,
                "ducts": 0,
                "ductSize": 0,
            },
        ]

        result = calculate_vb_multi_impedance(
            SimpleNamespace(kVA=100),
            winding_data,
            {"revisedVoltsPerTurn": 4},
            {},
            {"breakdown": {"pairs": []}},
        )

        self.assertAlmostEqual(result["b"], 6.1, places=2)

    def test_vb_multi_impedance_uses_actual_previous_winding_for_outer_gap_terms(self):
        winding_data = [
            {
                "name": "lv",
                "windingType": "HELICAL",
                "turnsPerPhase": 10,
                "phaseCurrent": 100,
                "loadLoss": 0,
                "condIns": 1,
                "radialThickness": 11,
                "innerDiameter": 100,
                "outerDiameter": 120,
                "breadth": 10,
                "turnsPerLayer": 10,
                "axialParallel": 1,
                "windingLength": 100,
                "endClearance": 0,
                "ducts": 0,
                "ductSize": 0,
            },
            {
                "name": "hv",
                "windingType": "HELICAL",
                "turnsPerPhase": 40,
                "phaseCurrent": 10,
                "loadLoss": 0,
                "condIns": 2,
                "radialThickness": 12,
                "innerDiameter": 140,
                "outerDiameter": 160,
                "breadth": 10,
                "turnsPerLayer": 10,
                "axialParallel": 1,
                "windingLength": 100,
                "endClearance": 0,
                "gapFromPrevious": 10,
                "ducts": 0,
                "ductSize": 0,
            },
            {
                "name": "outer",
                "windingType": "HELICAL",
                "turnsPerPhase": 20,
                "phaseCurrent": 10,
                "loadLoss": 0,
                "condIns": 3,
                "radialThickness": 13,
                "innerDiameter": 200,
                "outerDiameter": 220,
                "breadth": 10,
                "turnsPerLayer": 10,
                "axialParallel": 1,
                "windingLength": 100,
                "endClearance": 0,
                "gapFromPrevious": 20,
                "ducts": 0,
                "ductSize": 0,
            },
        ]

        result = calculate_vb_multi_impedance(
            SimpleNamespace(kVA=100),
            winding_data,
            {"revisedVoltsPerTurn": 4},
            {},
            {"breakdown": {"pairs": []}},
        )

        outer_terms = result["breakdown"]["vb"]["termBreakdown"]["outer"]
        self.assertAlmostEqual(outer_terms["delta"], 1.25, places=2)
        self.assertAlmostEqual(outer_terms["ddelta"], 18.0, places=2)

    def test_vb_multi_impedance_uses_scaled_outer_alpha_contribution(self):
        winding_data = [
            {
                "name": "lv",
                "windingType": "HELICAL",
                "turnsPerPhase": 10,
                "phaseCurrent": 100,
                "loadLoss": 0,
                "condIns": 1,
                "radialThickness": 11,
                "innerDiameter": 100,
                "outerDiameter": 120,
                "breadth": 10,
                "turnsPerLayer": 10,
                "axialParallel": 1,
                "windingLength": 100,
                "endClearance": 0,
                "ducts": 0,
                "ductSize": 0,
            },
            {
                "name": "hv",
                "windingType": "HELICAL",
                "turnsPerPhase": 40,
                "phaseCurrent": 10,
                "loadLoss": 0,
                "condIns": 2,
                "radialThickness": 12,
                "innerDiameter": 140,
                "outerDiameter": 160,
                "breadth": 10,
                "turnsPerLayer": 10,
                "axialParallel": 1,
                "windingLength": 100,
                "endClearance": 0,
                "gapFromPrevious": 10,
                "ducts": 0,
                "ductSize": 0,
            },
            {
                "name": "outer",
                "windingType": "HELICAL",
                "turnsPerPhase": 20,
                "phaseCurrent": 10,
                "loadLoss": 0,
                "condIns": 3,
                "radialThickness": 13,
                "innerDiameter": 200,
                "outerDiameter": 220,
                "breadth": 10,
                "turnsPerLayer": 10,
                "axialParallel": 1,
                "windingLength": 100,
                "endClearance": 0,
                "gapFromPrevious": 20,
                "ducts": 0,
                "ductSize": 0,
            },
        ]

        result = calculate_vb_multi_impedance(
            SimpleNamespace(kVA=100),
            winding_data,
            {"revisedVoltsPerTurn": 4},
            {},
            {"breakdown": {"pairs": []}},
        )

        outer_terms = result["breakdown"]["vb"]["termBreakdown"]["outer"]
        self.assertAlmostEqual(outer_terms["prodAlpha"], 0.78, places=2)
        self.assertEqual(result["ex"], 0.23)


class CoreMaterialSpecificLossTests(TestCase):
    def test_specific_loss_uses_core_material_csv_table(self):
        self.assertEqual(get_specific_loss("NipM4", 1.7, 50), 1.3)
        self.assertEqual(get_specific_loss("NipM4", 1.7, 60), 1.72)

    def test_specific_loss_respects_explicit_wkg_grade(self):
        self.assertEqual(get_specific_loss("NipM4", 1.7, 50, 2.22), 2.22)
