import csv
import math
from functools import lru_cache
from pathlib import Path

from api.services.numberUtils import (
    four_digit_decimal,
    next_0_integer,
    next_5or0_integer,
    next_integer,
    one_digit_decimal,
    one_digit_decimal_floor,
    previous_5or0_integer,
    six_digit_decimal,
    three_digit_decimal,
    two_digit_decimal,
    two_digit_decimal_floor,
    two_digit_decimal_part,
)


COPPER = "COPPER"
ALUMINIUM = "ALUMINIUM"
ECONOMIC = "ECONOMIC"
ENERGY_EFFICIENT = "ENERGY_EFFICIENT"
CLASS_B = "CLASS_B"
CLASS_F = "CLASS_F"
CLASS_H = "CLASS_H"
PRIME = "PRIME"
STEP_LAP = "STEP_LAP"
RADIATOR = "RADIATOR"


def _normalize_name(value):
    return "" if value is None else str(value).strip()


def _normalize_upper(value):
    return _normalize_name(value).upper()


def _vector_group_char(vector_group, index, uppercase=False):
    group_name = _normalize_name(vector_group)
    if uppercase:
        group_name = group_name.upper()
    return group_name[index] if len(group_name) > index else ""


def _is_copper(material):
    return _normalize_upper(material) == COPPER


def _is_aluminium(material):
    return _normalize_upper(material) == ALUMINIUM


def _is_economic(trans_cost_type):
    return _normalize_upper(trans_cost_type) == ECONOMIC


def _is_energy_efficient(trans_cost_type):
    return _normalize_upper(trans_cost_type) == ENERGY_EFFICIENT


def _is_dry_class(dry_temp_class, class_name):
    return _normalize_upper(dry_temp_class) == class_name


def _is_winding_type(winding_type, expected):
    return _normalize_upper(winding_type) == expected


def has_star_connection(vector_group):
    return _vector_group_char(vector_group, 0, uppercase=True) == "Y" or _vector_group_char(vector_group, 1, uppercase=True) == "Y"


def get_frequency(frequency):
    return 50 if frequency is None else frequency


def get_build_factor(kva, core_type, build_factor):
    if build_factor not in (None, 0):
        return build_factor

    normalized_core_type = _normalize_upper(core_type) or PRIME
    if normalized_core_type == PRIME:
        if kva <= 500:
            return 1.3
        if kva <= 10000:
            return 1.25
        return 1.2
    if normalized_core_type == STEP_LAP:
        if kva <= 500:
            return 1.25
        if kva <= 10000:
            return 1.2
        return 1.1
    return 0.0


def get_flux_density(flux_density, dry_type):
    if flux_density not in (None, 0):
        return flux_density
    return 1.6 if dry_type else 1.73333


def get_core_material(core_material):
    return core_material if _normalize_name(core_material) else "NipM4"


@lru_cache(maxsize=1)
def _load_core_material_specific_loss_table():
    csv_path = Path(__file__).resolve().parents[1] / "data" / "CoreMaterialsMulti.csv"
    material_table = {}

    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        rows = csv.reader(csv_file)
        header = next(rows, [])
        flux_density_points = []
        for value in header[1:-1]:
            try:
                flux_density_points.append(float(value))
            except (TypeError, ValueError):
                flux_density_points.append(None)

        for row in rows:
            if not row:
                continue
            material_name = row[0].strip()
            if not material_name:
                continue

            specific_losses = {}
            for flux_density, loss_value in zip(flux_density_points, row[1:-1]):
                if flux_density is None:
                    continue
                try:
                    specific_losses[flux_density] = float(loss_value)
                except (TypeError, ValueError):
                    continue

            if specific_losses:
                material_table[material_name] = specific_losses

    return material_table


def get_specific_loss(core_material, flux_density, frequency, w_kg_grade=None):
    if w_kg_grade not in (None, 0, 0.0):
        return two_digit_decimal(w_kg_grade)

    specific_loss_map = _load_core_material_specific_loss_table().get(get_core_material(core_material))
    if not specific_loss_map:
        return 0.0

    lower_flux_density = one_digit_decimal_floor(flux_density - 0.01)
    upper_flux_density = one_digit_decimal(flux_density)
    lower_specific_loss = specific_loss_map.get(lower_flux_density)
    upper_specific_loss = specific_loss_map.get(upper_flux_density)

    if lower_specific_loss is None and upper_specific_loss is None:
        return 0.0
    if lower_specific_loss is None:
        specific_loss = upper_specific_loss
    elif upper_specific_loss is None or upper_flux_density == lower_flux_density:
        specific_loss = lower_specific_loss
    else:
        specific_loss = interpolate_specific_loss(
            flux_density,
            lower_flux_density,
            upper_flux_density,
            lower_specific_loss,
            upper_specific_loss,
            frequency,
        )
        return specific_loss

    if frequency == 60:
        specific_loss *= 1.32
    return two_digit_decimal(specific_loss)


def get_core_type(core_type):
    return core_type if _normalize_name(core_type) and _normalize_name(core_type) != "0" else PRIME


def get_low_voltage(low_voltage):
    return 433 if low_voltage is None else low_voltage


def get_high_voltage(high_voltage):
    return 11000 if high_voltage is None else high_voltage


def get_vector_group(vector_group):
    return vector_group if vector_group is not None else "Dyn11"


def get_k_value(kva, input_k_value, lv_conductor_material, trans_cost_type):
    if input_k_value not in (None, 0.0):
        return input_k_value

    k_value = 0.0
    if _is_economic(trans_cost_type):
        if _is_copper(lv_conductor_material):
            k_value = (0.45 + 0.6) / 2
        elif _is_aluminium(lv_conductor_material):
            k_value = (0.3 + 0.4) / 2
    elif _is_energy_efficient(trans_cost_type):
        if _is_copper(lv_conductor_material):
            k_value = (0.6 + 0.75) / 2
        elif _is_aluminium(lv_conductor_material):
            k_value = (0.4 + 0.5) / 2

    if kva > 1950:
        k_value = 0.442
    return k_value


def get_current_density(conductor_material, trans_cost_type, dry_type, dry_temp_class, is_lv, current_density):
    if current_density is not None:
        return current_density

    current_density_value = 0.0
    if not dry_type:
        if _is_copper(conductor_material) and _is_economic(trans_cost_type):
            current_density_value = 4.24
        elif _is_copper(conductor_material) and _is_energy_efficient(trans_cost_type):
            current_density_value = 1.5
        elif _is_aluminium(conductor_material) and _is_economic(trans_cost_type):
            current_density_value = 2.37
        elif _is_aluminium(conductor_material) and _is_energy_efficient(trans_cost_type):
            current_density_value = 0.6
    elif _is_dry_class(dry_temp_class, CLASS_B):
        if _is_copper(conductor_material):
            return 1.8 if is_lv else 2.2
        if _is_aluminium(conductor_material):
            return 1.4 if is_lv else 1.6
    elif _is_dry_class(dry_temp_class, CLASS_F):
        if _is_copper(conductor_material):
            return 2.2 if is_lv else 2.5
        if _is_aluminium(conductor_material):
            return 1.6 if is_lv else 1.8
    elif _is_dry_class(dry_temp_class, CLASS_H):
        if _is_copper(conductor_material):
            return 2.4 if is_lv else 2.8
        if _is_aluminium(conductor_material):
            return 1.8 if is_lv else 2.0
    return current_density_value


def get_volts_per_turn(k_value, kva):
    return three_digit_decimal(k_value * math.sqrt(kva))


def get_lv_volts_per_phase(voltage_value, vector_group):
    if voltage_value is None:
        return None
    volts_per_phase = voltage_value / math.sqrt(3) if _vector_group_char(vector_group, 1) == "y" else voltage_value
    return two_digit_decimal(volts_per_phase)


def get_hv_volts_per_phase(voltage_value, vector_group):
    if voltage_value is None:
        return None
    volts_per_phase = voltage_value / math.sqrt(3) if _vector_group_char(vector_group, 0) == "Y" else voltage_value
    return two_digit_decimal(volts_per_phase)


def get_turns_per_phase(volts_per_phase, volts_per_turn, turns_from_user=None, vector_group=None, is_lv=None):
    if turns_from_user is not None:
        return int(math.ceil(turns_from_user))
    return int(math.ceil(volts_per_phase / volts_per_turn))


def get_revised_volts_per_turn(volts_per_phase, turns_per_phase, vector_group=None):
    return three_digit_decimal(volts_per_phase / turns_per_phase)


def get_reversed_revised_volts_per_turn(net_area, frequency, flux_density):
    return three_digit_decimal(net_area * 4.44 * frequency * flux_density * math.pow(10, -6))


def get_net_area(revised_volts_per_turn, frequency, flux_density):
    return next_integer(revised_volts_per_turn / (4.44 * frequency * flux_density * math.pow(10, -6)))


def get_core_diameter(area, core_dia_from_user=None):
    if core_dia_from_user is not None:
        return core_dia_from_user
    return math.sqrt(area / (math.pi / 4))


def get_possible_k_value(kva, lv_conductor_material, trans_cost_type=None):
    if _is_copper(lv_conductor_material):
        return [0.4, 0.8]
    if _is_aluminium(lv_conductor_material):
        return [0.25, 0.55]
    return [0.0, 0.0]


def get_diameter(area):
    return math.sqrt(area / (math.pi / 4))


def get_hrg_core_dia(kva, dry_type):
    if dry_type:
        if kva <= 2:
            return 55
        if kva <= 5:
            return 62
        if kva <= 8:
            return 68
        if kva <= 10:
            return 72
        if kva <= 16:
            return 82
        if kva <= 25:
            return 90
        if kva <= 40:
            return 102
        if kva <= 50:
            return 107
        if kva <= 63:
            return 114
        if kva <= 100:
            return 135
        if kva <= 150:
            return 145
        if kva <= 180:
            return 150
        if kva <= 300:
            return 162
        if kva <= 450:
            return 172
        if kva <= 500:
            return 210
        if kva <= 1500:
            return 231
        if kva <= 1800:
            return 260
        if kva <= 1950:
            return 295
        return 0

    if kva <= 2:
        return 46
    if kva <= 5:
        return 52
    if kva <= 8:
        return 56
    if kva <= 10:
        return 60
    if kva <= 16:
        return 68
    if kva <= 25:
        return 75
    if kva <= 40:
        return 85
    if kva <= 50:
        return 90
    if kva <= 63:
        return 95
    if kva <= 100:
        return 112
    if kva <= 150:
        return 121
    if kva <= 180:
        return 125
    if kva <= 300:
        return 135
    if kva <= 450:
        return 143
    if kva <= 500:
        return 175
    if kva <= 1500:
        return 192
    if kva <= 1800:
        return 216
    if kva <= 1950:
        return 245
    return 0


