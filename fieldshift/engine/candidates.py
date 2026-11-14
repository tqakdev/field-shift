"""Build and filter rotation strategy candidates."""

from __future__ import annotations

from typing import Any

from fieldshift.engine.calendar import cover_fits_window, months_label
from fieldshift.engine.crop_water import irrigation_requirement_mm
from fieldshift.engine.crops import crop_by_id, load_crops
from fieldshift.engine.scoring import score_climate_fit, score_strategy
from fieldshift.models import PriorityWeights, WaterAccess

# Documented water-wise gates.
WATER_WISE_RAIN_CV = 0.30
WATER_WISE_ANNUAL_DEFICIT_MM = -150.0
CLIMATE_FIT_MIN = 0.45

GRAIN_LEGUME_IDS = {
    "soybean",
    "field_pea",
    "lentil",
    "mung_bean",
    "pigeon_pea",
}
# Warm/kharif-leaning drought swaps (cool legumes filtered by season_compatible).
WATER_WISE_POOL = [
    "sorghum",
    "maize",
    "millet",
    "mung_bean",
    "pigeon_pea",
    "soybean",
    "field_pea",
    "lentil",
]
COOL_SEASON_IDS = {
    "field_pea",
    "lentil",
    "winter_wheat",
    "spring_wheat",
    "barley",
    "oats",
    "canola",
    "chickpea",
}


def climate_ok(crop: dict[str, Any], features: dict[str, Any], water_access: WaterAccess) -> bool:
    """Filter: frost-free days, GDD (water need checked via IR scoring, not hard fail)."""
    frost = features.get("frost_window", {}).get("frost_free_days")
    gdd = features.get("gdd", {}).get("gdd_annual_mean")
    if frost is not None and crop["min_frost_free_days"] > frost:
        return False
    if gdd is not None and crop["gdd_required"] > gdd * 1.05:
        return False
    # Irrigated: allow high water-need crops through climate filter (score handles IR)
    if water_access == "irrigated":
        return True
    rain = features.get("rain", {}).get("rain_annual_mm") or 0.0
    need = sum(crop["water_need_mm"]) / 2.0
    if need > rain * 1.30:
        return False
    return True


def rotation_has_grain_legume(rotation: list[str]) -> bool:
    def is_grain_legume(cid: str) -> bool:
        c = crop_by_id(cid)
        return cid in GRAIN_LEGUME_IDS or (
            c["family"] == "fabaceae" and c["type"] == "cash"
        )

    return any(is_grain_legume(cid) for cid in rotation)


def most_water_demanding(rotation: list[str], features: dict[str, Any]) -> str | None:
    """Cash crop with highest irrigation requirement (Kc×ET0 − rain_eff)."""
    cash = [c for c in rotation if crop_by_id(c)["type"] == "cash"]
    if not cash:
        return None
    ranked = sorted(
        cash,
        key=lambda cid: irrigation_requirement_mm(cid, features)["irrigation_mm"],
        reverse=True,
    )
    return ranked[0]


def season_months_for_crop(crop_id: str, features: dict[str, Any]) -> list[int]:
    mapping = features.get("crop_season_map") or {}
    months = (mapping.get(crop_id) or {}).get("months")
    if months:
        return list(months)
    from fieldshift.engine.calendar import active_months

    return sorted(active_months(crop_id))


def season_label_for_crop(crop_id: str, features: dict[str, Any]) -> str | None:
    mapping = features.get("crop_season_map") or {}
    return (mapping.get(crop_id) or {}).get("season_label")


def season_compatible(
    replacement_id: str,
    replaced_id: str,
    features: dict[str, Any],
    *,
    mode: str = "strict",
) -> bool:
    """Replacement must fit the *replaced* crop's season window (not annual climate).

    Hard rule: cool-season crops (field pea, lentil, wheat, …) cannot replace a
    kharif/summer slot (e.g. rice). Fit is scored with heat/GDD/frost/Tmax over
    the replaced season months.

    ``mode="water_wise"``: allow a warm drought crop to occupy the field's summer
    fallow window when replacing a winter cereal (system shift to summer cropping).
    """
    label = season_label_for_crop(replaced_id, features)
    months = season_months_for_crop(replaced_id, features)
    rep = crop_by_id(replacement_id)
    # Explicit warm-slot gate (Punjab rice)
    if label in {"kharif", "summer"} and (
        rep["season"] == "cool" or replacement_id in COOL_SEASON_IDS
    ):
        return False
    if label in {"rabi", "winter"} and rep["season"] == "warm":
        if mode != "water_wise":
            return False
        fallow = list(
            features.get("bare_months", {}).get("months")
            or features.get("phenology", {}).get("fallow_months")
            or [7, 8, 9]
        )
        summer_months = sorted(set(fallow) | {5, 6, 7, 8, 9})
        fit = score_climate_fit(
            [replacement_id], features, season_months=summer_months
        )
        return fit >= CLIMATE_FIT_MIN
    fit = score_climate_fit([replacement_id], features, season_months=months)
    return fit >= CLIMATE_FIT_MIN


