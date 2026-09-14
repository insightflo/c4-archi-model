#!/usr/bin/env python3
"""Enforce renderer receipts for every diagram input (external review P0-2).

For every archify IR source under ``<root>/diagrams/`` the package must carry, under
``qa/`` (``<root>/../qa`` is also accepted for out-of-tree builds):
  * ``archify-validate-<stem>.json`` — archify ``validate`` receipt recording success
    (JSON with ``ok:true``)
  * ``archify-deliver-<stem>.json``  — archify ``deliver`` receipt: success plus the
    delivered artifact path and its digest (observed v0.8.0 fields: ``output``,
    ``artifact.sha256``, ``artifact.bytes``)
For every ``*.flowmap.json`` source:
  * ``repo-flowmap-validate-<stem>.json`` — validator receipt recording success; the
    observed receipt is the validator stdout text (``[PASS] ...``), a JSON receipt with
    ``ok:true`` is accepted equally
  * ``repo-flowmap-build-<stem>.json`` — builder receipt (JSON) with ``exitCode:0`` and
    the artifact path; observed fields are ``output``/``outputBytes`` — the builder
    records no digest, so the byte size is verified instead
``archify-svg-<stem>.json`` extraction receipts are optional but verified when present.
The recorded artifact is re-hashed / re-measured, so any change made after the receipt
was written is detected. Receipt stems may be a human alias of the source stem
(``01-context`` for ``01-system-context``) and are resolved with the same unique
token-subset matching as view ids.

Checks (documented contract):
  RCP-000  ERROR  invalid validator input (e.g. --data given but unreadable)
  RCP-001  ERROR  required validate receipt is missing for a diagram source
  RCP-002  ERROR  validate receipt records a failure (ok:false / no [PASS])
  RCP-003  ERROR  required deliver/build receipt is missing for a diagram source
  RCP-004  ERROR  deliver/build (or optional svg) receipt records a failure or
                   abnormal exit
  RCP-005  ERROR  recorded artifact digest or size does not match the file on disk
                   (the artifact changed after the receipt was written)
  RCP-006  ERROR  the artifact file a receipt points to does not exist, or the
                   receipt records neither a digest nor a size
  RCP-007  ERROR  a report-data diagram asset is not produced by any known renderer
                   receipt family (archify html/svg, repo-flowmap html) — i.e. a
                   custom renderer, which violates the v0.7.0+ contract
  RCP-008  WARNING  a renderer receipt exists without a matching diagram source
"""
from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True

import argparse
import json
from pathlib import Path
from typing import Any

from c4_validation import ValidationReport, load_json, print_report, sha256_file, write_report
from validate_diagram_inputs import (
    FAMILY_ARCHIFY,
    FAMILY_FLOWMAP,
    alias_match,
    discover_inputs,
    qa_dirs,
)

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent

ARCHIFY_VALIDATE_PREFIX = "archify-validate-"
ARCHIFY_DELIVER_PREFIX = "archify-deliver-"
ARCHIFY_SVG_PREFIX = "archify-svg-"
FLOWMAP_VALIDATE_PREFIX = "repo-flowmap-validate-"
FLOWMAP_BUILD_PREFIX = "repo-flowmap-build-"
ALL_PREFIXES = (ARCHIFY_VALIDATE_PREFIX, ARCHIFY_DELIVER_PREFIX, ARCHIFY_SVG_PREFIX,
                FLOWMAP_VALIDATE_PREFIX, FLOWMAP_BUILD_PREFIX)


def _stem_of(receipt_name: str, prefix: str) -> str:
    return receipt_name[len(prefix):-len(".json")]