def _core_area_factor(dia):
    if dia <= 100:
        return 0.88
    if dia <= 150:
        return 0.9
    if dia <= 200:
        return 0.91
    if dia <= 250:
        return 0.92
    return 0.93


def get_gross_core_area(net_core_area, dia, core_dia_from_user=None):
    if core_dia_from_user is not None:
        return math.ceil(math.pow(core_dia_from_user, 2) * math.pi / 4)
    return next_5or0_integer(net_core_area / _core_area_factor(dia))


def get_revised_net_area(gross_area, dia):
    return next_5or0_integer(gross_area * _core_area_factor(dia))


def get_current_per_phase(kva, volts_per_phase):
    return two_digit_decimal((kva * 1000) / (3 * volts_per_phase))


def get_window_height(k_value, dia, conductor_material, given_window_height=None, dry_type=False):
    if given_window_height is not None:
        return int(math.ceil(given_window_height))

    if _is_copper(conductor_material):
        window_height_factor = (0.8 / k_value) + 0.5
    else:
        window_height_factor = 1.5 / k_value

    if dry_type:
        if _is_copper(conductor_material):
            window_height_factor = (-3.33 * k_value) + 5.17
        else:
            window_height_factor = 1.5 / k_value

    return next_integer(window_height_factor * dia)


def get_end_clearance(kva, voltage, vector_group, end_clr=None, dry_type=False, is_lv=False):
    end_clearance = 8 * 2
    char_at = 1 if is_lv else 0

    if voltage <= 1100:
        if kva <= 25:
            end_clearance = 8 * 2
        elif kva <= 100:
            end_clearance = 10 * 2
        else:
            end_clearance = 15 * 2
    elif voltage <= 11000:
        if kva <= 25:
            end_clearance = 20 * 2
        elif kva <= 1000:
            end_clearance = 25 * 2
        else:
            end_clearance = 30 * 2
    elif voltage <= 22000:
        if kva <= 100:
            end_clearance = 30 * 2
        else:
            end_clearance = 35 * 2
    elif voltage <= 33000:
        if kva <= 100:
            end_clearance = 35 * 2
        else:
            end_clearance = 45 * 2
    elif voltage <= 66000:
        if _vector_group_char(vector_group, char_at, uppercase=True) == "Y":
            end_clearance = 80
            if kva <= 500:
                end_clearance += 40
            elif kva <= 2500:
                end_clearance += 50
            else:
                end_clearance += 60
        else:
            end_clearance = 80 * 2
    elif voltage <= 132000:
        if _vector_group_char(vector_group, char_at, uppercase=True) == "Y":
            end_clearance = 95
            if kva <= 500:
                end_clearance += 40
            elif kva <= 2500:
                end_clearance += 50
            else:
                end_clearance += 60
        else:
            end_clearance = 95 * 2
    else:
        if _vector_group_char(vector_group, char_at, uppercase=True) == "Y":
            end_clearance = 115
            if kva <= 500:
                end_clearance += 40
            elif kva <= 2500:
                end_clearance += 50
            else:
                end_clearance += 60
        else:
            end_clearance = 115 * 2

    if dry_type:
        if voltage <= 1100:
            end_clearance = 2 * 40 if kva <= 100 else 2 * 60
        elif voltage <= 11000:
            end_clearance = 2 * 140
        elif voltage <= 22000:
            end_clearance = 2 * 200
        elif voltage <= 33000:
            end_clearance = 2 * 240

    if end_clr is not None and end_clr >= 0.25 * end_clearance:
        return end_clr
    return float(end_clearance)


def get_lv_end_clearance(kva, vector_group, end_clr, dry_type, low_voltage, high_voltage):
    voltage = high_voltage if high_voltage > 11000 and low_voltage > 1100 else low_voltage
    end_clearance = get_end_clearance(kva, voltage, vector_group, end_clr, dry_type, True)

    if not dry_type:
        return end_clearance

    hilo_gap = 0
    if high_voltage <= 1100:
        hilo_gap = 15
    elif high_voltage <= 11000:
        hilo_gap = 31
    elif high_voltage <= 22000:
        hilo_gap = 58
    elif high_voltage <= 33000:
        hilo_gap = 90

    if high_voltage <= 1100 or end_clr is not None:
        return end_clearance
    return end_clearance - (2 * hilo_gap)


def get_perma_wood_ring(kva, voltage, dry_type):
    if dry_type or voltage < 11000:
        return 0
    if kva <= 5000:
        return 20
    if kva <= 20000:
        return 25
    if kva <= 50000:
        return 35
    return 50


def get_winding_length(window_height, end_clearance, perma_wood_ring):
    return next_integer(window_height - end_clearance - perma_wood_ring)


def get_disc_winding_length(breadth, cond_insulation, insulation_compression, no_of_discs, disc_duct_size):
    term1 = (breadth + (cond_insulation * insulation_compression)) * no_of_discs
    term2 = (disc_duct_size * insulation_compression) * (no_of_discs - 1)
    return next_integer(term1 + term2)


def get_lv_turns_per_layer(lv_turns_per_phase, no_of_layers):
    return lv_turns_per_phase / no_of_layers


def get_number_of_conductors(conductor_x_section, conductor_material):
    rough_no = int(math.ceil(conductor_x_section / (51.14 if _is_copper(conductor_material) else 60)))
    conductor_map = {
        2: 2,
        3: 3,
        4: 4,
        5: 5,
        6: 6,
        7: 8,
        8: 8,
        9: 10,
        10: 10,
        11: 12,
        12: 12,
        13: 14,
        14: 14,
        15: 14,
        16: 16,
        17: 16,
        18: 18,
        19: 18,
        20: 20,
        21: 20,
        22: 20,
        23: 24,
        24: 24,
        25: 24,
        26: 28,
        27: 28,
        28: 28,
        29: 28,
        30: 32,
        31: 32,
        32: 32,
        33: 32,
        34: 36,
        35: 36,
        36: 36,
    }
    return conductor_map.get(rough_no, 1)


def get_conductor_cross_section(current_per_phase, current_density):
    return three_digit_decimal(current_per_phase / current_density)


def is_conductor_round(conductor_x_sec):
    return conductor_x_sec <= 7


def get_x_sec_per_conductor(total_cross_section, no_of_conductors):
    return two_digit_decimal(total_cross_section / no_of_conductors)


def get_axial_parallel_conductors(no_of_conductors, radial_parallel_conductors, axial_parallel_cond=None):
    if axial_parallel_cond is not None:
        return axial_parallel_cond
    return next_integer(no_of_conductors / radial_parallel_conductors)


def get_radial_parallel_conductors(no_of_conductors, conductor_flag, radial_parallel_cond=None):
    radial_parallel = 1
    if no_of_conductors == 2:
        radial_parallel = 1 if conductor_flag == 0 else 2
    elif no_of_conductors == 3:
        radial_parallel = 1 if conductor_flag == 0 else 3
    elif no_of_conductors == 4:
        radial_parallel = 1 if conductor_flag == 0 else 2
    elif no_of_conductors == 6:
        radial_parallel = 1 if conductor_flag == 0 else 2 if conductor_flag == 1 else 3
    elif no_of_conductors == 8:
        radial_parallel = 1 if conductor_flag == 0 else 2
    elif no_of_conductors == 10:
        radial_parallel = 1 if conductor_flag == 0 else 2
    elif no_of_conductors == 12:
        radial_parallel = 1 if conductor_flag == 0 else 2 if conductor_flag == 1 else 3
    elif no_of_conductors == 14:
        radial_parallel = 1 if conductor_flag == 0 else 2
    elif no_of_conductors == 16:
        radial_parallel = 1 if conductor_flag == 0 else 2 if conductor_flag == 1 else 4
    elif no_of_conductors == 18:
        radial_parallel = 1 if conductor_flag == 0 else 2 if conductor_flag == 1 else 3
    elif no_of_conductors == 20:
        radial_parallel = 2 if conductor_flag == 0 else 4
    elif no_of_conductors == 24:
        radial_parallel = 4
    elif no_of_conductors == 28:
        radial_parallel = 4
    elif no_of_conductors == 30:
        radial_parallel = 5
    elif no_of_conductors == 32:
        radial_parallel = 4
    elif no_of_conductors == 36:
        radial_parallel = 4 if conductor_flag == 0 else 6

    return radial_parallel if radial_parallel_cond is None else radial_parallel_cond


def get_bi(winding_length, turns_per_layer, axial_parallel_conductors, transposition, radial_parallel_conductors):
    bi = (winding_length - transposition) / ((turns_per_layer + 1) * axial_parallel_conductors)
    if radial_parallel_conductors > 1:
        return two_digit_decimal(bi)
    return two_digit_decimal_floor(bi)


def get_conductor_insulation(kva, voltage, is_round, vector_group, is_enamel, cond_ins, dry_type):
    conductor_insulation = 0.2
    if is_round:
        if voltage <= 11000:
            conductor_insulation = 0.2 if kva <= 200 else 0.22
        elif voltage <= 22000:
            conductor_insulation = 0.25
        elif voltage <= 33000:
            conductor_insulation = 0.3
    else:
        if voltage <= 11000:
            if kva <= 100:
                conductor_insulation = 0.3
            elif kva <= 1000:
                conductor_insulation = 0.35
            else:
                conductor_insulation = 0.4
        elif voltage <= 33000:
            conductor_insulation = 0.5 if kva <= 1000 else 0.6
        elif voltage <= 66000:
            conductor_insulation = 0.8
        elif voltage <= 132000:
            conductor_insulation = 1.2 if _vector_group_char(vector_group, 0) == "D" else 1.0

    if is_enamel:
        if voltage <= 11000:
            conductor_insulation = 0.05
        elif voltage <= 22000:
            conductor_insulation = 0.1
        elif voltage <= 33000:
            conductor_insulation = 0.13
    if dry_type:
        conductor_insulation = 0.3

    if cond_ins is not None and cond_ins >= conductor_insulation * 0.7:
        return cond_ins
    return conductor_insulation


