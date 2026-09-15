#!/usr/bin/env python3
"""Run the bundled repo-flowmap fork and emit input/output receipts at execution time.

Legacy --input/--output remains supported. --model/--view maps canonical facts to
native flowmap data; all graphics are still drawn by assets/repo-flowmap/template.html.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

BUNDLE = Path(__file__).resolve().parents[1] / "assets/repo-flowmap"
SKILL = BUNDLE.parents[1]


def assert_distinct_paths(reads: dict[str, Path], writes: dict[str, Path]) -> None:
    """Preflight BEFORE mkdir/receipt invalidation/write, including symlinks/hardlinks.

    Does not claim race-free protection against a hostile concurrent filesystem actor.
    Every planned output is distinct from every input and every other output.
    """
    def same(a: Path, b: Path) -> bool:
        if a.resolve() == b.resolve():
            return True
        return a.exists() and b.exists() and a.samefile(b)
    for name, dest in writes.items():
        if dest.exists() and not dest.is_file():
            raise ValueError(f"output {name} is not a regular file: {dest}")
        if dest.is_symlink():
            raise ValueError(f"path collision/alias: output {name} is a symlink: {dest}")
        for srcname, src in reads.items():
            if same(src, dest) or src.resolve().is_relative_to(dest.resolve()):
                raise ValueError(f"path collision: input {srcname} and output {name}: {dest}")
        for other, path in writes.items():
            if name != other and same(path, dest):
                raise ValueError(f"path collision: outputs {name} and {other}: {dest}")


def write_receipt(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--input", type=Path, help="diagrams/<stem>.flowmap.json (optional with --model/--view)")
    parser.add_argument("--output", type=Path, help="diagrams/<stem>.flowmap.html")
    parser.add_argument("--model", type=Path, help="canonical model inside --root; map, do not render externally")
    parser.add_argument("--view", help="exact canonical View ID")
    parser.add_argument("--ledger", type=Path, default=Path("qa/evidence-ledger.json"))
    args = parser.parse_args()
    root = args.root.resolve()
    if bool(args.model) != bool(args.view):
        parser.error("--model and --view must be supplied together")
    if args.view and (not args.view or any(c in args.view for c in '/\\') or args.view in {'.', '..'}):
        parser.error("View ID is not a safe file stem")
    if not args.model and (args.input is None or args.output is None):
        parser.error("legacy mode requires --input and --output")
    source = root / (args.input or Path("diagrams") / (args.view + ".flowmap.json"))
    output = root / (args.output or Path("diagrams") / (args.view + ".flowmap.html"))
    stem = source.name[:-len(".flowmap.json")] if source.name.endswith(".flowmap.json") else ""
    qa = root / "qa"
    validation_path = qa / f"repo-flowmap-validate-{stem}.json"
    build_path = qa / f"repo-flowmap-build-{stem}.json"
    model_path = root / args.model if args.model else None
    ledger_path = root / args.ledger
    # All static preflight precedes even failed-receipt writes.
    try:
        for path in (source, output):
            if path.parent.resolve() != root / "diagrams" or path.parent != root / "diagrams":
                raise ValueError("input/output must be directly inside the non-symlink diagrams/ directory")
        if not stem or output.name != stem + ".flowmap.html":
            raise ValueError("input/output require the same nonempty .flowmap.json/.flowmap.html stem")
        if qa.resolve() != qa:
            raise ValueError("qa must not be a symlink")
        reads = {"template": BUNDLE / "template.html", "native-build": BUNDLE / "scripts/build_flowmap.mjs",
                 "native-validator": BUNDLE / "scripts/validate_flowmap.mjs"}
        writes = {"HTML": output, "validate receipt": validation_path, "build receipt": build_path}
        if model_path is not None:
            if not model_path.resolve().is_relative_to(root) or not ledger_path.resolve().is_relative_to(root):
                raise ValueError("canonical model and ledger must stay inside --root")
            reads.update(model=model_path, ledger=ledger_path)
            writes["derived input"] = source
        else:
            reads["input"] = source
            try:
                predata = json.loads(source.read_bytes())
            except (OSError, ValueError):
                predata = None
            if isinstance(predata, dict) and isinstance(predata.get("c4"), dict):
                rel = predata["c4"].get("modelPath")
                if not isinstance(rel, str) or not rel:
                    raise ValueError("typed input requires a canonical modelPath")
                reads["canonical"] = root / rel
                reads["ledger"] = ledger_path
                if not reads["canonical"].resolve().is_relative_to(root):
                    raise ValueError("canonical modelPath escapes --root")
        assert_distinct_paths(reads, writes)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    # Path conflicts leave ALL inputs/outputs untouched. Other run failures invalidate
    # receipts, so an older output cannot masquerade as a new successful render.
    qa.mkdir(parents=True, exist_ok=True)
    base = {"input": source.relative_to(root).as_posix(), "output": output.relative_to(root).as_posix()}
    pending = {**base, "ok": False, "message": "run not completed"}
    write_receipt(validation_path, pending)
    write_receipt(build_path, pending)
    stage = "validate"
    model_raw = ledger_raw = None
    try:
        if model_path is not None:
            from repo_flowmap_adapter import project
            from c4_validation import validate_model, validate_ledger
            model_raw = model_path.read_bytes()
            ledger_raw = ledger_path.read_bytes()
            model, ledger = json.loads(model_raw), json.loads(ledger_raw)
            report = validate_model(model, SKILL / "references/architecture-model.schema.json", ledger)
            report.merge(validate_ledger(ledger, SKILL / "references/evidence-ledger.schema.json", model))
            if report.errors:
                raise ValueError("canonical/evidence validation failed: " + "; ".join(f.message for f in report.errors))
            mapped = project(model, model_path.resolve().relative_to(root).as_posix(),
                             hashlib.sha256(model_raw).hexdigest(), args.view)
            raw = (json.dumps(mapped, ensure_ascii=False, indent=2) + "\n").encode()
        else:
            raw = source.read_bytes()
            mapped = json.loads(raw)
        if "c4" in mapped:
            from repo_flowmap_adapter import implementation_hash, project
            from c4_validation import validate_model, validate_ledger
            # Existing typed input must be checked too; do not trust an adapter stamp.
            c4 = mapped["c4"]
            if not isinstance(c4, dict):
                raise ValueError("c4 must be an object")
            actual_model = (root / c4["modelPath"]).resolve()
            if not actual_model.is_relative_to(root):
                raise ValueError("c4 modelPath escapes --root")
            if model_path is None:
                # Additional inputs discovered in legacy mode are still checked before
                # any artifact write (receipts have already been invalidated).
                assert_distinct_paths({"canonical": actual_model}, {"HTML": output, "validate": validation_path, "build": build_path})
            current = actual_model.read_bytes()
            from validate_diagram_inputs import resolve_view
            if resolve_view(stem, [v["id"] for v in json.loads(current)["views"]]) != c4["viewId"]:
                raise ValueError("source filename/View association does not match the exact typed View")
            if model_path is None:
                ledger_raw = ledger_path.read_bytes()
                typed_model, typed_ledger = json.loads(current), json.loads(ledger_raw)
                checks = validate_model(typed_model, SKILL / "references/architecture-model.schema.json", typed_ledger)
                checks.merge(validate_ledger(typed_ledger, SKILL / "references/evidence-ledger.schema.json", typed_model))
                if checks.errors:
                    raise ValueError("canonical/evidence validation failed: " + "; ".join(f.message for f in checks.errors))
            expected = project(json.loads(current), actual_model.relative_to(root).as_posix(),
                               hashlib.sha256(current).hexdigest(), c4["viewId"])
            if expected != mapped:
                raise ValueError("DIA-008: typed flowmap does not equal the current canonical projection")
            base.update(viewId=c4["viewId"], renderer="repo-flowmap", forkVersion=1,
                        rendererSha256=implementation_hash(BUNDLE))
        base["specification"] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
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
                if result.returncode:
                    write_receipt(receipt_path, receipt)
                    if stage == "validate":
                        write_receipt(build_path, {**base, "ok": False, "message": "validation failed; build not run"})
                    print(result.stderr or result.stdout, file=sys.stderr)
                    return 1
                if stage == "validate":
                    write_receipt(receipt_path, receipt)
            if model_path is not None:
                if model_path.read_bytes() != model_raw or ledger_path.read_bytes() != ledger_raw:
                    raise ValueError("model/ledger changed during build")
            elif source.read_bytes() != raw:
                raise ValueError("input changed during build; rerun against current source")
            if "c4" in mapped and (actual_model.read_bytes() != current or ledger_path.read_bytes() != ledger_raw):
                raise ValueError("canonical model changed during build")
            artifact = candidate.read_bytes()
            receipt["artifact"] = {"sha256": hashlib.sha256(artifact).hexdigest(), "bytes": len(artifact)}
            source.parent.mkdir(parents=True, exist_ok=True)
            if model_path is not None:
                derived = Path(work) / "derived-final.json"
                derived.write_bytes(raw)
                derived.replace(source)
            candidate.replace(output)
            write_receipt(build_path, receipt)
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, RuntimeError) as exc:
        failed = {**base, "ok": False, "message": str(exc)}
        if stage == "validate":
            write_receipt(validation_path, failed)
        write_receipt(build_path, failed)
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    print(f"[PASS] {output}; native repo-flowmap receipts: {qa}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
