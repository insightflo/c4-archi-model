#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True
import argparse
from pathlib import Path
from c4_validation import ValidationReport, print_report, validate_html_text, validate_svg, write_report

def main() -> int:
    p=argparse.ArgumentParser(description="Validate an offline HTML report and optional SVG assets")
    p.add_argument("html",type=Path);p.add_argument("--svg",type=Path,action="append",default=[]);p.add_argument("--output-json",type=Path);a=p.parse_args()
    report=ValidationReport("html-assets")
    report.merge(validate_html_text(a.html.read_text(encoding="utf-8",errors="replace"),a.html.name))
    for path in a.svg: report.merge(validate_svg(path))
    print_report(report)
    if a.output_json: write_report(a.output_json,report)
    return 1 if report.errors else 0
if __name__=="__main__": raise SystemExit(main())