def get_breadth(breadth_insulated, conductor_insulation, radial_parallel_conductors):
    breadth = breadth_insulated - conductor_insulation
    if radial_parallel_conductors > 1:
        return one_digit_decimal(breadth)
    return one_digit_decimal_floor(breadth)


def get_height(min_conductor_cross_section, breadth):
    return one_digit_decimal((min_conductor_cross_section + 0.86) / breadth)


def get_height_insulated(height, insulation):
    return one_digit_decimal(height + insulation)


def get_round_cond_dia(cond_x_sec, cond_dia_user, conductor_material):
    min_dia = 0.3 if _is_copper(conductor_material) else 0.8
    if cond_dia_user not in (None, 0):
        return max(cond_dia_user, min_dia)
    return max(one_digit_decimal(get_diameter(cond_x_sec)), min_dia)


def get_transposition(bi, winding_length, transpose, turns_per_layer, radial_parallel, axial_parallel_cond):
    if radial_parallel <= 1:
        return 0
    transposition = int(math.floor(winding_length + transpose - ((bi * (turns_per_layer + 1)) * axial_parallel_cond)))
    return min(transposition, 35)


def get_revised_conductor_cross_section(breadth, height):
    corner_radius_area = 0
    if 5.0 <= breadth <= 20.5 and height <= 1.65:
        corner_radius_area = 0.215
    if 5.0 <= breadth <= 20.0 and 1.65 < height <= 2.30:
        corner_radius_area = 0.363
    if 5.0 <= breadth <= 20.0 and 2.3 < height <= 3.65:
        corner_radius_area = 0.55
    if 5.0 <= breadth <= 20.0 and 3.65 < height <= 5.95:
        corner_radius_area = 0.86
    if 6.3 <= breadth <= 20.0 and 5.95 < height <= 10.0:
        corner_radius_area = 1.34
    if breadth >= 30:
        corner_radius_area = 0
    return three_digit_decimal((breadth * height) - corner_radius_area)


def get_actual_conductor_x_sec(revised_cond_x_sec, no_of_conductors):
    return three_digit_decimal(revised_cond_x_sec * no_of_conductors)


def get_inter_layer_insulation(volts_per_turn, turns_per_layer, conductor_insulation, is_enamel, inter_layer_ins, dry_type):
    breakdown_voltage = 12000 if is_enamel or dry_type else 8000
    inter_layer = ((volts_per_turn * 2 * 2 * turns_per_layer) / breakdown_voltage) - conductor_insulation
    if inter_layer_ins is not None and inter_layer_ins >= inter_layer * 0.9:
        return inter_layer_ins
    if inter_layer < 0:
        return 0.1
    return one_digit_decimal(inter_layer)


def get_duct_size(kva, winding_length, duct_size_user=None, dry_type=False):
    if winding_length <= 399:
        duct_size = 3
    elif winding_length <= 499:
        duct_size = 4
    elif winding_length <= 599:
        duct_size = 5
    else:
        duct_size = 6

    if dry_type:
        if kva <= 100:
            duct_size = 8
        elif kva <= 250:
            duct_size = 10
        elif kva <= 500:
            duct_size = 12
        elif kva <= 1000:
            duct_size = 16
        else:
            duct_size = 20

    if duct_size_user is not None and duct_size_user >= duct_size * 0.5:
        return duct_size_user
    return duct_size


def get_radial_thickness(hi, radial_parallel_conductors, no_of_layers, inter_layer_insulation, ducts, duct_size, is_lv):
    no_layers = int(math.ceil(no_of_layers)) if two_digit_decimal_part(no_of_layers) > 0 else int(no_of_layers)
    factor = 0.3 if is_lv else 0
    radial_thickness = (
        (hi * radial_parallel_conductors * no_layers)
        + (ducts * duct_size)
        + (inter_layer_insulation * (no_layers - 1 - ducts))
        + (factor * no_layers)
    )
    return next_integer(radial_thickness)


def get_disc_radial_thickness(height, radial_parallel, cond_ins, expansion, turns_per_disc, no_of_duct, duct_thickness):
    return next_integer(((height + (cond_ins * expansion)) * radial_parallel * turns_per_disc) + (no_of_duct * duct_thickness))


def get_core_lv_gap(kva, voltage, core_to_lv_gap=None, dry_type=False):
    if dry_type:
        if voltage <= 1100:
            core_lv_gap = 6 if kva <= 50 else 10
        elif voltage <= 3300:
            core_lv_gap = 12
        else:
            core_lv_gap = 20
    else:
        if voltage <= 1100:
            if kva <= 25:
                core_lv_gap = 1.5
            elif kva <= 100:
                core_lv_gap = 2
            elif kva <= 1000:
                core_lv_gap = 3
            elif kva <= 2500:
                core_lv_gap = 4
            else:
                core_lv_gap = 5
        elif voltage <= 6600:
            core_lv_gap = 6 if kva <= 1000 else 7
        elif voltage <= 11000:
            if kva <= 100:
                core_lv_gap = 7
            elif kva <= 2500:
                core_lv_gap = 8
            else:
                core_lv_gap = 9
        elif voltage <= 22000:
            core_lv_gap = 12
        elif voltage <= 33000:
            core_lv_gap = 24
        elif voltage <= 66000:
            core_lv_gap = 32
        else:
            core_lv_gap = 50

    if core_to_lv_gap is not None and core_to_lv_gap >= 0.65 * core_lv_gap:
        return core_to_lv_gap
    return core_lv_gap


def get_id(inner_dia, gap):
    return int(math.ceil(inner_dia + (2 * gap)))


def get_od(inner_dia, radial_thickness):
    return int(math.ceil(inner_dia + (2 * radial_thickness)))


def get_lv_hv_gap(kva, high_voltage, vector_group, lv_to_hv_gap=None, dry_type=False):
    lv_hv_gap = 8
    if high_voltage <= 1100:
        lv_hv_gap = 5 if kva <= 500 else 6
    elif high_voltage <= 6600:
        lv_hv_gap = 6 if kva <= 1000 else 7
    elif high_voltage <= 11000:
        if kva <= 100:
            lv_hv_gap = 7
        elif kva <= 2500:
            lv_hv_gap = 8
        else:
            lv_hv_gap = 9
    elif high_voltage <= 33000:
        lv_hv_gap = 18
    elif high_voltage <= 66000:
        if kva <= 60000:
            lv_hv_gap = 28
    elif high_voltage <= 132000:
        lv_hv_gap = 54 if _vector_group_char(vector_group, 0) == "D" else 43

    if dry_type:
        if high_voltage <= 11000:
            lv_hv_gap = 31
        elif high_voltage <= 22000:
            lv_hv_gap = 54
        elif high_voltage <= 33000:
            lv_hv_gap = 90

    if lv_to_hv_gap is not None and lv_to_hv_gap >= 0.5 * lv_hv_gap:
        return lv_to_hv_gap
    return lv_hv_gap


def get_lmt(lv_id, lv_od):
    return ((lv_id + lv_od) / 2000) * math.pi


def get_rect_lmt(id_width, id_depth, od_width, od_depth, rad_thick, is_round):
    perimeter = id_width + id_depth + od_width + od_depth - (8 * rad_thick)
    if is_round:
        return (perimeter + (2 * math.pi * rad_thick)) * math.pow(10, -3)
    return (perimeter + 4 * math.pow(2 * rad_thick * rad_thick, 0.5)) * math.pow(10, -3)


def get_wire_length(lmt, turns_per_limb, no_of_limbs, no_of_cond):
    if no_of_cond <= 5:
        tolerance = (no_of_cond * 0.01) + 1
    elif no_of_cond <= 10:
        tolerance = (6 * 0.01) + 1
    else:
        tolerance = (7 * 0.01) + 1
    return math.ceil(lmt * turns_per_limb * no_of_limbs * no_of_cond * tolerance)


def get_r75(conductor_material, lmt, turns_per_limb, conductor_cross_section):
    resistivity = 0.02128 if _is_copper(conductor_material) else 0.0346
    return six_digit_decimal(resistivity * lmt * turns_per_limb / conductor_cross_section)


def get_r26(r75, conductor_material):
    absolute_temp = 235 if _is_copper(conductor_material) else 225
    return six_digit_decimal(r75 * ((absolute_temp + 26) / (absolute_temp + 75)))


def get_bare_weight(lmt, no_of_turns, conductor_cross_section, conductor_material):
    density = 8.89 if _is_copper(conductor_material) else 2.703
    return one_digit_decimal(lmt * no_of_turns * 3 * conductor_cross_section * math.pow(10, -3) * density)


def get_insulated_weight(bi, hi, breadth, height, conductor_material, bare_weight, is_enamel):
    material_density = 8.89 if _is_copper(conductor_material) else 2.703
    ins_density = 1.85 if is_enamel else 1.0
    multiplier = (((((bi * hi) - (breadth * height)) / (breadth * height)) * (ins_density / material_density)) + 1)
    return one_digit_decimal(multiplier * bare_weight)


def get_procurement_weight(insulated_weight, no_of_parallel_conductors):
    if no_of_parallel_conductors <= 4:
        return next_integer(insulated_weight * ((no_of_parallel_conductors * 0.01) + 1))
    if no_of_parallel_conductors <= 10:
        return next_integer(insulated_weight * 1.05)
    return next_integer(insulated_weight * 1.06)


def get_stray_loss(breadth, bi, height, turns_per_layer, radial_parallel_conductors, axial_parallel_conductors, conductor_insulation, conductor_material, no_of_layers, transposition, is_round):
    if is_round:
        slf = 0.8 if _is_copper(conductor_material) else 0.63
    else:
        slf = 0.9622 if _is_copper(conductor_material) else 0.76

    term1 = (breadth * turns_per_layer * axial_parallel_conductors) + transposition
    term2 = (bi * turns_per_layer * axial_parallel_conductors) + transposition - conductor_insulation
    term3 = math.pow((math.sqrt(term1 / term2) * slf * height / 10), 4)
    return four_digit_decimal(100 * term3 * (math.pow((no_of_layers * radial_parallel_conductors), 2) - 0.2) / 9)


def get_stray_loss_for_disc(breadth, height, turns_per_layer, radial_parallel_conductors, axial_parallel_conductors, conductor_insulation, conductor_material, no_of_layers, winding_length):
    slf = 0.9622 if _is_copper(conductor_material) else 0.76
    term1 = breadth * turns_per_layer * axial_parallel_conductors
    term2 = winding_length - conductor_insulation
    term3 = math.pow((math.sqrt(term1 / term2) * slf * height / 10), 4)
    return four_digit_decimal(100 * term3 * (math.pow((no_of_layers * radial_parallel_conductors), 2) - 0.2) / 9)


