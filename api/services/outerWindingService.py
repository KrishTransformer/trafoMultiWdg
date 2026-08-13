from api.services._windingServiceSupport import build_hv_section_results


def calculate_outer_windings(
    multi_winding,
    hv_source,
    seed_dimensions,
    allocated_turns,
    allocated_voltage,
    allow_turns_fallback=True,
):
    return build_hv_section_results(
        section_name="outer",
        winding_type=getattr(multi_winding, "outerWindingType", "HELICAL"),
        winding=getattr(multi_winding, "outerWindings", None),
        hv_source=hv_source,
        material=(getattr(multi_winding, "outerConductorMaterial", None) or getattr(multi_winding, "hvConductorMaterial", "COPPER")),
        allocated_turns=allocated_turns,
        allocated_voltage=allocated_voltage,
        seed_dimensions=seed_dimensions,
        dry_type=bool(getattr(multi_winding, "dryType", False)),
        ambient_temp=getattr(multi_winding, "ambientTemp", 50) or 50,
        winding_temp=getattr(multi_winding, "windingTemp", 55) or 55,
        current_density_override=getattr(multi_winding, "outerCurrentDensity", None),
        allow_turns_fallback=allow_turns_fallback,
    )
