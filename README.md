# logdiff

A Python CLI tool that compares baseline log/text files against new log/text files to determine if a test has **passed** or **failed**.

Two checks run on each file pair:
- **Message order** — verifies messages appear in the same sequence (insertions, deletions, and reorderings are flagged)
- **Numeric values** — compares every number in aligned log lines, with configurable absolute or percentage tolerance

## Project Structure

```
logdiff/            # Core comparison package
  cli.py            # CLI entry point
  comparator.py     # Order + numeric comparison logic
  parser.py         # Log line parsing and numeric extraction
  reporter.py       # Pass/fail output (text, JSON, JUnit XML)
  config.py         # Config dataclass

web/                # Web application
  app.py            # FastAPI backend
  static/
    index.html      # Drag-and-drop UI
    style.css
    app.js

tests/
  fixtures/
    baseline/       # Example baseline log files
    new/            # Example new log files to compare
  test_comparator.py
  test_parser.py

requirements.txt    # Web app dependencies
start.sh            # One-command local server launcher
pyproject.toml
```

## Web Application (local GUI)

### Quickstart

```bash
./start.sh
```

Then open **http://localhost:8000** in your browser.

The script automatically creates a virtual environment, installs dependencies, and starts the server. Use Ctrl+C to stop.

### What you can do in the UI

- **Drag and drop** a baseline file onto the left zone and a new file onto the right zone (or click to browse)
- Set numeric **tolerance** (absolute or percentage)
- Toggle **ignore order** or **ignore numerics** checks
- Click **Compare files** to see a colour-coded PASS/FAIL result with per-mismatch details

### Manual start (if you prefer)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn web.app:app --reload
```

## Requirements

- Python 3.9+
- No mandatory third-party dependencies (stdlib only)

## Installation

```bash
# Install in development mode (pip >= 22 required)
pip install -e ".[dev]"

# Or run directly without installing
PYTHONPATH=. python3 -m logdiff <baseline> <new>
```

## Usage

```
python3 -m logdiff BASELINE NEW [options]
```

### Arguments

| Argument | Description |
|---|---|
| `BASELINE` | Baseline directory or file (the expected/reference output) |
| `NEW` | New directory or file to compare against the baseline |

### Options

| Option | Description |
|---|---|
| `--tolerance FLOAT` | Absolute numeric tolerance (default: `0.0` — exact match) |
| `--tolerance-pct PCT` | Percentage tolerance, e.g. `0.05` for 5% |
| `--pattern GLOB` | Filename glob when comparing directories (default: `*`) |
| `--ignore-order` | Skip message order comparison |
| `--ignore-numerics` | Skip numeric value comparison |
| `--no-ignore-timestamps` | Include timestamps when comparing messages |
| `--output {text,json,junit}` | Output format (default: `text`) |
| `--config FILE` | Path to `logdiff.toml` config file |
| `--verbose` | Show matched lines even on passing files |
| `--fail-fast` | Stop after the first failing file pair |

## Examples

### Compare two directories with 5% numeric tolerance

```bash
python3 -m logdiff tests/fixtures/baseline tests/fixtures/new --tolerance-pct 0.05
```

```
PASS  app.log vs app.log

Overall: PASS — 1/1 file pairs passed
```

### Compare with exact match (shows failures)

```bash
python3 -m logdiff tests/fixtures/baseline tests/fixtures/new
```

```
FAIL  app.log vs app.log
  [baseline:4, new:4] numeric mismatch : expected 1.23 got 1.31 (diff=0.08, tolerance=0.0)
    context: 'pleted in 1.23s with err'
  [baseline:5, new:5] numeric mismatch (usage): expected 512.0 got 520.0 (diff=8, tolerance=0.0)
    context: 'ory usage=512 MB, cpu=4'
  [baseline:5, new:5] numeric mismatch (cpu): expected 45.2 got 47.1 (diff=1.9, tolerance=0.0)
    context: '2 MB, cpu=45.2%'

Overall: FAIL — 0/1 file pairs passed
```

### JSON output for CI integration

```bash
python3 -m logdiff baseline/ new/ --tolerance 0.1 --output json
```

### Check only message order (ignore numeric values)

```bash
python3 -m logdiff baseline/ new/ --ignore-numerics
```

### Use in a shell script or CI pipeline

```bash
python3 -m logdiff baseline/ new/ --tolerance-pct 0.05
if [ $? -eq 0 ]; then
  echo "Tests passed"
else
  echo "Tests failed"
fi
```

The exit code is `0` on overall PASS, `1` on any failure, `2` on usage/file errors.

## Config File

You can store defaults in a `logdiff.toml` file:

```toml
[logdiff]
tolerance_pct = 0.05
ignore_timestamps = true
output_format = "text"
exclude_patterns = ["^DEBUG"]
```

Then run:

```bash
python3 -m logdiff baseline/ new/ --config logdiff.toml
```

## How It Works

### Timestamp stripping

Timestamps are stripped from lines before comparison (enabled by default). This prevents wall-clock differences between runs from being flagged as mismatches.

Supported formats: ISO 8601, syslog, epoch, and time-only.

### Message order comparison

Messages are normalised by replacing all numbers with `<N>` before the order diff. This ensures lines like `Completed in 1.23s` and `Completed in 1.31s` are treated as the same message template (and their numeric difference is handled by the numeric comparator), rather than flagged as an order change.

Diffing uses Python's `difflib.SequenceMatcher` (longest common subsequence), so inserted debug lines do not cause false order failures.

### Numeric comparison

Every number in each aligned log line is extracted and compared. Numbers can optionally be matched by label (e.g. `latency=1.23` — the label `latency` is captured alongside the value).

Tolerance modes:
- **Absolute** (`--tolerance`): `|new - baseline| <= tolerance`
- **Percentage** (`--tolerance-pct`): `|new - baseline| / |baseline| <= pct`

## Running Tests

```bash
PYTHONPATH=. python3 -m pytest tests/ -v
```