def get_stray_loss_for_x_over(breadth, height, turns_per_layer, no_of_coils, radial_parallel_conductors, axial_parallel_conductors, conductor_insulation, conductor_material, no_of_layers, winding_length, is_round):
    if is_round:
        slf = 0.8 if _is_copper(conductor_material) else 0.63
    else:
        slf = 0.9622 if _is_copper(conductor_material) else 0.76

    term1 = breadth * turns_per_layer * no_of_coils * axial_parallel_conductors
    term2 = winding_length - conductor_insulation
    term3 = math.pow((math.sqrt(term1 / term2) * slf * height / 10), 4)
    return four_digit_decimal(100 * term3 * (math.pow((no_of_layers * radial_parallel_conductors), 2) - 0.2) / 9)


def get_stray_loss_for_foil(height, radial_parallel_cond, conductor_material, no_of_layers):
    slf = 0.9622 if _is_copper(conductor_material) else 0.76
    term1 = math.pow(slf * (height / 10), 4)
    return four_digit_decimal(100 * term1 * (math.pow((no_of_layers * radial_parallel_cond), 2) - 0.2) / 9)


def get_load_loss(conductor_material, bare_weight, current_density, stray_loss):
    llf = 2.4 if _is_copper(conductor_material) else 12.79
    return next_5or0_integer(llf * bare_weight * math.pow(current_density, 2) * ((stray_loss / 100) + 1))


def get_ambient_temp(ambient_temp):
    return 50 if ambient_temp is None else ambient_temp


def get_winding_temp(winding_temp):
    return 55 if winding_temp is None else winding_temp


def get_top_oil_temp(top_oil_temp):
    return 50 if top_oil_temp is None else top_oil_temp


def get_gradient_limit(dry_type, dry_temp_class):
    if not dry_type:
        return 14.5
    if _is_dry_class(dry_temp_class, CLASS_B):
        return 90
    if _is_dry_class(dry_temp_class, CLASS_F):
        return 105
    if _is_dry_class(dry_temp_class, CLASS_H):
        return 115
    return 14.5


def get_lv_gradient(load_loss, available_surface_for_cooling, winding_length, transposition, lmt, dry_type, is_lv):
    hdf = 60 if ((available_surface_for_cooling - 2) / 2) != 0 else 55
    if dry_type:
        hdf = 4 if is_lv else 5
    gradient = load_loss / (3 * (available_surface_for_cooling * 0.75) * hdf * (winding_length + transposition) * 0.001 * lmt)
    return one_digit_decimal(gradient)


def get_hv_gradient(load_loss, available_surface_for_cooling, winding_length, transposition, lmt, dry_type):
    hdf = 60 if ((available_surface_for_cooling - 2) / 2) != 0 else 55
    if dry_type:
        hdf = 5
    gradient = load_loss / (3 * (((available_surface_for_cooling - 1) * 0.75) + 1) * hdf * (winding_length + transposition) * 0.001 * lmt)
    return one_digit_decimal(gradient)


def get_lv_gradient_with_partial_duct(load_loss, available_surface_for_cooling, winding_length, lmt):
    hdf = 60 if ((available_surface_for_cooling - 2) / 2) != 0 else 55
    gradient = load_loss / (3 * (available_surface_for_cooling * 0.375) * hdf * winding_length * 0.001 * lmt)
    return one_digit_decimal(gradient)


def get_v0(current_density, cross_sec_per_cond, stray_loss, height_insulated, wdg_temp, amb_temp):
    temperature = two_digit_decimal(wdg_temp + amb_temp)
    alpha = two_digit_decimal((-0.1305 * temperature) + 56.4714)
    term1 = math.pow(current_density, 2) * cross_sec_per_cond * (1 + (stray_loss / 100))
    term2 = 20 * alpha * 0.75 * height_insulated
    return three_digit_decimal(term1 / term2)


def get_psi(breadth_insulated, radial_thickness, duct_size, no_of_ducts):
    eff_rad_thick = (radial_thickness - (no_of_ducts * duct_size)) / (no_of_ducts + 1)
    return three_digit_decimal(0.99 - ((0.4 * 0.75 * breadth_insulated) / eff_rad_thick) - (1.39 / eff_rad_thick))


def get_rw(v0, psi, conductor_insulation):
    term1 = 1.16 * math.pow(v0 * psi, 0.2) * math.pow(10, -4)
    term2 = ((((1 / term1) * 3.2 * math.pow(10, -4)) + conductor_insulation) / 3.2) * 100
    return three_digit_decimal(term2)


def hv_step_voltage(high_voltage, step_percent):
    return one_digit_decimal(step_percent * high_voltage / 100)


def ampere_turns(lv_turns_per_phase, lv_current_per_phase):
    return next_integer(lv_current_per_phase * lv_turns_per_phase)


def h1h2(radial_thickness, no_of_ducts, duct_thickness, conductor_insulation):
    ducts = 1 if no_of_ducts == 0 else no_of_ducts
    return radial_thickness - (((((duct_thickness + conductor_insulation) / 4) + conductor_insulation) * ducts))


def get_l(lv_bi, hv_bi, lv_turns_per_layer, hv_turns_per_layer, lv_axial_cond, hv_axial_cond, lv_cond_ins, hv_cond_ins, lv_wdg_length, hv_wdg_length, is_helical):
    if is_helical:
        return ((lv_bi * lv_turns_per_layer * lv_axial_cond) + (hv_bi * hv_turns_per_layer * hv_axial_cond)) / 2
    return (lv_wdg_length + hv_wdg_length - lv_cond_ins - hv_cond_ins) / 2


def ls(lv_bi, hv_bi, lv_turns_per_layer, hv_turns_per_layer, lv_axial_cond, hv_axial_cond, hv_od, lv_id, lv_cond_ins, hv_cond_ins, lv_wdg_length, hv_wdg_length, lv_winding_type, hv_winding_type, lv_transposition, hv_transposition, hv_no_of_coils):
    if _is_winding_type(lv_winding_type, "HELICAL") and _is_winding_type(hv_winding_type, "HELICAL"):
        l_value = two_digit_decimal(((lv_bi * lv_turns_per_layer * lv_axial_cond) + lv_transposition + (hv_bi * hv_turns_per_layer * hv_axial_cond) + hv_transposition - lv_cond_ins - hv_cond_ins) / 2)
    elif _is_winding_type(lv_winding_type, "HELICAL") and _is_winding_type(hv_winding_type, "XOVER"):
        l_value = two_digit_decimal(((lv_bi * lv_turns_per_layer * lv_axial_cond) + lv_transposition + (hv_bi * hv_turns_per_layer * hv_no_of_coils) - lv_cond_ins - hv_cond_ins) / 2)
    elif _is_winding_type(lv_winding_type, "HELICAL") and _is_winding_type(hv_winding_type, "DISC"):
        l_value = two_digit_decimal(((lv_bi * lv_turns_per_layer * lv_axial_cond) + lv_transposition + hv_wdg_length - lv_cond_ins - hv_cond_ins) / 2)
    else:
        term2 = (lv_wdg_length + (hv_bi * hv_turns_per_layer * hv_axial_cond) - lv_cond_ins - hv_cond_ins) / 2
        if _is_winding_type(lv_winding_type, "DISC") and _is_winding_type(hv_winding_type, "HELICAL"):
            l_value = two_digit_decimal(term2)
        else:
            term1 = (lv_wdg_length + (hv_bi * hv_turns_per_layer * hv_no_of_coils) - lv_cond_ins - hv_cond_ins) / 2
            if _is_winding_type(lv_winding_type, "DISC") and _is_winding_type(hv_winding_type, "XOVER"):
                l_value = two_digit_decimal(term1)
            elif _is_winding_type(lv_winding_type, "FOIL") and _is_winding_type(hv_winding_type, "HELICAL"):
                l_value = two_digit_decimal(term2)
            elif _is_winding_type(lv_winding_type, "FOIL") and _is_winding_type(hv_winding_type, "XOVER"):
                l_value = two_digit_decimal(term1)
            else:
                l_value = two_digit_decimal((lv_wdg_length + hv_wdg_length - lv_cond_ins - hv_cond_ins) / 2)

    breadth = two_digit_decimal((hv_od - lv_id - lv_cond_ins - hv_cond_ins) / 2)
    power = math.pi * l_value / breadth
    k_r = three_digit_decimal(1 - ((1 - math.exp(-power)) / power))
    return [three_digit_decimal(l_value / k_r), l_value, breadth, k_r]


def ex(volts_per_turn, lv_hv_gap, lv_cond_ins, hv_cond_ins, h1, h2, ampere_turn_value, ls_value, lv_od, frequency_factor):
    delta = lv_hv_gap + ((hv_cond_ins + lv_cond_ins) / 2)
    delta1 = delta + ((h2 + h1) / 3)
    ds = lv_od - lv_cond_ins + delta + ((h2 - h1) / 3)
    term1 = 1.24 * ampere_turn_value * delta1 * ds * math.pow(10, -4)
    return [delta, delta1, ds, two_digit_decimal((term1 / (volts_per_turn * ls_value)) * frequency_factor)]


def er(lv_load_loss, hv_load_loss, kva, phase_current, low_voltage):
    if low_voltage <= 1100:
        if phase_current <= 300:
            tank_loss_factor = 0.8
        elif phase_current <= 700:
            tank_loss_factor = 1
        elif phase_current <= 2000:
            tank_loss_factor = 1.5
        elif phase_current <= 4000:
            tank_loss_factor = 2
        else:
            tank_loss_factor = 3
    else:
        tank_loss_factor = 0.4 if low_voltage <= 33000 else 0.3

    total_load_loss = lv_load_loss + hv_load_loss + (tank_loss_factor * kva)
    return two_digit_decimal((total_load_loss / (kva * math.pow(10, 3))) * 100)


def ek(er_value, ex_value):
    return two_digit_decimal(math.sqrt(math.pow(er_value, 2) + math.pow(ex_value, 2)))


