from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from itertools import zip_longest
from pathlib import Path
from typing import Optional

from .config import Config
from .parser import LogLine

# Replaces all numbers with a placeholder for order comparison.
# This ensures lines that differ only in numeric values (e.g. latency=1.23 vs 1.31)
# are treated as the same message template and not flagged as order mismatches.
_NUM_NORMALIZE_RE = re.compile(r'[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?')


@dataclass
class Mismatch:
    kind: str  # "order" | "numeric" | "missing"
    baseline_lineno: Optional[int]
    new_lineno: Optional[int]
    detail: str


@dataclass
class ComparisonResult:
    baseline_path: Path
    new_path: Path
    passed: bool
    order_mismatches: list[Mismatch] = field(default_factory=list)
    numeric_mismatches: list[Mismatch] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class Comparator:
    def __init__(self, config: Config):
        self.config = config

    def compare(
        self,
        baseline: list[LogLine],
        new: list[LogLine],
        baseline_path: Path,
        new_path: Path,
    ) -> ComparisonResult:
        order_mismatches: list[Mismatch] = []
        numeric_mismatches: list[Mismatch] = []
        warnings: list[str] = []

        # Build aligned pairs via SequenceMatcher on normalized message templates.
        # Numbers are replaced with <N> so that lines differing only in numeric values
        # (e.g. latency=1.23 vs latency=1.31) are treated as the same message template
        # and checked by the numeric comparator rather than flagged as order mismatches.
        baseline_msgs = [_NUM_NORMALIZE_RE.sub("<N>", ln.message) for ln in baseline]
        new_msgs = [_NUM_NORMALIZE_RE.sub("<N>", ln.message) for ln in new]
        matcher = difflib.SequenceMatcher(None, baseline_msgs, new_msgs, autojunk=False)
        opcodes = matcher.get_opcodes()

        if not self.config.ignore_order:
            order_mismatches = self._compare_order(baseline, new, opcodes)

        if not self.config.ignore_numerics:
            numeric_mismatches, num_warnings = self._compare_numerics(
                baseline, new, opcodes
            )
            warnings.extend(num_warnings)

        passed = not order_mismatches and not numeric_mismatches
        return ComparisonResult(
            baseline_path=baseline_path,
            new_path=new_path,
            passed=passed,
            order_mismatches=order_mismatches,
            numeric_mismatches=numeric_mismatches,
            warnings=warnings,
        )

    def _compare_order(
        self,
        baseline: list[LogLine],
        new: list[LogLine],
        opcodes: list[tuple],
    ) -> list[Mismatch]:
        mismatches: list[Mismatch] = []
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == "equal":
                continue
            if tag == "replace":
                # Check if lines differ only in the normalized template (structural change)
                # vs. same template with different numbers (handled by numeric comparator).
                for bi, ni in zip_longest(range(i1, i2), range(j1, j2)):
                    b_line = baseline[bi] if bi is not None else None
                    n_line = new[ni] if ni is not None else None
                    b_lineno = b_line.line_number if b_line else None
                    n_lineno = n_line.line_number if n_line else None
                    b_norm = _NUM_NORMALIZE_RE.sub("<N>", b_line.message) if b_line else "<missing>"
                    n_norm = _NUM_NORMALIZE_RE.sub("<N>", n_line.message) if n_line else "<missing>"
                    # Only flag as order mismatch when the message templates differ
                    if b_norm != n_norm:
                        b_msg = b_line.message if b_line else "<missing>"
                        n_msg = n_line.message if n_line else "<missing>"
                        mismatches.append(Mismatch(
                            kind="order",
                            baseline_lineno=b_lineno,
                            new_lineno=n_lineno,
                            detail=f"message changed\n    baseline: {b_msg!r}\n         new: {n_msg!r}",
                        ))
            elif tag == "delete":
                for bi in range(i1, i2):
                    mismatches.append(Mismatch(
                        kind="missing",
                        baseline_lineno=baseline[bi].line_number,
                        new_lineno=None,
                        detail=f"message missing from new file: {baseline[bi].message!r}",
                    ))
            elif tag == "insert":
                for ni in range(j1, j2):
                    mismatches.append(Mismatch(
                        kind="missing",
                        baseline_lineno=None,
                        new_lineno=new[ni].line_number,
                        detail=f"extra message in new file: {new[ni].message!r}",
                    ))
        return mismatches

    def _compare_numerics(
        self,
        baseline: list[LogLine],
        new: list[LogLine],
        opcodes: list[tuple],
    ) -> tuple[list[Mismatch], list[str]]:
        mismatches: list[Mismatch] = []
        warnings: list[str] = []

        for tag, i1, i2, j1, j2 in opcodes:
            if tag == "equal":
                pairs = list(zip(range(i1, i2), range(j1, j2)))
            elif tag == "replace":
                # Include replace pairs where templates match (differ only in numbers)
                pairs = [
                    (bi, ni)
                    for bi, ni in zip_longest(range(i1, i2), range(j1, j2))
                    if bi is not None and ni is not None
                    and _NUM_NORMALIZE_RE.sub("<N>", baseline[bi].message)
                    == _NUM_NORMALIZE_RE.sub("<N>", new[ni].message)
                ]
            else:
                continue
            for bi, ni in pairs:
                b_line = baseline[bi]
                n_line = new[ni]
                line_mismatches, line_warnings = self._compare_line_numerics(
                    b_line, n_line
                )
                mismatches.extend(line_mismatches)
                warnings.extend(line_warnings)

        return mismatches, warnings

    def _compare_line_numerics(
        self,
        b_line: LogLine,
        n_line: LogLine,
    ) -> tuple[list[Mismatch], list[str]]:
        mismatches: list[Mismatch] = []
        warnings: list[str] = []

        if len(b_line.numerics) != len(n_line.numerics):
            msg = (
                f"baseline line {b_line.line_number} has {len(b_line.numerics)} numbers, "
                f"new line {n_line.line_number} has {len(n_line.numerics)}"
            )
            if self.config.numeric_count_mismatch_is_fail:
                mismatches.append(Mismatch(
                    kind="numeric",
                    baseline_lineno=b_line.line_number,
                    new_lineno=n_line.line_number,
                    detail=f"numeric token count mismatch: {msg}",
                ))
            else:
                warnings.append(f"WARNING: {msg}")

        for bt, nt in zip(b_line.numerics, n_line.numerics):
            if not self._within_tolerance(bt.value, nt.value):
                diff = abs(nt.value - bt.value)
                label = f"({bt.label})" if bt.label else ""
                mismatches.append(Mismatch(
                    kind="numeric",
                    baseline_lineno=b_line.line_number,
                    new_lineno=n_line.line_number,
                    detail=(
                        f"numeric mismatch {label}: "
                        f"expected {bt.value} got {nt.value} "
                        f"(diff={diff:.6g}, tolerance={self._tolerance_desc()})"
                        f"\n    context: {bt.context!r}"
                    ),
                ))

        return mismatches, warnings

    def _within_tolerance(self, baseline: float, new: float) -> bool:
        if self.config.tolerance_pct > 0:
            if baseline == 0:
                return new == 0
            return abs(new - baseline) / abs(baseline) <= self.config.tolerance_pct
        return abs(new - baseline) <= self.config.tolerance

    def _tolerance_desc(self) -> str:
        if self.config.tolerance_pct > 0:
            return f"{self.config.tolerance_pct * 100:.4g}%"
        return str(self.config.tolerance)
