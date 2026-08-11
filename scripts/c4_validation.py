#!/usr/bin/env python3
"""Validation engine for c4-archi-model v0.4.0.

The implementation is renderer- and agent-independent. It validates the data
contracts, C4 semantics, evidence traceability, bounded coverage, presentation
references, offline HTML assets, and portable package integrity.
"""
from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True

import fnmatch
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from schema_runtime import load_json as schema_load_json, validate as schema_validate

VALIDATION_VERSION = "0.4.0"


@dataclass
class Finding:
    code: str
    severity: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "severity": self.severity, "path": self.path, "message": self.message}


@dataclass
class Check:
    id: str
    label: str
    result: str
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "label": self.label, "result": self.result, "detail": self.detail}


@dataclass
class ValidationReport:
    name: str
    findings: list[Finding] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)

    def error(self, code: str, path: str, message: str) -> None:
        self.findings.append(Finding(code, "ERROR", path, message))

    def warning(self, code: str, path: str, message: str) -> None:
        self.findings.append(Finding(code, "WARNING", path, message))

    def pass_check(self, code: str, label: str, detail: str = "") -> None:
        self.checks.append(Check(code, label, "PASS", detail))

    def fail_check(self, code: str, label: str, detail: str = "") -> None:
        self.checks.append(Check(code, label, "FAIL", detail))

    def not_run(self, code: str, label: str, detail: str = "") -> None:
        self.checks.append(Check(code, label, "NOT RUN", detail))

    def merge(self, other: "ValidationReport") -> None:
        self.findings.extend(other.findings)
        self.checks.extend(other.checks)

    @property
    def errors(self) -> list[Finding]:
        return [item for item in self.findings if item.severity == "ERROR"]

    @property
    def warnings(self) -> list[Finding]:
        return [item for item in self.findings if item.severity == "WARNING"]

    @property
    def result(self) -> str:
        if self.errors:
            return "FAIL"
        if self.warnings:
            return "WARN"
        return "PASS"

    def to_dict(self) -> dict[str, Any]:
        return {
            "validatorVersion": VALIDATION_VERSION,
            "name": self.name,
            "result": self.result,
            "errorCount": len(self.errors),
            "warningCount": len(self.warnings),
            "findings": [item.to_dict() for item in self.findings],
            "checks": [item.to_dict() for item in self.checks],
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    data = schema_load_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def write_report(path: Path, report: ValidationReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_report(report: ValidationReport) -> None:
    print(f"Validation: {report.name}")
    print(f"Result: {report.result}")
    print(f"Errors: {len(report.errors)}")
    print(f"Warnings: {len(report.warnings)}")
    for check in report.checks:
        suffix = f" — {check.detail}" if check.detail else ""
        print(f"[{check.result}] {check.id} {check.label}{suffix}")
    for item in report.findings:
        print(f"[{item.severity}] {item.code} {item.path}: {item.message}")


def aggregate_reports(name: str, reports: Iterable[ValidationReport]) -> ValidationReport:
    combined = ValidationReport(name)
    for report in reports:
        combined.merge(report)
    return combined


def schema_report(name: str, data: dict[str, Any], schema_path: Path) -> ValidationReport:
    report = ValidationReport(name)
    try:
        schema = load_json(schema_path)
        issues = schema_validate(data, schema)
    except (OSError, ValueError, RuntimeError) as exc:
        report.error("SCHEMA-000", "$", str(exc))
        report.fail_check("SCHEMA-000", f"{name} schema loaded", str(exc))
        return report
    for issue in issues:
        report.error("SCHEMA-001", issue.path, issue.message)
    if issues:
        report.fail_check("SCHEMA-001", f"{name} matches JSON Schema", f"{len(issues)} violation(s)")
    else:
        report.pass_check("SCHEMA-001", f"{name} matches JSON Schema", schema_path.name)
    return report


def duplicate_values(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _ids(items: Iterable[Any]) -> set[str]:
    return {item.get("id") for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)}


def safe_package_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("path must be a non-empty string")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes package root: {relative}") from exc
    return candidate


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _model_claim_ids(model: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for collection in (model.get("elements", []), model.get("relationships", []), model.get("views", [])):
        for item in collection:
            if not isinstance(item, dict):
                continue
            found.update(v for v in item.get("claimIds", []) if isinstance(v, str))
            for step in item.get("steps", []):
                if isinstance(step, dict):
                    found.update(v for v in step.get("claimIds", []) if isinstance(v, str))
    return found


def _model_step_ids(model: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for view in model.get("views", []):
        if isinstance(view, dict):
            found.update(step.get("id") for step in view.get("steps", []) if isinstance(step, dict) and isinstance(step.get("id"), str))
    return found


def _all_canonical_ids(model: dict[str, Any]) -> set[str]:
    return (_ids(model.get("elements", [])) | _ids(model.get("relationships", [])) |
            _ids(model.get("views", [])) | _model_step_ids(model))


def validate_session(data: dict[str, Any], schema_path: Path, model: dict[str, Any] | None = None) -> ValidationReport:
    report = schema_report("architecture-session", data, schema_path)
    if report.errors:
        return report

    overlap = set(data["inScope"]) & set(data["outOfScope"])
    if overlap:
        report.error("SES-001", "$.inScope", f"items occur in both inScope and outOfScope: {sorted(overlap)}")
    else:
        report.pass_check("SES-001", "Scope inclusion and exclusion do not conflict")

    if data["analysisProfile"] == "focus" and not data["targetIds"]:
        report.error("SES-002", "$.targetIds", "focus profile requires at least one targetId")
    else:
        report.pass_check("SES-002", "Analysis profile has a usable target scope", data["analysisProfile"])

    if model is not None:
        model_ids = _ids(model.get("elements", [])) | _ids(model.get("views", []))
        unknown = sorted(set(data["targetIds"]) - model_ids)
        if unknown:
            report.error("SES-003", "$.targetIds", f"unknown target IDs: {unknown}")
        else:
            report.pass_check("SES-003", "Session target IDs resolve in the canonical model", str(len(data["targetIds"])))

    requested = data["outputSurface"]["requestedFormats"]
    if data["outputSurface"]["htmlRequired"] and "html" not in requested:
        report.error("SES-004", "$.outputSurface.requestedFormats", "htmlRequired=true requires html")
    elif "html" not in requested:
        report.warning("SES-004", "$.outputSurface.requestedFormats", "HTML is the default human entry point but was not requested")
    else:
        report.pass_check("SES-004", "HTML is included as the human entry point")
    return report


def validate_model(data: dict[str, Any], schema_path: Path, ledger: dict[str, Any] | None = None) -> ValidationReport:
    report = schema_report("architecture-model", data, schema_path)
    if report.errors:
        return report

    elements = data["elements"]
    relationships = data["relationships"]
    views = data["views"]
    element_by_id = {item["id"]: item for item in elements}
    rel_by_id = {item["id"]: item for item in relationships}
    view_by_id = {item["id"]: item for item in views}

    all_ids = [item["id"] for item in elements + relationships + views]
    all_ids.extend(step["id"] for view in views for step in view.get("steps", []))
    duplicates = sorted(duplicate_values(all_ids))
    if duplicates:
        report.error("MOD-001", "$", f"IDs must be globally unique: {duplicates}")
    else:
        report.pass_check("MOD-001", "Canonical IDs are globally unique", str(len(all_ids)))

    target = data["metadata"]["targetSystemId"]
    if target is not None and (target not in element_by_id or element_by_id[target]["type"] != "softwareSystem"):
        report.error("MOD-002", "$.metadata.targetSystemId", "targetSystemId must reference a softwareSystem")
    else:
        report.pass_check("MOD-002", "Target software system resolves", str(target))

    expected_parent = {"person": None, "softwareSystem": None, "container": "softwareSystem", "component": "container", "codeElement": "component"}
    parent_errors = 0
    for index, element in enumerate(elements):
        path = f"$.elements[{index}]"
        etype = element["type"]
        parent = element["parentId"]
        if etype in expected_parent:
            expected = expected_parent[etype]
            if expected is None and parent is not None:
                report.error("MOD-003", path + ".parentId", f"{etype} must not have a parent")
                parent_errors += 1
            elif expected is not None and (parent not in element_by_id or element_by_id[parent]["type"] != expected):
                report.error("MOD-003", path + ".parentId", f"{etype} parent must reference {expected}")
                parent_errors += 1
        elif etype == "deploymentNode":
            if parent is not None and (parent not in element_by_id or element_by_id[parent]["type"] != "deploymentNode"):
                report.error("MOD-003", path + ".parentId", "deploymentNode parent must be another deploymentNode or null")
                parent_errors += 1
        elif etype == "infrastructureNode":
            if parent is not None and (parent not in element_by_id or element_by_id[parent]["type"] != "deploymentNode"):
                report.error("MOD-003", path + ".parentId", "infrastructureNode parent must be a deploymentNode or null")
                parent_errors += 1
        instance_of = element["instanceOfId"]
        if instance_of is not None and instance_of not in element_by_id:
            report.error("MOD-004", path + ".instanceOfId", f"unknown instanceOfId {instance_of!r}")
        if element["derivation"] == "unresolved" and element["confidence"] == "VERIFIED":
            report.error("MOD-005", path, "unresolved element cannot be VERIFIED")
        if not element["claimIds"]:
            report.error("MOD-006", path + ".claimIds", "every canonical element requires at least one evidence claim")
    if not parent_errors:
        report.pass_check("MOD-003", "C4 parent hierarchy is valid", str(len(elements)))

    vague = {"uses", "use", "data", "api", "call", "calls", "connects", "connection", "사용", "데이터", "호출", "연결"}
    rel_errors = 0
    for index, rel in enumerate(relationships):
        path = f"$.relationships[{index}]"
        if rel["sourceId"] not in element_by_id:
            report.error("MOD-007", path + ".sourceId", f"unknown element {rel['sourceId']!r}")
            rel_errors += 1
        if rel["destinationId"] not in element_by_id:
            report.error("MOD-007", path + ".destinationId", f"unknown element {rel['destinationId']!r}")
            rel_errors += 1
        if rel["sourceId"] == rel["destinationId"] and not rel["rationale"]:
            report.warning("MOD-008", path, "self-relationship should explain its rationale")
        normalized = re.sub(r"[\s.。]+", "", rel["description"].strip().lower())
        if normalized in vague or len(normalized) < 3:
            report.error("MOD-009", path + ".description", "use a directional verb and purpose, not a vague label")
            rel_errors += 1
        if rel["derivation"] == "unresolved" and rel["confidence"] == "VERIFIED":
            report.error("MOD-010", path, "unresolved relationship cannot be VERIFIED")
            rel_errors += 1
        if not rel["claimIds"]:
            report.error("MOD-011", path + ".claimIds", "every canonical relationship requires at least one evidence claim")
            rel_errors += 1
    if not rel_errors:
        report.pass_check("MOD-007", "Relationship endpoints, descriptions, and evidence links are valid", str(len(relationships)))

    allowed_by_type = {
        "systemLandscape": {"person", "softwareSystem"},
        "systemContext": {"person", "softwareSystem"},
        "container": {"person", "softwareSystem", "container"},
        "component": {"person", "softwareSystem", "container", "component"},
        "code": {"person", "softwareSystem", "container", "component", "codeElement"},
        "dynamic": {"person", "softwareSystem", "container", "component", "codeElement"},
        "deployment": {"softwareSystem", "container", "deploymentNode", "infrastructureNode"},
    }
    view_errors = 0
    global_step_ids: list[str] = []
    for index, view in enumerate(views):
        path = f"$.views[{index}]"
        element_ids = set(view["elementIds"])
        relation_ids = set(view["relationshipIds"])
        unknown_elements = sorted(element_ids - set(element_by_id))
        unknown_relations = sorted(relation_ids - set(rel_by_id))
        unknown_next = sorted(set(view["nextViewIds"]) - set(view_by_id))
        if unknown_elements:
            report.error("VIEW-001", path + ".elementIds", f"unknown elements: {unknown_elements}")
            view_errors += 1
        if unknown_relations:
            report.error("VIEW-002", path + ".relationshipIds", f"unknown relationships: {unknown_relations}")
            view_errors += 1
        if unknown_next:
            report.error("VIEW-003", path + ".nextViewIds", f"unknown next views: {unknown_next}")
            view_errors += 1
        for rel_id in relation_ids & set(rel_by_id):
            rel = rel_by_id[rel_id]
            if rel["sourceId"] not in element_ids or rel["destinationId"] not in element_ids:
                report.error("VIEW-004", path + ".relationshipIds", f"relationship {rel_id!r} endpoints must both appear in elementIds")
                view_errors += 1
        disallowed = sorted(eid for eid in element_ids if eid in element_by_id and element_by_id[eid]["type"] not in allowed_by_type[view["type"]])
        if disallowed:
            report.error("VIEW-005", path + ".elementIds", f"{view['type']} contains disallowed element types: {disallowed}")
            view_errors += 1

        scope = view["scopeId"]
        if view["type"] in {"systemContext", "container"}:
            if scope not in element_by_id or element_by_id[scope]["type"] != "softwareSystem":
                report.error("VIEW-006", path + ".scopeId", f"{view['type']} scope must be a softwareSystem")
                view_errors += 1
        elif view["type"] == "component":
            if scope not in element_by_id or element_by_id[scope]["type"] != "container":
                report.error("VIEW-006", path + ".scopeId", "component scope must be a container")
                view_errors += 1
            wrong = [eid for eid in element_ids if eid in element_by_id and element_by_id[eid]["type"] == "component" and element_by_id[eid]["parentId"] != scope]
            if wrong:
                report.error("VIEW-007", path + ".elementIds", f"component view expands components outside its scope: {wrong}")
                view_errors += 1
        elif view["type"] == "code":
            if scope not in element_by_id or element_by_id[scope]["type"] != "component":
                report.error("VIEW-006", path + ".scopeId", "code scope must be a component")
                view_errors += 1
        elif view["type"] == "systemLandscape" and scope is not None:
            report.warning("VIEW-008", path + ".scopeId", "systemLandscape normally has null scope")

        steps = view["steps"]
        if view["type"] == "dynamic":
            if not steps:
                report.error("VIEW-009", path + ".steps", "dynamic view requires at least one step")
                view_errors += 1
            orders = [step["order"] for step in steps]
            if sorted(orders) != list(range(1, len(steps) + 1)):
                report.error("VIEW-010", path + ".steps", f"orders must be consecutive 1..N; got {orders}")
                view_errors += 1
            for step_index, step in enumerate(steps):
                global_step_ids.append(step["id"])
                if step["relationshipId"] not in rel_by_id:
                    report.error("VIEW-011", f"{path}.steps[{step_index}].relationshipId", "unknown relationship")
                    view_errors += 1
                elif step["relationshipId"] not in relation_ids:
                    report.error("VIEW-011", f"{path}.steps[{step_index}].relationshipId", "step relationship must also appear in relationshipIds")
                    view_errors += 1
        elif steps:
            report.error("VIEW-012", path + ".steps", "only dynamic views may contain steps")
            view_errors += 1

        count = len(element_ids)
        if view["type"] == "systemContext" and count > 10:
            report.warning("VIS-001", path + ".elementIds", f"System Context visual budget exceeded: {count} elements")
        if view["type"] == "container" and count > 14:
            report.warning("VIS-002", path + ".elementIds", f"Container visual budget exceeded: {count} elements")
        if view["type"] == "component":
            components = sum(1 for eid in element_ids if eid in element_by_id and element_by_id[eid]["type"] == "component")
            if components > 15:
                report.warning("VIS-003", path + ".elementIds", f"Component visual budget exceeded: {components} components")
        if view["type"] == "dynamic" and not (2 <= len(steps) <= 15):
            report.warning("VIS-004", path + ".steps", f"Dynamic view has {len(steps)} steps; primary reading is usually clearer with 5-12")
        if not view["claimIds"]:
            report.warning("VIEW-013", path + ".claimIds", "view has no direct evidence claim; composition is only traceable through contained items")

    step_duplicates = sorted(duplicate_values(global_step_ids))
    if step_duplicates:
        report.error("VIEW-014", "$.views", f"dynamic step IDs must be globally unique: {step_duplicates}")
        view_errors += 1
    if not view_errors:
        report.pass_check("VIEW-001", "C4 views reference valid scopes, elements, relationships, and ordered steps", str(len(views)))

    if ledger is not None:
        ledger_claims = _ids(ledger.get("claims", []))
        missing = sorted(_model_claim_ids(data) - ledger_claims)
        if missing:
            report.error("MOD-012", "$", f"canonical model references unknown claim IDs: {missing}")
        else:
            report.pass_check("MOD-012", "All canonical claim IDs resolve in the evidence ledger", str(len(_model_claim_ids(data))))
    return report


def validate_ledger(data: dict[str, Any], schema_path: Path, model: dict[str, Any] | None = None,
                    session: dict[str, Any] | None = None) -> ValidationReport:
    report = schema_report("evidence-ledger", data, schema_path)
    if report.errors:
        return report

    if session is not None and data["sessionId"] != session["sessionId"]:
        report.error("EVD-001", "$.sessionId", "ledger sessionId does not match architecture session")
    else:
        report.pass_check("EVD-001", "Evidence ledger session matches")

    sources = data["sources"]
    claims = data["claims"]
    source_ids = _ids(sources)
    claim_ids = _ids(claims)
    dup_sources = sorted(duplicate_values(item["id"] for item in sources))
    dup_claims = sorted(duplicate_values(item["id"] for item in claims))
    if dup_sources:
        report.error("EVD-002", "$.sources", f"duplicate source IDs: {dup_sources}")
    if dup_claims:
        report.error("EVD-003", "$.claims", f"duplicate claim IDs: {dup_claims}")
    if not dup_sources and not dup_claims:
        report.pass_check("EVD-002", "Source and claim IDs are unique", f"sources={len(sources)}, claims={len(claims)}")

    snapshot_sources = set(data["snapshot"]["sourceIds"])
    if snapshot_sources != source_ids:
        report.error("EVD-004", "$.snapshot.sourceIds", f"snapshot sourceIds must exactly match registered sources; snapshot={sorted(snapshot_sources)}, sources={sorted(source_ids)}")
    if session is not None and session["sourceSnapshotId"] is not None and data["snapshot"]["id"] != session["sourceSnapshotId"]:
        report.error("EVD-005", "$.snapshot.id", "snapshot ID does not match architecture session")
    if model is not None and model["metadata"]["sourceSnapshotId"] is not None and data["snapshot"]["id"] != model["metadata"]["sourceSnapshotId"]:
        report.error("EVD-006", "$.snapshot.id", "snapshot ID does not match canonical model metadata")

    for index, source in enumerate(sources):
        if source["kind"] in {"code", "infrastructure", "runtime", "api", "data-model"} and not source["immutableRef"] and not source["contentHash"]:
            report.warning("EVD-007", f"$.sources[{index}]", "mutable technical source has neither immutableRef nor contentHash")

    model_ids: set[str] = set()
    view_ids: set[str] = set()
    if model is not None:
        model_ids = _all_canonical_ids(model)
        view_ids = _ids(model.get("views", []))
    evidence_errors = 0
    for index, claim in enumerate(claims):
        path = f"$.claims[{index}]"
        referenced_sources = {item["sourceId"] for item in claim["supports"] + claim["contradictions"]}
        unknown_sources = sorted(referenced_sources - source_ids)
        if unknown_sources:
            report.error("EVD-008", path, f"claim references unregistered sources: {unknown_sources}")
            evidence_errors += 1
        if claim["confidence"] == "VERIFIED" and not claim["supports"]:
            report.error("EVD-009", path, "VERIFIED claim requires support")
            evidence_errors += 1
        if claim["confidence"] in {"DOC_ONLY", "PARTIAL"} and not claim["supports"]:
            report.warning("EVD-010", path, f"{claim['confidence']} claim has no support")
        if claim["confidence"] == "CONFLICT" and not claim["contradictions"]:
            report.error("EVD-011", path, "CONFLICT claim requires at least one contradiction")
            evidence_errors += 1
        if claim["confidence"] != "CONFLICT" and claim["contradictions"]:
            report.warning("EVD-012", path, "claim has contradictions but confidence is not CONFLICT")
        if claim["derivation"] == "unresolved" and claim["confidence"] == "VERIFIED":
            report.error("EVD-013", path, "unresolved claim cannot be VERIFIED")
            evidence_errors += 1
        if model is not None:
            unknown_targets = sorted(set(claim["targetIds"]) - model_ids)
            if unknown_targets:
                report.error("EVD-014", path + ".targetIds", f"unknown canonical IDs: {unknown_targets}")
                evidence_errors += 1
            for used_index, used in enumerate(claim["usedBy"]):
                if used["kind"] in {"element", "relationship", "step", "view"} and used["id"] not in model_ids:
                    report.error("EVD-015", f"{path}.usedBy[{used_index}]", f"unknown canonical ID {used['id']!r}")
                    evidence_errors += 1
                if used["kind"] == "view" and used["id"] not in view_ids:
                    report.error("EVD-016", f"{path}.usedBy[{used_index}]", f"view usage does not reference a canonical view: {used['id']!r}")
                    evidence_errors += 1
                if used["kind"] == "step" and used["id"] not in _model_step_ids(model):
                    report.error("EVD-016", f"{path}.usedBy[{used_index}]", f"step usage does not reference a canonical dynamic step: {used['id']!r}")
                    evidence_errors += 1
    if not evidence_errors:
        report.pass_check("EVD-008", "Claims use registered sources and valid canonical references", str(len(claims)))

    if model is not None:
        if data["modelRevision"] != model["metadata"]["modelRevision"]:
            report.error("EVD-017", "$.modelRevision", "ledger modelRevision does not match canonical model")
        missing = sorted(_model_claim_ids(model) - claim_ids)
        if missing:
            report.error("EVD-018", "$.claims", f"canonical model references missing claims: {missing}")
        else:
            report.pass_check("EVD-018", "Canonical claims exist in the ledger", str(len(_model_claim_ids(model))))
    return report


def _coverage_categories() -> tuple[str, ...]:
    return ("explored", "unknownRelevant", "unknownOutOfScope", "expansionPoints", "boundaries")


def _coverage_item_ids(data: dict[str, Any] | None) -> set[str]:
    if not data:
        return set()
    found: set[str] = set()
    for key in _coverage_categories():
        found.update(_ids(data.get(key, [])))
    return found


def validate_coverage(data: dict[str, Any], schema_path: Path, model: dict[str, Any] | None = None,
                      ledger: dict[str, Any] | None = None, session: dict[str, Any] | None = None) -> ValidationReport:
    report = schema_report("coverage", data, schema_path)
    if report.errors:
        return report

    if session is not None and data["sessionId"] != session["sessionId"]:
        report.error("COV-001", "$.sessionId", "coverage sessionId does not match architecture session")
    else:
        report.pass_check("COV-001", "Coverage session matches")
    if model is not None and data["modelRevision"] != model["metadata"]["modelRevision"]:
        report.error("COV-002", "$.modelRevision", "coverage modelRevision does not match canonical model")

    all_items = [item for key in _coverage_categories() for item in data[key]]
    duplicates = sorted(duplicate_values(item["id"] for item in all_items))
    if duplicates:
        report.error("COV-003", "$", f"coverage item IDs must be unique: {duplicates}")
    else:
        report.pass_check("COV-003", "Coverage item IDs are unique", str(len(all_items)))

    canonical_ids = _all_canonical_ids(model) if model else set()
    view_ids = _ids(model.get("views", [])) if model else set()
    source_ids = _ids(ledger.get("sources", [])) if ledger else set()
    claim_ids = _ids(ledger.get("claims", [])) if ledger else set()
    ref_errors = 0
    for category in _coverage_categories():
        for index, item in enumerate(data[category]):
            path = f"$.{category}[{index}]"
            if model is not None:
                unknown_model = sorted(set(item["affectedModelIds"]) - canonical_ids)
                unknown_views = sorted(set(item["affectedViewIds"]) - view_ids)
                if unknown_model:
                    report.error("COV-004", path + ".affectedModelIds", f"unknown canonical IDs: {unknown_model}")
                    ref_errors += 1
                if unknown_views:
                    report.error("COV-005", path + ".affectedViewIds", f"unknown view IDs: {unknown_views}")
                    ref_errors += 1
            if ledger is not None:
                unknown_sources = sorted(set(item["sourceIds"]) - source_ids)
                unknown_claims = sorted(set(item["claimIds"]) - claim_ids)
                if unknown_sources:
                    report.error("COV-006", path + ".sourceIds", f"unknown source IDs: {unknown_sources}")
                    ref_errors += 1
                if unknown_claims:
                    report.error("COV-007", path + ".claimIds", f"unknown claim IDs: {unknown_claims}")
                    ref_errors += 1
    if not ref_errors:
        report.pass_check("COV-004", "Coverage references resolve", str(len(all_items)))

    completion = data["completion"]
    item_ids = {item["id"] for item in all_items}
    unknown_blocking_ids = sorted(set(completion["blockingIds"]) - item_ids)
    if unknown_blocking_ids:
        report.error("COV-008", "$.completion.blockingIds", f"unknown coverage IDs: {unknown_blocking_ids}")
    blockers = [item for item in data["unknownRelevant"] if item["impact"] in {"blocks-answer", "blocks-change"} or item["confidence"] == "CONFLICT"]
    blocker_ids = {item["id"] for item in blockers}
    if not blocker_ids.issubset(set(completion["blockingIds"])):
        report.error("COV-009", "$.completion.blockingIds", f"missing blocker IDs: {sorted(blocker_ids - set(completion['blockingIds']))}")
    result = completion["result"]
    if result == "PASS":
        if blockers or completion["blockingIds"]:
            report.error("COV-010", "$.completion.result", "PASS is not allowed while blockers remain")
        if not completion["questionAnswered"] or not completion["stopConditionMet"]:
            report.error("COV-011", "$.completion", "PASS requires questionAnswered and stopConditionMet")
    elif result == "PASS_BOUNDED":
        remaining = data["unknownRelevant"] or data["unknownOutOfScope"] or data["boundaries"]
        if blockers:
            report.error("COV-012", "$.completion.result", "PASS_BOUNDED cannot hide blocking unknowns")
        if not remaining:
            report.error("COV-013", "$.completion.result", "PASS_BOUNDED requires an explicit remaining boundary")
        if not completion["questionAnswered"] or not completion["stopConditionMet"]:
            report.error("COV-014", "$.completion", "PASS_BOUNDED requires questionAnswered and stopConditionMet")
    elif result == "REQUEST_CHANGES":
        if not completion["blockingIds"]:
            report.error("COV-015", "$.completion.blockingIds", "REQUEST_CHANGES requires at least one blocker")
    elif result == "NOT_RUN" and (completion["questionAnswered"] or completion["stopConditionMet"]):
        report.error("COV-016", "$.completion", "NOT_RUN cannot claim the question or stop condition was completed")
    if not any(item.code.startswith("COV-0") and item.severity == "ERROR" for item in report.findings):
        report.pass_check("COV-008", "Coverage completion is consistent", result)
    return report


def validate_understanding(data: dict[str, Any], schema_path: Path, session: dict[str, Any] | None = None,
                           model: dict[str, Any] | None = None, ledger: dict[str, Any] | None = None) -> ValidationReport:
    report = schema_report("human-understanding", data, schema_path)
    if report.errors:
        return report

    if session is not None:
        if data["sessionId"] != session["sessionId"]:
            report.error("HUG-001", "$.sessionId", "understanding sessionId does not match architecture session")
        if data["audienceMode"] != session["audienceMode"]:
            report.error("HUG-002", "$.audienceMode", "understanding audienceMode does not match architecture session")
    if data["method"] == "persona-simulation" and not data["simulated"]:
        report.error("HUG-003", "$.simulated", "persona-simulation must set simulated=true")
    if data["method"] == "human-review" and data["simulated"]:
        report.error("HUG-004", "$.simulated", "human-review cannot be simulated")
    if data["method"] == "not-run" and data["result"] != "NOT_RUN":
        report.error("HUG-005", "$.result", "not-run method requires NOT_RUN")
    if data["method"] != "not-run" and data["testedAt"] is None:
        report.error("HUG-006", "$.testedAt", "executed gate requires testedAt")

    required_beginner = {"B-01", "B-02", "B-03", "B-04", "B-05"}
    required_expert = {"E-01", "E-02", "E-03", "E-04", "E-05", "E-06"}
    question_ids = [item["id"] for item in data["questions"]]
    duplicates = sorted(duplicate_values(question_ids))
    if duplicates:
        report.error("HUG-007", "$.questions", f"duplicate question IDs: {duplicates}")
    if data["result"] != "NOT_RUN":
        required: set[str] = set()
        if data["audienceMode"] in {"beginner", "both"}:
            required |= required_beginner
        if data["audienceMode"] in {"expert", "both"}:
            required |= required_expert
        missing = sorted(required - set(question_ids))
        if missing:
            report.error("HUG-008", "$.questions", f"missing required comprehension questions: {missing}")
        for index, item in enumerate(data["questions"]):
            if item["result"] != "NOT_RUN" and not item["answer"]:
                report.error("HUG-009", f"$.questions[{index}].answer", "executed question requires an answer")

    question_results = [item["result"] for item in data["questions"]]
    if data["result"] == "PASS" and any(result != "PASS" for result in question_results):
        report.error("HUG-010", "$.result", "PASS requires every question to PASS")
    if data["result"] == "PASS_BOUNDED" and ("REQUEST_CHANGES" in question_results or not data["limitations"]):
        report.error("HUG-011", "$.result", "PASS_BOUNDED requires no REQUEST_CHANGES questions and at least one limitation")
    if data["result"] == "REQUEST_CHANGES" and "REQUEST_CHANGES" not in question_results:
        report.warning("HUG-012", "$.result", "REQUEST_CHANGES has no question marked REQUEST_CHANGES")
    if data["result"] == "NOT_RUN" and any(result != "NOT_RUN" for result in question_results):
        report.error("HUG-013", "$.questions", "NOT_RUN gate cannot contain executed question results")

    canonical_ids = _all_canonical_ids(model) if model else set()
    view_ids = _ids(model.get("views", [])) if model else set()
    evidence_ids = (_ids(ledger.get("claims", [])) | _ids(ledger.get("sources", []))) if ledger else set()
    for index, item in enumerate(data["questions"]):
        if model is not None:
            unknown_model = sorted(set(item["modelIds"]) - canonical_ids)
            unknown_views = sorted(set(item["viewIds"]) - view_ids)
            if unknown_model:
                report.error("HUG-014", f"$.questions[{index}].modelIds", f"unknown canonical IDs: {unknown_model}")
            if unknown_views:
                report.error("HUG-015", f"$.questions[{index}].viewIds", f"unknown view IDs: {unknown_views}")
        if ledger is not None:
            unknown_evidence = sorted(set(item["expectedEvidenceRefs"]) - evidence_ids)
            if unknown_evidence:
                report.error("HUG-016", f"$.questions[{index}].expectedEvidenceRefs", f"unknown evidence refs: {unknown_evidence}")
    if not report.errors:
        report.pass_check("HUG-001", "Human-understanding gate is internally consistent", data["result"])
    return report


def _report_claim_refs(data: dict[str, Any]) -> set[str]:
    found = set(data.get("overview", {}).get("claimIds", []))
    for flow in data.get("flows", []):
        for note in flow.get("presentation", {}).get("notes", []):
            found.update(note.get("claimIds", []))
    for section in data.get("audienceSections", []):
        found.update(section.get("claimIds", []))
    for key in ("benefits", "tradeoffs", "risks"):
        for item in data.get("analysis", {}).get(key, []):
            found.update(item.get("claimIds", []))
    return found


def _report_issue_refs(data: dict[str, Any]) -> set[str]:
    found = set(data.get("issueRefs", []))
    for section in data.get("audienceSections", []):
        found.update(section.get("issueIds", []))
    for key in ("benefits", "tradeoffs", "risks"):
        for item in data.get("analysis", {}).get(key, []):
            found.update(item.get("issueIds", []))
    for flow in data.get("flows", []):
        for note in flow.get("presentation", {}).get("notes", []):
            found.update(note.get("issueIds", []))
    return found


def validate_report_data(data: dict[str, Any], schema_path: Path, *, root: Path | None = None,
                         session: dict[str, Any] | None = None, model: dict[str, Any] | None = None,
                         ledger: dict[str, Any] | None = None, coverage: dict[str, Any] | None = None,
                         understanding: dict[str, Any] | None = None) -> ValidationReport:
    report = schema_report("html-report-data", data, schema_path)
    if report.errors:
        return report

    model_elements = {item["id"]: item for item in model.get("elements", [])} if model else {}
    model_views = {item["id"]: item for item in model.get("views", [])} if model else {}
    claim_ids = _ids(ledger.get("claims", [])) if ledger else set()
    issue_ids = _coverage_item_ids(coverage)

    diagram_ids = [item["id"] for item in data["diagrams"]]
    if duplicate_values(diagram_ids):
        report.error("HTML-DATA-001", "$.diagrams", f"duplicate diagram IDs: {sorted(duplicate_values(diagram_ids))}")
    view_refs = [item["viewId"] for item in data["diagrams"]]
    if duplicate_values(view_refs):
        report.warning("HTML-DATA-002", "$.diagrams", "more than one diagram maps to the same canonical view")
    for index, diagram in enumerate(data["diagrams"]):
        path = f"$.diagrams[{index}]"
        if model is not None and diagram["viewId"] not in model_views:
            report.error("HTML-DATA-003", path + ".viewId", f"unknown canonical view {diagram['viewId']!r}")
        if not diagram["assetPath"] and not diagram["dataUri"]:
            severity = report.error if diagram["required"] else report.warning
            severity("HTML-DATA-004", path, "diagram needs assetPath or dataUri")
        for next_id in diagram["presentation"]["nextViewIds"]:
            if model is not None and next_id not in model_views:
                report.error("HTML-DATA-005", path + ".presentation.nextViewIds", f"unknown next view {next_id!r}")

    flow_ids = [item["id"] for item in data["flows"]]
    if duplicate_values(flow_ids):
        report.error("HTML-DATA-006", "$.flows", f"duplicate flow IDs: {sorted(duplicate_values(flow_ids))}")
    for index, flow in enumerate(data["flows"]):
        path = f"$.flows[{index}]"
        view = model_views.get(flow["viewId"])
        if model is not None and (view is None or view["type"] != "dynamic"):
            report.error("HTML-DATA-007", path + ".viewId", "flow viewId must reference a dynamic view")
            continue
        if view:
            step_ids = {item["id"] for item in view["steps"]}
            presentation_ids = [item["stepId"] for item in flow["presentation"]["stepNotes"]]
            unknown_steps = sorted(set(presentation_ids) - step_ids)
            if unknown_steps:
                report.error("HTML-DATA-008", path + ".presentation.stepNotes", f"unknown step IDs: {unknown_steps}")
            if duplicate_values(presentation_ids):
                report.error("HTML-DATA-009", path + ".presentation.stepNotes", "step presentation IDs must be unique")

    presented: list[str] = []
    for group_index, group in enumerate(data["elementGroups"]):
        if group["scopeModelId"] is not None and model is not None and group["scopeModelId"] not in model_elements:
            report.error("HTML-DATA-010", f"$.elementGroups[{group_index}].scopeModelId", "unknown canonical element")
        for item_index, item in enumerate(group["elements"]):
            presented.append(item["modelId"])
            if model is not None and item["modelId"] not in model_elements:
                report.error("HTML-DATA-011", f"$.elementGroups[{group_index}].elements[{item_index}].modelId", "unknown canonical element")
    if duplicate_values(presented):
        report.warning("HTML-DATA-012", "$.elementGroups", "same canonical element appears in multiple presentation cards")

    for index, section in enumerate(data["audienceSections"]):
        path = f"$.audienceSections[{index}]"
        if session is not None and session["audienceMode"] != "both" and section["audience"] not in {"both", session["audienceMode"]}:
            report.warning("HTML-DATA-013", path + ".audience", "section is not for the selected audience mode")
        if model is not None:
            unknown = sorted(set(section["modelIds"]) - _all_canonical_ids(model))
            if unknown:
                report.error("HTML-DATA-014", path + ".modelIds", f"unknown canonical IDs: {unknown}")
        if not (section["claimIds"] or section["modelIds"] or section["issueIds"]):
            report.error("HTML-DATA-015", path, "factual audience section needs claimIds, modelIds, or issueIds")

    if not data["overview"]["claimIds"]:
        report.error("HTML-DATA-016", "$.overview.claimIds", "overview summary must map to at least one evidence claim")
    for key in ("benefits", "tradeoffs", "risks"):
        for index, item in enumerate(data["analysis"][key]):
            if not (item["claimIds"] or item["issueIds"]):
                report.error("HTML-DATA-017", f"$.analysis.{key}[{index}]", "analysis item needs a claim or coverage issue")

    if ledger is not None:
        unknown_claims = sorted(_report_claim_refs(data) - claim_ids)
        if unknown_claims:
            report.error("HTML-DATA-018", "$", f"unknown claim IDs: {unknown_claims}")
        else:
            report.pass_check("HTML-DATA-018", "HTML factual sections map to evidence claims", str(len(_report_claim_refs(data))))
    if coverage is not None:
        unknown_issues = sorted(_report_issue_refs(data) - issue_ids)
        if unknown_issues:
            report.error("HTML-DATA-019", "$", f"unknown coverage issue IDs: {unknown_issues}")

    if root is not None:
        for index, item in enumerate(data["build"]["expectedFiles"]):
            rel = item if isinstance(item, str) else item["path"]
            required = True if isinstance(item, str) else item["required"]
            try:
                path = safe_package_path(root, rel)
            except ValueError as exc:
                report.error("HTML-DATA-020", f"$.build.expectedFiles[{index}]", str(exc))
                continue
            if required and not path.is_file():
                report.error("HTML-DATA-021", f"$.build.expectedFiles[{index}]", f"required file does not exist: {rel}")
            elif not required and not path.is_file():
                report.warning("HTML-DATA-022", f"$.build.expectedFiles[{index}]", f"optional file does not exist: {rel}")

    if not report.errors:
        report.pass_check("HTML-DATA-001", "Presentation data resolves canonical IDs without redefining canonical facts")
    return report


EXTERNAL_HTML_PATTERNS = [
    re.compile(r"<script\b[^>]*\bsrc\s*=\s*['\"]https?://", re.I),
    re.compile(r"<link\b[^>]*\bhref\s*=\s*['\"]https?://", re.I),
    re.compile(r"@import\s+(?:url\()?['\"]?https?://", re.I),
    re.compile(r"<img\b[^>]*\bsrc\s*=\s*['\"]https?://", re.I),
    re.compile(r"url\(\s*['\"]?https?://", re.I),
]


def validate_html_text(html_text: str, name: str = "index.html") -> ValidationReport:
    report = ValidationReport("html-static")
    for pattern in EXTERNAL_HTML_PATTERNS:
        if pattern.search(html_text):
            report.error("HTML-STATIC-001", name, "runtime external dependency detected")
    placeholders = re.findall(r"__REPORT_DATA_JSON__|\{\{[A-Z0-9_ -]+\}\}|__[A-Z0-9_]+__", html_text)
    if placeholders:
        report.error("HTML-STATIC-002", name, f"unresolved placeholders remain: {sorted(set(placeholders))[:10]}")
    if "javascript:" in html_text.lower():
        report.error("HTML-STATIC-003", name, "javascript: URL detected")
    lower = html_text.lower()
    if "<html" not in lower or "<meta charset=" not in lower:
        report.error("HTML-STATIC-004", name, "basic HTML document markers are missing")
    if not report.errors:
        report.pass_check("HTML-STATIC-001", "HTML is offline and has no unresolved template tokens")
    return report


def validate_svg(path: Path) -> ValidationReport:
    report = ValidationReport(f"svg:{path.name}")
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
        root = ET.fromstring(text)
    except (OSError, UnicodeError, ET.ParseError) as exc:
        report.error("SVG-001", str(path), f"invalid SVG: {exc}")
        return report
    lower = text.lower()
    if "<script" in lower or "javascript:" in lower:
        report.error("SVG-002", str(path), "script or javascript URL is not allowed")
    if "<foreignobject" in lower:
        report.error("SVG-003", str(path), "foreignObject is not allowed in embedded SVG")
    external = re.findall(r"(?:href|xlink:href|src)\s*=\s*['\"](https?://[^'\"]+)", text, flags=re.I)
    external += re.findall(r"url\(\s*['\"]?(https?://[^)'\"]+)", text, flags=re.I)
    if external:
        report.error("SVG-004", str(path), f"external SVG resources are not allowed: {external[:3]}")
    if "viewbox" not in {key.lower() for key in root.attrib}:
        report.warning("SVG-005", str(path), "SVG has no viewBox; responsive scaling may be poor")
    if not report.errors:
        report.pass_check("SVG-001", "SVG is parseable and self-contained", path.name)
    return report


def validate_package_manifest(root: Path, manifest: dict[str, Any], schema_path: Path,
                              manifest_path: Path | None = None) -> ValidationReport:
    report = schema_report("output-package-manifest", manifest, schema_path)
    if report.errors:
        return report
    banned_names = {".DS_Store"}
    banned_parts = {".git", "__pycache__", ".pytest_cache", ".mypy_cache"}
    banned_suffixes = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3"}

    listed_paths = [item["path"] for item in manifest["files"]]
    duplicates = sorted(duplicate_values(listed_paths))
    if duplicates:
        report.error("PKG-001", "$.files", f"duplicate manifest paths: {duplicates}")
    listed = set(listed_paths)

    excluded: set[str] = set()
    if manifest_path is not None:
        try:
            excluded.add(manifest_path.resolve().relative_to(root.resolve()).as_posix())
        except ValueError:
            pass
    if manifest["validation"]["reportPath"]:
        excluded.add(manifest["validation"]["reportPath"])

    actual: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            report.error("PKG-002", str(path), "symbolic links are not allowed")
            continue
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel in excluded:
            continue
        actual.add(rel)
        if path.name in banned_names or any(part in banned_parts for part in path.parts) or path.suffix.lower() in banned_suffixes:
            report.error("PKG-003", rel, "temporary, cache, VCS, or database file is not allowed")

    for index, item in enumerate(manifest["files"]):
        rel = item["path"]
        try:
            path = safe_package_path(root, rel)
        except ValueError as exc:
            report.error("PKG-004", f"$.files[{index}].path", str(exc))
            continue
        if not path.is_file():
            report.error("PKG-005", rel, "manifest file does not exist")
            continue
        if path.stat().st_size != item["bytes"]:
            report.error("PKG-006", rel, f"byte size mismatch: manifest={item['bytes']}, actual={path.stat().st_size}")
        if sha256_file(path) != item["sha256"]:
            report.error("PKG-007", rel, "SHA-256 mismatch")

    unlisted = sorted(actual - listed)
    missing = sorted(listed - actual)
    if unlisted:
        report.error("PKG-008", "$", f"unlisted package files: {unlisted}")
    if missing:
        report.error("PKG-009", "$", f"manifest lists files not present in package scan: {missing}")

    try:
        entry = safe_package_path(root, manifest["entryPoint"])
    except ValueError as exc:
        report.error("PKG-010", "$.entryPoint", str(exc))
        entry = None
    if entry is not None and not entry.is_file():
        report.error("PKG-011", "$.entryPoint", "entry point does not exist")
    elif entry is not None and entry.suffix.lower() == ".html":
        report.merge(validate_html_text(entry.read_text(encoding="utf-8", errors="replace"), manifest["entryPoint"]))

    for key, rel in manifest["paths"].items():
        if rel is None:
            continue
        try:
            path = safe_package_path(root, rel)
        except ValueError as exc:
            report.error("PKG-012", f"$.paths.{key}", str(exc))
            continue
        if not path.is_file():
            report.error("PKG-013", f"$.paths.{key}", f"declared path does not exist: {rel}")
    if not report.errors:
        report.pass_check("PKG-001", "Manifest hashes, inventory, entry point, and package hygiene are valid", str(len(listed)))
    return report




def _matches_forbidden(relative: str, patterns: Iterable[str]) -> str | None:
    path = Path(relative)
    candidates = [relative, path.name, *path.parts]
    for pattern in patterns:
        if any(fnmatch.fnmatch(candidate, pattern) for candidate in candidates):
            return pattern
    return None


def _skill_frontmatter_name(skill_path: Path) -> str | None:
    try:
        text = skill_path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, flags=re.S)
    if not match:
        return None
    name_match = re.search(r"^name:\s*([^\s#]+)\s*$", match.group(1), flags=re.M)
    return name_match.group(1).strip() if name_match else None


def validate_skill_package_manifest(root: Path, manifest: dict[str, Any], schema_path: Path,
                                    manifest_path: Path | None = None) -> ValidationReport:
    """Validate the installable c4-archi-model skill directory itself."""
    report = schema_report("skill-package-manifest", manifest, schema_path)
    if report.errors:
        return report

    root = root.resolve()
    manifest_path = (manifest_path or root / "manifest.json").resolve()
    try:
        manifest_rel = manifest_path.relative_to(root).as_posix()
    except ValueError:
        report.error("SKPKG-001", "$.manifest", "manifest must be inside skill package root")
        manifest_rel = "manifest.json"

    entrypoint = manifest["entrypoint"]
    try:
        entry_path = safe_package_path(root, entrypoint)
    except ValueError as exc:
        report.error("SKPKG-002", "$.entrypoint", str(exc))
        entry_path = None
    if entry_path is None or not entry_path.is_file():
        report.error("SKPKG-003", "$.entrypoint", f"entrypoint does not exist: {entrypoint}")
    elif _skill_frontmatter_name(entry_path) != manifest["packageName"]:
        report.error("SKPKG-004", "SKILL.md", "frontmatter name does not match packageName")
    else:
        report.pass_check("SKPKG-004", "SKILL frontmatter name matches package name", manifest["packageName"])

    version_path = root / "VERSION"
    if not version_path.is_file():
        report.error("SKPKG-005", "VERSION", "VERSION file is missing")
    else:
        version = version_path.read_text(encoding="utf-8").strip()
        if version != manifest["version"]:
            report.error("SKPKG-006", "VERSION", f"version mismatch: manifest={manifest['version']}, VERSION={version}")
        elif not (root / "CHANGELOG.md").read_text(encoding="utf-8", errors="replace").find(f"## {version}") >= 0:
            report.error("SKPKG-007", "CHANGELOG.md", f"release heading for {version} is missing")
        else:
            report.pass_check("SKPKG-005", "VERSION, manifest, and changelog agree", version)

    required = set(manifest["requiredFiles"])
    if manifest_rel not in required:
        report.error("SKPKG-008", "$.requiredFiles", f"manifest must list itself as required: {manifest_rel}")
    for relative in sorted(required):
        try:
            path = safe_package_path(root, relative)
        except ValueError as exc:
            report.error("SKPKG-009", "$.requiredFiles", str(exc))
            continue
        if not path.is_file():
            report.error("SKPKG-010", relative, "required file is missing")

    listed_paths = [item["path"] for item in manifest["files"]]
    duplicates = sorted(duplicate_values(listed_paths))
    if duplicates:
        report.error("SKPKG-011", "$.files", f"duplicate manifest paths: {duplicates}")
    if manifest_rel in listed_paths:
        report.error("SKPKG-012", "$.files", "manifest.json must not hash itself")
    listed = set(listed_paths)

    actual: set[str] = set()
    forbidden_patterns = manifest["forbiddenPatterns"]
    for path in root.rglob("*"):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            report.error("SKPKG-013", rel, "symbolic links are not allowed")
            continue
        if not path.is_file() or rel == manifest_rel:
            continue
        actual.add(rel)
        matched = _matches_forbidden(rel, forbidden_patterns)
        if matched:
            report.error("SKPKG-014", rel, f"forbidden package pattern matched: {matched}")

    for index, item in enumerate(manifest["files"]):
        rel = item["path"]
        try:
            path = safe_package_path(root, rel)
        except ValueError as exc:
            report.error("SKPKG-015", f"$.files[{index}].path", str(exc))
            continue
        if not path.is_file():
            report.error("SKPKG-016", rel, "manifest file does not exist")
            continue
        if path.stat().st_size != item["size"]:
            report.error("SKPKG-017", rel, f"size mismatch: manifest={item['size']}, actual={path.stat().st_size}")
        if sha256_file(path) != item["sha256"]:
            report.error("SKPKG-018", rel, "SHA-256 mismatch")

    unlisted = sorted(actual - listed)
    missing = sorted(listed - actual)
    if unlisted:
        report.error("SKPKG-019", "$.files", f"unlisted skill files: {unlisted}")
    if missing:
        report.error("SKPKG-020", "$.files", f"manifest lists missing files: {missing}")

    if not manifest["agentIndependent"] or manifest["runtime"]["externalPackagesRequired"]:
        report.error("SKPKG-021", "$", "skill package must remain agent-independent and dependency-free")

    python_errors: list[str] = []
    for path in sorted((root / "scripts").glob("*.py")):
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except (OSError, SyntaxError) as exc:
            python_errors.append(f"{path.name}: {exc}")
    if python_errors:
        report.error("SKPKG-022", "scripts", f"Python syntax errors: {python_errors}")
    else:
        report.pass_check("SKPKG-022", "Python scripts compile", str(len(list((root / 'scripts').glob('*.py')))))

    if not report.errors:
        report.pass_check("SKPKG-001", "Skill manifest, hashes, required files, version, and hygiene are valid", str(len(listed)))
    return report


def _load_bundle_file(root: Path, relative: str | None, key: str, required: bool,
                      report: ValidationReport) -> dict[str, Any] | None:
    if relative is None:
        if required:
            report.error("BUNDLE-001", f"$.build.{key}", "required bundle path is null")
        return None
    try:
        path = safe_package_path(root, relative)
    except ValueError as exc:
        report.error("BUNDLE-002", f"$.build.{key}", str(exc))
        return None
    if not path.is_file():
        if required:
            report.error("BUNDLE-003", f"$.build.{key}", f"required file does not exist: {relative}")
        else:
            report.warning("BUNDLE-004", f"$.build.{key}", f"optional file does not exist: {relative}")
        return None
    try:
        return load_json(path)
    except (OSError, ValueError, RuntimeError) as exc:
        report.error("BUNDLE-005", f"$.build.{key}", str(exc))
        return None


def bundle_reports(root: Path, skill_root: Path, report_data: dict[str, Any]) -> tuple[dict[str, dict[str, Any] | None], list[ValidationReport]]:
    refs = skill_root / "references"
    report_schema = schema_report("html-report-data", report_data, refs / "html-report-data.schema.json")
    if report_schema.errors:
        return {"session": None, "model": None, "ledger": None, "coverage": None, "understanding": None}, [report_schema]

    load_report = ValidationReport("bundle-load")
    build = report_data["build"]
    bundle = {
        "session": _load_bundle_file(root, build["sessionPath"], "sessionPath", True, load_report),
        "model": _load_bundle_file(root, build["canonicalModelPath"], "canonicalModelPath", True, load_report),
        "ledger": _load_bundle_file(root, build["evidenceLedgerPath"], "evidenceLedgerPath", True, load_report),
        "coverage": _load_bundle_file(root, build["coveragePath"], "coveragePath", True, load_report),
        "understanding": _load_bundle_file(root, build["understandingPath"], "understandingPath", False, load_report),
    }
    reports: list[ValidationReport] = [load_report]
    session = bundle["session"]
    model = bundle["model"]
    ledger = bundle["ledger"]
    coverage = bundle["coverage"]
    understanding = bundle["understanding"]
    if session is not None:
        reports.append(validate_session(session, refs / "architecture-session.schema.json", model))
    if model is not None:
        reports.append(validate_model(model, refs / "architecture-model.schema.json", ledger))
    if ledger is not None:
        reports.append(validate_ledger(ledger, refs / "evidence-ledger.schema.json", model, session))
    if coverage is not None:
        reports.append(validate_coverage(coverage, refs / "coverage.schema.json", model, ledger, session))
    if understanding is not None:
        reports.append(validate_understanding(understanding, refs / "human-understanding.schema.json", session, model, ledger))
    reports.append(validate_report_data(report_data, refs / "html-report-data.schema.json", root=root, session=session, model=model, ledger=ledger, coverage=coverage, understanding=understanding))
    return bundle, reports
