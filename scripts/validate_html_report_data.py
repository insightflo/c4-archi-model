#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True
import argparse
from pathlib import Path
from c4_validation import bundle_reports, aggregate_reports, load_json, print_report, validate_report_data, write_report
SCRIPT_DIR=Path(__file__).resolve().parent; SKILL_ROOT=SCRIPT_DIR.parent

def main() -> int:
    p=argparse.ArgumentParser(description="Validate html/report-data.json and its linked C4 artifacts")
    p.add_argument("--root",type=Path,required=True);p.add_argument("--data",type=Path,required=True);p.add_argument("--skill-root",type=Path,default=SKILL_ROOT)
    p.add_argument("--output-json",type=Path);a=p.parse_args();root=a.root.resolve();data_path=a.data if a.data.is_absolute() else root/a.data
    data=load_json(data_path);_,reports=bundle_reports(root,a.skill_root.resolve(),data);report=aggregate_reports("html-report-bundle",reports)
    print_report(report)
    if a.output_json: write_report(a.output_json,report)
    return 1 if report.errors else 0
if __name__=="__main__": raise SystemExit(main())
