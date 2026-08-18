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
from api.services.circWdgService import (
    _get_high_side_distribution,
    _get_post_hv_gap_for_voltage,
    _resolve_post_hv_gap_to_previous,
)
from api.services.impedanceVbService import calculate_vb_multi_impedance
from api.services.numberUtils import next_integer
from api.services.windingFormulae import (
    displacement_volume,
    get_connection_weight,
    get_largest_blade,
    get_load_loss,
    get_procurement_weight,
    get_specific_loss,
    get_tank_height,
    get_tank_length,
    get_tank_width,
    select_radiators,
)


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

    def test_3wdg_outer_voltage_uses_actual_tap_span(self):
        payload = {
            "designId": "1234",
            "windingSelection": "3_WDG",
            "kVA": 10000,
            "kValue": 0.45,
            "fluxDensity": 1.52,
            "vectorGroup": "Dyn11",
            "lowVoltage": 11000,
            "highVoltage": 33000,
            "tapStepsPercentage": 2.5,
            "tapStepPositive": 2,
            "tapStepNegative": 6,
            "lvWindingType": "DISC",
            "hvWindingType": "DISC",
            "corseWindingType": "Helical",
            "fineWindingType": "Helical",
            "outerWindingType": "Helical",
            "lvCurrentDensity": 2.1,
            "hvCurrentDensity": 2.1,
            "outerCurrentDensity": 2,
            "core": {
                "coreDia": 445,
                "limbHt": 920,
            },
            "radialGaps": {
                "coreToLv": 10,
                "lvToHv": None,
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
        results = response.json()["results"]
        self.assertEqual(results["phaseVoltageDivision"]["outer"], 6600)
        self.assertEqual(results["outerWinding"]["voltsPerPhase"], 6600.0)
        self.assertEqual(results["calculatedRadialGaps"]["hvToOuter"], 18.0)
        self.assertEqual(results["outerWinding"]["noOfLayers"], 1.0)
        self.assertEqual(
            results["outerWinding"]["turnsPerLayer"],
            results["outerWinding"]["turnsPerPhase"],
        )
        self.assertEqual(results["outerWinding"]["fillingGap"], 20.0)
        self.assertEqual(results["fillingGaps"]["outer"], 20.0)
        self.assertEqual(response.json()["inputs"]["windingModels"]["outer"]["noOfLayers"], 1.0)
        self.assertEqual(
            response.json()["inputs"]["windingModels"]["outer"]["turnsPerLayer"],
            response.json()["inputs"]["windingModels"]["outer"]["turnsPerPhase"],
        )
        self.assertLessEqual(
            results["outerWinding"]["windingLength"],
            results["core"]["limbHt"]
            - results["outerWinding"]["endClearance"]
            - results["lvWinding"]["permaWoodRing"]
            - results["outerWinding"]["fillingGap"]
        )
        self.assertEqual(
            results["outerWinding"]["windingLength"]
            + results["outerWinding"]["endClearance"]
            + results["lvWinding"]["permaWoodRing"]
            + results["outerWinding"]["fillingGap"],
            results["core"]["limbHt"],
        )
        self.assertNotEqual(
            results["outerWinding"]["windingLength"],
            results["hvWinding"]["windingLength"],
        )
        self.assertNotEqual(
            results["outerWinding"]["endClearance"],
            results["hvWinding"]["endClearance"],
        )
        self.assertEqual(
            results["phaseVoltageDivision"]["outer"],
            int(
                results["hvWinding"]["hvHighestTapVoltage"]
                - results["hvWinding"]["hvLowestTapVoltage"]
            ),
        )

    def test_3wdg_outer_defaults_parallel_conductors_independently_from_hv_main(self):
        payload = {
            "designId": "1234",
            "windingSelection": "3_WDG",
            "kVA": 10000,
            "kValue": 0.45,
            "fluxDensity": 1.52,
            "vectorGroup": "Dyn11",
            "lowVoltage": 11000,
            "highVoltage": 33000,
            "tapStepsPercentage": 2.5,
            "tapStepPositive": 2,
            "tapStepNegative": 6,
            "lvWindingType": "DISC",
            "hvWindingType": "DISC",
            "corseWindingType": "Helical",
            "fineWindingType": "Helical",
            "outerWindingType": "Helical",
            "lvCurrentDensity": 2.1,
            "hvCurrentDensity": 2.1,
            "outerCurrentDensity": 2,
            "core": {
                "coreDia": 445,
                "limbHt": 920,
            },
            "radialGaps": {
                "coreToLv": 10,
                "lvToHv": None,
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
        results = response.json()["results"]
        self.assertEqual(results["hvWinding"]["radialParallelCond"], 3)
        self.assertEqual(results["outerWinding"]["radialParallelCond"], 1)
        self.assertEqual(results["outerWinding"]["axialParallelCond"], 1)
        self.assertEqual(
            response.json()["inputs"]["windingModels"]["outer"]["noInParallel"],
            "Rad 1 X Axi 1 = 1",
        )

    def test_3wdg_missing_hv_to_outer_uses_voltage_class_gap_for_outer_geometry(self):
        payload = {
            "designId": "1234",
            "windingSelection": "3_WDG",
            "kVA": 10000,
            "kValue": 0.45,
            "fluxDensity": 1.52,
            "vectorGroup": "Dyn11",
            "lowVoltage": 11000,
            "highVoltage": 33000,
            "tapStepsPercentage": 2.5,
            "tapStepPositive": 2,
            "tapStepNegative": 6,
            "lvWindingType": "DISC",
            "hvWindingType": "DISC",
            "outerWindingType": "Helical",
            "lvCurrentDensity": 2.1,
            "hvCurrentDensity": 2.1,
            "outerCurrentDensity": 2,
            "core": {
                "coreDia": 445,
                "limbHt": 920,
            },
            "radialGaps": {
                "coreToLv": 10,
                "lvToHv": None,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        outer_results = response.json()["results"]["outerWinding"]
        self.assertEqual(response.json()["results"]["calculatedRadialGaps"]["hvToOuter"], 18.0)
        self.assertEqual(outer_results["seedDimensions"]["gapToPrevious"], 18.0)
        self.assertEqual(
            outer_results["innerDiameter"],
            outer_results["seedDimensions"]["previousOuterDiameter"] + 36.0,
        )

    def test_3wdg_explicit_hv_to_outer_gap_overrides_voltage_class_gap(self):
        payload = {
            "windingSelection": "3_WDG",
            "kVA": 10000,
            "kValue": 0.45,
            "fluxDensity": 1.52,
            "vectorGroup": "Dyn11",
            "lowVoltage": 11000,
            "highVoltage": 33000,
            "tapStepsPercentage": 2.5,
            "tapStepPositive": 2,
            "tapStepNegative": 6,
            "lvWindingType": "DISC",
            "hvWindingType": "DISC",
            "outerWindingType": "Helical",
            "lvCurrentDensity": 2.1,
            "hvCurrentDensity": 2.1,
            "outerCurrentDensity": 2,
            "core": {
                "coreDia": 445,
                "limbHt": 920,
            },
            "radialGaps": {
                "coreToLv": 10,
                "lvToHv": None,
                "hvToOuter": 10,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        outer_results = response.json()["results"]["outerWinding"]
        self.assertEqual(response.json()["results"]["calculatedRadialGaps"]["hvToOuter"], 10.0)
        self.assertEqual(outer_results["seedDimensions"]["gapToPrevious"], 10.0)
        self.assertEqual(
            outer_results["innerDiameter"],
            outer_results["seedDimensions"]["previousOuterDiameter"] + 20.0,
        )

    def test_multi_wdg_calculator_honors_user_core_dia_input(self):
        payload = {
            "kVA": 100,
            "kValue": 0.45,
            "frequency": 50,
            "fluxDensity": 1.7,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
        }

        auto_response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(auto_response.status_code, 200)

        payload["core"] = {"coreDia": 220}
        user_core_response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(user_core_response.status_code, 200)
        self.assertNotEqual(auto_response.json()["results"]["core"]["coreDia"], 220)
        self.assertEqual(user_core_response.json()["results"]["core"]["coreDia"], 220)
        self.assertEqual(user_core_response.json()["results"]["coilDimensions"]["coreDia"], 220)
        self.assertNotEqual(
            auto_response.json()["results"]["revisedVoltsPerTurn"],
            user_core_response.json()["results"]["revisedVoltsPerTurn"],
        )
        self.assertNotEqual(
            auto_response.json()["results"]["core"]["area"],
            user_core_response.json()["results"]["core"]["area"],
        )

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
                "hvToCorse": 8,
                "corseToFine": 6,
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
        self.assertIn("hvToCorse", insulation)
        self.assertIn("corseToFine", insulation)
        self.assertIn("fineToOuter", insulation)
        self.assertNotIn("hvHv", insulation)

    def test_4wdg_c_first_extra_gap_uses_hv_to_corse_pair(self):
        payload = {
            "windingSelection": "4 Wdg (LV, HV-Main, Corse and Outer)",
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
            "lvWindingType": "Helical",
            "hvWindingType": "Disc",
            "corseWindingType": "Helical",
            "outerWindingType": "Helical",
            "radialGaps": {
                "coreToLv": 5,
                "lvToHv": 10,
                "hvToCorse": 8,
                "corseToOuter": 10,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["results"]["insulation"]["hvToCorse"],
            "1mm x 3 PB + rest Oil",
        )

    def test_4wdg_c_accepts_numeric_tap_inputs_as_strings(self):
        payload = {
            "designId": None,
            "windingSelection": "4 Wdg (LV, HV-Main, Corse and Outer)",
            "kVA": 25000,
            "kValue": 0.45,
            "fluxDensity": 1.6888,
            "vectorGroup": "Dyn11",
            "lowVoltage": 33000,
            "highVoltage": 132000,
            "tapStepsPercentage": "1.25",
            "tapStepPositive": "4",
            "tapStepNegative": 12,
            "lvWindingType": "DISC",
            "hvWindingType": "DISC",
            "corseWindingType": "HELICAL",
            "fineWindingType": "HELICAL",
            "outerWindingType": "HELICAL",
            "lvCurrentDensity": 3.63,
            "hvCurrentDensity": 3.63,
            "corseCurrentDensity": 3.63,
            "fineCurrentDensity": 4.24,
            "outerCurrentDensity": 3.63,
            "core": {
                "coreDia": None,
                "limbHt": None,
            },
            "outerWindings": {
                "turnsPerPhase": None,
            },
            "cost": {
                "copperCostPerKg": 850,
                "aluminiumCostPerKg": 235,
                "coreCostPerKg": 250,
                "steelCostPerKg": 90,
                "oilCostPerKg": 80,
                "insulationCostPerKg": 170,
                "radiatorCostPerKg": 200,
            },
            "radialGaps": {
                "coreToLv": None,
                "lvToHv": None,
                "lvToCoarse": None,
                "fineToCoarse": None,
                "fineToOuter": None,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["selectedCode"], "4_WDG_C")
        self.assertEqual(response.json()["inputs"]["tapSteps"]["percentage"], 1.25)
        self.assertEqual(response.json()["inputs"]["tapSteps"]["positive"], 4)
        self.assertEqual(response.json()["inputs"]["tapSteps"]["negative"], 12)

    def test_4wdg_f_first_extra_gap_uses_hv_to_fine_pair(self):
        payload = {
            "windingSelection": "4 Wdg (LV, HV-Main, Fine and Outer)",
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
            "lvWindingType": "Helical",
            "hvWindingType": "Disc",
            "fineWindingType": "Helical",
            "outerWindingType": "Helical",
            "radialGaps": {
                "coreToLv": 5,
                "lvToHv": 10,
                "hvToFine": 8,
                "fineToOuter": 10,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["results"]["insulation"]["hvToFine"],
            "1mm x 3 PB + rest Oil",
        )

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
                "hvToCorse": 8,
                "corseToFine": 6,
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
                "hvToCorse": 8,
                "corseToFine": 6,
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
                "hvToCorse": 8,
                "corseToFine": 6,
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
        hv_end_clearance = response.json()["results"]["hvWinding"]["endClearance"]
        corse_end_clearance = response.json()["results"]["corseWinding"]["endClearance"]
        fine_end_clearance = response.json()["results"]["fineWinding"]["endClearance"]
        outer_end_clearance = response.json()["results"]["outerWinding"]["endClearance"]
        self.assertEqual(response.json()["results"]["fillingGaps"]["corse"], 20.0)
        self.assertEqual(response.json()["results"]["fillingGaps"]["fine"], 20.0)
        self.assertEqual(response.json()["results"]["fillingGaps"]["outer"], 20.0)
        self.assertEqual(response.json()["results"]["corseWinding"]["fillingGap"], 20.0)
        self.assertEqual(response.json()["results"]["fineWinding"]["fillingGap"], 20.0)
        self.assertEqual(response.json()["results"]["outerWinding"]["fillingGap"], 20.0)
        self.assertEqual(response.json()["results"]["outerWinding"]["noOfLayers"], 1.0)
        self.assertEqual(
            response.json()["results"]["outerWinding"]["turnsPerLayer"],
            response.json()["results"]["outerWinding"]["turnsPerPhase"],
        )
        self.assertEqual(response.json()["inputs"]["windingModels"]["outer"]["noOfLayers"], 1.0)
        self.assertEqual(
            response.json()["inputs"]["windingModels"]["outer"]["turnsPerLayer"],
            response.json()["inputs"]["windingModels"]["outer"]["turnsPerPhase"],
        )
        self.assertEqual(
            response.json()["inputs"]["windingModels"]["outer"]["endClearances"],
            outer_end_clearance,
        )
        for winding_name in ("corse", "fine", "outer"):
            winding = response.json()["results"][f"{winding_name}Winding"]
            self.assertEqual(
                winding["windingLength"]
                + winding["endClearance"]
                + response.json()["results"]["lvWinding"]["permaWoodRing"]
                + winding["fillingGap"],
                response.json()["results"]["core"]["limbHt"],
            )
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
                "hvToCorse": 8,
                "corseToFine": 6,
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

    def test_multi_wdg_hv_main_load_loss_uses_direct_normal_and_lowest_formula(self):
        multi_winding = MultiWindings(
            kVA=100,
            kValue=0.45,
            vectorGroup="Dyn11",
            lowVoltage=433,
            highVoltage=11000,
            windings="5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
        )
        multi_winding.hvWindingType = "Helical"
        multi_winding.hvConductorMaterial = "COPPER"

        lv_results = calculate_lv_windings(multi_winding)
        hv_results = calculate_hv_windings(multi_winding, lv_results)

        expected_normal = next_integer(
            get_load_loss(
                multi_winding.hvConductorMaterial,
                hv_results["hvBareWeight"],
                hv_results["hVRevisedCurrDenAtNormal"],
                hv_results["%hvStrayLoss"],
            )
        )
        expected_lowest = next_integer(
            get_load_loss(
                multi_winding.hvConductorMaterial,
                hv_results["hvBareWeight"],
                hv_results["hVRevisedCurrDenAtLowest"],
                hv_results["%hvStrayLoss"],
            )
        )

        self.assertEqual(hv_results["hvLoadLossAtNormal"], expected_normal)
        self.assertEqual(hv_results["hvLoadLossAtLowest"], expected_lowest)

    def test_3wdg_disc_hv_main_does_not_breach_available_limb_height(self):
        payload = {
            "designId": "1234",
            "windingSelection": "3_WDG",
            "kVA": 10000,
            "kValue": 0.45,
            "fluxDensity": 1.52,
            "vectorGroup": "Dyn11",
            "lowVoltage": 11000,
            "highVoltage": 33000,
            "tapStepsPercentage": 2.5,
            "tapStepPositive": 2,
            "tapStepNegative": 6,
            "lvWindingType": "DISC",
            "hvWindingType": "DISC",
            "corseWindingType": "Helical",
            "fineWindingType": "Helical",
            "outerWindingType": "Helical",
            "lvCurrentDensity": 2.1,
            "hvCurrentDensity": 2.1,
            "outerCurrentDensity": 2,
            "core": {
                "coreDia": 445,
                "limbHt": 920,
            },
            "radialGaps": {
                "coreToLv": 10,
                "lvToHv": None,
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
        results = response.json()["results"]
        hv_winding = results["hvWinding"]
        self.assertLessEqual(
            hv_winding["windingLength"] + hv_winding["endClearance"] + results["lvWinding"]["permaWoodRing"],
            payload["core"]["limbHt"],
        )

    def test_3wdg_disc_main_stray_loss_loops_reduce_hv_and_lv_losses_without_changing_lengths(self):
        payload = {
            "designId": "1234",
            "windingSelection": "3_WDG",
            "kVA": 10000,
            "kValue": 0.45,
            "fluxDensity": 1.52,
            "vectorGroup": "Dyn11",
            "lowVoltage": 11000,
            "highVoltage": 33000,
            "tapStepsPercentage": 2.5,
            "tapStepPositive": 2,
            "tapStepNegative": 6,
            "lvWindingType": "DISC",
            "hvWindingType": "DISC",
            "corseWindingType": "Helical",
            "fineWindingType": "Helical",
            "outerWindingType": "Helical",
            "lvCurrentDensity": 2.1,
            "hvCurrentDensity": 2.1,
            "outerCurrentDensity": 2,
            "core": {
                "coreDia": 445,
                "limbHt": 920,
            },
            "radialGaps": {
                "coreToLv": 10,
                "lvToHv": None,
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
        results = response.json()["results"]
        self.assertEqual(results["hvWinding"]["radialParallelCond"], 3)
        self.assertLess(results["hvWinding"]["strayLoss"], 10.0)
        self.assertEqual(results["hvWinding"]["windingLength"], 803)
        self.assertEqual(results["hvWinding"]["endClearance"], 91.0)
        self.assertEqual(results["lvWinding"]["lvRadialParallelConductors"], 9)
        self.assertLess(results["lvWinding"]["%lvStrayLoss"], 10.0)
        self.assertEqual(results["lvWinding"]["lvWindingLength"], 802)
        self.assertEqual(results["lvWinding"]["lvEndClearance"], 93)

    def test_multi_wdg_response_exposes_hv_main_density_and_load_loss_fields(self):
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
                "hvToCorse": 8,
                "corseToFine": 6,
                "fineToOuter": 10,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        hv_winding = response.json()["results"]["hvWinding"]
        self.assertIn("hvCurrentAtLowest", hv_winding)
        self.assertIn("hVRevisedCurrDenAtNormal", hv_winding)
        self.assertIn("hVRevisedCurrDenAtLowest", hv_winding)
        self.assertIn("hvLoadLossAtNormal", hv_winding)
        self.assertIn("hvLoadLossAtLowest", hv_winding)
        self.assertIn("hvDiscDuctsSize", hv_winding)
        impedance = response.json()["results"]["impedance"]
        self.assertIn("lowestTap", impedance)
        self.assertIn("normalTap", impedance)
        self.assertIn("highestTap", impedance)
        self.assertEqual(impedance["normalTap"]["ek"], impedance["ek"])
        self.assertIn("includedHvWindings", impedance["lowestTap"])
        self.assertIn("includedHvWindings", impedance["normalTap"])
        self.assertIn("includedHvWindings", impedance["highestTap"])

    def test_multi_wdg_impedance_delta_uses_lv_to_hv_gap(self):
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
                "hvToCorse": 8,
                "corseToFine": 6,
                "fineToOuter": 10,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        hv_dims = results["coilDimensions"]["windingDimensions"]["hv"]
        self.assertEqual(hv_dims["gapFromPrevious"], 10)
        normal_tap = results["impedance"]["normalTap"]
        expected_delta = 10 + (
            (results["lvWinding"]["lvConductorInsulation"] + results["hvWinding"]["conductorInsulation"]) / 2
        )
        self.assertEqual(normal_tap["delta"], round(expected_delta, 2))

    def test_disc_arrangements_are_visible_in_response_json(self):
        payload = {
            "windingSelection": "3 Wdg (LV, HV-Main and Outer)",
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
            "tapStepsPercentage": 2.5,
            "tapStepPositive": 2,
            "tapStepNegative": 2,
            "lvWindingType": "Disc",
            "hvWindingType": "Disc",
            "outerWindingType": "Disc",
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
        results = response.json()["results"]
        self.assertIn("lvDiscArrangement", results["lvWinding"])
        self.assertIn("hvDiscArrangement", results["hvWinding"])
        self.assertIn("discArrangement", results["outerWinding"])
        self.assertIn("F +", results["lvWinding"]["lvDiscArrangement"])
        self.assertIn("F +", results["hvWinding"]["hvDiscArrangement"])
        self.assertIn("F +", results["outerWinding"]["discArrangement"])

    def test_multi_wdg_response_exposes_core_loss(self):
        payload = {
            "windingSelection": "5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
            "hvWindingType": "Helical",
            "corseWindingType": "Helical",
            "fineWindingType": "Helical",
            "outerWindingType": "Helical",
            "radialGaps": {
                "coreToLv": 5,
                "lvToHv": 10,
                "hvToCorse": 8,
                "corseToFine": 6,
                "fineToOuter": 10,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.json()["results"]["coreLoss"], 0)
        self.assertEqual(response.json()["results"]["core"]["coreLoss"], response.json()["results"]["coreLoss"])
        self.assertEqual(response.json()["results"]["hvWinding"]["coreLoss"], response.json()["results"]["coreLoss"])

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
                "hvToCorse": 8,
                "corseToFine": 6,
                "fineToOuter": 10,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        for winding_name in ("corse", "fine"):
            model = response.json()["inputs"]["windingModels"][winding_name]
            result = results[f"{winding_name}Winding"]
            self.assertEqual(model["turnsPerLayer"], result["turnsPerLayer"])
            self.assertEqual(model["noOfLayers"], result["noOfLayers"])
            self.assertNotEqual(model["noOfLayers"], model["turnsPerPhase"])
            self.assertEqual(model["endClearances"], result["endClearance"])
            self.assertGreater(result["turnsPerLayer"], 0)
            self.assertGreater(result["noOfLayers"], 0)
            self.assertEqual(result["fillingGap"], 20.0)
            self.assertEqual(
                result["windingLength"]
                + result["endClearance"]
                + results["lvWinding"]["permaWoodRing"]
                + result["fillingGap"],
                results["core"]["limbHt"],
            )

        outer_model = response.json()["inputs"]["windingModels"]["outer"]
        outer_result = results["outerWinding"]
        self.assertEqual(outer_model["turnsPerLayer"], outer_result["turnsPerLayer"])
        self.assertEqual(outer_model["endClearances"], outer_result["endClearance"])
        self.assertEqual(outer_model["noOfLayers"], 1.0)
        self.assertEqual(outer_result["turnsPerLayer"], outer_result["turnsPerPhase"])
        self.assertEqual(outer_result["fillingGap"], 20.0)
        self.assertEqual(
            outer_result["windingLength"]
            + outer_result["endClearance"]
            + results["lvWinding"]["permaWoodRing"]
            + outer_result["fillingGap"],
            results["core"]["limbHt"],
        )
        self.assertEqual(outer_result["noOfLayers"], 1.0)
        self.assertEqual(results["fillingGaps"], {"corse": 20.0, "fine": 20.0, "outer": 20.0})

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
                "hvToCorse": 8,
                "corseToFine": 6,
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

    def test_lv_disc_winding_service_exposes_disc_arrangement(self):
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
        multi_winding.lvWindingType = "DISC"
        multi_winding.lvWindings = Windings(endClearances=40)

        lv_results = calculate_lv_windings(multi_winding)

        self.assertIn("lvDiscArrangement", lv_results)
        self.assertIn("F +", lv_results["lvDiscArrangement"])
        self.assertGreaterEqual(lv_results["lvNoOfSpacers"], 0)
        self.assertGreaterEqual(lv_results["lvWidthOfSpacer"], 0)

    def test_lv_disc_forces_single_axial_parallel_conductor(self):
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
        multi_winding.lvWindingType = "DISC"
        multi_winding.lvWindings = Windings(endClearances=40, axialParallelCond=4)

        lv_results = calculate_lv_windings(multi_winding)

        self.assertEqual(lv_results["lvAxialParallelConductors"], 1)

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
        self.assertIn("hvDiscArrangement", disc_results)
        self.assertIn("F +", disc_results["hvDiscArrangement"])

    def test_hv_disc_forces_single_axial_parallel_conductor(self):
        multi_winding = MultiWindings(
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
        multi_winding.hvWindingType = "DISC"
        multi_winding.hvWindings = Windings(axialParallelCond=5)

        lv_results = calculate_lv_windings(multi_winding)
        hv_results = calculate_hv_windings(multi_winding, lv_results)

        self.assertEqual(hv_results["hvAxialParallelConductors"], 1)

    def test_hv_disc_sizes_conductor_from_disc_count_without_breaching_available_length(self):
        multi_winding = MultiWindings(
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
        multi_winding.hvWindingType = "DISC"
        multi_winding.core = SimpleNamespace(limbHt=900)
        multi_winding.hvWindings = Windings(endClearances=60)

        lv_results = calculate_lv_windings(multi_winding)
        hv_results = calculate_hv_windings(multi_winding, lv_results)

        available_winding_length = 900 - 60 - lv_results["permaWoodRing"]
        self.assertLessEqual(hv_results["hvWindingLength"], available_winding_length)
        self.assertAlmostEqual(
            hv_results["hvRevisedCondCrossSection"],
            hv_results["hvBreadth"] * hv_results["hvHeight"],
            places=2,
        )

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

    def test_hv_taller_than_lv_governs_final_limb_height(self):
        multi_winding = MultiWindings(
            kVA=10000,
            kValue=0.45,
            frequency=50,
            fluxDensity=1.7,
            vectorGroup="Dyn11",
            lowVoltage=433,
            highVoltage=11000,
            lvConductorMaterial="COPPER",
            hvConductorMaterial="COPPER",
        )
        multi_winding.hvWindingType = "HELICAL"
        multi_winding.hvWindings = Windings(endClearances=20, ducts=1)

        initial_lv_results = calculate_lv_windings(multi_winding)
        intermediate_hv_results = calculate_hv_windings(multi_winding, initial_lv_results)
        initial_active_part_height = (
            (2 * initial_lv_results["coreDiameter"])
            + initial_lv_results["windowHeight"]
        )

        self.assertEqual(
            intermediate_hv_results["coreLength"],
            (2 * initial_lv_results["coreDiameter"])
            + (3 * initial_lv_results["windowHeight"])
            + (4 * intermediate_hv_results["centerDistance"]),
        )
        self.assertTrue(
            intermediate_hv_results["activePartSize"].endswith(
                f"{initial_active_part_height} H mm"
            )
        )

        results = calculate_circ_wdg(multi_winding)["results"]
        lv_results = results["lvWinding"]
        hv_results = results["hvWinding"]
        expected_limb_height = (
            hv_results["hvWindingLength"]
            + hv_results["hvEndClearance"]
            + lv_results["permaWoodRing"]
        )

        self.assertGreater(hv_results["hvWindingLength"], lv_results["lvWindingLength"])
        self.assertGreater(expected_limb_height, lv_results["windowHeight"])
        self.assertEqual(results["core"]["limbHt"], expected_limb_height)
        self.assertEqual(
            hv_results["coreLength"],
            (2 * results["core"]["coreDia"])
            + (3 * expected_limb_height)
            + (4 * results["coilDimensions"]["centerDistance"]),
        )
        self.assertEqual(
            hv_results["activePartSize"],
            results["coilDimensions"]["activePartSize"],
        )
        self.assertTrue(
            results["coilDimensions"]["activePartSize"].endswith(
                f"{(2 * results['core']['coreDia']) + expected_limb_height} H mm"
            )
        )

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
        fine_seed = {"previousWinding": "corse", "previousOuterDiameter": 280.0, "previousRadialThickness": 10.0, "previousWindingLength": 420.0, "gapField": "corseToFine", "gapToPrevious": 6.0}
        corse_seed = {"previousWinding": "hv", "previousOuterDiameter": 240.0, "previousRadialThickness": 18.0, "previousWindingLength": 420.0, "gapField": "hvToCorse", "gapToPrevious": 8.0}
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
        self.assertIn("discArrangement", outer_results)
        self.assertIn("F +", outer_results["discArrangement"])
        self.assertEqual(outer_results["noOfLayers"], 1.0)
        self.assertEqual(outer_results["turnsPerLayer"], outer_results["turnsPerPhase"])
        self.assertEqual(outer_results["fillingGap"], 20.0)
        self.assertTrue(fine_results["implemented"])
        self.assertEqual(fine_results["windingType"], "HELICAL")
        self.assertEqual(fine_results["voltsPerPhase"], 270)
        self.assertEqual(fine_results["fillingGap"], 20.0)
        self.assertTrue(corse_results["implemented"])
        self.assertEqual(corse_results["windingType"], "HELICAL")
        self.assertEqual(corse_results["voltsPerPhase"], 540)
        self.assertEqual(corse_results["fillingGap"], 20.0)
        self.assertEqual(outer_results["axialParallelCond"], 1)

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
        self.assertEqual(helical_results["noOfLayers"], 1.0)
        self.assertEqual(disc_results["noOfLayers"], 1.0)
        self.assertEqual(helical_results["turnsPerLayer"], helical_results["turnsPerPhase"])
        self.assertEqual(disc_results["turnsPerLayer"], disc_results["turnsPerPhase"])
        self.assertNotEqual(helical_results["breadth"], disc_results["breadth"])
        self.assertNotEqual(helical_results["windingLength"], disc_results["windingLength"])
        self.assertNotEqual(helical_results["loadLoss"], disc_results["loadLoss"])

    def test_outer_disc_stray_loss_loop_updates_radial_parallels_without_changing_length_or_clearance(self):
        multi_winding = MultiWindings(
            kVA=1800,
            kValue=0.45,
            vectorGroup="Dyn11",
            lowVoltage=11000,
            highVoltage=33000,
            windings="5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
        )
        multi_winding.lvWindingType = "DISC"
        multi_winding.hvWindingType = "DISC"
        multi_winding.outerWindingType = "DISC"
        multi_winding.outerCurrentDensity = 2

        lv_results = calculate_lv_windings(multi_winding)
        hv_results = calculate_hv_windings(multi_winding, lv_results)
        outer_seed = {
            "previousWinding": "fine",
            "previousOuterDiameter": 700.0,
            "previousRadialThickness": 20.0,
            "previousWindingLength": 420.0,
            "previousEndClearance": 80.0,
            "gapField": "fineToOuter",
            "gapToPrevious": 10.0,
        }

        fixed_parallel = Windings(endClearances=60, ducts=None, ductSize=None, isEnamel=False, radialParallelCond=1)
        auto_parallel = Windings(endClearances=60, ducts=None, ductSize=None, isEnamel=False)

        multi_winding.outerWindings = fixed_parallel
        fixed_results = calculate_outer_windings(
            multi_winding,
            hv_results,
            outer_seed,
            100,
            500,
            limb_height=450,
            perma_wood_ring=lv_results["permaWoodRing"],
        )

        multi_winding.outerWindings = auto_parallel
        auto_results = calculate_outer_windings(
            multi_winding,
            hv_results,
            outer_seed,
            100,
            500,
            limb_height=450,
            perma_wood_ring=lv_results["permaWoodRing"],
        )

        self.assertEqual(fixed_results["radialParallelCond"], 1)
        self.assertGreater(auto_results["radialParallelCond"], fixed_results["radialParallelCond"])
        self.assertLess(auto_results["height"], fixed_results["height"])
        self.assertLessEqual(auto_results["strayLoss"], 10.0)
        self.assertEqual(auto_results["windingLength"], fixed_results["windingLength"])
        self.assertEqual(auto_results["endClearance"], fixed_results["endClearance"])

    def test_hv_disc_winding_model_forces_single_axial_parallel_in_response(self):
        payload = {
            "windingSelection": "3 Wdg (LV, HV-Main and Outer)",
            "kVA": 100,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 433,
            "highVoltage": 11000,
            "tapStepSize": 2.5,
            "tapChangerStep": 9,
            "tapChangerPercentage": 2.5,
            "tapChangerType": "OLTC",
            "positiveTap": 5,
            "negativeTap": 15,
            "hvWindingType": "Disc",
            "outerWindingType": "Disc",
            "hvWindings": {
                "axialParallelCond": 5,
            },
            "outerWindings": {
                "axialParallelCond": 4,
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
        hv_model = response.json()["inputs"]["windingModels"]["hv"]
        self.assertEqual(hv_model["axialParallelCond"], 1)
        self.assertEqual(
            hv_model["noInParallel"],
            f'Rad {hv_model["radialParallelCond"]} X Axi 1 = {hv_model["radialParallelCond"]}',
        )

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

    def test_3wdg_tank_and_oil_uses_outermost_geometry_and_sums_high_side_connections(self):
        payload = {
            "designId": "1234",
            "windingSelection": "3_WDG",
            "kVA": 10000,
            "kValue": 0.45,
            "fluxDensity": 1.52,
            "vectorGroup": "Dyn11",
            "lowVoltage": 11000,
            "highVoltage": 33000,
            "tapStepsPercentage": 2.5,
            "tapStepPositive": 2,
            "tapStepNegative": 6,
            "lvWindingType": "DISC",
            "hvWindingType": "DISC",
            "corseWindingType": "Helical",
            "fineWindingType": "Helical",
            "outerWindingType": "Helical",
            "lvCurrentDensity": 2.1,
            "hvCurrentDensity": 2.1,
            "outerCurrentDensity": 2,
            "core": {
                "coreDia": 445,
                "limbHt": 920,
            },
            "radialGaps": {
                "coreToLv": 10,
                "lvToHv": None,
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
        results = response.json()["results"]
        tank_and_oil = results["tankAndOil"]
        hv_winding = results["hvWinding"]
        outer_winding = results["outerWinding"]

        expected_hv_connection_weight = round(
            get_connection_weight(hv_winding["condCrossSec"], "COPPER", 1000)
            + get_connection_weight(outer_winding["condCrossSec"], "COPPER", 1000),
            1,
        )
        expected_hv_connection_volume = round(
            displacement_volume(get_connection_weight(hv_winding["condCrossSec"], "COPPER", 1000), 8.89)
            + displacement_volume(get_connection_weight(outer_winding["condCrossSec"], "COPPER", 1000), 8.89),
            2,
        )
        expected_total_conductor_weight = next_integer(
            results["lvWinding"]["lvProcurementWeight"]
            + get_procurement_weight(hv_winding["insulatedWeight"], hv_winding["noOfConductors"])
            + get_procurement_weight(outer_winding["insulatedWeight"], outer_winding["noOfConductors"])
            + tank_and_oil["lvConnectionWeight"]
            + expected_hv_connection_weight
        )

        self.assertEqual(tank_and_oil["outermostWinding"], "outer")
        self.assertEqual(tank_and_oil["outermostOuterDiameter"], results["coilDimensions"]["outermostOD"])
        self.assertEqual(
            tank_and_oil["tankLength"],
            get_tank_length(
                results["coilDimensions"]["outermostOD"],
                results["core"]["cenDist"],
                payload["highVoltage"],
                payload["kVA"],
                False,
                tank_and_oil["wdgTankGap"],
            ),
        )
        self.assertEqual(
            tank_and_oil["tankWidth"],
            get_tank_width(
                results["coilDimensions"]["outermostOD"],
                payload["highVoltage"],
                payload["kVA"],
                tank_and_oil["connectionGap"],
                tank_and_oil["wdgTankGap"],
            ),
        )
        self.assertEqual(
            tank_and_oil["tankHeight"],
            get_tank_height(
                results["core"]["limbHt"],
                get_largest_blade(results["core"]["coreDia"]),
                payload["kVA"],
                payload["highVoltage"],
                False,
                payload["tapStepsPercentage"],
                tank_and_oil["topYokeCoverGap"],
            ),
        )
        self.assertEqual(tank_and_oil["hvConnectionWeight"], expected_hv_connection_weight)
        self.assertEqual(tank_and_oil["volumeConnectionWeight"], expected_hv_connection_volume + round(displacement_volume(tank_and_oil["lvConnectionWeight"], 8.89), 2))
        self.assertEqual(tank_and_oil["totalConductorWeight"], expected_total_conductor_weight)
        self.assertEqual(
            tank_and_oil["totalConnectionWeight"],
            next_integer(
                tank_and_oil["tapInsWeight"]
                + tank_and_oil["tapLeadWeight"]
                + tank_and_oil["lvConnectionWeight"]
                + tank_and_oil["hvConnectionWeight"]
            ),
        )


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

    def test_3wdg_puts_full_tap_range_in_outer(self):
        multi_winding = MultiWindings(
            windings="3 Wdg (LV, HV-Main and Outer)",
            tapStepPositive=2,
            tapStepNegative=2,
        )

        distribution = _get_high_side_distribution(multi_winding, self.lv_results, self.hv_results)

        self.assertEqual(distribution["hv"]["turns"], 100.0)
        self.assertEqual(distribution["outer"]["turns"], 40.0)
        self.assertEqual(distribution["outer"]["voltsPerPhase"], 1000.0)
        self.assertEqual(distribution["outer"]["taps"], 4.0)
        self.assertEqual(distribution["fine"]["turns"], 0.0)
        self.assertEqual(distribution["corse"]["turns"], 0.0)

    def test_4wdg_c_splits_tap_range_evenly_between_corse_and_outer(self):
        multi_winding = MultiWindings(
            windings="4 Wdg (LV, HV-Main, Corse and Outer)",
            tapStepPositive=2,
            tapStepNegative=2,
        )

        distribution = _get_high_side_distribution(multi_winding, self.lv_results, self.hv_results)

        self.assertEqual(distribution["outer"]["turns"], 20.0)
        self.assertEqual(distribution["outer"]["voltsPerPhase"], 500.0)
        self.assertEqual(distribution["outer"]["taps"], 2.0)
        self.assertEqual(distribution["corse"]["turns"], 20.0)
        self.assertEqual(distribution["corse"]["voltsPerPhase"], 500.0)
        self.assertEqual(distribution["corse"]["taps"], 2.0)
        self.assertEqual(distribution["fine"]["turns"], 0.0)

    def test_4wdg_f_splits_tap_range_evenly_between_fine_and_outer(self):
        multi_winding = MultiWindings(
            windings="4 Wdg (LV, HV-Main, Fine and Outer)",
            tapStepPositive=2,
            tapStepNegative=2,
        )

        distribution = _get_high_side_distribution(multi_winding, self.lv_results, self.hv_results)

        self.assertEqual(distribution["outer"]["turns"], 20.0)
        self.assertEqual(distribution["outer"]["voltsPerPhase"], 500.0)
        self.assertEqual(distribution["outer"]["taps"], 2.0)
        self.assertEqual(distribution["fine"]["turns"], 20.0)
        self.assertEqual(distribution["fine"]["voltsPerPhase"], 500.0)
        self.assertEqual(distribution["fine"]["taps"], 2.0)
        self.assertEqual(distribution["corse"]["turns"], 0.0)

    def test_5wdg_splits_tap_range_between_corse_fine_and_outer(self):
        multi_winding = MultiWindings(
            windings="5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
            tapStepPositive=2,
            tapStepNegative=2,
        )

        distribution = _get_high_side_distribution(multi_winding, self.lv_results, self.hv_results)

        self.assertEqual(distribution["outer"]["turns"], 10.0)
        self.assertEqual(distribution["outer"]["voltsPerPhase"], 250.0)
        self.assertEqual(distribution["outer"]["taps"], 1.0)
        self.assertEqual(distribution["fine"]["turns"], 10.0)
        self.assertEqual(distribution["fine"]["voltsPerPhase"], 250.0)
        self.assertEqual(distribution["fine"]["taps"], 1.0)
        self.assertEqual(distribution["corse"]["turns"], 20.0)
        self.assertEqual(distribution["corse"]["voltsPerPhase"], 500.0)
        self.assertEqual(distribution["corse"]["taps"], 2.0)


class PostHvGapSelectionTests(TestCase):
    def test_voltage_class_gap_table_matches_expected_thresholds(self):
        self.assertEqual(_get_post_hv_gap_for_voltage(500, 1100, "Dyn11"), 5.0)
        self.assertEqual(_get_post_hv_gap_for_voltage(750, 6600, "Dyn11"), 6.0)
        self.assertEqual(_get_post_hv_gap_for_voltage(2000, 11000, "Dyn11"), 8.0)
        self.assertEqual(_get_post_hv_gap_for_voltage(10000, 13283.52, "Dyn11"), 18.0)
        self.assertEqual(_get_post_hv_gap_for_voltage(10000, 66000, "Dyn11"), 28.0)
        self.assertEqual(_get_post_hv_gap_for_voltage(10000, 132000, "Dyn11"), 54.0)
        self.assertEqual(_get_post_hv_gap_for_voltage(10000, 132000, "Yyn0"), 43.0)

    def test_resolve_post_hv_gap_keeps_explicit_gap(self):
        multi_winding = MultiWindings(kVA=10000, vectorGroup="Dyn11")
        multi_winding.outerWindings = Windings(turnsPerPhase=137.0)

        gap = _resolve_post_hv_gap_to_previous(
            multi_winding,
            "outer",
            "hvToOuter",
            SimpleNamespace(hvToOuter=10.0),
            {"outer": {"turns": 137.0}},
            {"revisedVoltsPerTurn": 48.48},
        )

        self.assertEqual(gap, 10.0)

    def test_5wdg_distribution_ignores_outer_capacity_limits(self):
        multi_winding = MultiWindings(
            windings="5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
            tapStepPositive=2,
            tapStepNegative=2,
        )
        multi_winding.outerWindings = Windings(turnsPerPhase=20.0)

        distribution = _get_high_side_distribution(multi_winding, self.lv_results, self.hv_results)

        self.assertEqual(distribution["outer"]["turns"], 10.0)
        self.assertEqual(distribution["outer"]["taps"], 1.0)
        self.assertEqual(distribution["fine"]["turns"], 10.0)
        self.assertEqual(distribution["fine"]["taps"], 1.0)
        self.assertEqual(distribution["corse"]["turns"], 20.0)
        self.assertEqual(distribution["corse"]["taps"], 2.0)


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
                "hvToCorse": 8,
                "corseToFine": 6,
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
        self.assertGreater(response.json()["results"]["tankAndOil"]["topOilTemperature"], 0)
        self.assertEqual(response.json()["results"]["kW55"], response.json()["results"]["tankAndOil"]["kw55"])
        self.assertEqual(response.json()["results"]["hvWinding"]["kW55"], response.json()["results"]["tankAndOil"]["kw55"])
        self.assertEqual(response.json()["results"]["common"]["kW55"], response.json()["results"]["tankAndOil"]["kw55"])

    def test_5wdg_disc_payload_returns_clear_error_for_invalid_kw55_thermal_state(self):
        payload = {
            "windingSelection": "5 Wdg (LV, HV-Main, Corse, Fine and Outer)",
            "kVA": 50000,
            "kValue": 0.45,
            "vectorGroup": "Dyn11",
            "lowVoltage": 11000,
            "highVoltage": 33000,
            "lvCurrentDensity": 6.0,
            "hvCurrentDensity": 6.0,
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
                "hvToCorse": 8,
                "corseToFine": 6,
                "fineToOuter": 10,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid KW55 thermal state", response.json()["error"])

    def test_5wdg_taps_split_into_corse_fine_and_outer(self):
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
                "hvToCorse": 8,
                "corseToFine": 6,
                "fineToOuter": 10,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        outer_turns = response.json()["results"]["outerWinding"]["turnsPerPhase"]
        fine_turns = response.json()["results"]["fineWinding"]["turnsPerPhase"]
        corse_turns = response.json()["results"]["corseWinding"]["turnsPerPhase"]
        self.assertAlmostEqual(outer_turns, fine_turns, places=2)
        self.assertAlmostEqual(corse_turns, fine_turns * 2, places=2)

    def test_5wdg_extra_windings_default_parallel_conductors_independently(self):
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
                "hvToCorse": 8,
                "corseToFine": 6,
                "fineToOuter": 10,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual(results["corseWinding"]["radialParallelCond"], 1)
        self.assertEqual(results["corseWinding"]["axialParallelCond"], 1)
        self.assertEqual(results["fineWinding"]["radialParallelCond"], 1)
        self.assertEqual(results["fineWinding"]["axialParallelCond"], 1)
        self.assertEqual(results["outerWinding"]["radialParallelCond"], 1)
        self.assertEqual(results["outerWinding"]["axialParallelCond"], 1)


class VbMultiImpedanceTests(TestCase):
    def test_vb_multi_impedance_uses_outermost_included_winding_for_normal_b(self):
        winding_data = [
            {
                "name": "lv",
                "windingType": "HELICAL",
                "turnsPerPhase": 10,
                "phaseCurrent": 100,
                "loadLoss": 100,
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
                "loadLoss": 200,
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
                "hvLoadLossAtNormal": 210,
                "hvLoadLossAtLowest": 180,
            },
            {
                "name": "outer",
                "windingType": "HELICAL",
                "turnsPerPhase": 20,
                "phaseCurrent": 10,
                "loadLoss": 50,
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
            SimpleNamespace(kVA=100, tapStepPositive=1, tapStepNegative=3),
            winding_data,
            {"revisedVoltsPerTurn": 4},
            {},
            {"breakdown": {"pairs": []}},
        )

        self.assertAlmostEqual(result["b"], 58.0, places=2)
        self.assertEqual(
            result["breakdown"]["tapConditions"]["normal"]["includedHvWindings"],
            ["hv", "outer"],
        )
        self.assertEqual(
            result["breakdown"]["tapConditions"]["normal"]["outermostHvWinding"],
            "outer",
        )

    def test_vb_multi_impedance_tracks_lowest_and_normal_tap_losses(self):
        winding_data = [
            {
                "name": "lv",
                "windingType": "HELICAL",
                "turnsPerPhase": 10,
                "phaseCurrent": 100,
                "loadLoss": 100,
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
                "loadLoss": 200,
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
                "hvLoadLossAtNormal": 210,
                "hvLoadLossAtLowest": 180,
            },
            {
                "name": "outer",
                "windingType": "HELICAL",
                "turnsPerPhase": 20,
                "phaseCurrent": 10,
                "loadLoss": 50,
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
            SimpleNamespace(kVA=100, tapStepPositive=1, tapStepNegative=3),
            winding_data,
            {"revisedVoltsPerTurn": 4},
            {},
            {"breakdown": {"pairs": []}},
        )

        self.assertEqual(result["breakdown"]["tapConditions"]["lowest"]["loadLoss"], 280.0)
        self.assertEqual(result["breakdown"]["tapConditions"]["normal"]["loadLoss"], 360.0)
        self.assertEqual(result["er"], 0.36)
        self.assertEqual(result["breakdown"]["tapConditions"]["lowest"]["er"], 0.28)

    def test_vb_multi_impedance_excludes_outer_from_normal_geometry_below_half_turns(self):
        winding_data = [
            {
                "name": "lv",
                "windingType": "HELICAL",
                "turnsPerPhase": 10,
                "phaseCurrent": 100,
                "loadLoss": 100,
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
                "loadLoss": 200,
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
                "hvLoadLossAtNormal": 210,
                "hvLoadLossAtLowest": 180,
            },
            {
                "name": "corse",
                "windingType": "HELICAL",
                "turnsPerPhase": 10,
                "phaseCurrent": 10,
                "loadLoss": 40,
                "condIns": 3,
                "radialThickness": 14,
                "innerDiameter": 170,
                "outerDiameter": 190,
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
                "name": "fine",
                "windingType": "HELICAL",
                "turnsPerPhase": 5,
                "phaseCurrent": 10,
                "loadLoss": 20,
                "condIns": 4,
                "radialThickness": 15,
                "innerDiameter": 200,
                "outerDiameter": 220,
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
                "turnsPerPhase": 5,
                "phaseCurrent": 10,
                "loadLoss": 10,
                "condIns": 5,
                "radialThickness": 16,
                "innerDiameter": 230,
                "outerDiameter": 250,
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
            SimpleNamespace(kVA=100, tapStepPositive=1, tapStepNegative=3),
            winding_data,
            {"revisedVoltsPerTurn": 4},
            {},
            {"breakdown": {"pairs": []}},
        )

        self.assertEqual(
            result["breakdown"]["tapConditions"]["normal"]["includedHvWindings"],
            ["hv", "corse", "fine"],
        )
        self.assertEqual(
            result["breakdown"]["tapConditions"]["normal"]["outermostHvWinding"],
            "fine",
        )
        self.assertFalse(result["breakdown"]["normalTapUsage"]["outer"]["included"])
        self.assertEqual(result["breakdown"]["tapConditions"]["normal"]["loadLoss"], 380.0)
        self.assertEqual(result["breakdown"]["tapConditions"]["highest"]["outermostHvWinding"], "outer")


class CoreMaterialSpecificLossTests(TestCase):
    def test_specific_loss_uses_core_material_csv_table(self):
        self.assertEqual(get_specific_loss("NipM4", 1.7, 50), 1.3)
        self.assertEqual(get_specific_loss("NipM4", 1.7, 60), 1.72)

    def test_specific_loss_respects_explicit_wkg_grade(self):
        self.assertEqual(get_specific_loss("NipM4", 1.7, 50, 2.22), 2.22)
