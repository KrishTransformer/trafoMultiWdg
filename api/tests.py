import json

from django.test import Client, TestCase

from api.formulae import calculate_winding_formulae
from api.models import MultiWindings
from api.services import calculate_circ_wdg, calculate_hv_windings, calculate_lv_windings


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
        results = response.json()["results"]
        self.assertEqual(results["voltsPerTurn"], 4.5)
        self.assertEqual(results["lvVoltsPerPhase"], 249.99)
        self.assertEqual(results["hvVoltsPerPhase"], 11000.0)
        self.assertEqual(results["lvTurnsPerPhase"], 56)
        self.assertEqual(results["hvTurnsPerPhase"], 2465)
        self.assertEqual(results["lvCurrentPerPhase"], 133.34)
        self.assertEqual(results["hvCurrentPerPhase"], 3.03)
        self.assertEqual(results["lvEndClearance"], 40.0)
        self.assertEqual(results["hvEndClearance"], 60.0)
        self.assertEqual(results["lvWinding"]["lvTurnsPerPhase"], 56)
        self.assertEqual(results["hvWinding"]["hvTurnsPerPhase"], 2465)
        self.assertIn("common", results)
        self.assertIn("core", results)
        self.assertIn("coilDimensions", results)
        self.assertEqual(response.json()["inputs"]["windingModels"]["lv"]["turnsPerPhase"], 56)
        self.assertEqual(response.json()["inputs"]["windingModels"]["lv"]["phaseCurrent"], 133.34)
        self.assertEqual(response.json()["inputs"]["windingModels"]["lv"]["endClearances"], 40)
        self.assertEqual(response.json()["inputs"]["windingModels"]["hv"]["turnsPerPhase"], 2465)
        self.assertEqual(response.json()["inputs"]["radialGaps"]["coreToLv"], 5)

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
        self.assertGreater(hv_results["hvOd"], hv_results["hvId"])

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
