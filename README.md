# Delivery Scheduled for Today or Past

Deterministic implementation using transcript-relative date anchoring and
reusable delivery-date events.

## Core definition implemented

The metric asks only whether the **NEW delivery date** selected/confirmed by
the agent is today or in the past.

The original/failed delivery date is historical context and is never itself
treated as the target schedule.

## Transcript-relative "today"

The implementation takes the **first explicit date in the agent's historical
failed/original-delivery statement** as `transcript_today`.

Example:

```text
We were unable to deliver your order on 16 August.
```

becomes:

```text
historical_delivery_date = 2026-08-16
transcript_today = 2026-08-16
```

This is a transcript-relative anchor. It is not the execution date and does
not use the machine's current date.

## Date normalization

Relative expressions are converted to calendar dates relative to the anchor:

- `today` -> anchor
- `tomorrow` -> anchor + 1 day
- `day after tomorrow` -> anchor + 2 days
- `yesterday` -> anchor - 1 day
- `आज` -> anchor
- `कल` -> tomorrow in scheduling context
- `परसों` -> anchor + 2 days
- `next week Sunday` -> the next Sunday in the following week
- explicit dates such as `18 August`, `18th August`, `18/08/2026`, `18 अगस्त`
  are normalized to a `datetime.date`

## Delivery-date events

The reusable event layer classifies dates as:

- `historical_delivery_date`
- `customer_requested_date`
- `agent_proposed_date`
- `agent_accepted_date`
- `agent_rejected_date`
- `agent_confirmed_date`
- `customer_accepted_date`
- `unknown_date`

Metric 2 uses the effective NEW agent schedule, preferring the latest explicit
agent confirmation and otherwise the latest clear agent proposal/commitment.

## Metric decision

```text
effective_new_schedule_date <= transcript_today
    -> true

effective_new_schedule_date > transcript_today
    -> false
```

If no reliable historical anchor can be established, the metric returns
`false` and the audit output explains that `transcript_today` could not be
established.

## Run unit tests

```bash
python -m pip install -r requirements.txt
python -m pytest -q test_delivery_date_events.py test_delivery_scheduled_today_past.py
```

## Run all 18 problematic calls

```bash
python -m pytest -q test_problematic_calls.py
```

## Produce a detailed regression report

```bash
python run_regression.py
```

This writes:

```text
regression_report.json
```

containing, for every call:

- expected output
- actual output
- transcript_today
- historical delivery date
- effective new schedule date
- date expression
- all detected delivery-date events
- reason for the final decision

## Main API

```python
from delivery_scheduled_today_past import (
    evaluate_delivery_scheduled_today_past,
)

result = evaluate_delivery_scheduled_today_past(transcript)
print(result)
```
