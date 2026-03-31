from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from .comparator import ComparisonResult, Mismatch
from .config import Config

_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_RESET = "\033[0m"
_BOLD = "\033[1m"


class Reporter:
    def __init__(self, config: Config, use_color: bool = True):
        self.config = config
        self.use_color = use_color

    def render(self, results: list[ComparisonResult]) -> str:
        fmt = self.config.output_format
        if fmt == "json":
            return self._render_json(results)
        if fmt == "junit":
            return self._render_junit(results)
        return self._render_text(results)

    # ------------------------------------------------------------------
    # Text output
    # ------------------------------------------------------------------

    def _render_text(self, results: list[ComparisonResult]) -> str:
        lines: list[str] = []
        for r in results:
            lines.append(self._file_header(r))
            all_mismatches = r.order_mismatches + r.numeric_mismatches
            if not all_mismatches and not r.warnings:
                if self.config.verbose:
                    lines.append("  All checks passed.")
            else:
                for m in r.order_mismatches:
                    lines.append(self._format_mismatch(m))
                for m in r.numeric_mismatches:
                    lines.append(self._format_mismatch(m))
                for w in r.warnings:
                    lines.append(f"  {self._yellow(w)}")
        lines.append("")
        lines.append(self._summary(results))
        return "\n".join(lines)

    def _file_header(self, r: ComparisonResult) -> str:
        status = self._green("PASS") if r.passed else self._red("FAIL")
        return (
            f"{self._bold(status)}  "
            f"{r.baseline_path.name} vs {r.new_path.name}"
        )

    def _format_mismatch(self, m: Mismatch) -> str:
        locs = []
        if m.baseline_lineno is not None:
            locs.append(f"baseline:{m.baseline_lineno}")
        if m.new_lineno is not None:
            locs.append(f"new:{m.new_lineno}")
        loc = ", ".join(locs) if locs else "unknown"
        return f"  [{loc}] {m.detail}"

    def _summary(self, results: list[ComparisonResult]) -> str:
        passed = sum(1 for r in results if r.passed)
        total = len(results)
        overall = "PASS" if passed == total else "FAIL"
        color = self._green if passed == total else self._red
        return color(f"Overall: {overall} — {passed}/{total} file pairs passed")

    # ------------------------------------------------------------------
    # JSON output
    # ------------------------------------------------------------------

    def _render_json(self, results: list[ComparisonResult]) -> str:
        overall = "PASS" if all(r.passed for r in results) else "FAIL"
        payload = {
            "overall": overall,
            "files": [self._result_to_dict(r) for r in results],
        }
        return json.dumps(payload, indent=2)

    def _result_to_dict(self, r: ComparisonResult) -> dict:
        return {
            "baseline": str(r.baseline_path),
            "new": str(r.new_path),
            "result": "PASS" if r.passed else "FAIL",
            "order_mismatches": [self._mismatch_to_dict(m) for m in r.order_mismatches],
            "numeric_mismatches": [self._mismatch_to_dict(m) for m in r.numeric_mismatches],
            "warnings": r.warnings,
        }

    @staticmethod
    def _mismatch_to_dict(m: Mismatch) -> dict:
        return {
            "kind": m.kind,
            "baseline_lineno": m.baseline_lineno,
            "new_lineno": m.new_lineno,
            "detail": m.detail,
        }

    # ------------------------------------------------------------------
    # JUnit XML output
    # ------------------------------------------------------------------

    def _render_junit(self, results: list[ComparisonResult]) -> str:
        suite = ET.Element("testsuite", name="logdiff", tests=str(len(results)))
        for r in results:
            case = ET.SubElement(
                suite, "testcase",
                name=f"{r.baseline_path.name} vs {r.new_path.name}",
                classname="logdiff",
            )
            if not r.passed:
                all_m = r.order_mismatches + r.numeric_mismatches
                failure = ET.SubElement(case, "failure", message="Log comparison failed")
                failure.text = "\n".join(m.detail for m in all_m)
        ET.indent(suite, space="  ")
        return ET.tostring(suite, encoding="unicode")

    # ------------------------------------------------------------------
    # Color helpers
    # ------------------------------------------------------------------

    def _green(self, s: str) -> str:
        return f"{_GREEN}{s}{_RESET}" if self.use_color else s

    def _red(self, s: str) -> str:
        return f"{_RED}{s}{_RESET}" if self.use_color else s

    def _yellow(self, s: str) -> str:
        return f"{_YELLOW}{s}{_RESET}" if self.use_color else s

    def _bold(self, s: str) -> str:
        return f"{_BOLD}{s}{_RESET}" if self.use_color else s
