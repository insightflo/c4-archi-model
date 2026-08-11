#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True
import argparse,json
from pathlib import Path
from c4_validation import load_json, print_report, utc_now, validate_package_manifest, write_report, VALIDATION_VERSION
SCRIPT_DIR=Path(__file__).resolve().parent;SKILL_ROOT=SCRIPT_DIR.parent

def main() -> int:
    p=argparse.ArgumentParser(description="Validate a generated C4 architecture package")
    p.add_argument("--root",type=Path,required=True);p.add_argument("--manifest",type=Path,default=Path("manifest.json"));p.add_argument("--schema",type=Path,default=SKILL_ROOT/"references/output-package-manifest.schema.json")
    p.add_argument("--output-json",type=Path);p.add_argument("--update-manifest",action="store_true");a=p.parse_args();root=a.root.resolve();manifest_path=a.manifest if a.manifest.is_absolute() else root/a.manifest
    manifest=load_json(manifest_path);report=validate_package_manifest(root,manifest,a.schema,manifest_path)
    if a.output_json: write_report(a.output_json,report)
    if a.update_manifest:
        manifest["validation"]={"result":"PASS" if not report.errors else "FAIL","validatedAt":utc_now(),"validatorVersion":VALIDATION_VERSION,"reportPath":(a.output_json.resolve().relative_to(root).as_posix() if a.output_json and a.output_json.resolve().is_relative_to(root) else None)}
        manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print_report(report);return 1 if report.errors else 0
if __name__=="__main__": raise SystemExit(main())