def best_cover_for_bare(features: dict[str, Any], water_access: WaterAccess) -> str | None:
    window = features.get("bare_months", {}).get("months") or []
    covers = [
        c
        for c in load_crops()
        if c["type"] == "cover"
        and climate_ok(c, features, water_access)
        and cover_fits_window(c["id"], window)
    ]
    if not covers:
        window = features.get("bare_months", {}).get("phenology_fallow") or window
        covers = [
            c
            for c in load_crops()
            if c["type"] == "cover" and cover_fits_window(c["id"], window)
        ]
    if not covers:
        return None
    covers.sort(key=lambda c: float(c["frost_tolerance"]), reverse=True)
    return covers[0]["id"]


def best_legume_for_field(
    features: dict[str, Any], water_access: WaterAccess
) -> str | None:
    """Highest climate-fit cash legume; prefer field_pea in semi-arid wheat systems.

    Never returns lentil unless it has the strictly highest climate fit among
    legumes that pass the climate gate.
    """
    rotation = features.get("current_rotation") or []
    cash_slots = [c for c in rotation if crop_by_id(c)["type"] == "cash"]
    legumes = [
        c
        for c in load_crops()
        if c["nitrogen_fixing"]
        and c["type"] == "cash"
        and climate_ok(c, features, water_access)
        and any(season_compatible(c["id"], slot, features) for slot in cash_slots)
    ]
    if not legumes:
        return None
    rain = features.get("rain", {}).get("rain_annual_mm") or 800
    rain_cv = features.get("rain", {}).get("rain_cv") or 0.0
    semi_arid = rain < 750 or rain_cv > 0.22
    wheat_system = any("wheat" in c for c in rotation)

    scored: list[tuple[float, str]] = []
    for c in legumes:
        # Score fit over the best compatible slot's months
        best_fit = 0.0
        for slot in cash_slots:
            if not season_compatible(c["id"], slot, features):
                continue
            months = season_months_for_crop(slot, features)
            best_fit = max(
                best_fit,
                score_climate_fit([c["id"]], features, season_months=months),
            )
        scored.append((best_fit, c["id"]))
    scored.sort(reverse=True)
    fit_top, top_id = scored[0]

    if (semi_arid or wheat_system) and any(cid == "field_pea" for _, cid in scored):
        pea_fit = next(fit for fit, cid in scored if cid == "field_pea")
        if pea_fit >= fit_top - 0.05:
            return "field_pea"

    if top_id == "lentil":
        others = [(fit, cid) for fit, cid in scored if cid != "lentil"]
        if others and others[0][0] >= fit_top - 1e-9:
            return others[0][1]
        if any(cid == "field_pea" for _, cid in scored):
            return "field_pea"
    return top_id


def best_forage_or_cover_legume(
    features: dict[str, Any], water_access: WaterAccess
) -> tuple[str, str] | None:
    forages = [
        c
        for c in load_crops()
        if c["type"] == "forage"
        and c["nitrogen_fixing"]
        and climate_ok(c, features, water_access)
        and score_climate_fit([c["id"]], features) >= CLIMATE_FIT_MIN
    ]
    if forages:
        forages.sort(
            key=lambda c: score_climate_fit([c["id"]], features), reverse=True
        )
        return forages[0]["id"], "forage"
    window = features.get("bare_months", {}).get("months") or []
    covers = [
        c
        for c in load_crops()
        if c["type"] == "cover"
        and c["nitrogen_fixing"]
        and climate_ok(c, features, water_access)
        and cover_fits_window(c["id"], window)
    ]
    if covers:
        covers.sort(key=lambda c: float(c["frost_tolerance"]), reverse=True)
        return covers[0]["id"], "cover"
    return None


