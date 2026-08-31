
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional

from delivery_date_events import (
    DeliveryDateEvent,
    DeliveryDateEventExtractor,
    EventType,
)
from date_resolver import DateResolver


class MetricValue(str, Enum):
    TRUE = "true"
    FALSE = "false"


@dataclass
class EvaluationResult:
    metric: str
    value: str
    transcript_today: Optional[str]
    historical_delivery_date: Optional[str]
    effective_new_schedule_date: Optional[str]
    effective_schedule_expression: Optional[str]
    effective_schedule_event_type: Optional[str]
    reason: str
    events: List[Dict[str, Any]]

    def to_dict(self):
        return asdict(self)



class AddressLikeDeliveryContext:
    @staticmethod
    def is_historical_delivery_statement(text, failure_cues):
        normalized = text.strip().lower()

        has_delivery_subject = bool(
            re.search(
                r"\b(?:delivery|order)\b|डिलीवरी|ऑर्डर",
                normalized,
                re.I,
            )
        )

        if not has_delivery_subject:
            return False

        return any(
            re.search(pattern, normalized, re.I)
            for pattern in failure_cues
        )


class DeliveryScheduledTodayPastMetric:
    METRIC_NAME = "Delivery Scheduled for Today or Past"

    HISTORICAL_PATTERNS = DeliveryDateEventExtractor.HISTORICAL_PATTERNS

    @staticmethod
    def _find_anchor(turns):
        """
        Find transcript_today from the first explicit calendar date mentioned
        by the agent while describing the failed/original delivery.

        The real transcripts use many formulations, so this intentionally
        separates:
          1) delivery context, and
          2) failure/attempt context,

        instead of relying on one exact phrase such as "unable to deliver".
        """

        # A delivery/order turn plus ANY clear failure/attempt cue is enough.
        # This covers the actual ASR variants in the regression set.
        failure_cues = [
            # English
            r"\bunable\b",
            r"\bcouldn't\b",
            r"\bcould not\b",
            r"\bfailed\b",
            r"\bnot completed\b",
            r"\bdid not happen\b",
            r"\bnot delivered\b",
            r"\bnot deliver\b",
            r"\battempt(?:ed)?\b",
            r"\btried to deliver\b",
            r"\btry(?:ing)? to deliver\b",
            r"\bproblem\b",
            r"\bissue\b",

            # Hindi / Hinglish
            r"असमर्थ",
            r"असफल",
            r"नहीं हो पाई",
            r"नहीं हो पाया",
            r"नहीं हुई",
            r"नहीं हुआ",
            r"नहीं कर पाए",
            r"नहीं कर पाई",
            r"नहीं कर पाया",
            r"नहीं किया",
            r"समस्या",
            r"कोशिश",
            r"प्रयास",
            r"दिक्कत",
            r"सफल नहीं",
        ]

        # Explicit calendar dates only. Do NOT use today/tomorrow/कल here.
        explicit_only = re.compile(
            r"(?ix)"
            r"(?:"
            r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b"
            r"|"
            r"\b\d{1,2}(?:st|nd|rd|th)?\s+"
            r"(?:january|jan|february|feb|march|mar|april|apr|may|"
            r"june|jun|july|jul|august|aug|september|sep|sept|"
            r"october|oct|november|nov|december|dec)\b"
            r"|"
            r"\b(?:january|jan|february|feb|march|mar|april|apr|may|"
            r"june|jun|july|jul|august|aug|september|sep|sept|"
            r"october|oct|november|nov|december|dec)\s+"
            r"\d{1,2}(?:st|nd|rd|th)?\b"
            r"|"
            r"\b\d{1,2}\s*"
            r"(?:जनवरी|फरवरी|मार्च|अप्रैल|मई|जून|जुलाई|अगस्त|"
            r"सितंबर|सितम्बर|अक्टूबर|नवंबर|दिसंबर)\b"
            r")"
        )

        for turn in turns:
            if turn.role != "agent":
                continue

            text = turn.text

            # We only accept dates from turns that clearly concern the
            # original/failed delivery.
            has_delivery_context = bool(
                re.search(
                    r"\b(?:delivery|deliver|order)\b|डिलीवरी|डिलीवर|ऑर्डर",
                    text,
                    re.I,
                )
            )

            if not has_delivery_context:
                continue

            has_failure_context = any(
                re.search(pattern, text, re.I)
                for pattern in failure_cues
            )

            # Some original-delivery statements do not contain an explicit
            # "failed/unable" word. For example:
            # "our order delivery which was on 16 August, calling to reschedule".
            # When a delivery/order is described with a past-state/was-structure
            # AND the same turn is explicitly about rescheduling, the date is
            # still a reliable historical/original-delivery anchor.
            has_original_reschedule_context = (
                bool(
                    re.search(
                        r"\b(?:reschedule|rescheduling|schedule again)\b",
                        text,
                        re.I,
                    )
                )
                and bool(
                    re.search(
                        r"(?:delivery|order|डिलीवरी|ऑर्डर).*?"
                        r"(?:\bwas\b|\bwere\b|\bwas supposed to\b|"
                        r"था|थी|थे|होनी थी|हुआ था|हुई थी)",
                        text,
                        re.I,
                    )
                )
            )

            if not (has_failure_context or has_original_reschedule_context):
                continue

            for match in explicit_only.finditer(text):
                expression = match.group(0).strip()

                resolved = DateResolver.resolve(
                    expression,
                    date(DateResolver.SYNTHETIC_YEAR, 1, 1),
                    context="historical failed delivery",
                )

                if resolved:
                    return resolved.value, expression, turn.index

        return None, None, None
    @staticmethod
    def _date_from_event(event):
        if not event.date:
            return None
        try:
            return date.fromisoformat(event.date)
        except ValueError:
            return None

    @staticmethod
    def _is_schedule_event(event):
        return event.event_type in {
            EventType.AGENT_PROPOSED_DATE,
            EventType.AGENT_CONFIRMED_DATE,
        }

    @staticmethod
    def _is_historical(event):
        return event.event_type == EventType.HISTORICAL_DELIVERY_DATE

    @staticmethod
    def _is_customer_only(event):
        return event.event_type in {
            EventType.CUSTOMER_REQUESTED_DATE,
            EventType.CUSTOMER_ACCEPTED_DATE,
        }

    def evaluate(self, transcript: Any) -> Dict[str, Any]:
        from transcript_parser import TranscriptParser

        turns = TranscriptParser.parse(transcript)

        if not turns:
            return EvaluationResult(
                metric=self.METRIC_NAME,
                value=MetricValue.FALSE.value,
                transcript_today=None,
                historical_delivery_date=None,
                effective_new_schedule_date=None,
                effective_schedule_expression=None,
                effective_schedule_event_type=None,
                reason="No usable transcript turns.",
                events=[],
            ).to_dict()

        historical_date, historical_expression, historical_turn = self._find_anchor(turns)

        # Without the historical anchor we cannot safely compare dates.
        # The metric remains binary: unresolved cases return false.
        if historical_date is None:
            return EvaluationResult(
                metric=self.METRIC_NAME,
                value=MetricValue.FALSE.value,
                transcript_today=None,
                historical_delivery_date=None,
                effective_new_schedule_date=None,
                effective_schedule_expression=None,
                effective_schedule_event_type=None,
                reason=(
                    "No reliable explicit historical/original delivery date "
                    "was found, so transcript_today could not be established."
                ),
                events=[],
            ).to_dict()

        extractor = DeliveryDateEventExtractor(historical_date)
        events = extractor.extract_events(turns)

        # Remove the anchor historical date itself from the schedule candidates.
        schedule_events = [
            e for e in events
            if self._is_schedule_event(e)
            and e.turn_index >= 0
            and self._date_from_event(e) is not None
        ]

        # Select the effective schedule:
        #
        # 1. Prefer explicit agent confirmations.
        # 2. Otherwise use the latest clear agent proposal/commitment.
        #
        # This prevents a historical date from being mistaken for the target.
        confirmations = [
            e for e in schedule_events
            if e.event_type == EventType.AGENT_CONFIRMED_DATE
        ]

        if confirmations:
            effective = confirmations[-1]
        elif schedule_events:
            effective = schedule_events[-1]
        else:
            effective = None

        if effective is None:
            return EvaluationResult(
                metric=self.METRIC_NAME,
                value=MetricValue.FALSE.value,
                transcript_today=historical_date.isoformat(),
                historical_delivery_date=historical_date.isoformat(),
                effective_new_schedule_date=None,
                effective_schedule_expression=None,
                effective_schedule_event_type=None,
                reason=(
                    "No new agent delivery scheduling/confirmation event "
                    "was detected."
                ),
                events=[e.to_dict() for e in events],
            ).to_dict()

        scheduled_date = self._date_from_event(effective)

        if scheduled_date <= historical_date:
            value = MetricValue.TRUE.value
            reason = (
                f"Effective new schedule {scheduled_date.isoformat()} is "
                f"on or before transcript_today {historical_date.isoformat()}."
            )
        else:
            value = MetricValue.FALSE.value
            reason = (
                f"Effective new schedule {scheduled_date.isoformat()} is "
                f"after transcript_today {historical_date.isoformat()}."
            )

        return EvaluationResult(
            metric=self.METRIC_NAME,
            value=value,
            transcript_today=historical_date.isoformat(),
            historical_delivery_date=historical_date.isoformat(),
            effective_new_schedule_date=scheduled_date.isoformat(),
            effective_schedule_expression=effective.expression,
            effective_schedule_event_type=effective.event_type.value,
            reason=reason,
            events=[e.to_dict() for e in events],
        ).to_dict()


def evaluate_delivery_scheduled_today_past(transcript: Any) -> Dict[str, Any]:
    return DeliveryScheduledTodayPastMetric().evaluate(transcript)


if __name__ == "__main__":
    example = {
        "turns": [
            {
                "role": "agent",
                "text": "We were unable to deliver your order on 16 August.",
            },
            {
                "role": "agent",
                "text": "We can schedule the delivery for tomorrow.",
            },
        ]
    }

    print(
        json.dumps(
            evaluate_delivery_scheduled_today_past(example),
            ensure_ascii=False,
            indent=2,
        )
    )
