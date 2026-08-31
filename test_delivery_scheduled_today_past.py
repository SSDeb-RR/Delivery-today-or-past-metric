
import json

import pytest

from delivery_scheduled_today_past import (
    evaluate_delivery_scheduled_today_past,
)


def val(transcript):
    return evaluate_delivery_scheduled_today_past(transcript)["value"]


def test_historical_date_is_not_the_target():
    transcript = {
        "turns": [
            {"role": "agent", "text": "We were unable to deliver your order on 16 August."},
            {"role": "agent", "text": "We can schedule the delivery for tomorrow."},
        ]
    }

    result = evaluate_delivery_scheduled_today_past(transcript)

    assert result["transcript_today"] == "2000-08-16"
    assert result["historical_delivery_date"] == "2000-08-16"
    assert result["effective_new_schedule_date"] == "2000-08-17"
    assert result["value"] == "false"


def test_new_schedule_today_is_true():
    transcript = {
        "turns": [
            {"role": "agent", "text": "We were unable to deliver your order on 26 August."},
            {"role": "agent", "text": "We can schedule the delivery for today."},
        ]
    }

    result = evaluate_delivery_scheduled_today_past(transcript)
    assert result["transcript_today"] == "2000-08-26"
    assert result["effective_new_schedule_date"] == "2000-08-26"
    assert result["value"] == "true"


def test_new_schedule_past_is_true():
    transcript = {
        "turns": [
            {"role": "agent", "text": "We were unable to deliver your order on 26 August."},
            {"role": "agent", "text": "We have rescheduled your delivery for 22 August."},
        ]
    }

    result = evaluate_delivery_scheduled_today_past(transcript)
    assert result["effective_new_schedule_date"] == "2000-08-22"
    assert result["value"] == "true"


def test_new_schedule_tomorrow_is_false():
    transcript = {
        "turns": [
            {"role": "agent", "text": "The delivery failed on 16 August."},
            {"role": "agent", "text": "We can attempt the delivery again tomorrow."},
        ]
    }

    assert val(transcript) == "false"


def test_customer_request_does_not_become_agent_schedule():
    transcript = {
        "turns": [
            {"role": "agent", "text": "The delivery failed on 16 August."},
            {"role": "customer", "text": "Can you deliver it today?"},
            {"role": "agent", "text": "No, today is not possible. Tomorrow is the earliest."},
        ]
    }

    result = evaluate_delivery_scheduled_today_past(transcript)

    assert result["value"] == "false"
    assert result["effective_new_schedule_date"] == "2000-08-17"


def test_later_effective_date_wins():
    transcript = {
        "turns": [
            {"role": "agent", "text": "The delivery failed on 16 August."},
            {"role": "agent", "text": "We can deliver tomorrow."},
            {"role": "customer", "text": "No, please do 23 August."},
            {"role": "agent", "text": "Okay, your delivery is scheduled for 23 August."},
        ]
    }

    result = evaluate_delivery_scheduled_today_past(transcript)
    assert result["effective_schedule_expression"] == "23 August"
    assert result["value"] == "false"


def test_next_week_sunday_is_normalized():
    transcript = {
        "turns": [
            {"role": "agent", "text": "The delivery failed on 16 August."},
            {"role": "agent", "text": "We can schedule it for next week Sunday."},
        ]
    }

    result = evaluate_delivery_scheduled_today_past(transcript)
    assert result["effective_schedule_expression"] == "next week Sunday"
    assert result["value"] == "false"


def test_no_anchor_is_false_and_auditable():
    transcript = {
        "turns": [
            {"role": "agent", "text": "We can schedule your delivery for tomorrow."},
        ]
    }

    result = evaluate_delivery_scheduled_today_past(transcript)
    assert result["value"] == "false"
    assert result["transcript_today"] is None
    assert "could not be established" in result["reason"]


@pytest.mark.parametrize(
    "text",
    [
        "The delivery failed on 16 August. We can schedule it for 18 August.",
        "We were unable to deliver on 16 August. We'll reschedule for today.",
        "Delivery failed on 16 August. We can attempt again the day after tomorrow.",
        "We were unable to deliver on 16 August. We can schedule for 15 August.",
    ],
)
def test_mixed_historical_and_new_date_does_not_use_historical(text):
    result = evaluate_delivery_scheduled_today_past(
        {"turns": [{"role": "agent", "text": text}]}
    )
    # 18 Aug / today(16 Aug) / 18 Aug / 15 Aug respectively.
    # The fourth is a true violation.
    if "15 August" in text or (
        "today" in text.lower() and "reschedule" in text.lower()
    ):
        assert result["value"] == "true"
    else:
        assert result["value"] == "false"


def test_simple_input_format():
    transcript = {
        "customer": "Can you deliver today?",
        "agent": "We were unable to deliver on 16 August. We can schedule it for 17 August.",
    }
    # The simple form has one agent turn containing both history and new schedule.
    result = evaluate_delivery_scheduled_today_past(transcript)
    assert result["value"] == "false"
    assert result["effective_new_schedule_date"] == "2000-08-17"
