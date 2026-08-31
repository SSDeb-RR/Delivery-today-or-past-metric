import json

from delivery_scheduled_today_past import (
    evaluate_delivery_scheduled_today_past,
)

examples = [
    {
        "turns": [
            {"role": "agent", "text": "We were unable to deliver your order on 16 August."},
            {"role": "agent", "text": "We can schedule the delivery for tomorrow."},
        ]
    },
    {
        "turns": [
            {"role": "agent", "text": "We were unable to deliver your order on 26 August."},
            {"role": "agent", "text": "We have rescheduled your delivery for 22 August."},
        ]
    },
]

for i, transcript in enumerate(examples, 1):
    print("=" * 80)
    print(f"Example {i}")
    print(
        json.dumps(
            evaluate_delivery_scheduled_today_past(transcript),
            ensure_ascii=False,
            indent=2,
        )
    )
