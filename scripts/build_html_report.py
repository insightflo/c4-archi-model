#!/usr/bin/env python3
"""Build a self-contained C4 architecture HTML report from validated artifacts.

The builder validates the full linked artifact bundle before rendering. In
strict mode, schema, semantic, evidence, coverage, and canonical/presentation
alignment errors stop the build. In lenient mode, a diagnostic HTML is created
with an explicit FAIL banner and exit code 2.
"""
from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True

import argparse
import base64
import copy
import json
import mimetypes
import re
import sys
from pathlib import Path
from typing import Any, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from c4_validation import (
    ValidationReport,
    aggregate_reports,
    bundle_reports,
    load_json,
    print_report,
    safe_package_path,
    validate_html_text,
    validate_svg,
    write_report,
)

TOKEN = "__REPORT_DATA_JSON__"
TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".json", ".yaml", ".yml", ".toml", ".xml", ".html", ".htm",
    ".css", ".js", ".ts", ".tsx", ".jsx", ".py", ".java", ".kt", ".go", ".rs", ".c", ".h",
    ".cpp", ".hpp", ".cs", ".rb", ".php", ".sql", ".graphql", ".gql", ".puml", ".plantuml",
    ".dsl", ".mmd", ".mermaid", ".dot", ".d2", ".csv", ".tsv", ".log",
}


class BuildError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a validated, self-contained C4 HTML report")
    parser.add_argument("--root", type=Path, required=True, help="Generated C4 package root")
    parser.add_argument("--data", type=Path, required=True, help="html/report-data.json path")
    parser.add_argument("--template", type=Path, required=True, help="HTML template path")
    parser.add_argument("--output", type=Path, required=True, help="Output index.html path")
    parser.add_argument("--skill-root", type=Path, default=SCRIPT_DIR.parent,
                        help="c4-archi-model skill root containing references/")
    parser.add_argument("--validation-output", type=Path,
                        help="Optional JSON validation report path")
    parser.add_argument("--lenient", action="store_true",
                        help="Create a diagnostic FAIL HTML instead of stopping on validation errors")
    parser.add_argument("--max-embed-mb", type=float, default=8.0,
                        help="Maximum size for each embedded file, default 8 MiB")
    return parser.parse_args()


def resolve(root: Path, value: Path) -> Path:
    return value if value.is_absolute() else root / value


def guess_mime(path: Path, declared: str | None = None) -> str:
    if declared:
        return declared
    mime, _ = mimetypes.guess_type(path.name)
    if mime:
        return mime
    if path.suffix.lower() == ".svg":
        return "image/svg+xml"
    return "application/octet-stream"


def data_uri(path: Path, declared_mime: str | None, max_bytes: int) -> str:
    raw = path.read_bytes()
    if len(raw) > max_bytes:
        raise BuildError(f"file exceeds embed limit ({len(raw)} > {max_bytes} bytes): {path}")
    mime = guess_mime(path, declared_mime)
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def is_text_file(path: Path, mime: str) -> bool:
    return mime.startswith("text/") or path.suffix.lower() in TEXT_EXTENSIONS or mime in {
        "application/json", "application/xml", "application/yaml"
    }


def claim_map(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in ledger.get("claims", []) if isinstance(item, dict)}


def source_ids_for_claims(claims: dict[str, dict[str, Any]], claim_ids: Iterable[str]) -> list[str]:
    found: set[str] = set()
    for claim_id in claim_ids:
        claim = claims.get(claim_id)
        if not claim:
            continue
        for key in ("supports", "contradictions"):
            for item in claim.get(key, []):
                source_id = item.get("sourceId") if isinstance(item, dict) else None
                if isinstance(source_id, str):
                    found.add(source_id)
    return sorted(found)


def canonical_name(item_id: str | None, elements: dict[str, dict[str, Any]],
                   relationships: dict[str, dict[str, Any]], views: dict[str, dict[str, Any]]) -> str:
    if item_id in elements:
        return elements[item_id]["name"]
    if item_id in relationships:
        rel = relationships[item_id]
        return f"{elements.get(rel['sourceId'], {}).get('name', rel['sourceId'])} → " \
               f"{elements.get(rel['destinationId'], {}).get('name', rel['destinationId'])}: {rel['description']}"
    if item_id in views:
        return views[item_id]["title"]
    return item_id or ""


