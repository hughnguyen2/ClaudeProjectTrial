from __future__ import annotations

import pathlib
import sys
import tempfile

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# Allow running from repo root without installing the package
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from logdiff.comparator import Comparator
from logdiff.config import Config
from logdiff.parser import LogParser
from logdiff.reporter import Reporter

app = FastAPI(title="logdiff", description="Log file comparison tool")

STATIC_DIR = pathlib.Path(__file__).parent / "static"


@app.post("/compare")
async def compare(
    baseline: UploadFile = File(...),
    new: UploadFile = File(...),
    tolerance: float = Form(0.0),
    tolerance_pct: float = Form(0.0),
    ignore_order: bool = Form(False),
    ignore_numerics: bool = Form(False),
    ignore_timestamps: bool = Form(True),
):
    with tempfile.TemporaryDirectory() as tmp:
        b_path = pathlib.Path(tmp) / (baseline.filename or "baseline.log")
        n_path = pathlib.Path(tmp) / (new.filename or "new.log")
        b_path.write_bytes(await baseline.read())
        n_path.write_bytes(await new.read())

        config = Config(
            tolerance=tolerance,
            tolerance_pct=tolerance_pct,
            ignore_order=ignore_order,
            ignore_numerics=ignore_numerics,
            ignore_timestamps=ignore_timestamps,
            output_format="json",
        )
        parser = LogParser(config)
        comparator = Comparator(config)
        reporter = Reporter(config, use_color=False)

        baseline_lines = parser.parse_file(b_path)
        new_lines = parser.parse_file(n_path)
        result = comparator.compare(baseline_lines, new_lines, b_path, n_path)

        payload = reporter._result_to_dict(result)
        payload["baseline_line_count"] = len(baseline_lines)
        payload["new_line_count"] = len(new_lines)
        payload["baseline_filename"] = baseline.filename
        payload["new_filename"] = new.filename
        return JSONResponse(payload)


# Serve the frontend — must be mounted last so /compare route takes priority
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