def get_hv_hv_gap(kva, lv_voltage, hv_voltage, vector_group, hv_to_hv_gap=None, dry_type=False):
    difference_voltage = hv_voltage - lv_voltage
    if dry_type:
        if hv_voltage <= 3300:
            if kva <= 50:
                hv_hv_gap = 12
            elif kva <= 500:
                hv_hv_gap = 20
            else:
                hv_hv_gap = 36
        elif hv_voltage <= 11000:
            hv_hv_gap = 36
        elif hv_voltage <= 22000:
            hv_hv_gap = 54
        elif hv_voltage <= 33000:
            hv_hv_gap = 90
        else:
            hv_hv_gap = 100
    else:
        if difference_voltage <= 11000:
            if kva <= 100:
                hv_hv_gap = 7
            elif kva <= 1000:
                hv_hv_gap = 8
            else:
                hv_hv_gap = 10
        elif difference_voltage <= 33000:
            hv_hv_gap = 16
        elif hv_voltage <= 66000:
            hv_hv_gap = 35 if _vector_group_char(vector_group, 0) == "D" else 25
        elif hv_voltage <= 132000:
            hv_hv_gap = 60 if _vector_group_char(vector_group, 0) == "D" else 25
        else:
            hv_hv_gap = 7

    if hv_to_hv_gap is not None and hv_to_hv_gap >= 0.65 * hv_hv_gap:
        return hv_to_hv_gap
    return hv_hv_gap


def get_center_distance(hv_od, hv_hv_gap):
    return next_integer(hv_od + hv_hv_gap)


def get_core_length(core_diameter, window_height, center_distance):
    return (2 * core_diameter) + (3 * window_height) + (4 * center_distance)


def get_core_weight(core_length, net_core_area):
    return next_integer(core_length * net_core_area * 7.65 * math.pow(10, -6))


def get_core_loss(core_weight, build_factor, specific_loss):
    return next_5or0_integer(core_weight * build_factor * specific_loss)


def get_tank_loss(kva, phase_current, low_voltage, tank_loss=None, dry_type=False):
    if tank_loss is not None:
        return tank_loss

    if low_voltage <= 1100:
        if phase_current <= 300:
            factor = 0.8
        elif phase_current <= 700:
            factor = 1
        elif phase_current <= 2000:
            factor = 1.5
        elif phase_current <= 4000:
            factor = 2
        else:
            factor = 3
    else:
        factor = 0.4 if low_voltage <= 33000 else 0.3

    if dry_type:
        factor = 0.5
    return next_5or0_integer(kva * factor)


def get_kw55(core_loss, lv_load_loss, hv_load_loss, tank_loss, lv_gradient, hv_gradient):
    gradient55 = 14.5 if lv_gradient < 14.5 and hv_gradient < 14.5 else max(lv_gradient, hv_gradient)
    new_top_oil_temperature = 98 - 32 - (1.1 * gradient55)
    if new_top_oil_temperature <= 0:
        raise ValueError(
            "Invalid KW55 thermal state: computed top oil temperature is non-positive "
            f"for gradients LV={lv_gradient}, HV={hv_gradient}"
        )
    kw55_factor = math.pow(55 / new_top_oil_temperature, (1 / 0.7))
    total_loss = core_loss + (1.1 * (lv_load_loss + hv_load_loss + tank_loss))
    return next_5or0_integer(kw55_factor * total_loss)


def get_kw55_for_multiple_windings(core_loss, winding_load_losses, tank_loss, winding_gradients):
    gradients = [max(0.0, float(gradient)) for gradient in winding_gradients if gradient is not None]
    peak_gradient = max(gradients, default=0.0)
    gradient55 = 14.5 if peak_gradient < 14.5 else peak_gradient
    new_top_oil_temperature = 98 - 32 - (1.1 * gradient55)
    if new_top_oil_temperature <= 0:
        raise ValueError(
            "Invalid KW55 thermal state: computed top oil temperature is non-positive "
            f"for peak gradient {peak_gradient}"
        )
    kw55_factor = math.pow(55 / new_top_oil_temperature, (1 / 0.7))
    total_loss = core_loss + (1.1 * (sum(winding_load_losses) + tank_loss))
    return next_5or0_integer(kw55_factor * total_loss)


def get_disc_duct_size(line_voltage, is_inner_wdg, vector_group, disc_duct_from_user=None):
    if line_voltage <= 33000:
        disc_duct_size = 3 if is_inner_wdg else 3.5
    elif line_voltage <= 66000:
        if not is_inner_wdg:
            disc_duct_size = 4.5 if _vector_group_char(vector_group, 0) == "D" else 4
        else:
            disc_duct_size = 4.5 if _vector_group_char(vector_group, 1) == "d" else 4
    elif line_voltage <= 132000:
        disc_duct_size = 5 if _vector_group_char(vector_group, 0) == "D" else 4.5
    else:
        disc_duct_size = 0

    return disc_duct_size if disc_duct_from_user is None else disc_duct_from_user


def get_spacers_and_width(hv_id, no_of_discs, excess_turns):
    circumference = next_0_integer(math.pi * hv_id * 0.26)
    no_of_spacers = max(int(no_of_discs / excess_turns), 8)
    width = int(math.ceil(circumference / no_of_spacers))

    while width >= 40:
        no_of_spacers += 2
        width = int(math.ceil(circumference / no_of_spacers))
        if width < 40:
            break

    while width <= 25:
        no_of_spacers -= 2
        width = int(math.ceil(circumference / no_of_spacers))
        if width > 40:
            break

    return [no_of_spacers, previous_5or0_integer(width)]


def get_foil_end_strip(wdg_length):
    return 5 if wdg_length <= 500 else 10


def get_foil_length(winding_length, foil_length=None, end_strip=None):
    if foil_length is not None:
        return int(math.floor(foil_length))
    return previous_5or0_integer(winding_length - (end_strip * 2))


def get_no_of_coils(voltage, no_of_coils_from_user=None):
    if no_of_coils_from_user is not None:
        return no_of_coils_from_user
    if voltage <= 11000:
        return 4
    if voltage <= 33000:
        return 6
    return 4


def get_gap_between_coils(kva, high_voltage, is_dry):
    gap = 12
    if high_voltage <= 11000:
        if kva <= 100:
            gap = 4
        elif kva <= 1000:
            gap = 5
        else:
            gap = 6
    elif high_voltage <= 33000:
        gap = 6 if kva <= 2500 else 10

    if is_dry:
        if high_voltage <= 11000:
            if kva <= 100:
                gap = 8
            elif kva <= 250:
                gap = 10
            elif kva <= 500:
                gap = 12
            elif kva <= 1000:
                gap = 16
            else:
                gap = 20
        elif high_voltage <= 33000:
            gap = 16 if kva <= 2500 else 20
    return gap


def get_winding_length_per_coil(winding_length, gap_bw_coil, no_of_coils):
    return int(math.floor((winding_length - (gap_bw_coil * (no_of_coils - 1))) / no_of_coils))


def interpolate_specific_loss(req_flux_den, lower_flux_den, upper_flux_den, lower_specific_loss, upper_specific_loss, frequency):
    term1 = (req_flux_den - lower_flux_den) * (upper_specific_loss - lower_specific_loss)
    specific_loss = lower_specific_loss + (term1 / (upper_flux_den - lower_flux_den))
    if frequency == 60:
        return two_digit_decimal(specific_loss * 1.32)
    return two_digit_decimal(specific_loss)


def get_limit_ez(kva, limit_ez=None):
    if limit_ez is not None:
        return limit_ez
    if kva <= 10:
        return 10.5
    if kva <= 630:
        return 4.5
    if kva <= 1250:
        return 5
    if kva <= 3150:
        return 6.25
    if kva <= 6300:
        return 7.15
    if kva <= 12500:
        return 8.35
    if kva <= 25000:
        return 10
    return 12.5


def is_ez_within_range(limit_ez, ez, deviation_percentage):
    min_ez = limit_ez * (100 - deviation_percentage) / 100
    max_ez = limit_ez * (100 + deviation_percentage) / 100
    return min_ez <= ez <= max_ez


def get_modified_limb_ht_for_impedance(ez, limit_ez, limb_ht, kva):
    if kva > 1600:
        if ez < limit_ez:
            return limb_ht - ((limb_ht - ((ez / limit_ez) * limb_ht)) * 0.15)
        return limb_ht + ((limb_ht + ((ez / limit_ez) * limb_ht)) * 0.15)
    if kva < 20:
        if ez < limit_ez:
            return limb_ht - ((((ez / limit_ez) * limb_ht)) * 0.05)
        return limb_ht + ((((ez / limit_ez) * limb_ht)) * 0.05)
    if ez < limit_ez:
        return limb_ht - ((limb_ht - ((ez / limit_ez) * limb_ht)) * 0.5)
    return limb_ht + ((limb_ht + ((ez / limit_ez) * limb_ht)) * 0.5)


def get_efficiency_percentage(kva, total_load_loss, no_load_loss, load_factor, power_factor):
    term1 = (kva * math.pow(10, 3) * power_factor * load_factor) + no_load_loss + (math.pow(load_factor, 2) * total_load_loss)
    efficiency = (kva * math.pow(10, 3) * power_factor * load_factor) * 100 / term1
    return two_digit_decimal(efficiency)


def get_voltage_regulation(er_value, ex_value, power_factor):
    sin_phi = math.sqrt(1 - math.pow(power_factor, 2))
    term1 = math.pow((ex_value * power_factor) - (er_value * sin_phi), 2) / 200
    return two_digit_decimal((er_value * power_factor) + (ex_value * sin_phi) + term1)


def get_turns_at_tap(high_voltage, no_of_taps, tap_step_negative, tap_step_percent, volts_per_turn, vector_group):
    turns_at_tap = []
    least_tap = 100 - (tap_step_negative * tap_step_percent)
    factor = math.sqrt(3) if _vector_group_char(vector_group, 0) == "Y" else 1
    turns_at_tap.append(int(least_tap * high_voltage / (volts_per_turn * factor * 100)))
    for _ in range(no_of_taps - 1):
        least_tap += tap_step_percent
        turns_at_tap.append(int(least_tap * high_voltage / (volts_per_turn * factor * 100)))
    return turns_at_tap


def get_tap_voltages(high_voltage, tap_step_negative, tap_step_positive, tap_step_percent):
    voltage_step = int(math.floor(high_voltage * tap_step_percent / 100))
    tap_voltages = []
    for i in range(tap_step_positive, 0, -1):
        tap_voltages.append(int(math.floor(high_voltage + (i * voltage_step))))
    tap_voltages.append(int(high_voltage))
    for i in range(1, tap_step_negative + 1):
        tap_voltages.append(int(math.floor(high_voltage - (i * voltage_step))))
    return tap_voltages


