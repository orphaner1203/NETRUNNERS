import os
import pytest
from fastapi.testclient import TestClient

from main import app
import guardrails
import optimizer

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_solver_direct_calculation():
    demand = [20.0] * 24
    solar = [5.0 if 8 <= h <= 16 else 0.0 for h in range(24)]
    tariff = [12.0 if 17 <= h <= 20 else 6.0 for h in range(24)]

    res = optimizer.solve_schedule(
        demand=demand,
        solar=solar,
        tariff=tariff,
        battery_capacity=100.0,
        initial_energy=50.0,
        base_min_reserve=10.0,
        max_charge_per_hour=25.0,
        max_discharge_per_hour=25.0,
        directives=[],
    )

    assert len(res["hourly_plan"]) == 24
    assert res["total_grid_kwh"] > 0
    assert res["total_cost_bdt"] > 0
    assert "peak_grid_kwh" in res


def test_guardrails_sanitization():
    raw_directives = [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "min_reserve_override",
            "structured_adjustment": {
                "start_hour": 17,
                "end_hour": 20,
                "reserve_kwh": 30.0,
            },
            "explanation": "Valid reserve directive.",
        },
        {
            "note_index": 1,
            "applies": True,
            "directive_type": "invalid_directive_name",
            "structured_adjustment": {},
            "explanation": "Invalid type should be rejected.",
        },
    ]

    sanitized = guardrails.validate_interpretations(
        raw=raw_directives, num_notes=2, battery_capacity=100.0
    )

    assert sanitized[0]["applies"] is True
    assert sanitized[0]["directive_type"] == "min_reserve_override"
    assert sanitized[1]["applies"] is False
    assert sanitized[1]["directive_type"] == "none"


def test_optimize_energy_json_endpoint():
    payload = {
        "scenario_id": "test_scenario_01",
        "operator_notes": ["Keep extra reserve during peak hours."],
        "battery": {
            "capacity_kwh": 100.0,
            "initial_energy_kwh": 50.0,
            "minimum_energy_kwh": 10.0,
            "max_charge_kwh_per_hour": 25.0,
            "max_discharge_kwh_per_hour": 25.0,
        },
        "hours": [
            {"hour": h, "demand_kwh": 20.0, "solar_kwh": 5.0, "tariff_bdt_per_kwh": 6.0}
            for h in range(24)
        ],
    }

    response = client.post("/optimize-energy", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["scenario_id"] == "test_scenario_01"
    assert len(data["hourly_plan"]) == 24
    assert len(data["directive_interpretation"]) == 1


def test_optimize_text_plain_endpoint():
    os.environ["LLM_PROVIDER"] = "mock"
    raw_prompt = "Battery capacity 100kWh sitting at 50kWh. Do not discharge between 5 PM and 8 PM."

    response = client.post(
        "/optimize-text",
        content=raw_prompt,
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "hourly_plan" in data
    assert len(data["hourly_plan"]) == 24
    assert "plan_summary" in data