def coverage_items(coverage: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    items: dict[str, dict[str, Any]] = {}
    kinds: dict[str, str] = {}
    labels = {
        "explored": "확인한 영역",
        "unknownRelevant": "현재 질문에 관련된 미확인",
        "unknownOutOfScope": "현재 범위 밖의 미확인",
        "expansionPoints": "다음 확대 후보",
        "boundaries": "분석 경계",
        "boundaries": "분석 경계",
    }
    for key, label in labels.items():
        for item in coverage.get(key, []):
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                items[item["id"]] = item
                kinds[item["id"]] = label
    return items, kinds


def hydrate_report(data: dict[str, Any], bundle: dict[str, dict[str, Any] | None],
                   validation: ValidationReport) -> dict[str, Any]:
    hydrated = copy.deepcopy(data)
    session = bundle["session"] or {}
    model = bundle["model"] or {}
    ledger = bundle["ledger"] or {"sources": [], "claims": []}
    coverage = bundle["coverage"] or {"completion": {"result": "NOT_RUN", "reason": "Coverage not available"}}
    understanding = bundle["understanding"]

    elements = {item["id"]: item for item in model.get("elements", []) if isinstance(item, dict)}
    relationships = {item["id"]: item for item in model.get("relationships", []) if isinstance(item, dict)}
    views = {item["id"]: item for item in model.get("views", []) if isinstance(item, dict)}
    claims = claim_map(ledger)
    issues, issue_kinds = coverage_items(coverage)

    model_meta = model.get("metadata", {})
    report_meta = hydrated.setdefault("meta", {})
    report_meta.update({
        "title": report_meta.get("titleOverride") or model_meta.get("title") or "C4 Architecture Report",
        "mode": session.get("audienceMode", "beginner"),
        "analysisProfile": session.get("analysisProfile", "guided"),
        "modelVersion": model_meta.get("modelRevision", "unknown"),
        "scope": " · ".join(session.get("inScope", [])) or model_meta.get("description") or "Scope not recorded",
        "question": session.get("question", ""),
        "purpose": session.get("purpose", ""),
        "completionResult": coverage.get("completion", {}).get("result", "NOT_RUN"),
        "completionReason": coverage.get("completion", {}).get("reason", ""),
    })

    for diagram in hydrated.get("diagrams", []):
        view = views.get(diagram["viewId"], {})
        presentation = diagram.pop("presentation", {})
        diagram.update({
            "title": view.get("title", diagram["viewId"]),
            "type": view.get("type", "unknown"),
            "scope": canonical_name(view.get("scopeId"), elements, relationships, views),
            "description": presentation.get("intro") or view.get("description", ""),
            "question": view.get("question", ""),
            "readingTips": presentation.get("readingTips", []),
            "notShown": presentation.get("notShown") or view.get("notShown", []),
            "nextViewIds": presentation.get("nextViewIds") or view.get("nextViewIds", []),
            "nextViews": [views[item]["title"] for item in (presentation.get("nextViewIds") or view.get("nextViewIds", [])) if item in views],
            "caption": presentation.get("caption", ""),
            "alt": presentation.get("alt", view.get("title", "Architecture diagram")),
        })

    hydrated_flows: list[dict[str, Any]] = []
    for flow in hydrated.get("flows", []):
        view = views.get(flow["viewId"], {})
        presentation = flow.get("presentation", {})
        step_notes = {item["stepId"]: item for item in presentation.get("stepNotes", [])}
        steps: list[dict[str, Any]] = []
        for step in sorted(view.get("steps", []), key=lambda item: item.get("order", 0)):
            rel = relationships.get(step["relationshipId"], {})
            source = elements.get(rel.get("sourceId"), {})
            destination = elements.get(rel.get("destinationId"), {})
            presentation_step = step_notes.get(step["id"], {})
            step_claim_ids = list(dict.fromkeys((rel.get("claimIds") or []) + (step.get("claimIds") or [])))
            technical = rel.get("technology")
            default_text = step.get("note") or (f"통신 방식: {technical}" if technical else "")
            steps.append({
                "id": step["id"],
                "number": step["order"],
                "lane": f"{source.get('name', rel.get('sourceId', ''))} → {destination.get('name', rel.get('destinationId', ''))}",
                "title": rel.get("description", step["relationshipId"]),
                "text": presentation_step.get("explanation") or default_text,
                "attention": presentation_step.get("attention"),
                "analogy": presentation_step.get("analogy"),
                "kind": step.get("kind", "interaction"),
                "condition": step.get("condition"),
                "sourceIds": source_ids_for_claims(claims, step_claim_ids),
            })
        hydrated_flows.append({
            "id": flow["id"],
            "viewId": flow["viewId"],
            "kind": flow["kind"],
            "title": presentation.get("title") or view.get("title", flow["id"]),
            "description": presentation.get("description") or view.get("description", ""),
            "steps": steps,
            "notes": [
                {**note, "sourceIds": source_ids_for_claims(claims, note.get("claimIds", []))}
                for note in presentation.get("notes", [])
            ],
        })
    hydrated["flows"] = hydrated_flows

    for group in hydrated.get("elementGroups", []):
        for item in group.get("elements", []):
            canonical = elements.get(item["modelId"], {})
            presentation = item.pop("presentation", {})
            item.update({
                "id": item["modelId"],
                "name": canonical.get("name", item["modelId"]),
                "type": canonical.get("type", "unknown"),
                "technology": canonical.get("technology"),
                "description": canonical.get("description", ""),
                "status": canonical.get("derivation", "unresolved"),
                "confidence": canonical.get("confidence", "UNVERIFIED"),
                "why": presentation.get("whyItMatters"),
                "without": presentation.get("withoutIt"),
                "analogy": presentation.get("analogy"),
                "notes": presentation.get("notes", []),
                "claimIds": canonical.get("claimIds", []),
                "sourceIds": source_ids_for_claims(claims, canonical.get("claimIds", [])),
            })

    for section in hydrated.get("audienceSections", []):
        section["sourceIds"] = source_ids_for_claims(claims, section.get("claimIds", []))

    for key in ("benefits", "tradeoffs", "risks"):
        hydrated["analysis"][key] = [
            {**item, "sourceIds": source_ids_for_claims(claims, item.get("claimIds", []))}
            for item in hydrated.get("analysis", {}).get(key, [])
        ]

    selected_issue_ids = hydrated.get("issueRefs") or [item["id"] for item in coverage.get("unknownRelevant", [])]
    hydrated["issues"] = []
    for issue_id in selected_issue_ids:
        item = issues.get(issue_id)
        if not item:
            continue
        next_check = item.get("nextCheck")
        hydrated["issues"].append({
            "id": issue_id,
            "kind": issue_kinds.get(issue_id, "확인 필요"),
            "title": item.get("label", issue_id),
            "description": item.get("reason", ""),
            "impact": item.get("impact", ""),
            "candidates": [next_check] if next_check else [],
            "sourceIds": item.get("sourceIds", []),
            "confidence": item.get("confidence", "UNVERIFIED"),
        })

    hydrated["sources"] = ledger.get("sources", [])
    hydrated["traceability"] = []
    for claim in ledger.get("claims", []):
        primary_id = (claim.get("targetIds") or [""])[0]
        locators = [f"{item.get('sourceId')}: {item.get('locator')}" for item in claim.get("supports", [])]
        locators += [f"{item.get('sourceId')}: {item.get('locator')} [충돌]" for item in claim.get("contradictions", [])]
        hydrated["traceability"].append({
            "claimId": claim.get("id", ""),
            "modelId": primary_id,
            "kind": "claim",
            "name": canonical_name(primary_id, elements, relationships, views),
            "statement": claim.get("statement", ""),
            "status": f"{claim.get('derivation', '')}/{claim.get('confidence', '')}",
            "sourceIds": source_ids_for_claims(claims, [claim.get("id", "")]),
            "locator": " · ".join(locators),
            "diagrams": [item.get("id", "") for item in claim.get("usedBy", []) if item.get("kind") in {"view", "diagram", "flow"}],
        })

    coverage_completion = coverage.get("completion", {})
    qa_checks = [{
        "id": "COVERAGE",
        "label": "분석 범위 종료 판정",
        "result": coverage_completion.get("result", "NOT_RUN"),
        "detail": coverage_completion.get("reason", ""),
    }]
    if understanding:
        qa_checks.append({
            "id": "UNDERSTANDING",
            "label": f"이해도 Gate ({understanding.get('method', 'not-run')})",
            "result": understanding.get("result", "NOT_RUN"),
            "detail": " · ".join(understanding.get("limitations", [])) or understanding.get("persona", ""),
        })
        for question in understanding.get("questions", []):
            qa_checks.append({
                "id": question.get("id", ""),
                "label": question.get("question", ""),
                "result": question.get("result", "NOT_RUN"),
                "detail": question.get("issue") or question.get("answer") or "",
            })
    coverage_result = coverage_completion.get("result", "NOT_RUN")
    understanding_result = understanding.get("result", "NOT_RUN") if understanding else "NOT_RUN"
    result_rank = {"REQUEST_CHANGES": 4, "FAIL": 4, "PASS_BOUNDED": 3, "NOT_RUN": 2, "PASS": 1}
    overall_result = max((coverage_result, understanding_result), key=lambda value: result_rank.get(value, 2))
    hydrated["qa"] = {
        "result": overall_result,
        "summary": coverage_completion.get("reason", "") or "분석 범위와 이해도 검사를 확인하십시오.",
        "checks": qa_checks,
    }

    hydrated["stats"] = [
        {"label": "Software Systems", "value": sum(1 for item in elements.values() if item.get("type") == "softwareSystem")},
        {"label": "Containers", "value": sum(1 for item in elements.values() if item.get("type") == "container")},
        {"label": "Components", "value": sum(1 for item in elements.values() if item.get("type") == "component")},
        {"label": "Relationships", "value": len(relationships)},
        {"label": "Views", "value": len(views)},
        {"label": "Open Boundaries", "value": len(coverage.get("unknownRelevant", []))},
    ]

    hydrated["integrity"] = {
        "result": validation.result,
        "checks": [check.to_dict() for check in validation.checks],
        "warnings": [f"{item.code} {item.path}: {item.message}" for item in validation.findings],
    }
    return hydrated


def embed_assets(root: Path, data: dict[str, Any], max_bytes: int, report: ValidationReport) -> None:
    for index, diagram in enumerate(data.get("diagrams", [])):
        if diagram.get("dataUri"):
            diagram["assetStatus"] = "embedded"
            continue
        asset_path = diagram.get("assetPath")
        if not asset_path:
            message = "diagram has neither assetPath nor dataUri"
            if diagram.get("required", True):
                report.error("HTML-ASSET-001", f"$.diagrams[{index}]", message)
            else:
                report.warning("HTML-ASSET-001", f"$.diagrams[{index}]", message)
            diagram["assetStatus"] = "missing"
            continue
        try:
            path = safe_package_path(root, asset_path)
        except ValueError as exc:
            report.error("HTML-ASSET-002", f"$.diagrams[{index}].assetPath", str(exc))
            continue
        if not path.is_file():
            if diagram.get("required", True):
                report.error("HTML-ASSET-003", asset_path, "required diagram asset not found")
            else:
                report.warning("HTML-ASSET-003", asset_path, "optional diagram asset not found")
            diagram["assetStatus"] = "missing"
            continue
        if path.suffix.lower() == ".svg":
            report.merge(validate_svg(path))
        try:
            diagram["dataUri"] = data_uri(path, diagram.get("mimeType"), max_bytes)
            diagram["sourcePath"] = asset_path
            diagram["assetStatus"] = "embedded"
        except (OSError, BuildError) as exc:
            report.error("HTML-ASSET-004", asset_path, str(exc))

    for index, artifact in enumerate(data.get("artifacts", [])):
        if artifact.get("content") is not None:
            artifact["status"] = "embedded"
            continue
        content_path = artifact.get("contentPath")
        if not content_path:
            if artifact.get("required", False):
                report.error("HTML-ASSET-005", f"$.artifacts[{index}]", "required artifact has no contentPath or content")
            continue
        try:
            path = safe_package_path(root, content_path)
        except ValueError as exc:
            report.error("HTML-ASSET-006", f"$.artifacts[{index}].contentPath", str(exc))
            continue
        if not path.is_file():
            if artifact.get("required", False):
                report.error("HTML-ASSET-007", content_path, "required artifact file not found")
            else:
                report.warning("HTML-ASSET-007", content_path, "optional artifact file not found")
            artifact["status"] = "missing"
            continue
        if path.stat().st_size > max_bytes:
            report.error("HTML-ASSET-008", content_path, "artifact exceeds embed limit")
            continue
        mime = guess_mime(path, artifact.get("mimeType"))
        if not is_text_file(path, mime):
            report.error("HTML-ASSET-009", content_path, "raw artifact is not a supported text file")
            continue
        artifact["content"] = path.read_text(encoding="utf-8", errors="replace")
        artifact["sourcePath"] = content_path
        artifact["mimeType"] = mime
        artifact["status"] = "embedded"


def inject(template: str, data: dict[str, Any]) -> str:
    if template.count(TOKEN) != 1:
        raise BuildError(f"template must contain exactly one {TOKEN} token")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html_text = template.replace(TOKEN, payload)
    if TOKEN in html_text:
        raise BuildError("unresolved report data token remains")
    return html_text


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    data_path = resolve(root, args.data).resolve()
    template_path = args.template.resolve()
    output_path = args.output.resolve()
    skill_root = args.skill_root.resolve()
    max_bytes = int(args.max_embed_mb * 1024 * 1024)

    try:
        if not root.is_dir():
            raise BuildError(f"package root is not a directory: {root}")
        report_data = load_json(data_path)
        bundle, reports = bundle_reports(root, skill_root, report_data)
        validation = aggregate_reports("c4-html-build", reports)
        if args.validation_output:
            write_report(args.validation_output, validation)
        if validation.errors and not args.lenient:
            print_report(validation)
            raise BuildError("artifact validation failed before HTML rendering")

        hydrated = hydrate_report(report_data, bundle, validation)
        embed_assets(root, hydrated, max_bytes, validation)
        if validation.errors and not args.lenient:
            print_report(validation)
            raise BuildError("asset validation failed before HTML rendering")

        template = template_path.read_text(encoding="utf-8")
        template_report = validate_html_text(template.replace(TOKEN, "{}"), template_path.name)
        validation.merge(template_report)
        if validation.errors and not args.lenient:
            print_report(validation)
            raise BuildError("HTML template validation failed")

        hydrated["integrity"] = {
            "result": validation.result,
            "checks": [check.to_dict() for check in validation.checks],
            "warnings": [f"{item.code} {item.path}: {item.message}" for item in validation.findings],
        }
        html_text = inject(template, hydrated)
        output_report = validate_html_text(html_text, output_path.name, base_dir=output_path.parent)
        validation.merge(output_report)
        if output_report.errors and not args.lenient:
            print_report(validation)
            raise BuildError("generated HTML failed static validation")

        if args.lenient and validation.errors:
            hydrated["integrity"] = {
                "result": "FAIL",
                "checks": [check.to_dict() for check in validation.checks],
                "warnings": ["LENIENT DIAGNOSTIC BUILD"] + [f"{item.code} {item.path}: {item.message}" for item in validation.findings],
            }
            html_text = inject(template, hydrated)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_text, encoding="utf-8")
        if args.validation_output:
            write_report(args.validation_output, validation)
        print(f"Created: {output_path}")
        print(f"Size: {output_path.stat().st_size} bytes")
        print(f"Integrity: {validation.result if not validation.errors else 'FAIL'}")
        return 2 if args.lenient and validation.errors else 0
    except (BuildError, OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
