## 5 WDG Technical Checkup

### Files

- Payload: `samples/5wdg_tap_case_payload.json`
- Output: `samples/5wdg_tap_case_output.json`

### Run Status

- API response: `200`
- Selected design code: `5_WDG`

### Tap Distribution Check

- Input outer winding capacity used for the fullness check: `turnsPerPhase = 100`
- Calculated turns per tap: `61.6`
- Since `100 < 4 x 61.6`, the outer winding is full after `1` tap.
- Final tap allocation in output:
  - `outer = 61.6 turns = 1 tap`
  - `fine = 184.8 turns = 3 taps`
  - `corse = 0 turns = 0 tap`
- This matches the current `5_WDG` rule:
  - Fill the outer winding first
  - Send remaining taps to the last-but-one winding

### Electrical Summary

- Rating: `100 kVA`, `11 kV / 433 V`, `Dyn11`
- Revised volts/turn: `4.464`
- LV turns/phase: `56`
- HV main turns/phase: `2341.0`
- Phase voltage split:
  - `hvMain = 10450 V`
  - `corse = 0 V`
  - `fine = 824 V`
  - `outer = 274 V`
- Impedance `ek = 2.75 %`
- Voltage regulation at full load, unity PF: `2.23 %`
- Efficiency at full load, unity PF: `97.43 %`

### Winding Observation

- LV load loss: `945 W`, gradient: `13.5`
- HV main load loss: `1100 W`, gradient: `24.5`
- Fine load loss: `125 W`, gradient: `2.2`
- Outer load loss: `45 W`, gradient: `0.7`
- Corse winding is intentionally inactive in this case because the tap overflow stopped in the fine winding.

### Tank, Radiator, Oil

- Tank loss: `80 W`
- Tank size: `905 L X 355 W X 730 H mm`
- Overall size: `2290 L X 2455 W X 1643 H mm`
- Radiator selection: `500 X 300: 20 X 6`
- Radiator area: `34.77`
- Heat to be dissipated: `10430`
- `kW55 = 11350`
- Total oil: `382 L`
- Transformer weight: `1436 kg`

### Technical Read

- The tap distribution behavior is correct for the implemented `5_WDG` logic.
- The electrical outputs are internally consistent for the chosen tap split.
- Impedance and regulation look reasonable for a small distribution transformer case.
- The cooling package looks oversized for a `100 kVA` unit:
  - High radiator count
  - Large overall width
  - High oil quantity
  - High total weight
- This likely comes from the current thermal/tank calculation assumptions rather than from the tap allocation itself.

### Output Completeness Notes

- Main computed sections are present: windings, impedance, efficiency, dimensions, tank/oil, cost.
- Some `null` values remain in model/seed helper fields inside the response, but they are not blocking the main calculations.
- Input echo fields under `inputs.tank` and `inputs.cost` are `null` because those values were not supplied in the sample payload.
