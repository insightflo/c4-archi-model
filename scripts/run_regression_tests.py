#!/usr/bin/env python3
"""Adversarial regression tests for c4-archi-model validators and strict builder."""
from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True

import argparse
import copy
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from c4_validation import (
    ValidationReport,
    aggregate_reports,
    bundle_reports,
    load_json,
    validate_ledger,
    validate_model,
    validate_report_data,
    validate_svg,
)

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
EXAMPLES = SKILL_ROOT / "examples"
REFS = SKILL_ROOT / "references"


@dataclass
class TestResult:
    name: str
    passed: bool
    expected: str
    observed: str
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "passed": self.passed,
            "expected": self.expected,
            "observed": self.observed,
            "detail": self.detail,
        }


def codes(report: ValidationReport) -> set[str]:
    return {item.code for item in report.findings if item.severity == "ERROR"}


def expect_code(name: str, report: ValidationReport, expected_code: str) -> TestResult:
    found = sorted(codes(report))
    return TestResult(
        name=name,
        passed=expected_code in found,
        expected=expected_code,
        observed=", ".join(found) or "no error",
    )


def load_bundle() -> tuple[dict, dict, dict, dict, dict, dict]:
    session = load_json(EXAMPLES / "ordering-system.architecture-session.json")
    model = load_json(EXAMPLES / "ordering-system.architecture-model.json")
    ledger = load_json(EXAMPLES / "ordering-system.evidence-ledger.json")
    coverage = load_json(EXAMPLES / "ordering-system.coverage.json")
    understanding = load_json(EXAMPLES / "ordering-system.human-understanding.json")
    report_data = load_json(EXAMPLES / "html-report-data.example.json")
    return session, model, ledger, coverage, understanding, report_data


def baseline_test() -> TestResult:
    report_data = load_json(EXAMPLES / "html-report-data.example.json")
    _, reports = bundle_reports(SKILL_ROOT, SKILL_ROOT, report_data)
    combined = aggregate_reports("baseline", reports)
    return TestResult(
        name="valid-baseline",
        passed=not combined.errors,
        expected="PASS",
        observed=combined.result,
        detail=f"errors={len(combined.errors)}, warnings={len(combined.warnings)}",
    )


def model_mutation_test(name: str, mutate: Callable[[dict], None], expected_code: str) -> TestResult:
    _, model, ledger, _, _, _ = load_bundle()
    mutate(model)
    report = validate_model(model, REFS / "architecture-model.schema.json", ledger)
    return expect_code(name, report, expected_code)


def ledger_source_test() -> TestResult:
    session, model, ledger, _, _, _ = load_bundle()
    ledger["claims"][0]["supports"][0]["sourceId"] = "S404"
    report = validate_ledger(
        ledger,
        REFS / "evidence-ledger.schema.json",
        model,
        session,
    )
    return expect_code("unregistered-source", report, "EVD-008")


def report_mutation_test(name: str, mutate: Callable[[dict], None], expected_code: str) -> TestResult:
    session, model, ledger, coverage, understanding, report_data = load_bundle()
    mutate(report_data)
    report = validate_report_data(
        report_data,
        REFS / "html-report-data.schema.json",
        root=SKILL_ROOT,
        session=session,
        model=model,
        ledger=ledger,
        coverage=coverage,
        understanding=understanding,
    )
    return expect_code(name, report, expected_code)


def malicious_svg_test() -> TestResult:
    with tempfile.TemporaryDirectory(prefix="c4-svg-") as temp:
        path = Path(temp) / "malicious.svg"
        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
            '<script>alert(1)</script><image href="https://example.com/a.png"/>'
            '</svg>',
            encoding="utf-8",
        )
        report = validate_svg(path)
    found = codes(report)
    expected = {"SVG-002", "SVG-004"}
    return TestResult(
        name="malicious-svg",
        passed=expected.issubset(found),
        expected=", ".join(sorted(expected)),
        observed=", ".join(sorted(found)) or "no error",
    )


