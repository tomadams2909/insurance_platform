from decimal import Decimal

import pytest

from services.pricing import calculate_premium, get_vehicle_category


# --- Vehicle category ---

def test_category_low_value():
    assert get_vehicle_category(Decimal("10000")) == 1


def test_category_boundary_15k():
    assert get_vehicle_category(Decimal("15000")) == 2


def test_category_mid_value():
    assert get_vehicle_category(Decimal("25000")) == 2


def test_category_boundary_40k():
    assert get_vehicle_category(Decimal("40000")) == 3


def test_category_high_value():
    assert get_vehicle_category(Decimal("60000")) == 3


# --- GAP ---

def test_gap_cat1_12mo():
    # 10000 * 0.03 * 1.0 * (12/12) = 300 → rounds to 300
    assert calculate_premium("GAP", Decimal("10000"), 12) == Decimal("300")


def test_gap_cat2_24mo():
    # 25000 * 0.03 * 1.25 * (24/12) = 1875 → rounds to 1875
    assert calculate_premium("GAP", Decimal("25000"), 24) == Decimal("1875")


def test_gap_cat3_12mo():
    # 50000 * 0.03 * 1.55 * (12/12) = 2325 → rounds to 2325
    assert calculate_premium("GAP", Decimal("50000"), 12) == Decimal("2325")


# --- VRI ---

def test_vri_cat1_12mo():
    # 10000 * 0.04 * 1.0 * 1 = 400
    assert calculate_premium("VRI", Decimal("10000"), 12) == Decimal("400")


def test_vri_cat2_12mo():
    # 25000 * 0.04 * 1.25 * 1 = 1250
    assert calculate_premium("VRI", Decimal("25000"), 12) == Decimal("1250")


# --- COSMETIC ---

def test_cosmetic_cat1_12mo():
    # 99 * 1.0 * 1 = 99 → rounds to 100 (nearest 5)
    assert calculate_premium("COSMETIC", Decimal("10000"), 12) == Decimal("100")


def test_cosmetic_cat2_12mo():
    # 129 * 1.25 * 1 = 161.25 → rounds to 160
    assert calculate_premium("COSMETIC", Decimal("25000"), 12) == Decimal("160")


def test_cosmetic_cat3_12mo():
    # 169 * 1.55 * 1 = 261.95 → rounds to 260
    assert calculate_premium("COSMETIC", Decimal("50000"), 12) == Decimal("260")


# --- TYRE ESSENTIAL (4 wheels hardcoded) ---

def test_tyre_essential_cat1_12mo():
    # 18 * 4 * 1 = 72 → rounds to 70
    assert calculate_premium("TYRE_ESSENTIAL", Decimal("10000"), 12) == Decimal("70")


def test_tyre_essential_cat2_12mo():
    # 24 * 4 * 1 = 96 → rounds to 95
    assert calculate_premium("TYRE_ESSENTIAL", Decimal("20000"), 12) == Decimal("95")


def test_tyre_essential_cat3_12mo():
    # 32 * 4 * 1 = 128 → rounds to 130
    assert calculate_premium("TYRE_ESSENTIAL", Decimal("50000"), 12) == Decimal("130")


# --- TYRE PLUS (4 wheels hardcoded) ---

def test_tyre_plus_cat1_12mo():
    # 28 * 4 * 1 = 112 → rounds to 110
    assert calculate_premium("TYRE_PLUS", Decimal("10000"), 12) == Decimal("110")


def test_tyre_plus_cat2_12mo():
    # 36 * 4 * 1 = 144 → rounds to 145
    assert calculate_premium("TYRE_PLUS", Decimal("20000"), 12) == Decimal("145")


# --- TLP ---

def test_tlp_bucket1_12mo():
    # vehicle_value <= 15000 → 49/yr → rounds to 50
    assert calculate_premium("TLP", Decimal("12000"), 12) == Decimal("50")


def test_tlp_bucket2_12mo():
    # vehicle_value <= 30000 → 79/yr → rounds to 80
    assert calculate_premium("TLP", Decimal("22000"), 12) == Decimal("80")


def test_tlp_bucket3_12mo():
    # vehicle_value <= 50000 → 99/yr → rounds to 100
    assert calculate_premium("TLP", Decimal("45000"), 12) == Decimal("100")


def test_tlp_bucket4_12mo():
    # vehicle_value <= 999999 → 129/yr → rounds to 130
    assert calculate_premium("TLP", Decimal("80000"), 12) == Decimal("130")


# --- Term scaling ---

def test_gap_24mo_is_double_12mo():
    p12 = calculate_premium("GAP", Decimal("10000"), 12)
    p24 = calculate_premium("GAP", Decimal("10000"), 24)
    assert p24 == p12 * 2


def test_unknown_product_raises():
    with pytest.raises(ValueError, match="Unknown product"):
        calculate_premium("UNKNOWN", Decimal("10000"), 12)
