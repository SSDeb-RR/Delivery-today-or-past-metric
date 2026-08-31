
from datetime import date

from date_resolver import DateResolver
from delivery_date_events import (
    DeliveryDateEventExtractor,
    EventType,
)


def test_relative_dates():
    anchor = date(2026, 8, 16)

    assert DateResolver.resolve("today", anchor).value == date(2026, 8, 16)
    assert DateResolver.resolve("tomorrow", anchor).value == date(2026, 8, 17)
    assert DateResolver.resolve("day after tomorrow", anchor).value == date(2026, 8, 18)
    assert DateResolver.resolve("yesterday", anchor).value == date(2026, 8, 15)


def test_hindi_relative_dates():
    anchor = date(2026, 8, 16)

    assert DateResolver.resolve("आज", anchor).value == date(2026, 8, 16)
    assert DateResolver.resolve("कल", anchor, context="we can schedule tomorrow").value == date(2026, 8, 17)
    assert DateResolver.resolve("परसों", anchor).value == date(2026, 8, 18)


def test_next_week_weekday():
    anchor = date(2026, 8, 16)  # Sunday
    resolved = DateResolver.resolve("next week Sunday", anchor)
    assert resolved.value == date(2026, 8, 23)


def test_explicit_dates():
    anchor = date(2026, 8, 16)

    assert DateResolver.resolve("18 August", anchor).value == date(2026, 8, 18)
    assert DateResolver.resolve("18th August", anchor).value == date(2026, 8, 18)
    assert DateResolver.resolve("18/08/2026", anchor).value == date(2026, 8, 18)
    assert DateResolver.resolve("eighteenth August", anchor).value == date(2026, 8, 18)
    assert DateResolver.resolve("18 अगस्त", anchor).value == date(2026, 8, 18)


def test_event_roles():
    turns = [
        type("T", (), {"index": 0, "role": "agent", "text": "We were unable to deliver on 16 August."})(),
        type("T", (), {"index": 1, "role": "agent", "text": "We can schedule it for tomorrow."})(),
        type("T", (), {"index": 2, "role": "customer", "text": "Yes, tomorrow is fine."})(),
        type("T", (), {"index": 3, "role": "agent", "text": "Your delivery is scheduled for tomorrow."})(),
    ]

    extractor = DeliveryDateEventExtractor(date(2026, 8, 16))
    events = extractor.extract_events(turns)

    types = [e.event_type for e in events]
    assert EventType.HISTORICAL_DELIVERY_DATE in types
    assert EventType.AGENT_PROPOSED_DATE in types
    assert EventType.CUSTOMER_REQUESTED_DATE in types
    assert EventType.AGENT_CONFIRMED_DATE in types
