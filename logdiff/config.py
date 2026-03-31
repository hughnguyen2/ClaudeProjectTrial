from __future__ import annotations

import sys
from dataclasses import dataclass, field

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        tomllib = None  # type: ignore[assignment]


@dataclass
class Config:
    tolerance: float = 0.0
    tolerance_pct: float = 0.0
    ignore_timestamps: bool = True
    ignore_order: bool = False
    ignore_numerics: bool = False
    numeric_count_mismatch_is_fail: bool = False
    extra_files_is_fail: bool = False
    exclude_patterns: list[str] = field(default_factory=list)
    output_format: str = "text"
    verbose: bool = False
    fail_fast: bool = False
    pattern: str = "*"

    @classmethod
    def from_toml(cls, path: str) -> "Config":
        if tomllib is None:
            raise RuntimeError(
                "tomllib is not available (Python < 3.11). "
                "Install tomli: pip install tomli"
            )
        with open(path, "rb") as f:
            data = tomllib.load(f)
        section = data.get("logdiff", data)
        return cls(**{k: v for k, v in section.items() if k in cls.__dataclass_fields__})
