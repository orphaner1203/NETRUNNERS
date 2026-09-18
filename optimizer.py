from typing import Any, Dict, List
import numpy as np
from scipy.optimize import linprog


class InfeasibleScenarioError(Exception):
    pass


def solve_schedule(
    demand: List[float],
    solar: List[float],
    tariff: List[float],
    battery_capacity: float,
    initial_energy: float,
    base_min_reserve: float,
    max_charge_per_hour: float,
    max_discharge_per_hour: float,
    directives: List[Dict[str, Any]],
) -> Dict[str, Any]:
    T = len(demand)

    min_reserve_hourly = [base_min_reserve] * T
    max_charge_hourly = [max_charge_per_hour] * T
    max_discharge_hourly = [max_discharge_per_hour] * T

    for d in directives:
        dtype = d.get("directive_type")
        adj = d.get("structured_adjustment", {})
        start = adj.get("start_hour", 0)
        end = adj.get("end_hour", T - 1)

        for h in range(start, end + 1):
            if 0 <= h < T:
                if dtype == "min_reserve_override":
                    if "reserve_kwh" in adj:
                        min_reserve_hourly[h] = max(
                            min_reserve_hourly[h], adj["reserve_kwh"]
                        )
                elif dtype == "max_charge_limit":
                    if "max_charge_kwh" in adj:
                        max_charge_hourly[h] = min(
                            max_charge_hourly[h], adj["max_charge_kwh"]
                        )
                elif dtype == "no_discharge":
                    max_discharge_hourly[h] = 0.0

    c_obj = np.zeros(5 * T)
    for t in range(T):
        c_obj[5 * t + 0] = tariff[t]

    bounds = []
    for t in range(T):
        g_bound = (0, None)
        s_bound = (0, solar[t])
        c_bound = (0, max_charge_hourly[t])
        d_bound = (0, max_discharge_hourly[t])
        e_bound = (min_reserve_hourly[t], battery_capacity)
        bounds.extend([g_bound, s_bound, c_bound, d_bound, e_bound])

    A_eq = []
    b_eq = []

    for t in range(T):
        eq1 = np.zeros(5 * T)
        eq1[5 * t + 0] = 1.0
        eq1[5 * t + 1] = 1.0
        eq1[5 * t + 3] = 1.0
        eq1[5 * t + 2] = -1.0
        A_eq.append(eq1)
        b_eq.append(demand[t])

        eq2 = np.zeros(5 * T)
        eq2[5 * t + 4] = 1.0
        eq2[5 * t + 2] = -1.0
        eq2[5 * t + 3] = 1.0
        if t == 0:
            b_eq.append(initial_energy)
        else:
            eq2[5 * (t - 1) + 4] = -1.0
            b_eq.append(0.0)
        A_eq.append(eq2)

    res = linprog(c=c_obj, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")

    if not res.success:
        raise InfeasibleScenarioError(res.message)

    x = res.x
    hourly_plan = []
    total_grid = 0.0
    total_cost = 0.0
    peak_grid = 0.0

    for t in range(T):
        g = float(x[5 * t + 0])
        s = float(x[5 * t + 1])
        c = float(x[5 * t + 2])
        d = float(x[5 * t + 3])
        e = float(x[5 * t + 4])

        total_grid += g
        total_cost += g * tariff[t]
        peak_grid = max(peak_grid, g)

        if c > 0.001:
            action = "charge"
            b_kwh = round(c, 2)
        elif d > 0.001:
            action = "discharge"
            b_kwh = round(d, 2)
        else:
            action = "idle"
            b_kwh = 0.0

        hourly_plan.append(
            {
                "hour": t,
                "grid_kwh": round(g, 2),
                "solar_used_kwh": round(s, 2),
                "battery_action": action,
                "battery_kwh": b_kwh,
                "battery_energy_after_kwh": round(e, 2),
            }
        )

    return {
        "hourly_plan": hourly_plan,
        "total_grid_kwh": round(total_grid, 2),
        "total_cost_bdt": round(total_cost, 2),
        "peak_grid_kwh": round(peak_grid, 2),
    }