import json

from django.test import Client, TestCase


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
        self.assertEqual(response.json()["results"], {
            "lvVoltsPerPhase": 249.99,
            "hvVoltsPerPhase": 11000.0,
            "lvEndClearance": 40.0,
            "hvEndClearance": 60.0,
        })
        self.assertEqual(response.json()["inputs"]["windingModels"]["lv"]["endClearances"], 40)
        self.assertEqual(response.json()["inputs"]["radialGaps"]["coreToLv"], 5)

    def test_multi_wdg_calculator_rejects_get_requests(self):
        response = self.client.get("/api/multiWdgCalculator/")

        self.assertEqual(response.status_code, 405)
