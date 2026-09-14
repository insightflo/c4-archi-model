#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True
import argparse
from pathlib import Path
from c4_validation import ValidationReport,aggregate_reports,bundle_reports,load_json,print_report,write_report
import validate_diagram_inputs
import validate_render_receipts
SCRIPT_DIR=Path(__file__).resolve().parent;SKILL_ROOT=SCRIPT_DIR.parent

def main() -> int:
    p=argparse.ArgumentParser(description="Run all C4 artifact validators before HTML build")
    p.add_argument("--root",type=Path,required=True);p.add_argument("--data",type=Path,default=Path("html/report-data.json"));p.add_argument("--model",type=Path,default=Path("model/architecture-model.json"));p.add_argument("--skill-root",type=Path,default=SKILL_ROOT);p.add_argument("--output-json",type=Path)
    a=p.parse_args();root=a.root.resolve()
    data_path=a.data if a.data.is_absolute() else root/a.data
    model_path=a.model if a.model.is_absolute() else root/a.model
    combined=ValidationReport("c4-artifact-bundle")
    data=None
    if data_path.is_file():
        data=load_json(data_path)
        _,reports=bundle_reports(root,a.skill_root.resolve(),data)
        combined.merge(aggregate_reports("bundle",reports))
    else:
        skipped=ValidationReport("validate-all")
        skipped.pass_check("ALL-001","report-data absent; bundle validation skipped (text fallback allowed)",data_path.name)
        combined.merge(skipped)
    if model_path.is_file():
        effective_model=model_path
    elif data is not None:
        rel=data.get("build",{}).get("canonicalModelPath") if isinstance(data.get("build"),dict) else None
        effective_model=(root/rel) if isinstance(rel,str) and rel else None
    else:
        effective_model=None
    combined.merge(validate_diagram_inputs.run(root,model_path=effective_model,skill_root=a.skill_root.resolve()))
    combined.merge(validate_render_receipts.run(root,data_path=data_path if data_path.is_file() else None,skill_root=a.skill_root.resolve()))
    print_report(combined)
    if a.output_json: write_report(a.output_json,combined)
    return 1 if combined.errors else 0
if __name__=="__main__": raise SystemExit(main())
