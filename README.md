# trafoMultiWdg

## Local API

Use this endpoint in Postman for local testing:

```text
POST http://127.0.0.1:8001/api/multiWdgCalculator/
```

Set this header:

```text
Content-Type: application/json
```

## Canonical `radialGaps` Keys

The winding order is:

```text
lv -> hvMain -> corse -> fine -> outer
```

The canonical request keys now follow that order:

```json
{
  "coreToLv": 5,
  "lvToHv": 10,
  "hvToCorse": 8,
  "corseToFine": 6,
  "fineToOuter": 10,
  "hvToFine": 8,
  "hvToOuter": 10,
  "corseToOuter": 10
}
```

Selection usage:

- `3 Wdg`: `hvToOuter`
- `4 Wdg (Corse + Outer)`: `hvToCorse`, `corseToOuter`
- `4 Wdg (Fine + Outer)`: `hvToFine`, `fineToOuter`
- `5 Wdg`: `hvToCorse`, `corseToFine`, `fineToOuter`

Backward-compatible aliases are still accepted in requests:

- `lvToCoarse -> hvToCorse`
- `lvToFine -> hvToFine`
- `fineToCoarse -> corseToFine`
- `coarseToOuter -> corseToOuter`

## Clearance Override Limits

Users can edit radial gaps and winding `endClearances` at or above 20% of the calculated default value for the current design. There is no upper limit. For example, if `coreToLv` defaults to `5 mm`, the user value must be at least `1 mm`; any value from `1 mm` upward is accepted. Values below the lower limit are kept in the echoed `inputs`, but the calculator uses the default value in `results`.

This applies to `coreToLv`, `lvToHv`, `hvToCorse`, `hvToFine`, `hvToOuter`, `corseToFine`, `fineToOuter`, `corseToOuter`, `coilCoilGap`/`hVHVGap`, and all winding `endClearances`.

## HV Main Winding Loss Rule

The response exposes these HV-main fields:

- `hvWinding.hVRevisedCurrDenAtNormal`
- `hvWinding.hVRevisedCurrDenAtLowest`
- `hvWinding.hvLoadLossAtNormal`
- `hvWinding.hvLoadLossAtLowest`

For multi-winding selections, HV-main load loss uses the direct formulas:

```text
hvLoadLossAtNormal = getLoadLoss(material, hvBareWeight, hVRevisedCurrDenAtNormal, hvStrayLoss)
hvLoadLossAtLowest = getLoadLoss(material, hvBareWeight, hVRevisedCurrDenAtLowest, hvStrayLoss)
```

No turns-ratio multiplier is applied in multi-winding mode.

For `2 Wdg`, the legacy turns-ratio-scaled behavior is still preserved.

## Postman Example

```json
{
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
  "outerWindings": {
    "turnsPerPhase": 100
  },
  "radialGaps": {
    "coreToLv": 5,
    "lvToHv": 10,
    "hvToCorse": 8,
    "corseToFine": 6,
    "fineToOuter": 10
  }
}
```