def get_tap_currents(no_of_taps, tap_voltages, kva):
    return [two_digit_decimal((kva * 1000) / (3 * tap_voltages[i])) for i in range(no_of_taps)]


def get_test_and_imp_test(voltage):
    test_voltage = 3
    if voltage > 1100:
        test_voltage = 10
    if voltage > 3600:
        test_voltage = 20
    if voltage > 7200:
        test_voltage = 28
    if voltage > 12000:
        test_voltage = 50
    if voltage > 24000:
        test_voltage = 70
    if voltage > 36000:
        test_voltage = 140
    if voltage > 72500:
        test_voltage = 230
    if voltage > 123000:
        test_voltage = 275

    if voltage <= 1100:
        impulse_test_voltage = 0
    elif voltage <= 3600:
        impulse_test_voltage = 40
    elif voltage <= 7200:
        impulse_test_voltage = 60
    elif voltage <= 12000:
        impulse_test_voltage = 75
    elif voltage <= 24000:
        impulse_test_voltage = 125
    elif voltage <= 36000:
        impulse_test_voltage = 170
    elif voltage <= 72500:
        impulse_test_voltage = 325
    elif voltage <= 133000:
        impulse_test_voltage = 550
    else:
        impulse_test_voltage = 650
    return [test_voltage, impulse_test_voltage]


def get_core_lv_ins(lv_wdg_type, core_lv_gap):
    if _is_winding_type(lv_wdg_type, "DISC") or _is_winding_type(lv_wdg_type, "LAYERDISC"):
        return "3mm PB + rest Oil"
    return "0.5mm PB + rest Oil" if core_lv_gap <= 2 else "1mm PB + rest Oil"


def get_lv_hv_ins(lv_wdg_type, hv_wdg_type, lv_hv_gap):
    if _is_winding_type(lv_wdg_type, "DISC") or _is_winding_type(hv_wdg_type, "DISC"):
        return "3mm PB + rest Oil"
    if _is_winding_type(lv_wdg_type, "LAYERDISC") or _is_winding_type(hv_wdg_type, "LAYERDISC"):
        return "3mm PB + rest Oil"
    if lv_hv_gap <= 8:
        if lv_hv_gap % 2 == 0:
            return f"1mm PB + {math.ceil((lv_hv_gap - 1) / 2)}mm towards Lv {math.floor((lv_hv_gap - 1) / 2)}mm towards Hv"
        return f"1mm PB + {(lv_hv_gap - 1) / 2}mm on both sides"
    if lv_hv_gap <= 16:
        if lv_hv_gap % 2 == 0:
            return f"1mm x 2 PB + {(lv_hv_gap - 2) / 2}mm on both sides"
        return f"1mm x 2 PB + {math.ceil((lv_hv_gap - 2) / 2)}mm towards Lv {math.floor((lv_hv_gap - 2) / 2)}mm towards Hv"
    if lv_hv_gap % 2 == 0:
        return f"1mm x 3 PB + {math.ceil((lv_hv_gap - 3) / 2)}mm towards Lv {math.floor((lv_hv_gap - 3) / 2)}mm towards Hv"
    return f"1mm x 3 PB + {(lv_hv_gap - 3) / 2}mm on both sides"


def get_hv_hv_ins(lv_wdg_type, hv_wdg_type, hv_hv_gap):
    if _is_winding_type(lv_wdg_type, "DISC") or _is_winding_type(hv_wdg_type, "DISC"):
        return "1mm x 3 PB + rest Oil"
    if _is_winding_type(lv_wdg_type, "LAYERDISC") or _is_winding_type(hv_wdg_type, "LAYERDISC"):
        return "1mm x 3 PB + rest Oil"
    return "1mm x 2 PB + rest Oil" if hv_hv_gap <= 16 else "1mm x 4 PB + rest Oil"


def get_nl_current_percentage(core_weight, specific_loss, kva):
    return two_digit_decimal(core_weight * specific_loss / kva)


def get_loss_at_50_percent(core_loss, tank_loss, lv_load_loss, hv_load_loss_at_normal):
    return next_integer(((tank_loss + lv_load_loss + hv_load_loss_at_normal) / 4) + core_loss)


def get_loss_at_100_percent(core_loss, tank_loss, lv_load_loss, hv_load_loss_at_normal):
    return next_integer(tank_loss + lv_load_loss + hv_load_loss_at_normal + core_loss)


def get_largest_blade(core_diameter):
    return core_diameter - 3 - ((core_diameter - 3) % 5)


def get_yoke_insulation(kva):
    if kva <= 100:
        return 10
    if kva < 2500:
        return 15
    return 25


def get_wdg_to_tank_gap(hv_voltage, kva, wdg_to_tank_user=None):
    if wdg_to_tank_user is not None:
        return wdg_to_tank_user
    if hv_voltage <= 11000:
        return 25 if kva <= 500 else 30
    if hv_voltage <= 33000:
        return 40 if kva <= 100 else 50
    return 130


def get_tank_length(hv_od, center_distance, hv_voltage, kva, is_oltc, wdg_to_tank_user=None):
    wdg_tank_gap = get_wdg_to_tank_gap(hv_voltage, kva, wdg_to_tank_user)
    oltc_gap = 200 if is_oltc and kva > 160 else 0
    return next_5or0_integer(hv_od + (2 * center_distance) + (2 * wdg_tank_gap) + oltc_gap)


def get_connection_gap(hv_voltage, con_gap_user=None):
    if con_gap_user is not None:
        return con_gap_user
    if hv_voltage <= 11000:
        return 25
    if hv_voltage <= 33000:
        return 30
    return 100


def get_tank_width(hv_od, hv_voltage, kva, con_gap_user=None, wdg_to_tank_user=None):
    wdg_tank_gap = get_wdg_to_tank_gap(hv_voltage, kva, wdg_to_tank_user)
    connection_gap = get_connection_gap(hv_voltage, con_gap_user)
    return next_5or0_integer(hv_od + (2 * wdg_tank_gap) + connection_gap)


def get_top_yoke_to_cover(kva, hv_voltage, is_oltc, top_to_cover_user=None):
    if top_to_cover_user is not None:
        return top_to_cover_user
    if is_oltc:
        if hv_voltage <= 11000:
            if kva <= 160:
                return 60
            if kva <= 1000:
                return 75
            return 100
    else:
        if hv_voltage <= 11000:
            if kva <= 160:
                return 60
            if kva <= 1000:
                return 175
            return 190
        if hv_voltage <= 33000:
            return 190 if kva <= 1000 else 200
    return 60


def get_tank_height(window_height, largest_blade, kva, hv_voltage, is_oltc, tap_step_percent, top_yoke_to_cover_user):
    if is_oltc:
        if hv_voltage <= 11000:
            if kva <= 160:
                top_yoke_to_cover = 60
            elif kva <= 1000:
                top_yoke_to_cover = 75
            else:
                top_yoke_to_cover = 100
        else:
            top_yoke_to_cover = 60
    else:
        if hv_voltage <= 11000:
            if kva <= 160:
                top_yoke_to_cover = 60 if tap_step_percent == 0 else 175
            elif kva <= 1000:
                top_yoke_to_cover = 175
            else:
                top_yoke_to_cover = 190
        elif hv_voltage <= 33000:
            top_yoke_to_cover = 190 if kva <= 1000 else 200
        else:
            top_yoke_to_cover = 60

    yoke_insulation = get_yoke_insulation(kva)
    if top_yoke_to_cover_user != 0:
        top_yoke_to_cover = top_yoke_to_cover_user
    return next_5or0_integer(window_height + (2 * largest_blade) + yoke_insulation + top_yoke_to_cover)


def get_tank_capacity(tank_length, tank_width, tank_height):
    return next_integer(tank_length * tank_width * tank_height * math.pow(10, -6))


def get_lid_thickness(kva):
    if kva <= 63:
        return 3
    if kva <= 200:
        return 4
    if kva <= 400:
        return 5
    if kva <= 1000:
        return 6
    if kva <= 2500:
        return 8
    if kva <= 5000:
        return 10
    if kva <= 20000:
        return 12
    if kva <= 40000:
        return 16
    return 20


def get_tank_wall_thickness(kva):
    if kva <= 63:
        return 2.5
    if kva <= 400:
        return 4
    if kva <= 1000:
        return 5
    if kva <= 5000:
        return 6
    return 8


def get_tank_bottom_thickness(kva):
    if kva <= 63:
        return 3
    if kva <= 200:
        return 4
    if kva <= 400:
        return 5
    if kva <= 1000:
        return 6
    if kva <= 5000:
        return 8
    if kva <= 10000:
        return 10
    if kva <= 20000:
        return 12
    if kva <= 40000:
        return 16
    return 20


def get_frame_thickness(kva):
    if kva <= 63:
        return 6
    if kva <= 200:
        return 8
    if kva <= 630:
        return 10
    if kva <= 10000:
        return 12
    if kva <= 20000:
        return 14
    if kva <= 40000:
        return 18
    return 25


def get_connection_weight(conductor_xsec, conductor_material, length):
    material_density = 8.89 if _is_copper(conductor_material) else 2.703
    return one_digit_decimal((length * conductor_xsec * material_density) * 6 * math.pow(10, -6))


def get_tap_ins_weight(bare_wt, insulated_wt, hv_turns_at_highest, hv_turns_at_lowest):
    return one_digit_decimal((insulated_wt - bare_wt) * ((hv_turns_at_highest - hv_turns_at_lowest) / hv_turns_at_highest))


def get_tap_lead_weight(hv_cond_cross_sec, hv_cond_material, is_oltc, cen_dist, limb_ht, hv_od, core_dia, positive_tap, negative_tap, hv_cond_ins):
    material_density = 8.89 if _is_copper(hv_cond_material) else 2.703
    tap_count = positive_tap + negative_tap
    if is_oltc:
        tap_lead_length = (cen_dist + (hv_od / 2) + 500) * tap_count * 3
    else:
        tap_lead_length = (limb_ht + core_dia + 400) * tap_count * 3
    tap_lead_ins_weight = (0.5 * hv_cond_cross_sec + 16) * tap_lead_length * hv_cond_ins * math.pow(10, -6)
    return next_integer((tap_lead_length * 1.5 * hv_cond_cross_sec * material_density * math.pow(10, -6)) + tap_lead_ins_weight)


