
from __future__ import annotations

import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional, Tuple


MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2,
    "march": 3, "mar": 3, "april": 4, "apr": 4, "may": 5,
    "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
    "जनवरी": 1, "फरवरी": 2, "मार्च": 3, "अप्रैल": 4, "मई": 5,
    "जून": 6, "जुलाई": 7, "अगस्त": 8, "सितंबर": 9,
    "अक्टूबर": 10, "नवंबर": 11, "दिसंबर": 12,
}

EN_ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14,
    "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
    "nineteenth": 19, "twentieth": 20, "twenty-first": 21,
    "twenty first": 21, "twenty-second": 22, "twenty second": 22,
    "twenty-third": 23, "twenty third": 23, "twenty-fourth": 24,
    "twenty fourth": 24, "twenty-fifth": 25, "twenty fifth": 25,
    "twenty-sixth": 26, "twenty sixth": 26, "twenty-seventh": 27,
    "twenty seventh": 27, "twenty-eighth": 28, "twenty eighth": 28,
    "twenty-ninth": 29, "twenty ninth": 29, "thirtieth": 30,
    "thirty-first": 31, "thirty first": 31,
}

HI_NUMBERS = {
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5,
    "छह": 6, "छः": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
    "ग्यारह": 11, "बारह": 12, "तेरह": 13, "चौदह": 14, "पंद्रह": 15,
    "पन्द्रह": 15, "सोलह": 16, "सत्रह": 17, "अठारह": 18,
    "उन्नीस": 19, "बीस": 20, "इक्कीस": 21, "बाईस": 22, "तेईस": 23,
    "चौबीस": 24, "पच्चीस": 25, "छब्बीस": 26, "सत्ताईस": 27,
    "अट्ठाईस": 28, "उनतीस": 29, "तीस": 30, "इकतीस": 31,
}

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

@dataclass(frozen=True)
class ResolvedDate:
    expression: str
    value: date
    confidence: str
    reason: str


