from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .comparator import Comparator
from .config import Config
from .parser import LogParser
from .reporter import Reporter


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="logdiff",
        description="Compare log files for message order and numeric value differences.",
    )
    parser.add_argument("baseline", help="Baseline directory or file")
    parser.add_argument("new", help="New directory or file to compare against baseline")
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.0,
        metavar="FLOAT",
        help="Absolute numeric tolerance (default: 0.0 — exact match)",
    )
    parser.add_argument(
        "--tolerance-pct",
        type=float,
        default=0.0,
        metavar="PCT",
        help="Percentage tolerance, e.g. 0.05 for 5%%",
    )
    parser.add_argument(
        "--pattern",
        default="*",
        metavar="GLOB",
        help="Filename glob when comparing directories (default: *)",
    )
    parser.add_argument(
        "--ignore-order",
        action="store_true",
        help="Skip message order comparison",
    )
    parser.add_argument(
        "--ignore-numerics",
        action="store_true",
        help="Skip numeric value comparison",
    )
    parser.add_argument(
        "--no-ignore-timestamps",
        action="store_true",
        help="Do not strip timestamps before comparing messages",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json", "junit"],
        default="text",
        dest="output_format",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        help="Path to logdiff.toml config file",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show matched lines even on passing files",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first failing file pair",
    )
    return parser.parse_args(argv)


def build_config(args: argparse.Namespace) -> Config:
    if args.config:
        config = Config.from_toml(args.config)
    else:
        config = Config()

    # CLI flags override config file
    config.tolerance = args.tolerance
    config.tolerance_pct = args.tolerance_pct
    config.ignore_order = args.ignore_order
    config.ignore_numerics = args.ignore_numerics
    config.ignore_timestamps = not args.no_ignore_timestamps
    config.output_format = args.output_format
    config.verbose = args.verbose
    config.fail_fast = args.fail_fast
    config.pattern = args.pattern
    return config


def resolve_pairs(baseline_arg: str, new_arg: str, pattern: str) -> list[tuple[Path, Path]]:
    baseline = Path(baseline_arg)
    new = Path(new_arg)

    if not baseline.exists():
        raise FileNotFoundError(f"Baseline path does not exist: {baseline}")
    if not new.exists():
        raise FileNotFoundError(f"New path does not exist: {new}")

    if baseline.is_file() and new.is_file():
        return [(baseline, new)]

    if baseline.is_file() and new.is_dir():
        candidate = new / baseline.name
        if not candidate.exists():
            raise FileNotFoundError(f"No matching file in new dir: {candidate}")
        return [(baseline, candidate)]

    if baseline.is_dir() and new.is_file():
        candidate = baseline / new.name
        if not candidate.exists():
            raise FileNotFoundError(f"No matching file in baseline dir: {candidate}")
        return [(candidate, new)]

    # Both directories
    pairs: list[tuple[Path, Path]] = []
    baseline_files = {f.name: f for f in baseline.glob(pattern) if f.is_file()}
    new_files = {f.name: f for f in new.glob(pattern) if f.is_file()}

    for name, b_file in sorted(baseline_files.items()):
        if name in new_files:
            pairs.append((b_file, new_files[name]))
        else:
            print(f"WARNING: {name} found in baseline but not in new directory — treating as FAIL")
            pairs.append((b_file, Path("/dev/null")))  # will fail gracefully

    for name in sorted(new_files):
        if name not in baseline_files:
            print(f"WARNING: {name} found in new directory but not in baseline — skipping")

    if not pairs:
        raise RuntimeError(
            f"No matching files found between '{baseline}' and '{new}' (pattern: {pattern!r})"
        )

    return pairs


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    config = build_config(args)

    try:
        file_pairs = resolve_pairs(args.baseline, args.new, config.pattern)
    except (FileNotFoundError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    log_parser = LogParser(config)
    comparator = Comparator(config)
    use_color = config.output_format == "text" and sys.stdout.isatty()
    reporter = Reporter(config, use_color=use_color)

    results = []
    for b_path, n_path in file_pairs:
        try:
            baseline_lines = log_parser.parse_file(b_path)
            new_lines = log_parser.parse_file(n_path)
        except OSError as e:
            print(f"ERROR reading files: {e}", file=sys.stderr)
            sys.exit(2)

        result = comparator.compare(baseline_lines, new_lines, b_path, n_path)
        results.append(result)

        if config.fail_fast and not result.passed:
            break

    print(reporter.render(results))
    sys.exit(0 if all(r.passed for r in results) else 1)
