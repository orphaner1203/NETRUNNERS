import logging
from typing import Any, Dict, List
from models import ALLOWED_DIRECTIVE_TYPES

logger = logging.getLogger(__name__)


def validate_interpretations(
    raw: List[Dict[str, Any]], num_notes: int, battery_capacity: float
) -> List[Dict[str, Any]]:
    sanitized: List[Dict[str, Any]] = []

    for idx in range(num_notes):
        matched = next((item for item in raw if item.get("note_index") == idx), None)

        if not matched:
            sanitized.append(
                {
                    "note_index": idx,
                    "applies": False,
                    "directive_type": "none",
                    "structured_adjustment": {},
                    "explanation": "No directive extracted by LLM.",
                }
            )
            continue

        dtype = matched.get("directive_type", "none")
        applies = bool(matched.get("applies", False))
        explanation = str(matched.get("explanation", ""))
        adj = matched.get("structured_adjustment", {})

        if dtype not in ALLOWED_DIRECTIVE_TYPES:
            sanitized.append(
                {
                    "note_index": idx,
                    "applies": False,
                    "directive_type": "none",
                    "structured_adjustment": {},
                    "explanation": f"Rejected invalid directive_type '{dtype}'.",
                }
            )
            continue

        if not applies or dtype == "none":
            sanitized.append(
                {
                    "note_index": idx,
                    "applies": False,
                    "directive_type": "none",
                    "structured_adjustment": {},
                    "explanation": explanation or "Directive marked non-applicable.",
                }
            )
            continue

        start = adj.get("start_hour")
        end = adj.get("end_hour")

        if start is not None and (not isinstance(start, int) or not (0 <= start <= 23)):
            applies = False
        if end is not None and (not isinstance(end, int) or not (0 <= end <= 23)):
            applies = False
        if start is not None and end is not None and start > end:
            applies = False

        reserve = adj.get("reserve_kwh")
        if reserve is not None:
            if not isinstance(reserve, (int, float)) or reserve < 0:
                applies = False
            elif reserve > battery_capacity:
                adj["reserve_kwh"] = battery_capacity

        sanitized.append(
            {
                "note_index": idx,
                "applies": applies,
                "directive_type": dtype if applies else "none",
                "structured_adjustment": adj if applies else {},
                "explanation": explanation,
            }
        )

    return sanitized


def directives_for_optimizer(sanitized: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [item for item in sanitized if item["applies"]]