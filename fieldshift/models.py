"""Pydantic v2 schemas — internal data contracts for the fieldshift package + Streamlit UI."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]
WaterAccess = Literal["rainfed", "limited", "irrigated"]
SoilType = Literal["sand", "loam", "clay", "silt", "unknown"]
TimelapseIndex = Literal["ndvi", "rgb"]


class HealthResponse(BaseModel):
    """Liveness / mode probe."""

    status: str = "ok"
    demo_mode: bool
    version: str = "0.1.0"
    phase: str = "1-scaffold"


class DemoField(BaseModel):
    """A pre-loaded demo field listed on the home page."""

    id: str
    name: str
    country: str
    polygon: dict[str, Any]
    climate_label: str


class EvidenceItem(BaseModel):
    """A single evidence string tagged with its dataset source."""

    text: str
    source: str
    data_through: str | None = None


class ScoreSet(BaseModel):
    """Per-criterion scores in [0, 1] plus weighted total."""

    water: float
    soil_health: float
    erosion: float
    pest_break: float
    climate_fit: float
    income: float
    total: float


class CropInSequence(BaseModel):
    """One crop slot in a rotation sequence."""

    crop_id: str
    months: str


class StrategyCard(BaseModel):
    """One rotation strategy shown to the farmer."""

    id: str
    name: str
    sequence: list[CropInSequence]
    scores: ScoreSet
    delta_vs_current: dict[str, float]
    why: str
    evidence: list[EvidenceItem]
    benefits: list[str]
    data_gaps: list[str]
    risks_for_local_review: list[str]
    confidence: Confidence


class PriorityWeights(BaseModel):
    """Farmer priority sliders (relative weights)."""

    water: float = 1.0
    soil_health: float = 1.0
    erosion: float = 1.0
    pest_break: float = 1.0
    climate_fit: float = 1.0
    income: float = 1.0


class ScenarioParams(BaseModel):
    """What-if adjustments applied before re-scoring."""

    rain_mult: float = Field(default=1.0, ge=0.7, le=1.3)
    temp_offset: float = Field(default=0.0, ge=0.0, le=3.0)


class StrategyRequest(BaseModel):
    """Body for POST /api/fields/{id}/strategies."""

    current_rotation: list[str]
    soil_type: SoilType = "unknown"
    water_access: WaterAccess = "rainfed"
    livestock: bool = False
    weights: PriorityWeights = Field(default_factory=PriorityWeights)
    scenario: ScenarioParams = Field(default_factory=ScenarioParams)


class StrategyResult(BaseModel):
    """Response containing ranked strategy cards."""

    field_id: str
    strategies: list[StrategyCard]


class MonthlySeriesPoint(BaseModel):
    """One calendar-month climatology / profile point."""

    month: int = Field(ge=1, le=12)
    ndvi: float | None = None
    soil_moisture: float | None = None
    rain_mm: float | None = None
    water_balance_mm: float | None = None
    temperature_c: float | None = None


class FieldFeatures(BaseModel):
    """Derived field features from the harmonized monthly table."""

    bare_months: list[int] = Field(default_factory=list)
    bare_months_label: str = ""
    stress_months: list[int] = Field(default_factory=list)
    stress_months_label: str = ""
    frost_window_label: str = ""
    frost_free_days: float | None = None
    gdd_annual: float | None = None
    heat_days_trend: str = ""
    rain_annual_mm: float | None = None
    rain_cv: float | None = None
    slope_pct_mean: float | None = None
    erosion_risk: float | None = None
    water_deficit_annual_mm: float | None = None
    data_coverage_note: str = ""


class FieldConditions(BaseModel):
    """Full conditions payload for a field page."""

    field_id: str
    name: str
    country: str
    climate_label: str
    polygon: dict[str, Any]
    monthly_profile: list[MonthlySeriesPoint]
    features: FieldFeatures
    timelapse_url: str | None = None
    sources_used: list[str] = Field(default_factory=list)
    # Phase 7 embeds; null until US module / cross-checks exist
    us_module: dict[str, Any] | None = None
    cross_checks: dict[str, Any] | None = None


class AnalyzeRequest(BaseModel):
    """Body for POST /api/analyze."""

    polygon: dict[str, Any]
    name: str | None = None


class TimelapseResponse(BaseModel):
    """Time-lapse GIF/URL for a field."""

    url: str
    frames: int | None = None
    start: str | None = None
    end: str | None = None
    cached_static: bool = False


class CropSummary(BaseModel):
    """Crop list entry for dropdowns."""

    id: str
    name: str
    type: Literal["cover", "cash", "forage"]
    family: str
    season: Literal["cool", "warm"]


class DataSourceMeta(BaseModel):
    """One dataset row for the About page."""

    purpose: str
    name: str
    id_or_access: str
    resolution: str
    link: str


class UsModuleResponse(BaseModel):
    """US enhancement payload. Empty/null parts until Phase 7."""

    in_conus: bool | None = None
    detected_rotation: list[str] | None = None
    soil: dict[str, Any] | None = None
    prices: dict[str, Any] | None = None
    county_yields: dict[str, Any] | None = None
    rain_validation: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)


class ValidationResponse(BaseModel):
    """Cross-check statistics. Empty until Phase 7."""

    cross_checks: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)


class ErrorDetail(BaseModel):
    """Consistent API error body."""

    detail: str