def scan_receipts(root: Path) -> dict:
    """Return {prefix: [(stem, path)]} for recognized renderer receipts."""
    index: dict = {prefix: [] for prefix in ALL_PREFIXES}
    for directory in qa_dirs(root):
        for path in sorted(directory.glob("*.json")):
            name = path.name
            for prefix in ALL_PREFIXES:
                if name.startswith(prefix) and name.endswith(".json"):
                    index[prefix].append((_stem_of(name, prefix), path))
                    break
    return index


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _load_receipt(path: Path) -> dict | None:
    try:
        data = json.loads(_read_text(path))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _validate_receipt_ok(path: Path) -> tuple:
    """(ok, detail). Accepts a JSON receipt with ok:true or a [PASS] stdout receipt."""
    text = _read_text(path)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        if "[PASS]" in text and "[FAIL]" not in text:
            return True, ""
        return False, "stdout receipt records no [PASS]"
    if data.get("ok") is True:
        return True, ""
    return False, "receipt records ok=false" if data.get("ok") is False else "receipt records no ok:true"


def _build_receipt_failed(data: dict) -> str | None:
    """Return a failure detail string, or None when the receipt records success."""
    if data.get("ok") is False:
        return "receipt records ok=false"
    exit_code = data.get("exitCode")
    if exit_code is not None and exit_code != 0:
        return f"receipt records exitCode={exit_code}"
    return None


def _resolve_output_candidates(root: Path, output: str) -> list:
    """Candidate artifact paths in priority order. Receipts may record build-time
    absolute paths, so a package that was copied or moved must still verify its own
    artifact: a package-owned file (under root) always wins over the recorded path."""
    candidate = Path(output)
    if candidate.is_absolute():
        candidates = [root / "diagrams" / candidate.name, candidate]
    else:
        candidates = [base / candidate for base in (root, root.parent, Path.cwd())]
    unique: list = []
    seen: set = set()
    for item in candidates:
        key = str(item)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _choose_artifact(root: Path, candidates: list) -> Path | None:
    """Prefer an existing candidate inside the package root, then any existing one."""
    root_resolved = root.resolve()
    existing = [c for c in candidates if c.is_file()]
    for chosen in existing:
        try:
            chosen.resolve().relative_to(root_resolved)
            return chosen
        except ValueError:
            continue
    return existing[0] if existing else None


def _artifact_fields(data: dict) -> tuple:
    artifact = data.get("artifact") if isinstance(data.get("artifact"), dict) else {}
    output = data.get("output")
    digest = artifact.get("sha256") or data.get("svgSha256")
    size = artifact.get("bytes") or data.get("outputBytes") or data.get("svgBytes")
    return output, digest, size


def _verify_artifact(report: ValidationReport, root: Path, receipt_path: Path, data: dict) -> None:
    rel = str(receipt_path)
    output, digest, size = _artifact_fields(data)
    if not isinstance(output, str) or not output.strip():
        report.error("RCP-006", rel, "receipt records no artifact output path")
        return
    candidates = _resolve_output_candidates(root, output)
    artifact = _choose_artifact(root, candidates)
    if artifact is None:
        tried = ", ".join(str(c) for c in candidates)
        report.error("RCP-006", rel, f"artifact does not exist: {output} (tried {tried})")
        return
    if isinstance(digest, str) and digest:
        actual = sha256_file(artifact)
        if actual != digest:
            report.error("RCP-005", rel,
                         f"artifact sha256 mismatch for {artifact.name}: receipt={digest}, actual={actual} "
                         f"(artifact changed after the receipt was written)")
    elif size is not None:
        actual = artifact.stat().st_size
        if actual != size:
            report.error("RCP-005", rel,
                         f"artifact size mismatch for {artifact.name}: receipt={size}, actual={actual} "
                         f"(artifact changed after the receipt was written)")
    else:
        report.error("RCP-006", rel, "receipt records neither an artifact digest nor a size")


def _find_receipt(stem: str, entries: list):
    stems = [candidate for candidate, _ in entries]
    resolved = alias_match(stem, stems)
    if resolved is None:
        return None
    for candidate, path in entries:
        if candidate == resolved:
            return path
    return None


