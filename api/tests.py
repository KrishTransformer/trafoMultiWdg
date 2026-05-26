import json

from django.test import Client, TestCase

from api.formulae import calculate_winding_formulae
from api.models import MultiWindings, Windings
from api.services import (
    calculate_circ_wdg,
    calculate_corse_windings,
    calculate_fine_windings,
    calculate_hv_windings,
    calculate_lv_windings,
    calculate_outer_windings,
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
        self.assertEqual(response.json()["inputs"]["windingModels"]["hv"]["turnsPerPhase"], 2465)
        self.assertEqual(response.json()["inputs"]["windingModels"]["hv"]["terminal"], 11000.0)
        self.assertEqual(response.json()["inputs"]["radialGaps"]["coreToLv"], 5)
        self.assertEqual(
            response.json()["inputs"]["windingTypes"]["lv"],
            "LAYER_DISC",
        )
        self.assertEqual(
            response.json()["inputs"]["windingTypes"]["hv"],
            "XOVER",
        )
        self.assertNotIn("outer", response.json()["inputs"]["windingTypes"])
        self.assertEqual(
            len(response.json()["results"]["impedance"]["pairs"]),
            1,
        )
        self.assertIn("ex", response.json()["results"]["impedance"])
        self.assertIn("er", response.json()["results"]["impedance"])
        self.assertIn("ek", response.json()["results"]["impedance"])
        self.assertEqual(
            response.json()["results"]["impedance"]["method"],
            "pairwise",
        )
        self.assertEqual(
            response.json()["results"]["impedance"]["pairs"][0]["pair"],
            "lv-hv",
        )
        self.assertEqual(
            response.json()["results"]["common"]["ex"],
            response.json()["results"]["impedance"]["totals"]["ex"],
        )
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
                "LvtoHV": 10,
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
        self.assertEqual(
            response.json()["results"]["impedance"]["method"],
            "vb_multi_wdg",
        )
        self.assertIn(
            "vb",
            response.json()["results"]["impedance"],
        )
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
        self.assertEqual(response.json()["inputs"]["windingModels"]["fine"]["endClearances"], 70)
        self.assertEqual(response.json()["inputs"]["windingModels"]["corse"]["endClearances"], 65)
        self.assertEqual(
            response.json()["inputs"]["windingModels"]["corse"]["windingLength"],
            response.json()["results"]["hvWinding"]["windingLength"],
        )
        self.assertIn(
            "Seed CORSE OD",
            response.json()["inputs"]["windingModels"]["fine"]["noInParallel"],
        )
        self.assertEqual(
            response.json()["inputs"]["windingModels"]["outer"]["turnsLayers"],
            "FINE -> fineToOuter -> OUTER",
        )
        self.assertEqual(
            response.json()["inputs"]["windingTypes"]["outer"],
            "DISC",
        )
        self.assertEqual(
            set(response.json()["inputs"]["windingTypes"].keys()),
            {"lv", "hv", "corse", "fine", "outer"},
        )
        self.assertEqual(
            response.json()["results"]["outerWinding"]["status"],
            "calculated",
        )
        self.assertTrue(response.json()["results"]["outerWinding"]["implemented"])
        self.assertGreater(response.json()["inputs"]["windingModels"]["outer"]["loadLoss"], 0)
        self.assertEqual(
            response.json()["results"]["fineWinding"]["status"],
            "calculated",
        )
        self.assertEqual(
            response.json()["results"]["corseWinding"]["status"],
            "calculated",
        )
        self.assertTrue(response.json()["results"]["fineWinding"]["implemented"])
        self.assertTrue(response.json()["results"]["corseWinding"]["implemented"])
        self.assertEqual(
            response.json()["results"]["corseWinding"]["seedDimensions"]["previousWinding"],
            "hv",
        )
        self.assertEqual(
            response.json()["results"]["fineWinding"]["seedDimensions"]["previousWinding"],
            "corse",
        )
        self.assertEqual(
            response.json()["results"]["outerWinding"]["seedDimensions"]["previousWinding"],
            "fine",
        )
        self.assertEqual(
            response.json()["results"]["corseWinding"]["seedDimensions"]["gapField"],
            "lvToCoarse",
        )
        self.assertEqual(
            response.json()["results"]["fineWinding"]["seedDimensions"]["gapField"],
            "fineToCoarse",
        )
        self.assertEqual(
            response.json()["results"]["outerWinding"]["seedDimensions"]["gapField"],
            "fineToOuter",
        )
        self.assertEqual(
            response.json()["results"]["coilDimensions"]["outermostWinding"],
            "outer",
        )
        self.assertEqual(
            response.json()["results"]["coilDimensions"]["corseID"],
            response.json()["results"]["coilDimensions"]["windingDimensions"]["corse"]["innerDiameter"],
        )
        self.assertEqual(
            response.json()["results"]["coilDimensions"]["fineOD"],
            response.json()["results"]["coilDimensions"]["windingDimensions"]["fine"]["outerDiameter"],
        )
        self.assertEqual(
            response.json()["results"]["coilDimensions"]["outerGap"],
            response.json()["results"]["coilDimensions"]["windingDimensions"]["outer"]["gapFromPrevious"],
        )
        self.assertEqual(
            len(response.json()["results"]["impedance"]["pairs"]),
            4,
        )
        self.assertEqual(
            response.json()["results"]["impedance"]["pairs"][1]["pair"],
            "hv-corse",
        )
        self.assertEqual(
            response.json()["results"]["impedance"]["pairs"][2]["pair"],
            "corse-fine",
        )
        self.assertEqual(
            response.json()["results"]["impedance"]["pairs"][3]["pair"],
            "fine-outer",
        )
        self.assertGreater(
            response.json()["results"]["impedance"]["totals"]["er"],
            1.0,
        )
        self.assertGreater(
            response.json()["results"]["impedance"]["vb"]["deltaDs"],
            0.0,
        )
        self.assertEqual(
            response.json()["results"]["common"]["ek"],
            response.json()["results"]["ez"]["value"],
        )
        self.assertEqual(
            response.json()["inputs"]["coilDimensions"]["corseID"],
            response.json()["results"]["coilDimensions"]["corseID"],
        )
        self.assertEqual(
            response.json()["inputs"]["coilDimensions"]["outermostWinding"],
            "outer",
        )
        self.assertEqual(
            len(response.json()["results"]["coilDimensions"]["radialBuild"]),
            5,
        )
        self.assertGreater(
            response.json()["results"]["coilDimensions"]["outermostOD"],
            response.json()["results"]["coilDimensions"]["hVOD"],
        )
        self.assertEqual(
            response.json()["results"]["coilDimensions"]["radialBuild"][2]["seededFrom"],
            "hv",
        )
        self.assertEqual(
            response.json()["results"]["coilDimensions"]["radialBuild"][3]["seededFrom"],
            "corse",
        )
        self.assertEqual(
            response.json()["results"]["coilDimensions"]["radialBuild"][4]["seededFrom"],
            "fine",
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
        self.assertEqual(
            response.json()["results"]["impedance"]["activeWindingOrder"],
            ["lv", "hv", "fine", "outer"],
        )

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
                "LvtoHV": 10,
                "lvToOuter": 10,
            },
        }

        response = self.client.post(
            "/api/multiWdgCalculator/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
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
                "LvtoHV": 10,
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
            result = response.json()["results"][f"{winding_name}Winding"]
            self.assertEqual(model["turnsPerLayer"], 204.0)
            self.assertEqual(model["noOfLayers"], 1.0)
            self.assertNotEqual(model["noOfLayers"], model["turnsPerPhase"])
            self.assertEqual(model["endClearances"], 49.0)
            self.assertEqual(result["turnsPerLayer"], 204.0)
            self.assertEqual(result["noOfLayers"], 1.0)
            self.assertEqual(result["endClearance"], 49.0)

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

    def test_formulae_module_reexports_calculator(self):
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
            "HELICAL": (12, 4.67),
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
