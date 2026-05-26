from decimal import Decimal, ROUND_HALF_UP
import math


def _quantize(value, pattern):
    return float(Decimal(str(value)).quantize(Decimal(pattern), rounding=ROUND_HALF_UP))


def one_digit_decimal(value):
    return _quantize(value, "0.0")


def two_digit_decimal(value):
    return _quantize(value, "0.00")


def three_digit_decimal(value):
    return _quantize(value, "0.000")


def four_digit_decimal(value):
    return _quantize(value, "0.0000")


def six_digit_decimal(value):
    return _quantize(value, "0.000000")


def one_digit_decimal_floor(value):
    return math.floor(value * 10) / 10.0


def two_digit_decimal_floor(value):
    return math.floor(value * 100) / 100.0


def two_digit_decimal_part(value):
    return abs(value - int(value))


def next_integer(value):
    return int(math.ceil(value))


def next_0_integer(value):
    return int(math.ceil(value))


def next_5or0_integer(value):
    return int(math.ceil(value / 5.0) * 5)


def previous_5or0_integer(value):
    return int(math.floor(value / 5.0) * 5)
