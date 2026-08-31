
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from date_resolver import DateResolver, ResolvedDate


class EventType(str, Enum):
    HISTORICAL_DELIVERY_DATE = "historical_delivery_date"
    CUSTOMER_REQUESTED_DATE = "customer_requested_date"
    AGENT_PROPOSED_DATE = "agent_proposed_date"
    AGENT_ACCEPTED_DATE = "agent_accepted_date"
    AGENT_REJECTED_DATE = "agent_rejected_date"
    AGENT_CONFIRMED_DATE = "agent_confirmed_date"
    CUSTOMER_ACCEPTED_DATE = "customer_accepted_date"
    UNKNOWN_DATE = "unknown_date"


@dataclass
class DeliveryDateEvent:
    turn_index: int
    speaker: str
    expression: str
    date: Optional[str]
    event_type: EventType
    confidence: str
    reason: str
    text: str

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["event_type"] = self.event_type.value
        return data


class DeliveryDateEventExtractor:
    """
    Turns date mentions into semantic delivery-date events.

    The first agent historical/original failed-delivery date is the anchor
    used by the metric as transcript_today.
    """

    HISTORICAL_PATTERNS = [
        r"unable to deliver .*?\b(?:on|for)\b",
        r"couldn't deliver .*?\b(?:on|for)\b",
        r"could not deliver .*?\b(?:on|for)\b",
        r"delivery .*?failed .*?\b(?:on|for)\b",
        r"failed .*?delivery .*?\b(?:on|for)\b",
        r"delivery .*?attempt(?:ed)? .*?\b(?:on|for)\b",
        r"delivery .*?was .*?\b(?:on|for)\b",
        r"delivery .*?16th august",
        r"delivery .*?twenty fourth august",
        r"डिलीवरी .*?नहीं हो पाई .*?(?:को|पर)",
        r"डिलीवरी .*?असफल .*?(?:को|पर)",
        r"डिलीवरी .*?करने में असमर्थ .*?(?:को|पर)",
        r"डिलीवरी .*?का प्रयास .*?(?:को|पर)",
        r"डिलीवरी .*?हो नहीं पाई .*?(?:को|पर)",
        r"डिलीवरी .*?हुई थी",
        r"delivery .*?सफल नहीं हो पाई",
        r"delivery .*?नहीं हो पाई",
        r"delivery .*?असफल रही",
    ]

    CUSTOMER_REQUEST_PATTERNS = [
        r"\b(can you|could you|would you|please)\b.*\b(deliver|try|schedule|attempt)\b",
        r"\b(?:do|deliver|try|schedule)\b.*\b(on|for|tomorrow|today|yesterday)\b",
        r"\bnext week\b",
        r"\btomorrow\b",
        r"\btoday\b",
        r"\bday after tomorrow\b",
        r"\bnext (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        r"\b(?:कल|आज|परसों)\b",
    ]

    AGENT_SCHEDULE_PATTERNS = [
        r"\b(?:schedule|reschedule|book|arrange)\b",
        r"\b(?:deliver|attempt)\b.*\b(?:today|tomorrow|yesterday|day after tomorrow)\b",
        r"\btomorrow\b.*\bearliest\b",
        r"\b(?:deliver|attempt)\b.*\b(?:on|for)\b",
        r"\bwe can\b.*\b(?:deliver|attempt|schedule|reschedule)\b",
        r"\bi can\b.*\b(?:deliver|attempt|schedule|reschedule)\b",
        r"\bi(?:'ll| will)\b.*\b(?:deliver|attempt|schedule|reschedule)\b",
        r"\bwe(?:'ll| will)\b.*\b(?:deliver|attempt|schedule|reschedule)\b",
        r"delivery .* schedule",
        r"delivery .* reschedule",
        r"डिलीवरी .* schedule",
        r"डिलीवरी .* reschedule",
        r"डिलीवरी .* शेड्यूल",
        r"डिलीवरी .* पुनर्निर्धारित",
        r"कर सकते हैं",
        r"कर देंगे",
        r"कर देती हूँ",
        r"कर देती हूं",
        r"कर दूंगी",
        r"कर दूँगी",
        r"कर दो",
        r"कर दी गई",
        r"कर दी गयी",
        r"schedule कर",
        r"reschedule कर",
    ]

    AGENT_CONFIRM_PATTERNS = [
        r"\b(?:your|the) delivery (?:is|has been) scheduled\b",
        r"\bdelivery .* scheduled for\b",
        r"\bdelivery .* rescheduled for\b",
        r"\bscheduled .* for\b",
        r"\brescheduled .* for\b",
        r"डिलीवरी .* schedule कर दी",
        r"डिलीवरी .* शेड्यूल कर दी",
        r"डिलीवरी .* reschedule कर दी",
        r"डिलीवरी .* पुनर्निर्धारित कर दी",
        r"आपकी delivery .* schedule कर दी",
        r"आपकी डिलीवरी .* शेड्यूल कर दी",
    ]

    REJECTION_PATTERNS = [
        r"\bcannot\b.*\b(?:deliver|schedule|reschedule)\b",
        r"\bcan't\b.*\b(?:deliver|schedule|reschedule)\b",
        r"\bnot possible\b",
        r"\bwe can only\b",
        r"\bearliest .* tomorrow\b",
        r"आज .*नहीं.*(?:कर सकते|हो पाएगा)",
        r"आज संभव नहीं",
        r"कल से पहले .* नहीं",
        r"सबसे जल्दी .* कल",
        r"only .* tomorrow",
    ]

    def __init__(self, anchor):
        self.anchor = anchor

    @staticmethod
    def _matches(text: str, patterns) -> bool:
        return any(re.search(p, text, re.I) for p in patterns)

    @staticmethod
    def _date_like_expressions(text: str) -> List[str]:
        expressions: List[str] = []

        patterns = [
            r"\bday after tomorrow\b",
            r"\btomorrow\b",
            r"\byesterday\b",
            r"\btoday\b",
            r"\bnext week\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"\bnext (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"\bthis (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b",
            r"\b\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\b",
            r"\b[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?\b",
            r"\b(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth|twenty[- ]first|twenty[- ]second|twenty[- ]third|twenty[- ]fourth|twenty[- ]fifth|twenty[- ]sixth|twenty[- ]seventh|twenty[- ]eighth|twenty[- ]ninth|thirtieth|thirty[- ]first)\s+[A-Za-z]+\b",
            r"\b(?:आज|कल|परसों)\b",
            r"\b\d{1,2}\s*(?:अगस्त|सितंबर|सितम्बर|जुलाई|जून|मई|अप्रैल|मार्च|फरवरी|जनवरी|अक्टूबर|नवंबर|दिसंबर)\b",
            r"\b(?:एक|दो|तीन|चार|पांच|पाँच|छह|सात|आठ|नौ|दस|ग्यारह|बारह|तेरह|चौदह|पंद्रह|सोलह|सत्रह|अठारह|उन्नीस|बीस|इक्कीस|बाईस|तेईस|चौबीस|पच्चीस|छब्बीस|सत्ताईस|अट्ठाईस|उनतीस|तीस|इकतीस)\s+(?:अगस्त|सितंबर|सितम्बर|जुलाई|जून|मई|अप्रैल|मार्च|फरवरी|जनवरी|अक्टूबर|नवंबर|दिसंबर)\b",
        ]

        for p in patterns:
            expressions.extend(m.group(0) for m in re.finditer(p, text, re.I))

        # De-duplicate while preserving textual order.
        seen = set()
        out = []
        for e in expressions:
            key = e.lower()
            if key not in seen:
                seen.add(key)
                out.append(e)
        return out

    def extract_historical_anchor(self, turns) -> Optional[ResolvedDate]:
        for turn in turns:
            if turn.role != "agent":
                continue

            text = turn.text
            if not self._matches(text, self.HISTORICAL_PATTERNS):
                continue

            expressions = self._date_like_expressions(text)
            for expression in expressions:
                resolved = DateResolver.resolve(
                    expression,
                    self.anchor,
                    context="historical failed delivery",
                )
                if resolved:
                    return resolved

        return None


    def extract_events(self, turns) -> List[DeliveryDateEvent]:
        events: List[DeliveryDateEvent] = []

        # Analyze sentence/utterance clauses separately. This prevents a
        # historical date in the same turn from inheriting the schedule intent
        # of a later clause in that turn.
        for turn in turns:
            raw_text = turn.text
            clauses = [
                c.strip()
                for c in re.split(r"(?:[.!?]+|।+|;\s*)", raw_text)
                if c.strip()
            ]

            if not clauses:
                clauses = [raw_text]

            cursor = 0

            for clause in clauses:
                exprs = self._date_like_expressions(clause)
                if not exprs:
                    cursor += len(clause) + 1
                    continue

                clause_context = clause
                historical_match = self._matches(
                    clause_context,
                    self.HISTORICAL_PATTERNS,
                )

                # Short local cues that occur BEFORE a date expression.
                # These are deliberately narrower than the full historical
                # patterns so "deliver on 16 August" is not mistaken for a
                # schedule just because "deliver on" contains an "on" token.
                historical_cues = [
                    r"\bunable to deliver\b",
                    r"\bunable to\b",
                    r"\bcouldn't deliver\b",
                    r"\bcould not deliver\b",
                    r"\bfailed\b",
                    r"\bdelivery failed\b",
                    r"\bdelivery attempt\b",
                    r"\battempted to deliver\b",
                    r"\bwe were unable\b",
                    r"\bनहीं हो पाई\b",
                    r"\bअसफल\b",
                    r"\bडिलीवरी.*प्रयास\b",
                    r"\bडिलीवरी.*नहीं हो पाई\b",
                    r"\bडिलीवरी.*असफल\b",
                    r"delivery .*?सफल नहीं हो पाई",
                    r"delivery .*?नहीं हो पाई",
                    r"delivery .*?असफल रही",
                ]

                historical_cue_positions = []
                for cue in historical_cues:
                    match = re.search(cue, clause_context, re.I)
                    if match:
                        historical_cue_positions.append(match.start())

                # Only strong scheduling phrases count as a schedule cue
                # BEFORE a date. Generic phrases like "deliver on" must NOT
                # be used here, because they also occur in historical failure
                # statements such as "unable to deliver on 16 August".
                strong_schedule_cues = [
                    r"\bschedule(?:d|s|ing)?\b.*\b(?:for|on|to)\b",
                    r"\breschedule(?:d|s|ing)?\b.*\b(?:for|on|to)\b",
                    r"\bdelivery\s+(?:is|has been)\s+(?:scheduled|rescheduled)\b",
                    r"\b(?:i|we)(?:'ll| will| can)\b.*\b(?:schedule|reschedule)\b",
                    r"schedule कर",
                    r"reschedule कर",
                    r"शेड्यूल कर",
                    r"पुनर्निर्धारित कर",
                ]

                schedule_positions = []
                for schedule_pattern in strong_schedule_cues:
                    match = re.search(schedule_pattern, clause_context, re.I)
                    if match:
                        schedule_positions.append(match.start())

                first_historical_cue_pos = (
                    min(historical_cue_positions)
                    if historical_cue_positions
                    else None
                )

                first_schedule_pos = (
                    min(schedule_positions)
                    if schedule_positions
                    else None
                )

                clause_is_rejection = self._matches(
                    clause_context,
                    self.REJECTION_PATTERNS,
                )

                clause_is_confirmation = self._matches(
                    clause_context,
                    self.AGENT_CONFIRM_PATTERNS,
                )

                clause_is_schedule = self._matches(
                    clause_context,
                    self.AGENT_SCHEDULE_PATTERNS,
                )

                clause_is_customer_request = self._matches(
                    clause_context,
                    self.CUSTOMER_REQUEST_PATTERNS,
                )

                for expression in exprs:
                    resolved = DateResolver.resolve(
                        expression,
                        self.anchor,
                        context=clause_context,
                    )

                    if not resolved:
                        events.append(
                            DeliveryDateEvent(
                                turn.index,
                                turn.role,
                                expression,
                                None,
                                EventType.UNKNOWN_DATE,
                                "low",
                                "Date expression could not be resolved.",
                                raw_text,
                            )
                        )
                        continue

                    if turn.role == "agent":
                        expression_pos = clause_context.find(expression)

                        # Historical wins when a historical cue occurs before
                        # the date, unless a clear schedule phrase appears
                        # even earlier. This handles:
                        #
                        # "We failed delivery on 16 August. We can schedule..."
                        # and also a same-clause variant where both concepts
                        # occur in one sentence.
                        expression_is_historical = (
                            historical_match
                            and first_historical_cue_pos is not None
                            and (
                                first_schedule_pos is None
                                or first_historical_cue_pos < first_schedule_pos
                            )
                            and (
                                expression_pos < first_schedule_pos
                                if first_schedule_pos is not None
                                else True
                            )
                        )

                        if expression_is_historical:
                            event_type = EventType.HISTORICAL_DELIVERY_DATE
                            reason = "Historical/original delivery date."

                        elif clause_is_rejection:
                            event_type = EventType.AGENT_REJECTED_DATE
                            reason = "Agent rejects or limits a requested date."

                        elif clause_is_confirmation:
                            event_type = EventType.AGENT_CONFIRMED_DATE
                            reason = "Agent explicitly confirms a delivery schedule."

                        elif clause_is_schedule:
                            event_type = EventType.AGENT_PROPOSED_DATE
                            reason = "Agent proposes/commits to a new delivery date."

                        else:
                            event_type = EventType.UNKNOWN_DATE
                            reason = "Agent mentions a date without clear scheduling role."

                    else:
                        if clause_is_customer_request:
                            event_type = EventType.CUSTOMER_REQUESTED_DATE
                            reason = "Customer requests/discusses a delivery date."
                        elif re.search(
                            r"\b(?:yes|okay|fine|sure|ठीक|जी|कर दो|कर दीजिए)\b",
                            clause_context,
                            re.I,
                        ):
                            event_type = EventType.CUSTOMER_ACCEPTED_DATE
                            reason = "Customer accepts the currently discussed date."
                        else:
                            event_type = EventType.CUSTOMER_REQUESTED_DATE
                            reason = "Customer mentions a possible date."

                    events.append(
                        DeliveryDateEvent(
                            turn.index,
                            turn.role,
                            expression,
                            resolved.value.isoformat(),
                            event_type,
                            resolved.confidence,
                            resolved.reason,
                            raw_text,
                        )
                    )

                cursor += len(clause) + 1

        return events

