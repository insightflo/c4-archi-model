#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True
import argparse
from pathlib import Path
from typing import Any

from c4_validation import (
    ValidationReport, aggregate_reports, bundle_reports, load_json, print_report,
    safe_package_path, write_report,
)
import validate_diagram_inputs
import validate_render_receipts

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent


def validate_bundle(
    root: Path, skill_root: Path, data: dict[str, Any] | None,
    data_path: Path | None = None, model_path: Path | None = None,
) -> tuple[dict[str, dict[str, Any] | None], ValidationReport]:
    """Shared pre-render gates; use the report's canonical model unless overridden."""
    explicit_model = model_path is not None
    combined = ValidationReport("c4-artifact-bundle")
    bundle: dict[str, dict[str, Any] | None] = {}
    if data is not None:
        bundle, reports = bundle_reports(root, skill_root, data)
        combined.merge(aggregate_reports("bundle", reports))
    else:
        combined.pass_check("ALL-001", "report-data absent; bundle validation skipped (text fallback allowed)")

    if model_path is None:
        build = data.get("build", {}) if isinstance(data, dict) else {}
        rel = build.get("canonicalModelPath") if isinstance(build, dict) else None
        try:
            model_path = safe_package_path(root, rel) if isinstance(rel, str) and rel else root / "model/architecture-model.json"
        except ValueError as exc:
            combined.error("ALL-002", "$.build.canonicalModelPath", str(exc))
            return bundle, combined
    elif not model_path.is_absolute():
        model_path = root / model_path
    combined.merge(validate_diagram_inputs.run(root, model_path=model_path, skill_root=skill_root))
    # An absent conventional model is valid for text fallback, but an explicit or
    # report-linked model remains authoritative even when missing.
    receipt_model = model_path if explicit_model or model_path.is_file() or data is not None else None
    combined.merge(validate_render_receipts.run(
        root, data_path=data_path, skill_root=skill_root, model_path=receipt_model,
    ))
    return bundle, combined


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all C4 artifact validators before HTML build")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--data", type=Path, help="Report data (default: html/report-data.json, optional for text fallback)")
    parser.add_argument("--model", type=Path, help="Canonical model override (otherwise use report build path)")
    parser.add_argument("--skill-root", type=Path, default=SKILL_ROOT)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    data_path = args.data if args.data is not None else Path("html/report-data.json")
    if not data_path.is_absolute():
        data_path = root / data_path
    try:
        if args.data is not None or data_path.exists():
            data = load_json(data_path)
        else:
            data = None
        _, combined = validate_bundle(root, args.skill_root.resolve(), data,
                                      data_path if data is not None else None, args.model)
    except (OSError, ValueError, RuntimeError) as exc:
        combined = ValidationReport("c4-artifact-bundle")
        combined.error("ALL-001", str(data_path), f"report-data unavailable: {exc}")
    print_report(combined)
    if args.output_json:
        write_report(args.output_json, combined)
    return 1 if combined.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