def get_channel_weight(largest_blade, tank_length):
    condition_large_blade = 0.6 * largest_blade
    if condition_large_blade <= 75:
        ismc_weight = 6.8
    elif condition_large_blade <= 100:
        ismc_weight = 9.2
    elif condition_large_blade <= 125:
        ismc_weight = 12.7
    elif condition_large_blade <= 150:
        ismc_weight = 16.4
    elif condition_large_blade <= 175:
        ismc_weight = 19.1
    elif condition_large_blade <= 200:
        ismc_weight = 22.1
    elif condition_large_blade <= 225:
        ismc_weight = 25.9
    elif condition_large_blade <= 250:
        ismc_weight = 30.4
    elif condition_large_blade <= 300:
        ismc_weight = 38.8
    elif condition_large_blade <= 350:
        ismc_weight = 42.1
    else:
        ismc_weight = 49.4
    return one_digit_decimal(ismc_weight * 1.2 * tank_length * 4)


def displacement_volume(mass, density):
    return one_digit_decimal(mass / density)


def get_insulation_wt(kva, hv_voltage, vector_group):
    insulation_wt = next_integer(math.pow(kva / 63.0, 0.75) * 7.5)
    if 11000 < hv_voltage < 33000:
        insulation_wt = math.floor(insulation_wt * 1.1)
    elif 33000 <= hv_voltage < 66000:
        insulation_wt = math.floor(insulation_wt * 1.2)
    elif 66000 <= hv_voltage < 132000 and _vector_group_char(vector_group, 0) == "Y":
        insulation_wt = math.floor(insulation_wt * 1.4)
    elif 66000 <= hv_voltage < 132000 and _vector_group_char(vector_group, 0) == "D":
        insulation_wt = math.floor(insulation_wt * 1.6)
    elif hv_voltage >= 132000 and _vector_group_char(vector_group, 0) == "Y":
        insulation_wt = math.floor(insulation_wt * 1.8)
    elif hv_voltage >= 132000 and _vector_group_char(vector_group, 0) == "D":
        insulation_wt = math.floor(insulation_wt * 2.0)
    return insulation_wt


def get_heat_dis_by_tank_wall(tank_length, tank_width, tank_height):
    return next_integer(((tank_length + tank_width) * 2 * tank_height) * 500 * math.pow(10, -6))


def get_top_oil_temperature(lv_gradient, hv_gradient):
    gradient = 14.5 if lv_gradient < 14.5 and hv_gradient < 14.5 else max(lv_gradient, hv_gradient)
    return one_digit_decimal(98 - 32 - (1.1 * gradient))


def get_radiator_area(heat_to_be_dissipated, top_oil_temperature, top_oil_temp_user):
    top_oil_temperature_1 = min(top_oil_temperature, top_oil_temp_user)
    if 35 <= top_oil_temperature_1 < 40:
        watts_per_msq = 300
    elif 40 <= top_oil_temperature_1 < 45:
        watts_per_msq = 350
    elif 45 <= top_oil_temperature_1 < 50:
        watts_per_msq = 400
    else:
        watts_per_msq = 450
    return two_digit_decimal(heat_to_be_dissipated / watts_per_msq)


def get_radiator_height(tank_height, largest_blade, yoke_insulation):
    if tank_height <= 600:
        return 300
    if tank_height <= 700:
        return 400
    if tank_height <= 750:
        return 500

    radiator_height = int(tank_height - largest_blade - 120 - yoke_insulation)
    factor = radiator_height % 100
    if factor < 65:
        return radiator_height - factor
    return radiator_height - factor + 100


def get_radiator_width(radiator_height, user_rad_width=None):
    if user_rad_width is not None:
        return user_rad_width
    if radiator_height >= 800:
        return 520
    if 500 <= radiator_height <= 700:
        return 300
    return 226


def get_radiator_section(no_of_fins):
    if no_of_fins <= 8:
        no_of_radiators = 2
    elif no_of_fins <= 80:
        no_of_radiators = 4
    elif no_of_fins <= 120:
        no_of_radiators = 6
    elif no_of_fins <= 160:
        no_of_radiators = 8
    elif no_of_fins <= 200:
        no_of_radiators = 10
    else:
        no_of_radiators = 12

    section = next_integer(no_of_fins / no_of_radiators)
    revised_no_of_fins = section * no_of_radiators
    return [section, no_of_radiators, revised_no_of_fins]


def _vb_round1(value):
    return math.floor((value + 0.095) * 10) / 10.0


def _get_csp_heat(tank_length, tank_width, tank_height):
    tank_perimeter = 2 * (tank_length + tank_width)
    csp_air_height = tank_height * 0.55
    return tank_perimeter * csp_air_height * 250 / 1_000_000.0


def _get_temp_dependence_factor(temp_wdg, temp_top):
    return 400 - (temp_wdg - temp_top) * 8


