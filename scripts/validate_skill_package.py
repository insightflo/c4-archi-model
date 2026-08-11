#!/usr/bin/env python3
"""Validate the installable c4-archi-model skill directory."""
from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True

import argparse
from pathlib import Path

from c4_validation import load_json, print_report, validate_skill_package_manifest, write_report

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the c4-archi-model skill package")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("manifest.json"))
    parser.add_argument(
        "--schema",
        type=Path,
        default=SKILL_ROOT / "references/package-manifest.schema.json",
    )
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
    report = validate_skill_package_manifest(
        root,
        load_json(manifest_path),
        args.schema.resolve(),
        manifest_path,
    )
    print_report(report)
    if args.output_json:
        write_report(args.output_json, report)
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
