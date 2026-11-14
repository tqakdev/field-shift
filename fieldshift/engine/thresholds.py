"""Documented decision thresholds for tiered strategy cards and constraints.

Shown on the How it works page. Changing these changes farmer-facing tiers —
keep tests in sync.
"""

from __future__ import annotations

# --- Tier assignment (overall score is on [0, 1]) ---

# Best fit must beat the farmer's current rotation by at least this much.
BEST_FIT_MIN_DELTA = 0.02

# Worth considering: within this gap of the best-fit total (among suitable cards).
WORTH_CONSIDERING_OF_BEST = 0.05

# Below current by this much → "Not suitable here" (unless a hard constraint already failed).
NOT_SUITABLE_TOTAL_DELTA = 0.05

# Soft penalties applied to total when soft constraints fail (still shown as suitable).
BUDGET_LOW_COVER_PENALTY = 0.04
LABOR_LOW_COVER_PENALTY = 0.03

# Nitrogen fertilizer → soil_health bonus when a legume is in the strategy.
N_LEGUME_BONUS = {
    "low": 0.02,
    "medium": 0.04,
    "high": 0.07,
    "unknown": 0.03,
}

# Irrigated fields: each irrigation event per season adds a small water-score lift
# (capped). Models "I can make up shortfalls" without inventing mm applied.
IRRIGATION_EVENT_WATER_LIFT = 0.03
IRRIGATION_EVENT_WATER_CAP = 0.12

# Market access: "I have a buyer" lifts income; "no market" hard-blocks cash crops.
MARKET_BUYER_INCOME_LIFT = 0.05
MARKET_NO_BUYER_BLOCKS_CASH = True

# Machinery hard constraints (strategy contains crop types that need kit).
SMALL_GRAIN_IDS = frozenset(
    {"winter_wheat", "spring_wheat", "barley", "oats"}
)
ROW_CROP_IDS = frozenset({"maize", "soybean", "sorghum", "cotton", "sunflower"})
HAY_FORAGE_MIN = 0.5  # crop forage_value above this needs hay/forage equipment
