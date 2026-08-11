#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True
import argparse
from pathlib import Path
from c4_validation import load_json, print_report, validate_session, write_report

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent

def main() -> int:
    p=argparse.ArgumentParser(description="Validate architecture-session.json")
    p.add_argument("session", type=Path)
    p.add_argument("--model", type=Path)
    p.add_argument("--schema", type=Path, default=SKILL_ROOT/"references/architecture-session.schema.json")
    p.add_argument("--output-json", type=Path)
    a=p.parse_args()
    report=validate_session(load_json(a.session), a.schema, load_json(a.model) if a.model else None)
    print_report(report)
    if a.output_json: write_report(a.output_json, report)
    return 1 if report.errors else 0
if __name__=="__main__": raise SystemExit(main())