def strict_builder_test() -> TestResult:
    with tempfile.TemporaryDirectory(prefix="c4-builder-") as temp:
        temp_root = Path(temp)
        shutil.copytree(EXAMPLES, temp_root / "examples")
        model_path = temp_root / "examples/ordering-system.architecture-model.json"
        model = load_json(model_path)
        next(item for item in model["elements"] if item["id"] == "web-app")["parentId"] = "customer"
        model_path.write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        output = temp_root / "index.html"
        command = [
            sys.executable,
            str(SKILL_ROOT / "scripts/build_html_report.py"),
            "--root", str(temp_root),
            "--data", "examples/html-report-data.example.json",
            "--template", str(SKILL_ROOT / "assets/html-report-template.html"),
            "--output", str(output),
            "--skill-root", str(SKILL_ROOT),
        ]
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        passed = completed.returncode != 0 and not output.exists()
        detail = (completed.stdout + "\n" + completed.stderr).strip()[-1200:]
        return TestResult(
            name="strict-builder-rejection",
            passed=passed,
            expected="non-zero exit and no HTML",
            observed=f"exit={completed.returncode}, outputExists={output.exists()}",
            detail=detail,
        )


def run() -> list[TestResult]:
    results = [baseline_test()]
    results.append(model_mutation_test(
        "model-schema-violation",
        lambda model: next(item for item in model["relationships"] if item["id"] == "web-to-api").__setitem__("interactionStyle", "telepathy"),
        "SCHEMA-001",
    ))
    results.append(model_mutation_test(
        "bad-parent",
        lambda model: next(item for item in model["elements"] if item["id"] == "web-app").__setitem__("parentId", "customer"),
        "MOD-003",
    ))
    results.append(model_mutation_test(
        "missing-endpoint",
        lambda model: next(item for item in model["relationships"] if item["id"] == "web-to-api").__setitem__("destinationId", "ghost-api"),
        "MOD-007",
    ))
    results.append(model_mutation_test(
        "unknown-view-reference",
        lambda model: next(item for item in model["views"] if item["id"] == "ordering-container")["elementIds"].append("ghost-element"),
        "VIEW-001",
    ))

    def bad_order(model: dict) -> None:
        view = next(item for item in model["views"] if item["id"] == "ordering-create-order")
        view["steps"][1]["order"] = 3
    results.append(model_mutation_test("nonconsecutive-dynamic-order", bad_order, "VIEW-010"))

    results.append(ledger_source_test())
    results.append(report_mutation_test(
        "report-fact-redefinition",
        lambda report: report["elementGroups"][0]["elements"][0].__setitem__("name", "Fake Web App"),
        "SCHEMA-001",
    ))
    results.append(report_mutation_test(
        "unknown-report-model-id",
        lambda report: report["elementGroups"][0]["elements"][0].__setitem__("modelId", "ghost-container"),
        "HTML-DATA-011",
    ))
    results.append(malicious_svg_test())
    results.append(strict_builder_test())
    return results


def write_markdown(path: Path, results: list[TestResult]) -> None:
    lines = [
        "# c4-archi-model Regression Test Report",
        "",
        f"Result: **{'PASS' if all(item.passed for item in results) else 'FAIL'}**",
        "",
        "| Test | Expected | Observed | Result |",
        "|---|---|---|---|",
    ]
    for item in results:
        lines.append(f"| {item.name} | {item.expected} | {item.observed} | {'PASS' if item.passed else 'FAIL'} |")
    details = [item for item in results if item.detail]
    if details:
        lines.extend(["", "## Details", ""])
        for item in details:
            lines.extend([f"### {item.name}", "", "```text", item.detail, "```", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run adversarial regression tests")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    args = parser.parse_args()

    results = run()
    for item in results:
        print(f"[{'PASS' if item.passed else 'FAIL'}] {item.name}: expected={item.expected}; observed={item.observed}")
    payload = {
        "result": "PASS" if all(item.passed for item in results) else "FAIL",
        "tests": [item.to_dict() for item in results],
    }
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.output_md:
        write_markdown(args.output_md, results)
    return 0 if payload["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
