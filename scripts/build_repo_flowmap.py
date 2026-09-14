#!/usr/bin/env python3
"""Run bundled flowmap validation/build and record input/output hashes at build time.

Paths are relative to --root and must stay inside it. Both qa receipts are replaced
on every attempted run; failure preserves an old HTML but never attributes it as a
new successful output. No mode imports/backfills evidence for an existing artifact.
Requires Python and Node 18+; the vendored renderer/template are not modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

BUNDLE = Path(__file__).resolve().parents[1] / "assets/repo-flowmap"


def write_receipt(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, required=True, help="output package root")
    parser.add_argument("--input", type=Path, required=True, help="diagrams/<view>.flowmap.json")
    parser.add_argument("--output", type=Path, required=True, help="diagrams/<view>.flowmap.html")
    args = parser.parse_args()
    root = args.root.resolve()
    source = (root / args.input).resolve()
    output = (root / args.output).resolve()
    if (source.parent != root / "diagrams" or output.parent != root / "diagrams"
            or not source.name.endswith(".flowmap.json")
            or not output.name.endswith(".flowmap.html") or source == output):
        parser.error("input/output must be distinct diagrams/*.flowmap.json and diagrams/*.flowmap.html inside --root")
    stem = source.name[:-len(".flowmap.json")]
    if not stem or output.name != stem + ".flowmap.html":
        parser.error("input/output must share the same nonempty View stem")
    qa = root / "qa"
    if qa.resolve() != qa:
        parser.error("qa must not be a symlink")
    qa.mkdir(parents=True, exist_ok=True)
    validation_path = qa / f"repo-flowmap-validate-{stem}.json"
    build_path = qa / f"repo-flowmap-build-{stem}.json"
    if validation_path.is_symlink() or build_path.is_symlink():
        parser.error("receipt paths must not be symlinks")
    base = {"input": str(source.relative_to(root)), "output": str(output.relative_to(root))}
    pending = {**base, "ok": False, "message": "run not completed"}
    write_receipt(validation_path, pending)
    write_receipt(build_path, pending)
    stage = "validate"
    try:
        raw = source.read_bytes()
        base["specification"] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        # Validate and build the SAME immutable snapshot, not two reads of mutable IR.
        # Temporary output prevents a failed run from hashing an older delivered HTML.
        with tempfile.TemporaryDirectory(prefix=".flowmap-build-", dir=root) as work:
            snapshot = Path(work) / source.name
            candidate = Path(work) / output.name
            snapshot.write_bytes(raw)
            commands = (
                ("validate", ["node", str(BUNDLE / "scripts/validate_flowmap.mjs"), str(snapshot)], validation_path),
                ("build", ["node", str(BUNDLE / "scripts/build_flowmap.mjs"), str(snapshot),
                           str(BUNDLE / "template.html"), str(candidate)], build_path),
            )
            for stage, command, receipt_path in commands:
                result = subprocess.run(command, capture_output=True, text=True, check=False)
                receipt = {**base, "ok": result.returncode == 0, "exitCode": result.returncode,
                           "stdout": result.stdout, "stderr": result.stderr}
                if result.returncode != 0:
                    write_receipt(receipt_path, receipt)
                    if stage == "validate":
                        write_receipt(build_path, {**base, "ok": False, "message": "validation failed; build not run"})
                    print(result.stderr or result.stdout, file=sys.stderr)
                    return 1
                if stage == "validate":
                    write_receipt(receipt_path, receipt)
            if source.read_bytes() != raw:
                raise ValueError("input changed during build; rerun against the current source")
            artifact = candidate.read_bytes()
            receipt["artifact"] = {"sha256": hashlib.sha256(artifact).hexdigest(), "bytes": len(artifact)}
            candidate.replace(output)
            write_receipt(build_path, receipt)
    except (OSError, ValueError, UnicodeError) as exc:
        failed = {**base, "ok": False, "message": str(exc)}
        if stage == "validate":
            write_receipt(validation_path, failed)
        write_receipt(build_path, failed)
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    print(f"[PASS] {output}; receipts: {qa}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