def water_wise_replacements(
    features: dict[str, Any],
    water_access: WaterAccess,
    exclude: set[str],
    *,
    replace_crop: str | None = None,
) -> list[str]:
    """Rank drought-tolerant replacements by season climate_fit then income tier.

    Grain sorghum is boosted in semi-arid / wheat systems so Kansas considers it.
    Maize and kharif legumes (mung, pigeon pea) are always considered for rice.
    """
    from fieldshift.engine.scoring import MARKET_TIER

    rain = features.get("rain", {}).get("rain_annual_mm") or 800
    rain_cv = features.get("rain", {}).get("rain_cv") or 0.0
    rotation = features.get("current_rotation") or []
    prefer_sorghum = rain < 750 or rain_cv > 0.25 or any("wheat" in c for c in rotation)
    months = (
        season_months_for_crop(replace_crop, features) if replace_crop else None
    )

    pool = []
    for cid in WATER_WISE_POOL:
        if cid in exclude:
            continue
        c = crop_by_id(cid)
        if not climate_ok(c, features, water_access):
            continue
        if replace_crop and not season_compatible(
            cid, replace_crop, features, mode="water_wise"
        ):
            continue
        # Climate fit over replaced season, or summer fallow for warm↔winter water-wise
        fit_months = months
        if (
            replace_crop
            and season_label_for_crop(replace_crop, features) in {"rabi", "winter"}
            and c["season"] == "warm"
        ):
            fallow = list(
                features.get("bare_months", {}).get("months")
                or features.get("phenology", {}).get("fallow_months")
                or [7, 8, 9]
            )
            fit_months = sorted(set(fallow) | {5, 6, 7, 8, 9})
        fit = score_climate_fit([cid], features, season_months=fit_months)
        if fit < CLIMATE_FIT_MIN:
            continue
        if float(c["drought_tolerance"]) < 0.45 and cid not in {
            "maize",
            "soybean",
            "mung_bean",
        }:
            continue
        bonus = 0.08 if prefer_sorghum and cid == "sorghum" else 0.0
        if prefer_sorghum and cid == "soybean":
            bonus -= 0.06
        # Tropical kharif pulses belong in South Asia rice systems, not Great Plains wheat
        frost = features.get("frost_window", {}).get("frost_free_days")
        if frost is not None and frost < 220 and cid in {"mung_bean", "pigeon_pea"}:
            continue
        # Prefer maize as a rice alternative when climate allows
        if replace_crop == "rice" and cid == "maize":
            bonus += 0.05
        pool.append(
            (
                fit + bonus,
                MARKET_TIER.get(c["market_tier"], 0.3),
                float(c["drought_tolerance"]),
                cid,
            )
        )
    pool.sort(reverse=True)
    return [p[3] for p in pool]


def water_wise_needed(features: dict[str, Any]) -> bool:
    rain_cv = features.get("rain", {}).get("rain_cv") or 0.0
    deficit = features.get("water_balance", {}).get("annual_deficit_mm") or 0.0
    if rain_cv > WATER_WISE_RAIN_CV or deficit < WATER_WISE_ANNUAL_DEFICIT_MM:
        return True
    # High seasonal water-need cash crop (e.g. flooded rice) always warrants a swap option
    rotation = features.get("current_rotation") or []
    for cid in rotation:
        if crop_by_id(cid)["type"] != "cash":
            continue
        mid = sum(crop_by_id(cid)["water_need_mm"]) / 2.0
        if mid >= 800:
            return True
    return False


def best_swap_position(
    current: list[str],
    replacement: str,
    features: dict[str, Any],
    water_access: WaterAccess,
    weights: PriorityWeights | None = None,
) -> list[str]:
    """Replace the cash crop whose removal most improves weighted total.

    Only season-compatible slots are considered (cool crop cannot replace kharif rice).
    """
    weights = weights or PriorityWeights()
    baseline = score_strategy(
        current, features, weights=weights, water_access=water_access
    ).total
    best_seq = None
    best_delta = -1e9
    for i, cid in enumerate(current):
        if crop_by_id(cid)["type"] == "cover":
            continue
        if not season_compatible(replacement, cid, features):
            continue
        trial = list(current)
        trial[i] = replacement
        if trial == current:
            continue
        total = score_strategy(
            trial, features, weights=weights, water_access=water_access
        ).total
        delta = total - baseline
        if delta > best_delta:
            best_delta = delta
            best_seq = trial
    return best_seq if best_seq is not None else current


def season_label(crop_id: str, features: dict[str, Any] | None = None) -> str:
    if features:
        mapping = features.get("crop_season_map") or {}
        if crop_id in mapping:
            months = mapping[crop_id].get("months") or []
            label = mapping[crop_id].get("season_label")
            if months:
                base = months_label(sorted(months))
                return f"{label} {base}" if label and label != "fallback" else base
    from fieldshift.engine.calendar import active_months

    return months_label(sorted(active_months(crop_id)))


def _passes_plausibility(
    sequence: list[str], features: dict[str, Any], water_access: WaterAccess
) -> bool:
    for cid in sequence:
        c = crop_by_id(cid)
        if c["type"] == "cover":
            continue
        if not climate_ok(c, features, water_access):
            return False
        if score_climate_fit([cid], features) < CLIMATE_FIT_MIN:
            return False
    return True


