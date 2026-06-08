from api.services._windingServiceSupport import build_hv_section_results


def calculate_fine_windings(multi_winding, hv_source, seed_dimensions, allocated_turns, allocated_voltage):
    return build_hv_section_results(
        section_name="fine",
        winding_type=getattr(multi_winding, "fineWindingType", "HELICAL"),
        winding=getattr(multi_winding, "fineWindings", None),
        hv_source=hv_source,
        material=(getattr(multi_winding, "fineConductorMaterial", None) or getattr(multi_winding, "hvConductorMaterial", "COPPER")),
        allocated_turns=allocated_turns,
        allocated_voltage=allocated_voltage,
        seed_dimensions=seed_dimensions,
        dry_type=bool(getattr(multi_winding, "dryType", False)),
        current_density_override=getattr(multi_winding, "fineCurrentDensity", None),
    )
