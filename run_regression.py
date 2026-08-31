
import json
from collections import Counter
from pathlib import Path

from delivery_scheduled_today_past import (
    evaluate_delivery_scheduled_today_past,
)

BASE = Path(__file__).resolve().parent
DATA = BASE / "problematic_calls.json"
REPORT = BASE / "regression_report.json"


def main():
    with open(DATA, "r", encoding="utf-8") as f:
        cases = json.load(f)

    rows = []
    counts = Counter()

    for case in cases:
        actual = evaluate_delivery_scheduled_today_past(case["transcript"])
        expected = case["expected_output"]
        match = actual["value"] == expected
        counts["pass" if match else "fail"] += 1

        rows.append({
            "case_id": case["case_id"],
            "name": case["name"],
            "expected": expected,
            "actual": actual["value"],
            "match": match,
            "transcript_today": actual["transcript_today"],
            "historical_delivery_date": actual["historical_delivery_date"],
            "effective_new_schedule_date": actual["effective_new_schedule_date"],
            "effective_schedule_expression": actual["effective_schedule_expression"],
            "reason": actual["reason"],
            "events": actual["events"],
        })

    report = {
        "total": len(rows),
        "passed": counts["pass"],
        "failed": counts["fail"],
        "accuracy": counts["pass"] / len(rows) if rows else None,
        "results": rows,
    }

    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 80)
    print("Delivery Scheduled for Today or Past")
    print(f"Total:    {report['total']}")
    print(f"Passed:   {report['passed']}")
    print(f"Failed:   {report['failed']}")
    print(
        f"Accuracy: {report['accuracy']:.2%}"
        if report["accuracy"] is not None
        else "Accuracy: N/A"
    )
    print(f"Report:   {REPORT}")

    for row in rows:
        if not row["match"]:
            print("-" * 80)
            print("Case:", row["case_id"], row["name"])
            print("Expected:", row["expected"])
            print("Actual:", row["actual"])
            print("Transcript today:", row["transcript_today"])
            print("Historical date:", row["historical_delivery_date"])
            print("Effective schedule:", row["effective_new_schedule_date"])
            print("Expression:", row["effective_schedule_expression"])
            print("Reason:", row["reason"])


if __name__ == "__main__":
    main()
