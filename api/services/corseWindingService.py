from api.services._windingServiceSupport import build_hv_section_results


def calculate_corse_windings(
    multi_winding,
    hv_source,
    seed_dimensions,
    allocated_turns,
    allocated_voltage,
    allow_turns_fallback=True,
    limb_height=None,
    perma_wood_ring=0.0,
):
    return build_hv_section_results(
        section_name="corse",
        winding_type=getattr(multi_winding, "corseWindingType", "HELICAL"),
        winding=getattr(multi_winding, "corseWindings", None),
        hv_source=hv_source,
        material=(getattr(multi_winding, "corseConductorMaterial", None) or getattr(multi_winding, "hvConductorMaterial", "COPPER")),
        allocated_turns=allocated_turns,
        allocated_voltage=allocated_voltage,
        seed_dimensions=seed_dimensions,
        dry_type=bool(getattr(multi_winding, "dryType", False)),
        ambient_temp=getattr(multi_winding, "ambientTemp", 50) or 50,
        winding_temp=getattr(multi_winding, "windingTemp", 55) or 55,
        current_density_override=getattr(multi_winding, "corseCurrentDensity", None),
        allow_turns_fallback=allow_turns_fallback,
        limb_height=limb_height,
        perma_wood_ring=perma_wood_ring,
        kva=getattr(multi_winding, "kVA", 0.0),
    )