def _check_archify_source(report: ValidationReport, root: Path, stem: str, receipts: dict) -> None:
    validate_receipt = _find_receipt(stem, receipts[ARCHIFY_VALIDATE_PREFIX])
    if validate_receipt is None:
        report.error("RCP-001", f"diagrams/*{stem}*", f"archify validate receipt is missing for stem {stem!r}")
    else:
        ok, detail = _validate_receipt_ok(validate_receipt)
        if not ok:
            report.error("RCP-002", str(validate_receipt), f"archify validate receipt failed: {detail}")

    deliver_receipt = _find_receipt(stem, receipts[ARCHIFY_DELIVER_PREFIX])
    if deliver_receipt is None:
        report.error("RCP-003", f"diagrams/*{stem}*", f"archify deliver receipt is missing for stem {stem!r}")
    else:
        data = _load_receipt(deliver_receipt)
        if data is None:
            report.error("RCP-004", str(deliver_receipt), "deliver receipt is not a JSON object")
        else:
            failure = _build_receipt_failed(data)
            if failure:
                report.error("RCP-004", str(deliver_receipt), f"archify deliver receipt failed: {failure}")
            else:
                _verify_artifact(report, root, deliver_receipt, data)

    svg_receipt = _find_receipt(stem, receipts[ARCHIFY_SVG_PREFIX])
    if svg_receipt is not None:
        data = _load_receipt(svg_receipt)
        if data is None:
            report.error("RCP-004", str(svg_receipt), "svg extraction receipt is not a JSON object")
        elif data.get("ok") is False:
            report.error("RCP-004", str(svg_receipt), "svg extraction receipt records ok=false")
        else:
            _verify_artifact(report, root, svg_receipt, data)


def _check_flowmap_source(report: ValidationReport, root: Path, stem: str, receipts: dict) -> None:
    validate_receipt = _find_receipt(stem, receipts[FLOWMAP_VALIDATE_PREFIX])
    if validate_receipt is None:
        report.error("RCP-001", f"diagrams/*{stem}*", f"repo-flowmap validate receipt is missing for stem {stem!r}")
    else:
        ok, detail = _validate_receipt_ok(validate_receipt)
        if not ok:
            report.error("RCP-002", str(validate_receipt), f"repo-flowmap validate receipt failed: {detail}")

    build_receipt = _find_receipt(stem, receipts[FLOWMAP_BUILD_PREFIX])
    if build_receipt is None:
        report.error("RCP-003", f"diagrams/*{stem}*", f"repo-flowmap build receipt is missing for stem {stem!r}")
    else:
        data = _load_receipt(build_receipt)
        if data is None:
            report.error("RCP-004", str(build_receipt), "build receipt is not a JSON object")
        else:
            failure = _build_receipt_failed(data)
            if failure:
                report.error("RCP-004", str(build_receipt), f"repo-flowmap build receipt failed: {failure}")
            else:
                _verify_artifact(report, root, build_receipt, data)


def _receipts_without_source(report: ValidationReport, sources_by_family: dict, receipts: dict) -> None:
    for prefix, entries in receipts.items():
        family = FAMILY_ARCHIFY if prefix.startswith("archify-") else FAMILY_FLOWMAP
        source_stems = sorted(sources_by_family.get(family, {}))
        for stem, path in entries:
            if alias_match(stem, source_stems) is None:
                report.warning("RCP-008", str(path), f"renderer receipt without a matching diagram source (stem {stem!r})")


def _known_renderer_outputs(root: Path, receipts: dict) -> set:
    """Resolved artifact paths produced by known receipt families (deliver, svg, build)."""
    known: set = set()
    for prefix in (ARCHIFY_DELIVER_PREFIX, ARCHIFY_SVG_PREFIX, FLOWMAP_BUILD_PREFIX):
        for _, path in receipts[prefix]:
            data = _load_receipt(path)
            if data is None:
                continue
            output = data.get("output")
            if not isinstance(output, str) or not output.strip():
                continue
            candidates = _resolve_output_candidates(root, output)
            chosen = _choose_artifact(root, candidates) or candidates[0]
            known.add(str(chosen.resolve()))
    return known


