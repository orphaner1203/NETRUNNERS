import json
import os
import re
from typing import Any, Dict, List
import anthropic
from models import BatteryConfig, HourlyData, OptimizeRequest
import openai


class LLMInterpreterError(Exception):
    pass


def _get_provider_and_key():
    provider = os.getenv("LLM_PROVIDER", "mock").lower()
    api_key = os.getenv("LLM_API_KEY", "")
    return provider, api_key


def _extract_json_payload(text: str) -> str:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    start_brace = text.find("{")
    end_brace = text.rfind("}")
    if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
        return text[start_brace : end_brace + 1].strip()

    start_bracket = text.find("[")
    end_bracket = text.rfind("]")
    if start_bracket != -1 and end_bracket != -1 and end_bracket > start_bracket:
        return text[start_bracket : end_bracket + 1].strip()

    return text


def interpret_notes(notes: List[str]) -> List[Dict[str, Any]]:
    if not notes:
        return []

    provider, api_key = _get_provider_and_key()

    if provider == "mock":
        results = []
        for i, note in enumerate(notes):
            note_lower = note.lower()
            if "reserve" in note_lower or "keep" in note_lower:
                results.append(
                    {
                        "note_index": i,
                        "applies": True,
                        "directive_type": "min_reserve_override",
                        "structured_adjustment": {
                            "start_hour": 17,
                            "end_hour": 20,
                            "reserve_kwh": 30.0,
                        },
                        "explanation": "Mock parsed reserve directive.",
                    }
                )
            elif "do not discharge" in note_lower or "no discharge" in note_lower:
                results.append(
                    {
                        "note_index": i,
                        "applies": True,
                        "directive_type": "no_discharge",
                        "structured_adjustment": {"start_hour": 17, "end_hour": 20},
                        "explanation": "Mock parsed no-discharge directive.",
                    }
                )
            else:
                results.append(
                    {
                        "note_index": i,
                        "applies": False,
                        "directive_type": "none",
                        "structured_adjustment": {},
                        "explanation": "Mock ignored note.",
                    }
                )
        return results

    prompt = f"""
    Analyze these operator notes for energy optimization constraints:
    {json.dumps(notes)}

    Return a JSON list of objects matching:
    [
      {{
        "note_index": int,
        "applies": boolean,
        "directive_type": "min_reserve_override" | "max_charge_limit" | "no_discharge" | "none",
        "structured_adjustment": {{"start_hour": int (0-23), "end_hour": int (0-23), "reserve_kwh": float, "max_charge_kwh": float}},
        "explanation": string
      }}
    ]
    Return strictly JSON without markdown.
    """

    try:
        if provider == "openai":
            client = openai.OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            content = resp.choices[0].message.content
        elif provider == "anthropic":
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            content = resp.content[0].text
        else:
            raise LLMInterpreterError(f"Unsupported LLM provider: {provider}")

        cleaned_json = _extract_json_payload(content)
        return json.loads(cleaned_json)
    except Exception as exc:
        raise LLMInterpreterError(f"LLM Interpretation failed: {exc}")


def parse_raw_text_to_request(raw_text: str) -> OptimizeRequest:
    provider, api_key = _get_provider_and_key()

    prompt = f"""
    Convert the following natural language description into a JSON payload for grid energy optimization.
    The JSON must adhere strictly to this schema:
    {{
      "scenario_id": string,
      "operator_notes": [list of natural language directives/notes strings],
      "battery": {{
        "capacity_kwh": float,
        "initial_energy_kwh": float,
        "minimum_energy_kwh": float,
        "max_charge_kwh_per_hour": float,
        "max_discharge_kwh_per_hour": float
      }},
      "hours": [
        list of 24 objects for hours 0 to 23:
        {{"hour": int, "demand_kwh": float, "solar_kwh": float, "tariff_bdt_per_kwh": float}}
      ]
    }}

    Input Text:
    "{raw_text}"

    Return strictly raw JSON without markdown formatting.
    """

    try:
        if provider == "openai":
            client = openai.OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            content = resp.choices[0].message.content
        elif provider == "anthropic":
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=2500,
                messages=[{"role": "user", "content": prompt}],
            )
            content = resp.content[0].text
        else:
            return OptimizeRequest(
                scenario_id="human_text_scenario",
                operator_notes=[raw_text],
                battery=BatteryConfig(
                    capacity_kwh=100.0,
                    initial_energy_kwh=50.0,
                    minimum_energy_kwh=10.0,
                    max_charge_kwh_per_hour=25.0,
                    max_discharge_kwh_per_hour=25.0,
                ),
                hours=[
                    HourlyData(
                        hour=h,
                        demand_kwh=20.0,
                        solar_kwh=10.0 if 8 <= h <= 16 else 0.0,
                        tariff_bdt_per_kwh=12.0 if 17 <= h <= 20 else 6.0,
                    )
                    for h in range(24)
                ],
            )

        cleaned_json = _extract_json_payload(content)
        return OptimizeRequest.model_validate_json(cleaned_json)
    except Exception as exc:
        raise LLMInterpreterError(f"Failed to parse text input into schema: {exc}")