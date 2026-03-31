from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .config import Config

# Timestamp patterns tried in order; first match wins
_TS_PATTERNS = [
    # ISO 8601: 2026-03-31T10:00:00.123Z  or  2026-03-31 10:00:00
    re.compile(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?\s*'),
    # Syslog: Jan  3 12:00:00 hostname
    re.compile(r'^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\S+\s+'),
    # Epoch: 1711882800.123
    re.compile(r'^\d{10}(?:\.\d+)?\s+'),
    # Time only: 10:00:00.123
    re.compile(r'^\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\s+'),
]

_LEVEL_RE = re.compile(
    r'\b(DEBUG|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL|TRACE)\b\s*[:\-]?\s*',
    re.IGNORECASE,
)

# Matches: key=value numbers, plain numbers, scientific notation
# Group 'label' is optional key name; group 'value' is the number
_NUM_RE = re.compile(
    r'(?:(?P<label>[A-Za-z_]\w*)\s*[=:]\s*)?(?P<value>[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)'
)

_SEPARATOR_RE = re.compile(r'^[-=*#]{3,}\s*$')


@dataclass
class NumericToken:
    value: float
    position: int
    label: Optional[str]
    context: str


@dataclass
class LogLine:
    raw: str
    line_number: int
    timestamp: Optional[str]
    level: Optional[str]
    message: str
    numerics: list[NumericToken] = field(default_factory=list)


class LogParser:
    def __init__(self, config: Config):
        self.config = config
        self._exclude = [re.compile(p) for p in config.exclude_patterns]

    def parse_file(self, path: Path) -> list[LogLine]:
        lines: list[LogLine] = []
        with open(path, encoding="utf-8", errors="replace") as f:
            for lineno, raw in enumerate(f, start=1):
                raw = raw.rstrip("\n")
                parsed = self._parse_line(raw, lineno)
                if parsed is not None:
                    lines.append(parsed)
        return lines

    def _parse_line(self, raw: str, lineno: int) -> Optional[LogLine]:
        # Skip blank lines and separator lines
        stripped = raw.strip()
        if not stripped or _SEPARATOR_RE.match(stripped):
            return None

        # Skip excluded patterns
        for pat in self._exclude:
            if pat.search(raw):
                return None

        timestamp: Optional[str] = None
        remainder = raw

        if self.config.ignore_timestamps:
            for ts_pat in _TS_PATTERNS:
                m = ts_pat.match(remainder)
                if m:
                    timestamp = m.group(0).strip()
                    remainder = remainder[m.end():]
                    break

        level: Optional[str] = None
        m = _LEVEL_RE.match(remainder)
        if m:
            level = m.group(1).upper()
            remainder = remainder[m.end():]

        message = remainder.strip()
        numerics = self._extract_numerics(message)

        return LogLine(
            raw=raw,
            line_number=lineno,
            timestamp=timestamp,
            level=level,
            message=message,
            numerics=numerics,
        )

    def _extract_numerics(self, message: str) -> list[NumericToken]:
        tokens: list[NumericToken] = []
        for m in _NUM_RE.finditer(message):
            try:
                value = float(m.group("value"))
            except ValueError:
                continue
            start = m.start("value")
            context_start = max(0, start - 10)
            context_end = min(len(message), m.end("value") + 10)
            tokens.append(NumericToken(
                value=value,
                position=start,
                label=m.group("label"),
                context=message[context_start:context_end],
            ))
        return tokens
