#!/usr/bin/env python3
"""Generate a hash-locked manifest for the installable skill package."""
from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True

import argparse
import hashlib
import json
from pathlib import Path

from c4_validation import _matches_forbidden

DEFAULT_REQUIRED = [
    "SKILL.md",
    "VERSION",
    "CHANGELOG.md",
    "manifest.json",
    "assets/architecture-session.template.json",
    "assets/architecture-model.template.json",
    "assets/evidence-ledger.template.json",
    "assets/coverage.template.json",
    "assets/human-understanding.template.json",
    "assets/html-report-data.template.json",
    "assets/html-report-template.html",
    "assets/report-template.md",
    "assets/workspace-template.dsl",
    "assets/output-manifest.template.json",
    "assets/HANDOFF.template.md",
    "references/architecture-session.schema.json",
    "references/architecture-model.schema.json",
    "references/evidence-ledger.schema.json",
    "references/coverage.schema.json",
    "references/human-understanding.schema.json",
    "references/html-report-data.schema.json",
    "references/output-package-manifest.schema.json",
    "references/package-manifest.schema.json",
    "references/analysis-profiles.md",
    "references/c4-model-guide.md",
    "references/evidence-and-model.md",
    "references/source-snapshot.md",
    "references/writing-modes.md",
    "references/human-understanding-gates.md",
    "references/visual-budgets.md",
    "references/renderer-adapters.md",
    "references/html-output-guide.md",
    "references/validation-checklist.md",
    "scripts/c4_validation.py",
    "scripts/schema_runtime.py",
    "scripts/validate_all.py",
    "scripts/validate_architecture_session.py",
    "scripts/validate_architecture_model.py",
    "scripts/validate_evidence_ledger.py",
    "scripts/validate_coverage.py",
    "scripts/validate_human_understanding.py",
    "scripts/validate_html_report_data.py",
    "scripts/validate_html_assets.py",
    "scripts/build_html_report.py",
    "scripts/build_output_manifest.py",
    "scripts/validate_package.py",
    "scripts/generate_manifest.py",
    "scripts/run_regression_tests.py",
    "scripts/validate_skill_package.py",
    "examples/mini-example.md",
    "examples/html-report-data.example.json",
    "examples/html-report-example.html",
    "examples/invalid-fixtures/README.md",
]

DEFAULT_FORBIDDEN = [
    ".git",
    ".DS_Store",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".codegraph",
    "*.pyc",
    "*.pyo",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "*.pre-reconcile",
    "*.bak",
    "*.tmp",
    "*~",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate(root: Path, version: str) -> dict:
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        rel = path.relative_to(root).as_posix()
        # forbidden 패턴(.git/, .DS_Store, __pycache__/, *.pyc 등)은 패키지 자산이 아니므로
        # 해싱 대상에서 제외한다. git 저장소 루트에서 재생성해도 .git 내부가 들어가지 않게 한다.
        if _matches_forbidden(rel, DEFAULT_FORBIDDEN):
            continue
        files.append({"path": rel, "sha256": sha256(path), "size": path.stat().st_size})
    return {
        "$schema": "references/package-manifest.schema.json",
        "schemaVersion": "1.0",
        "packageName": "c4-archi-model",
        "version": version,
        "entrypoint": "SKILL.md",
        "language": "ko",
        "agentIndependent": True,
        "runtime": {
            "python": ">=3.9",
            "externalPackagesRequired": False,
        },
        "requiredFiles": DEFAULT_REQUIRED,
        "forbiddenPatterns": DEFAULT_FORBIDDEN,
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate manifest.json for c4-archi-model")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    manifest = generate(root, version)
    output = args.output.resolve() if args.output else root / "manifest.json"
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Created: {output}")
    print(f"Files hashed: {len(manifest['files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
