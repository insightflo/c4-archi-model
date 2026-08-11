#!/usr/bin/env python3
"""Create a hash-locked manifest for a generated C4 architecture package."""
from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True
import argparse,json
from pathlib import Path
from c4_validation import sha256_file,utc_now

BANNED_PARTS={".git","__pycache__",".pytest_cache",".mypy_cache"}
BANNED_NAMES={".DS_Store"}
BANNED_SUFFIXES={".pyc",".pyo",".db",".sqlite",".sqlite3"}

def role_for(path: str) -> str:
    if path == "index.html": return "entry-point"
    if path.endswith("architecture-session.json"): return "analysis-session"
    if path.endswith("architecture-model.json"): return "canonical-model"
    if path.endswith("evidence-ledger.json"): return "evidence-ledger"
    if path.endswith("coverage.json"): return "coverage"
    if path.endswith("human-understanding.json"): return "understanding-gate"
    if path.endswith("report-data.json"): return "html-presentation-data"
    if path.endswith("HANDOFF.md"): return "handoff"
    if path.startswith("diagrams/") and path.endswith((".svg",".png")): return "rendered-diagram"
    if path.startswith("diagrams/"): return "diagram-source"
    if path.startswith("qa/"): return "qa"
    if path.startswith("explanation/"): return "explanation"
    return "supporting-artifact"

def main() -> int:
    p=argparse.ArgumentParser(description="Build output manifest with SHA-256 and byte sizes")
    p.add_argument("--root",type=Path,required=True);p.add_argument("--output",type=Path,default=Path("manifest.json"));p.add_argument("--package-id",default="c4-architecture");p.add_argument("--title",default="C4 Architecture Report");p.add_argument("--package-version",default="1.0.0");p.add_argument("--entry-point",default="index.html");p.add_argument("--validation-report",default="qa/package-validation.json")
    a=p.parse_args();root=a.root.resolve();output=a.output if a.output.is_absolute() else root/a.output
    files=[]
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.resolve()==output.resolve(): continue
        rel=path.relative_to(root).as_posix()
        if rel==a.validation_report: continue
        if path.name in BANNED_NAMES or any(part in BANNED_PARTS for part in path.parts) or path.suffix.lower() in BANNED_SUFFIXES:
            raise SystemExit(f"ERROR: banned file in package: {rel}")
        files.append({"path":rel,"role":role_for(rel),"required":True,"sha256":sha256_file(path),"bytes":path.stat().st_size})
    paths={
      "session":"model/architecture-session.json",
      "model":"model/architecture-model.json",
      "evidence":"qa/evidence-ledger.json",
      "coverage":"qa/coverage.json",
      "understanding":"qa/human-understanding.json" if (root/"qa/human-understanding.json").is_file() else None,
      "reportData":"html/report-data.json",
      "handoff":"HANDOFF.md" if (root/"HANDOFF.md").is_file() else None
    }
    manifest={"schemaVersion":"0.4.0","packageId":a.package_id,"title":a.title,"packageVersion":a.package_version,"generatedAt":utc_now(),"entryPoint":a.entry_point,"paths":paths,"files":files,"validation":{"result":"NOT_RUN","validatedAt":None,"validatorVersion":None,"reportPath":a.validation_report}}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Created: {output}");print(f"Files: {len(files)}");return 0
if __name__=="__main__": raise SystemExit(main())
