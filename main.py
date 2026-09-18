from fastapi import Body, FastAPI, HTTPException
import guardrails
import llm_interpreter
from models import HealthResponse, OptimizeRequest, OptimizeResponse
import optimizer

app = FastAPI(
    title="GridWise Energy Optimizer",
    description="Pipeline: Natural Language Text -> Guardrail Validator -> MILP Optimizer",
    version="1.0.0",
)


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/optimize-energy", response_model=OptimizeResponse)
def optimize_energy(req: OptimizeRequest) -> OptimizeResponse:
    sorted_hours = sorted(req.hours, key=lambda h: h.hour)
    demand = [h.demand_kwh for h in sorted_hours]
    solar = [h.solar_kwh for h in sorted_hours]
    tariff = [h.tariff_bdt_per_kwh for h in sorted_hours]

    try:
        raw_interpretations = llm_interpreter.interpret_notes(req.operator_notes)
    except llm_interpreter.LLMInterpreterError:
        raw_interpretations = []

    sanitized_interpretations = guardrails.validate_interpretations(
        raw=raw_interpretations,
        num_notes=len(req.operator_notes),
        battery_capacity=req.battery.capacity_kwh,
    )

    directives = guardrails.directives_for_optimizer(sanitized_interpretations)

    try:
        res = optimizer.solve_schedule(
            demand=demand,
            solar=solar,
            tariff=tariff,
            battery_capacity=req.battery.capacity_kwh,
            initial_energy=req.battery.initial_energy_kwh,
            base_min_reserve=req.battery.minimum_energy_kwh,
            max_charge_per_hour=req.battery.max_charge_kwh_per_hour,
            max_discharge_per_hour=req.battery.max_discharge_kwh_per_hour,
            directives=directives,
        )
    except optimizer.InfeasibleScenarioError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Infeasible scenario optimization failed: {exc}",
        )

    applied = [d for d in sanitized_interpretations if d["applies"]]
    summary = (
        f"Schedule generated for {req.scenario_id}. Applied {len(applied)} directive(s). "
        f"Total cost: {res['total_cost_bdt']} BDT, Peak grid import: {res['peak_grid_kwh']} kWh."
    )

    return OptimizeResponse(
        scenario_id=req.scenario_id,
        directive_interpretation=sanitized_interpretations,
        hourly_plan=res["hourly_plan"],
        total_grid_kwh=res["total_grid_kwh"],
        total_cost_bdt=res["total_cost_bdt"],
        peak_grid_kwh=res["peak_grid_kwh"],
        plan_summary=summary,
    )


@app.post("/optimize-text", response_model=OptimizeResponse)
def optimize_from_text(
    raw_text: str = Body(..., media_type="text/plain")
) -> OptimizeResponse:
    try:
        parsed_req = llm_interpreter.parse_raw_text_to_request(raw_text)
    except llm_interpreter.LLMInterpreterError as exc:
        raise HTTPException(
            status_code=400, detail=f"Failed to process text prompt: {exc}"
        )

    return optimize_energy(parsed_req)