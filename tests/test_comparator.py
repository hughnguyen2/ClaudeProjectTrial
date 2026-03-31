from pathlib import Path

from logdiff.comparator import Comparator
from logdiff.config import Config
from logdiff.parser import LogParser

BASELINE = Path("baseline.log")
NEW = Path("new.log")


def parse_lines(text: str, **config_kwargs) -> list:
    config = Config(**config_kwargs)
    parser = LogParser(config)
    lines = []
    for i, raw in enumerate(text.strip().splitlines(), start=1):
        line = parser._parse_line(raw, i)
        if line is not None:
            lines.append(line)
    return lines


def compare(baseline_text: str, new_text: str, **config_kwargs):
    config = Config(**config_kwargs)
    parser = LogParser(config)
    comparator = Comparator(config)

    baseline = [
        parser._parse_line(raw, i)
        for i, raw in enumerate(baseline_text.strip().splitlines(), 1)
        if parser._parse_line(raw, i) is not None
    ]
    baseline = [l for l in baseline if l]

    new = [
        parser._parse_line(raw, i)
        for i, raw in enumerate(new_text.strip().splitlines(), 1)
        if parser._parse_line(raw, i) is not None
    ]
    new = [l for l in new if l]

    return comparator.compare(baseline, new, BASELINE, NEW)


class TestOrderComparison:
    def test_identical_messages_pass(self):
        log = "INFO  message one\nINFO  message two\n"
        result = compare(log, log)
        assert result.passed

    def test_reordered_messages_fail(self):
        baseline = "INFO  step one\nINFO  step two\n"
        new = "INFO  step two\nINFO  step one\n"
        result = compare(baseline, new)
        assert not result.passed
        assert result.order_mismatches

    def test_missing_message_fails(self):
        baseline = "INFO  step one\nINFO  step two\n"
        new = "INFO  step one\n"
        result = compare(baseline, new)
        assert not result.passed

    def test_extra_message_fails(self):
        baseline = "INFO  step one\n"
        new = "INFO  step one\nINFO  extra step\n"
        result = compare(baseline, new)
        assert not result.passed

    def test_ignore_order_skips_check(self):
        baseline = "INFO  step one\nINFO  step two\n"
        new = "INFO  step two\nINFO  step one\n"
        result = compare(baseline, new, ignore_order=True)
        assert result.order_mismatches == []


class TestNumericComparison:
    def test_exact_match_passes(self):
        log = "INFO  latency=1.23s errors=0\n"
        result = compare(log, log)
        assert result.passed

    def test_value_difference_fails(self):
        baseline = "INFO  latency=1.23s\n"
        new = "INFO  latency=1.50s\n"
        result = compare(baseline, new, tolerance=0.1)
        assert not result.passed
        assert result.numeric_mismatches

    def test_within_tolerance_passes(self):
        baseline = "INFO  latency=1.23s\n"
        new = "INFO  latency=1.28s\n"
        result = compare(baseline, new, tolerance=0.1)
        assert result.passed

    def test_percentage_tolerance(self):
        baseline = "INFO  value=100\n"
        new = "INFO  value=104\n"
        result = compare(baseline, new, tolerance_pct=0.05)
        assert result.passed

    def test_percentage_tolerance_fail(self):
        baseline = "INFO  value=100\n"
        new = "INFO  value=110\n"
        result = compare(baseline, new, tolerance_pct=0.05)
        assert not result.passed

    def test_ignore_numerics_skips_check(self):
        baseline = "INFO  value=100\n"
        new = "INFO  value=999\n"
        result = compare(baseline, new, ignore_numerics=True)
        assert result.numeric_mismatches == []


class TestFixtureFiles:
    def test_fixture_files_pass_with_tolerance(self):
        baseline_path = Path(__file__).parent / "fixtures" / "baseline" / "app.log"
        new_path = Path(__file__).parent / "fixtures" / "new" / "app.log"
        config = Config(tolerance_pct=0.10)  # 10% tolerance covers all diffs in fixture files
        parser = LogParser(config)
        comparator = Comparator(config)
        baseline = parser.parse_file(baseline_path)
        new = parser.parse_file(new_path)
        result = comparator.compare(baseline, new, baseline_path, new_path)
        assert result.passed

    def test_fixture_files_fail_with_strict_tolerance(self):
        baseline_path = Path(__file__).parent / "fixtures" / "baseline" / "app.log"
        new_path = Path(__file__).parent / "fixtures" / "new" / "app.log"
        config = Config(tolerance=0.0)
        parser = LogParser(config)
        comparator = Comparator(config)
        baseline = parser.parse_file(baseline_path)
        new = parser.parse_file(new_path)
        result = comparator.compare(baseline, new, baseline_path, new_path)
        assert not result.passed