def _get_radiator_length(tank_height, core_dia):
    clear_height = tank_height - core_dia - 85
    return int((clear_height + 50) // 100) * 100


def _get_max_sections(kva):
    if kva <= 63:
        return 10
    if kva <= 250:
        return 16
    if kva <= 500:
        return 32
    if kva <= 1600:
        return 72
    return 200


def _get_max_sections_per_radiator(kva):
    if kva <= 63:
        return 5
    if kva <= 250:
        return 6
    if kva <= 500:
        return 8
    if kva <= 1600:
        return 12
    return 19


def _get_default_radiator_width(kva):
    if kva <= 100:
        return 226
    if kva < 5000:
        return 300
    return 520


def _get_max_radiator_banks(tank_length, radiator_width, terminal_lv, terminal_hv):
    pitch = radiator_width + 70
    available_length = 2 * (tank_length + 200)
    radiator_banks = (int(available_length / pitch) // 2) * 2

    if _normalize_upper(terminal_lv) == "CABLE BOX":
        radiator_banks -= 2
    if _normalize_upper(terminal_hv) == "CABLE BOX":
        radiator_banks -= 2
    return max(2, radiator_banks)


def _get_radiator_sections(radiator_area, radiator_length, radiator_width, radiator_banks):
    area_in_sq_mm = radiator_area * 1_000_000
    section_area = radiator_length * 2 * radiator_width
    return int(((area_in_sq_mm / section_area) + 1) / radiator_banks)


def _get_radiator_section_weight_and_oil(radiator_length, radiator_width):
    if radiator_width <= 226:
        length_step = (radiator_length - 500) / 100.0
        width_factor = radiator_width / 226.0
        return (
            2.55 + length_step * 0.45 * width_factor,
            1.25 + length_step * 0.15 * width_factor,
        )
    if radiator_width <= 500:
        length_step = (radiator_length - 500) / 100.0
        width_factor = radiator_width / 300.0
        return (
            3.25 + length_step * 0.6 * width_factor,
            1.55 + length_step * 0.2 * width_factor,
        )

    length_step = (radiator_length - 600) / 100.0
    width_factor = radiator_width / 520.0
    return (
        6.52 + length_step * width_factor,
        2.52 + length_step * 0.4 * width_factor,
    )


def select_radiators(
    kva,
    cu_loss,
    fe_loss,
    tank_length,
    tank_width,
    tank_height,
    core_dia,
    temp_wdg,
    temp_top,
    terminal_lv=None,
    terminal_hv=None,
    *,
    dry_type=False,
    radiator_selection_enabled=True,
    csp_radiator=False,
    csp_only=False,
    pipes_only=False,
    csp_pipes=False,
    pipe_dia=38,
    user_rad_width=None,
):
    # Port of VB6 Sub Radiators().
    # This replaces radiator sizing from the older kw55-based approach.
    # Keep get_kw55* only as legacy reference; radiator selection is now
    # driven directly from CuLoss, FeLoss, TempWdg and TempTop.
    total_loss = cu_loss + fe_loss
    tank_dissipation = (tank_length + tank_width) * tank_height / 1000.0
    new_tank_height = 0.0
    pipe_length = 0.0
    total_radiator_weight = 0
    total_radiator_oil = 0.0
    csp_heat = 0.0

    def _build_result(**overrides):
        result = {
            "selectionText": "",
            "radiatorLength": 0,
            "radiatorWidth": 0,
            "radiatorSections": 0,
            "radiatorBanks": 0,
            "radiatorArea": 0.0,
            "temperatureDependenceFactor": 0.0,
            "tankDissipation": tank_dissipation,
            "cspHeat": csp_heat,
            "totalLoss": total_loss,
            "newTankHeight": new_tank_height,
            "pipeLength": pipe_length,
            "pipeOil": 0.0,
            "totalRadiatorWeight": total_radiator_weight,
            "totalRadiatorOil": total_radiator_oil,
            "extendedLayout": False,
        }
        result.update(overrides)
        return result

    def _no_radiator_result():
        nonlocal csp_heat, new_tank_height, pipe_length, total_radiator_weight, total_radiator_oil

        selection_text = ""
        if dry_type:
            return _build_result(
                selectionText=" NIL ",
                cspHeat=0.0,
                newTankHeight=0.0,
                pipeLength=0.0,
                totalRadiatorWeight=0,
                totalRadiatorOil=0.0,
            )

        if csp_only or csp_pipes:
            csp_heat = _get_csp_heat(tank_length, tank_width, tank_height)
            new_tank_height = tank_height * 1.55

        if pipes_only or csp_pipes:
            pipe_heat = total_loss - tank_dissipation - csp_heat
            pipe_heat_rate = math.pi * (pipe_dia / 1000.0) * 350
            if pipe_heat_rate > 0:
                pipe_length = _vb_round1(pipe_heat / pipe_heat_rate)
            if pipe_length > 0:
                selection_text = f"{pipe_dia}mm Pipes x {pipe_length} M "
                pipe_oil = math.pi * (pipe_dia / 100.0) * pipe_length
                total_radiator_oil += pipe_oil
                pipe_wall_volume = math.pi * 7.65 * 100 * (pipe_dia / 1000.0) * 3 / 1000.0
                total_radiator_weight = int(pipe_wall_volume * pipe_length) + 1
            else:
                pipe_oil = 0.0
        else:
            pipe_oil = 0.0

        if new_tank_height > 0:
            selection_text = f"{selection_text}:TankNewH = {int(new_tank_height)}" if selection_text else f":TankNewH = {int(new_tank_height)}"

        return _build_result(
            selectionText=selection_text,
            cspHeat=csp_heat,
            newTankHeight=new_tank_height,
            pipeLength=pipe_length,
            pipeOil=pipe_oil,
            totalRadiatorWeight=total_radiator_weight,
            totalRadiatorOil=total_radiator_oil,
        )

    if dry_type:
        return _no_radiator_result()

    if not radiator_selection_enabled or csp_only or pipes_only or csp_pipes:
        return _no_radiator_result()

    if csp_radiator:
        csp_heat = _get_csp_heat(tank_length, tank_width, tank_height)
        new_tank_height = tank_height * 1.55

    extralong = 0
    temp_dependence_factor = _get_temp_dependence_factor(temp_wdg, temp_top)
    radiator_length = _get_radiator_length(tank_height, core_dia)
    radiator_area = (total_loss - tank_dissipation - csp_heat) / temp_dependence_factor

    if radiator_area <= 0:
        return _no_radiator_result()

    max_sections = _get_max_sections(kva)
    max_sections_per_radiator = _get_max_sections_per_radiator(kva)
    radiator_width = _get_default_radiator_width(kva)
    max_radiator_banks = _get_max_radiator_banks(tank_length, radiator_width, terminal_lv, terminal_hv)

    if user_rad_width not in (None, 0):
        radiator_width = user_rad_width
        extralong = -1

    while True:
        radiator_banks = 2 if kva < 100 else 4

        while True:
            radiator_sections = _get_radiator_sections(
                radiator_area,
                radiator_length,
                radiator_width,
                radiator_banks,
            )
            if radiator_sections > max_sections_per_radiator:
                radiator_banks += 2
                if radiator_banks > max_radiator_banks:
                    radiator_banks -= 2
                    break
                continue
            break

        if extralong < 0:
            break

        if radiator_sections <= max_sections_per_radiator:
            break

        if radiator_width < 300:
            radiator_width = 300
            continue
        if radiator_width < 520:
            radiator_width = 520
            continue
        if extralong == 0:
            extralong = 1
            max_radiator_banks += 2
            continue

        extralong = 2
        radiator_length += 300

    selection_text = f"{radiator_length} x {radiator_width} - {radiator_sections} x {radiator_banks}"
    if extralong >= 1:
        selection_text = f"{selection_text}++"
    if extralong == 2:
        selection_text = f"++{selection_text}"

    radiator_weight, radiator_oil = _get_radiator_section_weight_and_oil(
        radiator_length,
        radiator_width,
    )

    total_radiator_weight = int(radiator_weight * radiator_banks * radiator_sections)
    total_radiator_oil = int(radiator_oil * radiator_banks * radiator_sections)

    return _build_result(
        selectionText=selection_text,
        radiatorLength=radiator_length,
        radiatorWidth=radiator_width,
        radiatorSections=radiator_sections,
        radiatorBanks=radiator_banks,
        radiatorArea=two_digit_decimal(radiator_area),
        temperatureDependenceFactor=temp_dependence_factor,
        cspHeat=csp_heat,
        newTankHeight=new_tank_height,
        totalRadiatorWeight=total_radiator_weight,
        totalRadiatorOil=total_radiator_oil,
        extendedLayout=extralong >= 1,
        maxSections=max_sections,
        maxSectionsPerRadiator=max_sections_per_radiator,
    )


def get_conservator_oil(oil_in_tank, oil_in_radiators):
    return next_integer((oil_in_radiators + oil_in_tank) * 0.04)


def get_conservator_capacity(kva, total_oil):
    return next_integer(total_oil * (0.1 if kva < 5000 else 0.08))


def get_conservator_dia(conservator_capacity):
    return next_5or0_integer(math.pow((conservator_capacity * 4) / (3 * math.pi), 1 / 3) * 100)


def get_conservator_length(conservator_capacity, conservator_dia):
    return next_5or0_integer((conservator_capacity / ((math.pi / 4) * math.pow(conservator_dia, 2))) * math.pow(10, 6))


def get_total_radiator_weight(radiator_length, radiator_width, radiator_section, no_of_radiators):
    radiator_weight = one_digit_decimal(radiator_length * radiator_width * radiator_section * no_of_radiators * 2 * 1.25 * 7.85 * math.pow(10, -6))
    radiator_head = one_digit_decimal(0.1 + ((radiator_section - 1) * 0.05))
    pipe_weight = one_digit_decimal((math.pi / 4) * (math.pow(90, 2) - math.pow(86, 2)) * (radiator_head * 2 * 7.85) / 1000)
    return next_integer(radiator_weight + pipe_weight)


def get_total_steel_weight(hv_voltage, kva, vector_group):
    if hv_voltage <= 11000:
        return math.pow(kva / 63, 0.7) * 122 + 1
    if hv_voltage < 33000:
        return math.pow(kva / 63, 0.72) * 122 + 1
    if hv_voltage < 66000:
        return math.pow(kva / 63, 0.74) * 122 + 1
    if hv_voltage < 132000:
        if _vector_group_char(vector_group, 0) == "Y":
            return math.pow(kva / 63, 0.75) * 122 + 1
        if _vector_group_char(vector_group, 0) == "D":
            return math.pow(kva / 63, 0.76) * 122 + 1
    if _vector_group_char(vector_group, 0) == "Y":
        return math.pow(kva / 63, 0.77) * 122 + 1
    if _vector_group_char(vector_group, 0) == "D":
        return math.pow(kva / 63, 0.78) * 122 + 1
    return 0


def get_oltc_spec(hv_voltage, tap_step_positive, tap_step_negative):
    tap_count = tap_step_positive + tap_step_negative + 1
    if hv_voltage <= 11000:
        if tap_count <= 9:
            return [250, 100, 98 * 1.4, 785, 1030, 720, 0]
        return [370, 200, 230 * 1.4, 785, 1290, 1070, 0]
    if hv_voltage <= 33000:
        if tap_count <= 9:
            return [385, 200, 335 * 1.4, 775, 1625, 745, 0]
        return [500, 300, 650 * 1.4, 805, 1762, 1215, 0]
    if hv_voltage <= 132000:
        return [660, 300, 0, 1000, 0, 2450, 1]
    return [0, 0, 0, 0, 0, 0, 0]


def get_bushing_voltage_and_height(line_volts):
    comparison_value = math.floor(line_volts / 100) / 10.0
    if comparison_value < 1.1:
        return [1.1, 372]
    if comparison_value <= 3.6:
        return [3.6, 220]
    if comparison_value <= 7.2:
        return [7.2, 340]
    if comparison_value <= 17.5:
        return [17.5, 560]
    if comparison_value <= 36:
        return [36, 861]
    if comparison_value <= 52:
        return [52, 740]
    if comparison_value <= 72.5:
        return [72.5, 1030]
    if comparison_value <= 123:
        return [123, 1450]
    if comparison_value <= 145:
        return [145, 1805]
    return [0, 0]


def get_bushing_current(phase_current, vector_group, is_lv):
    if is_lv:
        line_current = phase_current if _vector_group_char(vector_group, 1) == "y" else phase_current * math.sqrt(3)
    else:
        line_current = phase_current if _vector_group_char(vector_group, 0) == "Y" else phase_current * math.sqrt(3)

    if line_current < 251:
        return 250
    if line_current <= 630:
        return 630
    if line_current <= 1000:
        return 1000
    if line_current <= 2000:
        return 2000
    if line_current <= 3150:
        return 3150
    return 4000


def get_lifting_lugs(kva):
    if kva <= 100:
        return 100
    if kva <= 2500:
        return 150
    return 200


def get_corrugation_slits(tank_side):
    return int(math.floor((tank_side - 100) / 50)) * 2


def get_corrugation_area(kw55, trans_cost_type):
    return two_digit_decimal(kw55 / (450 if _is_economic(trans_cost_type) else 400))


def get_depth_of_corrugation(corrugation_area, height_of_fin, no_of_corrugation):
    return next_0_integer((corrugation_area / no_of_corrugation) / height_of_fin)


def get_radiator_type(radiator_type):
    return radiator_type if radiator_type is not None else RADIATOR


def get_revised_flux_density(revised_volts_per_turn, frequency, net_area):
    return round(revised_volts_per_turn / (4.44 * frequency * net_area * math.pow(10, -6)), 4)


def _get_winding_value(winding, field_name):
    if winding is None:
        return None
    return getattr(winding, field_name, None)


def build_winding_formula_context(multi_winding):
    return {
        "designId": multi_winding.designId,
        "windings": multi_winding.windings,
        "vectorGroup": multi_winding.vectorGroup,
        "ratings": {
            "kVA": multi_winding.kVA,
            "kValue": multi_winding.kValue,
            "frequency": multi_winding.frequency,
            "fluxDensity": multi_winding.fluxDensity,
            "lowVoltage": multi_winding.lowVoltage,
            "highVoltage": multi_winding.highVoltage,
        },
        "currentDensity": {
            "lv": multi_winding.lvCurrentDensity,
            "hv": multi_winding.hvCurrentDensity,
            "fine": multi_winding.fineCurrentDensity,
            "corse": multi_winding.corseCurrentDensity,
            "outer": multi_winding.outerCurrentDensity,
        },
        "conductorMaterial": {
            "lv": multi_winding.lvConductorMaterial,
            "hv": multi_winding.hvConductorMaterial,
            "fine": multi_winding.fineConductorMaterial,
            "corse": multi_winding.corseConductorMaterial,
            "outer": multi_winding.outerConductorMaterial,
        },
        "tapSteps": {
            "percentage": multi_winding.tapStepsPercentage,
            "positive": multi_winding.tapStepPositive,
            "negative": multi_winding.tapStepNegative,
        },
        "windingModels": {
            "lv": multi_winding.lvWindings,
            "hv": multi_winding.hvWindings,
            "fine": multi_winding.fineWindings,
            "corse": multi_winding.corseWindings,
            "outer": multi_winding.outerWindings,
        },
        "radialGaps": multi_winding.radialGaps,
    }


def calculate_winding_formulae(multi_winding):
    from api.services.circWdgService import calculate_circ_wdg

    return calculate_circ_wdg(multi_winding)


# Backward-compatible aliases for older imports.
getLvVoltsPerPhase = get_lv_volts_per_phase
getHvVoltsPerPhase = get_hv_volts_per_phase
getLvVoltsPerTurn = get_volts_per_turn
getLvTurnsPerPhase = get_turns_per_phase
getLvCurrentPerPhase = get_current_per_phase
getRevisedVoltsPerPhase = get_revised_volts_per_turn
getNetArea = get_net_area
grossArea = get_gross_core_area
getRevisedFluxDensity = get_revised_flux_density
