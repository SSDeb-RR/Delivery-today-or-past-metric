
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class Turn:
    index: int
    role: str
    text: str


class TranscriptParser:
    ROLE_ALIASES = {
        "agent": "agent",
        "assistant": "agent",
        "bot": "agent",
        "customer": "customer",
        "user": "customer",
        "caller": "customer",
    }

    @classmethod
    def _normalize(cls, text: Any) -> str:
        if text is None:
            return ""
        text = str(text).replace("\u00a0", " ")
        text = re.sub(r"[\r\n\t]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def parse(cls, payload: Any) -> List[Turn]:
        if payload is None:
            return []

        if isinstance(payload, str):
            payload = json.loads(payload)

        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict) and "turns" in payload:
            items = payload["turns"]
        elif isinstance(payload, dict):
            if "customer" in payload and "agent" in payload:
                return [
                    Turn(0, "customer", cls._normalize(payload["customer"])),
                    Turn(1, "agent", cls._normalize(payload["agent"])),
                ]
            return cls._parse_numbered(payload)
        else:
            raise TypeError("Transcript must be a dict, list, or JSON string.")

        result = []
        for item in items:
            if not isinstance(item, dict):
                continue
            role = item.get("role") or item.get("speaker") or item.get("type")
            text = item.get("text", item.get("content", ""))
            if role is None:
                continue
            role = cls.ROLE_ALIASES.get(str(role).strip().lower())
            if role is None:
                continue
            result.append(Turn(len(result), role, cls._normalize(text)))
        return result

    @classmethod
    def _parse_numbered(cls, payload: Dict[str, Any]) -> List[Turn]:
        pattern = re.compile(
            r"^(agent|assistant|customer|user|caller|bot)[_\-\s]?(\d+)$",
            re.I,
        )

        items = []
        order = {k: i for i, k in enumerate(payload.keys())}

        for key, value in payload.items():
            m = pattern.match(str(key))
            if not m:
                continue
            role = cls.ROLE_ALIASES.get(m.group(1).lower())
            if not role:
                continue
            items.append(
                (int(m.group(2)), order[key], role, cls._normalize(value))
            )

        items.sort(key=lambda x: (x[0], x[1]))
        return [Turn(i, x[2], x[3]) for i, x in enumerate(items)]
