from logdiff.config import Config
from logdiff.parser import LogParser


def make_parser(**kwargs) -> LogParser:
    return LogParser(Config(**kwargs))


def test_strips_iso_timestamp():
    parser = make_parser()
    line = parser._parse_line("2026-03-31 10:00:01 INFO  Hello world", 1)
    assert line is not None
    assert line.timestamp == "2026-03-31 10:00:01"
    assert line.level == "INFO"
    assert line.message == "Hello world"


def test_extracts_numerics():
    parser = make_parser()
    line = parser._parse_line("2026-01-01 10:00:00 INFO  size=100 latency=1.23s", 1)
    assert line is not None
    values = [t.value for t in line.numerics]
    assert 100.0 in values
    assert 1.23 in values


def test_numeric_labels():
    parser = make_parser()
    line = parser._parse_line("INFO  size=100", 1)
    assert line is not None
    labeled = {t.label: t.value for t in line.numerics if t.label}
    assert labeled.get("size") == 100.0


def test_blank_lines_skipped():
    parser = make_parser()
    assert parser._parse_line("", 1) is None
    assert parser._parse_line("   ", 1) is None


def test_separator_lines_skipped():
    parser = make_parser()
    assert parser._parse_line("---", 1) is None
    assert parser._parse_line("===", 1) is None


def test_no_timestamp_stripping():
    parser = make_parser(ignore_timestamps=False)
    line = parser._parse_line("2026-03-31 10:00:01 INFO  Hello world", 1)
    assert line is not None
    assert line.timestamp is None
    assert "2026" in line.message


def test_exclude_pattern():
    parser = make_parser(exclude_patterns=[r"DEBUG"])
    line = parser._parse_line("2026-01-01 00:00:00 DEBUG some noise", 1)
    assert line is None
