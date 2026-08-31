
import json
from pathlib import Path

import pytest

from delivery_scheduled_today_past import (
    evaluate_delivery_scheduled_today_past,
)


BASE = Path(__file__).resolve().parent
DATA = BASE / "problematic_calls.json"

with open(DATA, "r", encoding="utf-8") as f:
    CASES = json.load(f)


@pytest.mark.parametrize(
    "case",
    CASES,
    ids=[c["case_id"] for c in CASES],
)
def test_problematic_call(case):
    result = evaluate_delivery_scheduled_today_past(
        case["transcript"]
    )

    assert result["value"] == case["expected_output"], (
        f'{case["case_id"]} ({case["name"]}): '
        f'expected={case["expected_output"]}, '
        f'actual={result["value"]}, '
        f'reason={result["reason"]}, '
        f'effective_date={result["effective_new_schedule_date"]}, '
        f'transcript_today={result["transcript_today"]}'
    )
