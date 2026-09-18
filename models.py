from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

ALLOWED_DIRECTIVE_TYPES = {
    "min_reserve_override",
    "max_charge_limit",
    "no_discharge",
    "none",
}


class BatteryConfig(BaseModel):
    capacity_kwh: float
    initial_energy_kwh: float
    minimum_energy_kwh: float
    max_charge_kwh_per_hour: float
    max_discharge_kwh_per_hour: float


class HourlyData(BaseModel):
    hour: int
    demand_kwh: float
    solar_kwh: float
    tariff_bdt_per_kwh: float


class OptimizeRequest(BaseModel):
    scenario_id: str
    operator_notes: List[str] = Field(default_factory=list)
    battery: BatteryConfig
    hours: List[HourlyData]


class DirectiveInterpretation(BaseModel):
    note_index: int
    applies: bool
    directive_type: str
    structured_adjustment: Dict[str, Any]
    explanation: str


class HourlyPlanItem(BaseModel):
    hour: int
    grid_kwh: float
    solar_used_kwh: float
    battery_action: str
    battery_kwh: float
    battery_energy_after_kwh: float


class OptimizeResponse(BaseModel):
    scenario_id: str
    directive_interpretation: List[DirectiveInterpretation]
    hourly_plan: List[HourlyPlanItem]
    total_grid_kwh: float
    total_cost_bdt: float
    peak_grid_kwh: float
    plan_summary: str


class HealthResponse(BaseModel):
    status: str