def build_candidates(
    current_rotation: list[str],
    features: dict[str, Any],
    *,
    water_access: WaterAccess = "rainfed",
    weights: PriorityWeights | None = None,
) -> list[dict[str, Any]]:
    """Return strategy dicts. Always includes current."""
    current = [c for c in current_rotation if c]
    if not current:
        current = ["maize", "soybean"]
    weights = weights or PriorityWeights()
    # Ensure downstream helpers see the rotation (sorghum / field_pea prefs)
    features = {**features, "current_rotation": current}

    strategies: list[dict[str, Any]] = [
        {
            "id": "current",
            "name": " → ".join(crop_by_id(c)["name"] for c in current),
            "sequence": current,
        }
    ]

    cover = best_cover_for_bare(features, water_access)
    if cover:
        strategies.append(
            {
                "id": "current_plus_cover",
                "name": strategies[0]["name"] + f" + {crop_by_id(cover)['name']}",
                "sequence": current + [cover],
            }
        )

    if rotation_has_grain_legume(current):
        add = best_forage_or_cover_legume(features, water_access)
        if add:
            cid, mode = add
            if mode == "cover" and cid != cover:
                strategies.append(
                    {
                        "id": "legume_cover",
                        "name": strategies[0]["name"] + f" + {crop_by_id(cid)['name']}",
                        "sequence": current + [cid],
                    }
                )
            elif mode == "forage":
                strategies.append(
                    {
                        "id": "forage_legume",
                        "name": strategies[0]["name"] + f" + {crop_by_id(cid)['name']}",
                        "sequence": current + [cid],
                    }
                )
    else:
        legume = best_legume_for_field(features, water_access)
        if legume and legume not in current:
            swapped = best_swap_position(
                current, legume, features, water_access, weights
            )
            if swapped != current:
                strategies.append(
                    {
                        "id": "legume_swap",
                        "name": " → ".join(crop_by_id(c)["name"] for c in swapped),
                        "sequence": swapped,
                    }
                )

    if water_wise_needed(features):
        target = most_water_demanding(current, features)
        replacements = water_wise_replacements(
            features,
            water_access,
            exclude=set(current),
            replace_crop=target,
        )
        # Always replace the most water-demanding crop (e.g. rice in Punjab).
        # Walk climate_fit+income ranked pool; take first that beats current on
        # both water and total (equal weights). Fallback: best water improver.
        from fieldshift.engine.scoring import score_water

        if target is not None:
            baseline_w = score_water(current, features, water_access)
            baseline_t = score_strategy(
                current, features, weights=weights, water_access=water_access
            ).total
            chosen = None
            fallback = None
            fallback_w = -1.0
            for rep in replacements:
                if not season_compatible(rep, target, features, mode="water_wise"):
                    continue
                trial = list(current)
                try:
                    idx = trial.index(target)
                except ValueError:
                    break
                trial[idx] = rep
                if trial == current or not _passes_plausibility(
                    trial, features, water_access
                ):
                    continue
                w = score_water(trial, features, water_access)
                t = score_strategy(
                    trial, features, weights=weights, water_access=water_access
                ).total
                if w > fallback_w:
                    fallback_w = w
                    fallback = trial
                if w > baseline_w and t >= baseline_t - 0.01:
                    chosen = trial
                    break
            best_trial = chosen or (
                fallback if fallback_w > baseline_w else None
            )
            if best_trial is not None:
                strategies.append(
                    {
                        "id": "water_wise_swap",
                        "name": " → ".join(
                            crop_by_id(c)["name"] for c in best_trial
                        ),
                        "sequence": best_trial,
                    }
                )

    ww = crop_by_id("winter_wheat")
    grain = (
        "winter_wheat"
        if climate_ok(ww, features, water_access)
        and score_climate_fit(["winter_wheat"], features) >= CLIMATE_FIT_MIN
        else None
    )
    if grain and cover and len(current) >= 1 and grain not in current:
        mid = current[-1] if len(current) > 1 else current[0]
        seq = [current[0], mid, grain, cover]
        # dedupe consecutive
        deduped = [seq[0]]
        for x in seq[1:]:
            if x != deduped[-1]:
                deduped.append(x)
        strategies.append(
            {
                "id": "diversified_3yr",
                "name": " → ".join(crop_by_id(c)["name"] for c in deduped),
                "sequence": deduped,
            }
        )

    kept = [strategies[0]]
    for s in strategies[1:]:
        if _passes_plausibility(s["sequence"], features, water_access):
            kept.append(s)

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for s in kept:
        if s["id"] in seen:
            continue
        seen.add(s["id"])
        out.append(s)
        if len(out) >= 5:
            break
    return out