class DateResolver:
    """Deterministic date parser anchored to transcript_today."""

    # Year used only when the transcript itself does not provide one.
    # It is deliberately fixed: it is NOT the execution/call date.
    SYNTHETIC_YEAR = 2000

    @staticmethod
    def _make_date(year: int, month: int, day: int) -> Optional[date]:
        try:
            return date(year, month, day)
        except ValueError:
            return None

    @staticmethod
    def _parse_year(raw: Optional[str], fallback: int) -> int:
        if not raw:
            return fallback
        y = int(raw)
        return y + 2000 if y < 100 else y

    @classmethod
    def resolve_explicit(
        cls,
        expression: str,
        anchor: date,
    ) -> Optional[date]:
        text = expression.strip().lower()

        m = re.search(
            r'\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b',
            text,
        )
        if m:
            d = int(m.group(1))
            mo = int(m.group(2))
            y = cls._parse_year(m.group(3), anchor.year)
            return cls._make_date(y, mo, d)

        month_pattern = "|".join(
            sorted((re.escape(k) for k in MONTHS), key=len, reverse=True)
        )

        m = re.search(
            rf'\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_pattern})(?:\s+(\d{{4}}))?\b',
            text,
            re.I,
        )
        if m:
            d = int(m.group(1))
            mo = MONTHS[m.group(2).lower()]
            y = int(m.group(3)) if m.group(3) else anchor.year
            return cls._make_date(y, mo, d)

        m = re.search(
            rf'\b({month_pattern})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,\s*(\d{{4}}))?\b',
            text,
            re.I,
        )
        if m:
            mo = MONTHS[m.group(1).lower()]
            d = int(m.group(2))
            y = int(m.group(3)) if m.group(3) else anchor.year
            return cls._make_date(y, mo, d)

        ord_pattern = "|".join(
            sorted((re.escape(k) for k in EN_ORDINALS), key=len, reverse=True)
        )
        m = re.search(
            rf'\b({ord_pattern})\s+({month_pattern})(?:\s+(\d{{4}}))?\b',
            text,
            re.I,
        )
        if m:
            d = EN_ORDINALS[m.group(1).lower()]
            mo = MONTHS[m.group(2).lower()]
            y = int(m.group(3)) if m.group(3) else anchor.year
            return cls._make_date(y, mo, d)

        hi_day_pattern = "|".join(
            sorted((re.escape(k) for k in HI_NUMBERS), key=len, reverse=True)
        )
        m = re.search(
            rf'({hi_day_pattern})(?:\s+की|\s+को)?\s+({month_pattern})',
            text,
        )
        if m:
            d = HI_NUMBERS[m.group(1)]
            mo = MONTHS[m.group(2)]
            return cls._make_date(anchor.year, mo, d)

        m = re.search(r'\b(\d{1,2})\s*तारीख(?:\s*को)?\b', text)
        if m:
            d = int(m.group(1))
            return cls._make_date(anchor.year, anchor.month, d)

        return None

    @classmethod
    def resolve_relative(
        cls,
        expression: str,
        anchor: date,
        *,
        context: str = "",
    ) -> Optional[ResolvedDate]:
        text = expression.strip().lower()

        if re.search(r'\bday after tomorrow\b', text) or "परसों" in text:
            d = anchor + timedelta(days=2)
            return ResolvedDate(expression, d, "high", "day_after_tomorrow")

        if re.search(r'\btomorrow\b', text):
            d = anchor + timedelta(days=1)
            return ResolvedDate(expression, d, "high", "tomorrow")

        if re.search(r'\byesterday\b', text):
            d = anchor - timedelta(days=1)
            return ResolvedDate(expression, d, "high", "yesterday")

        if re.search(r'\btoday\b', text):
            return ResolvedDate(expression, anchor, "high", "today")

        if "आज" in text:
            return ResolvedDate(expression, anchor, "high", "आज")

        if "कल" in text:
            # Scheduling/proposal context => tomorrow.
            # Historical/failure context => yesterday.
            historical = any(
                x in context
                for x in [
                    "failed",
                    "unable",
                    "attempt",
                    "delivered",
                    "delivery was",
                    "नहीं हो पाई",
                    "असफल",
                    "हुई थी",
                    "हो गया था",
                    "ट्राय",
                ]
            )
            if historical and not any(
                x in context
                for x in ["schedule", "कर सकते", "कर देंगे", "कर दो", "कर देती", "कर दूँ"]
            ):
                d = anchor - timedelta(days=1)
                reason = "कल interpreted as yesterday from historical context"
            else:
                d = anchor + timedelta(days=1)
                reason = "कल interpreted as tomorrow from scheduling context"
            return ResolvedDate(expression, d, "medium", reason)

        # next/this weekday, including "next week sunday"
        weekday_match = re.search(
            r'\b(?:next week\s+|next\s+|this\s+|coming\s+)?'
            r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
            text,
            re.I,
        )
        if weekday_match:
            target = WEEKDAYS[weekday_match.group(1).lower()]
            current = anchor.weekday()

            if "next week" in text:
                days = (7 - current) + target
                if days == 0:
                    days = 7
            elif "next " in text or "coming " in text:
                days = (target - current) % 7
                if days == 0:
                    days = 7
            else:  # "this Sunday"
                days = (target - current) % 7

            return ResolvedDate(
                expression,
                anchor + timedelta(days=days),
                "high",
                "weekday_relative_to_anchor",
            )

        return None

    @classmethod
    def resolve(
        cls,
        expression: str,
        anchor: date,
        *,
        context: str = "",
    ) -> Optional[ResolvedDate]:
        rel = cls.resolve_relative(expression, anchor, context=context)
        if rel:
            return rel

        explicit = cls.resolve_explicit(expression, anchor)
        if explicit:
            return ResolvedDate(
                expression,
                explicit,
                "high",
                "explicit_calendar_date",
            )

        return None
