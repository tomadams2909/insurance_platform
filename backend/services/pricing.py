from decimal import Decimal, ROUND_HALF_UP


# Vehicle category thresholds (by purchase value)
def get_vehicle_category(vehicle_value: Decimal) -> int:
    if vehicle_value < 15000:
        return 1
    elif vehicle_value < 40000:
        return 2
    return 3

CATEGORY_MULTIPLIERS = {1: Decimal("1.0"), 2: Decimal("1.25"), 3: Decimal("1.55")}

# Annual base rates
GAP_BASE_RATE = Decimal("0.03")        # 3% of vehicle value
VRI_BASE_RATE = Decimal("0.04")        # 4% of vehicle value (higher than GAP)
COSMETIC_BASE_RATES = {1: Decimal("99"), 2: Decimal("129"), 3: Decimal("169")}  # flat per year

TYRE_ESSENTIAL_PER_WHEEL = {1: Decimal("18"), 2: Decimal("24"), 3: Decimal("32")}  # per wheel per year
TYRE_PLUS_PER_WHEEL = {1: Decimal("28"), 2: Decimal("36"), 3: Decimal("48")}       # per wheel per year

# TLP fixed annual premiums by vehicle value bucket
TLP_BUCKETS = [
    (Decimal("15000"), Decimal("49")),
    (Decimal("30000"), Decimal("79")),
    (Decimal("50000"), Decimal("99")),
    (Decimal("999999"), Decimal("129")),
]


def _round_to_nearest_5(value: Decimal) -> Decimal:
    return (value / 5).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * 5


def _term_factor(term_months: int) -> Decimal:
    return Decimal(term_months) / Decimal("12")


def calculate_premium(
    product: str,
    vehicle_value: Decimal,
    term_months: int,
    **kwargs,
) -> Decimal:
    vehicle_value = Decimal(str(vehicle_value))
    category = get_vehicle_category(vehicle_value)
    multiplier = CATEGORY_MULTIPLIERS[category]
    term = _term_factor(term_months)

    if product == "GAP":
        premium = vehicle_value * GAP_BASE_RATE * multiplier * term

    elif product == "VRI":
        premium = vehicle_value * VRI_BASE_RATE * multiplier * term

    elif product == "COSMETIC":
        premium = COSMETIC_BASE_RATES[category] * multiplier * term

    elif product == "TYRE_ESSENTIAL":
        premium = TYRE_ESSENTIAL_PER_WHEEL[category] * 4 * term

    elif product == "TYRE_PLUS":
        premium = TYRE_PLUS_PER_WHEEL[category] * 4 * term

    elif product == "TLP":
        annual_rate = next(rate for threshold, rate in TLP_BUCKETS if vehicle_value <= threshold)
        premium = annual_rate * term

    else:
        raise ValueError(f"Unknown product: {product}")

    return _round_to_nearest_5(premium)


# Product field requirements — used by routers and frontend schema endpoint
PRODUCT_SCHEMAS = {
    "GAP": {
        "required_fields": ["loan_amount"],
        "optional_fields": [],
        "affects_price": ["vehicle_value", "term_months"],
    },
    "VRI": {
        "required_fields": [],
        "optional_fields": [],
        "affects_price": ["vehicle_value", "term_months"],
    },
    "COSMETIC": {
        "required_fields": [],
        "optional_fields": [],
        "affects_price": ["vehicle_value", "term_months"],
    },
    "TYRE_ESSENTIAL": {
        "required_fields": [],
        "optional_fields": [],
        "affects_price": ["vehicle_value", "term_months"],
    },
    "TYRE_PLUS": {
        "required_fields": [],
        "optional_fields": [],
        "affects_price": ["vehicle_value", "term_months"],
    },
    "TLP": {
        "required_fields": ["tlp_limit"],
        "optional_fields": [],
        "affects_price": ["vehicle_value", "term_months"],
    },
}