def _check_report_assets(report: ValidationReport, root: Path, data: dict, receipts: dict) -> None:
    diagrams = data.get("diagrams")
    if not isinstance(diagrams, list):
        return
    known = _known_renderer_outputs(root, receipts)
    unattributed: list = []
    for index, diagram in enumerate(diagrams):
        if not isinstance(diagram, dict):
            continue
        asset_path = diagram.get("assetPath")
        if not isinstance(asset_path, str) or not asset_path.strip():
            continue  # dataUri-only or missing assets are validated elsewhere
        candidate = Path(asset_path)
        target = candidate if candidate.is_absolute() else root / candidate
        if str(target.resolve()) not in known:
            unattributed.append(f"diagrams[{index}] {asset_path}")
    if unattributed:
        detail = "; ".join(unattributed[:5])
        report.error("RCP-007", "$.diagrams",
                     f"diagram asset(s) not produced by a known renderer receipt family "
                     f"(custom renderer violates v0.7.0+): {detail}")
    else:
        report.pass_check("RCP-007", "report-data diagram assets map to known renderer receipt families",
                          str(len(known)) + " known artifact(s)")


def run(root: Path, data_path: Path | None = None, skill_root: Path | None = None,
        model_path: Path | None = None) -> ValidationReport:
    """Enforce renderer receipts. `skill_root`/`model_path` are accepted for pipeline
    symmetry with validate_all but intentionally unused here."""
    report = ValidationReport("render-receipts")
    root = Path(root).resolve()
    sources = discover_inputs(root)
    sources_by_family: dict = {FAMILY_ARCHIFY: {}, FAMILY_FLOWMAP: {}}
    for path, family in sources:
        sources_by_family[family][path.name.split(".")[0]] = path
    receipts = scan_receipts(root)

    findings_before = len(report.findings)
    for stem in sorted(sources_by_family[FAMILY_ARCHIFY]):
        _check_archify_source(report, root, stem, receipts)
    for stem in sorted(sources_by_family[FAMILY_FLOWMAP]):
        _check_flowmap_source(report, root, stem, receipts)
    _receipts_without_source(report, sources_by_family, receipts)

    data = None
    if data_path is not None:
        data_path = Path(data_path)
        if data_path.is_file():
            try:
                data = load_json(data_path)
            except (OSError, ValueError, RuntimeError) as exc:
                report.error("RCP-000", str(data_path), f"report-data unreadable: {exc}")
        elif data_path != Path(root / "html/report-data.json"):
            report.error("RCP-000", str(data_path), "report-data explicitly given but missing")
    if data is not None:
        _check_report_assets(report, root, data, receipts)

    if len(report.findings) == findings_before:
        covered = len(sources_by_family[FAMILY_ARCHIFY]) + len(sources_by_family[FAMILY_FLOWMAP])
        report.pass_check("RCP-001", "every diagram source carries passing validate + deliver/build receipts "
                                     "with matching artifacts", f"{covered} source(s)")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce renderer receipts (archify / repo-flowmap) for diagram inputs")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--data", type=Path, default=Path("html/report-data.json"),
                        help="report-data path relative to --root; enables the RCP-007 asset cross-check")
    parser.add_argument("--model", type=Path, default=Path("model/architecture-model.json"),
                        help="accepted for pipeline symmetry; unused")
    parser.add_argument("--skill-root", type=Path, default=SKILL_ROOT)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    data_path = args.data if args.data.is_absolute() else root / args.data
    report = run(root, data_path=data_path, skill_root=args.skill_root.resolve())
    print_report(report)
    if args.output_json:
        write_report(args.output_json, report)
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
