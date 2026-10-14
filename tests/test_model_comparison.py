"""D10 변경 전후 아키텍처 비교: 비교 스크립트·검증기·하이드레이션·보고서 보기.

정규 모델만 의미 진실 — 비교는 두 입력에 있는 것만 담고 원본을 수정하지 않는다.
브라우저 테스트는 로컬 Chrome+Playwright가 있을 때만 실행된다(기존 관례).
"""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from build_html_report import hydrate_report, inject  # noqa: E402 (repo-local scripts)
from c4_validation import (  # noqa: E402
    ValidationReport,
    bundle_reports,
    load_json,
    schema_report,
    validate_model_comparison,
)
from compare_architecture_models import compare_models  # noqa: E402
from test_report_story import CHROME, sync_playwright  # noqa: E402

REFS = ROOT / "references"
EXAMPLES = ROOT / "examples"


def make_element(element_id: str, element_type: str, parent: str | None = None, **overrides: Any) -> dict[str, Any]:
    element = {"id": element_id, "type": element_type, "name": element_id, "description": f"{element_id} 설명",
               "technology": None, "parentId": parent, "environment": None, "tags": [],
               "derivation": "explicit", "confidence": "DOC_ONLY", "rationale": None,
               "claimIds": [], "instanceOfId": None}
    element.update(overrides)
    return element


def make_relationship(rel_id: str, source: str, destination: str, **overrides: Any) -> dict[str, Any]:
    rel = {"id": rel_id, "sourceId": source, "destinationId": destination,
           "description": f"{rel_id} 설명", "technology": None, "interactionStyle": "synchronous",
           "derivation": "explicit", "confidence": "DOC_ONLY", "rationale": None, "claimIds": []}
    rel.update(overrides)
    return rel


def make_view(view_id: str, elements: list[str], relationships: list[str], scope: str | None = "sys") -> dict[str, Any]:
    return {"id": view_id, "type": "container", "title": f"{view_id} 제목", "scopeId": scope,
            "environment": None, "description": None, "question": "질문", "notShown": [],
            "elementIds": elements, "relationshipIds": relationships, "steps": [],
            "nextViewIds": [], "claimIds": []}


def make_model(elements: list[dict], relationships: list[dict], views: list[dict], revision: str = "1") -> dict[str, Any]:
    return {"metadata": {"title": "테스트 시스템", "description": None, "targetSystemId": None,
                         "schemaVersion": "0.4.0", "modelRevision": revision,
                         "generatorVersion": "test", "generatedAt": None, "sourceSnapshotId": None},
            "elements": elements, "relationships": relationships, "views": views}


def base_models() -> tuple[dict[str, Any], dict[str, Any]]:
    """요소 이동·변경, 관계 반전·재연결, 그림 밖 변경을 모두 담은 최소 전·후 쌍."""
    before = make_model(
        [make_element("sys", "softwareSystem"),
         make_element("old-sys", "softwareSystem", name="Old System"),
         make_element("web", "container", "sys", name="Order Web"),
         make_element("db", "container", "old-sys"),
         make_element("batch", "container", "sys"),
         make_element("extra", "person")],
        [make_relationship("keep", "web", "db"),
         make_relationship("reverse", "web", "db"),
         make_relationship("redirect", "web", "batch"),
         make_relationship("gone", "batch", "db"),
         make_relationship("reused", "batch", "db")],
        [make_view("v0", ["web", "db", "batch"], ["keep", "reverse", "redirect", "gone"])],
        revision="0")
    after = make_model(
        [make_element("sys", "softwareSystem"),
         make_element("web", "container", "sys", name="Web App"),
         make_element("db", "container", "sys"),
         make_element("api", "container", "sys")],
        [make_relationship("keep", "web", "db"),
         make_relationship("reverse", "db", "web"),
         make_relationship("redirect", "web", "api"),
         make_relationship("fresh", "api", "db"),
         make_relationship("reused", "api", "web")],
        [make_view("v1", ["web", "db", "api"], ["keep", "reverse", "redirect", "fresh"])],
        revision="1")
    return before, after


class CompareModelsTests(unittest.TestCase):
    def test_classification_covers_all_documented_kinds(self) -> None:
        result = compare_models(*base_models(), before_path="b.json", after_path="a.json")
        by_id = {change["id"]: change for change in result["changes"]}
        self.assertEqual(by_id["api"]["kind"], "added")
        self.assertEqual(by_id["api"]["target"], "element")
        self.assertIsNone(by_id["api"]["before"])
        self.assertEqual(by_id["batch"]["kind"], "removed")
        self.assertIsNone(by_id["batch"]["after"])
        self.assertEqual(by_id["db"]["kind"], "moved")
        self.assertIn("parentId", [field["field"] for field in by_id["db"]["changedFields"]])
        self.assertEqual(by_id["web"]["kind"], "modified")
        self.assertEqual([field["field"] for field in by_id["web"]["changedFields"]], ["name"])
        self.assertEqual(by_id["web"]["changedFields"][0]["before"], "Order Web")
        self.assertEqual(by_id["web"]["changedFields"][0]["after"], "Web App")
        self.assertEqual(by_id["fresh"]["kind"], "added")
        self.assertEqual(by_id["gone"]["kind"], "removed")
        self.assertEqual((by_id["reverse"]["kind"], by_id["reverse"]["subtype"]), ("rewired", "reversed"))
        self.assertEqual((by_id["redirect"]["kind"], by_id["redirect"]["subtype"]), ("rewired", "redirected"))

    def test_unmatched_and_uncertain_propagation(self) -> None:
        before, after = base_models()
        # 같은 ID의 type이 person → container로 바뀌면 미확정(불일치).
        after["elements"].append(make_element("extra", "container", "sys"))
        # extra로 이동하는 요소: 상위가 미확정 요소면 이동도 미확정.
        after["elements"].append(make_element("child", "codeElement" if False else "component", "extra"))
        after["elements"][-1]["type"] = "component"
        before["elements"].append(make_element("child", "component", "batch"))
        result = compare_models(before, after)
        by_id = {change["id"]: change for change in result["changes"]}
        self.assertEqual(by_id["extra"]["kind"], "unmatched")
        self.assertTrue(by_id["extra"]["uncertain"])
        self.assertEqual(by_id["child"]["kind"], "moved")
        self.assertTrue(by_id["child"]["uncertain"])
        self.assertTrue(any("ID 불일치" in reason for reason in by_id["child"]["uncertainReasons"]))
        # 출발·도착이 모두 바뀐 관계는 미확정 — 재연결로 단정하지 않는다.
        self.assertEqual(by_id["reused"]["kind"], "unmatched")
        self.assertTrue(by_id["reused"]["uncertain"])
        self.assertGreater(len(by_id["reused"]["uncertainReasons"]), 0)

    def test_summary_counts_and_identical_models_report_no_changes(self) -> None:
        before, after = base_models()
        result = compare_models(before, after)
        summary = result["summary"]
        self.assertEqual(summary["elementAdded"], 1)
        self.assertEqual(summary["elementRemoved"], 3)  # old-sys, batch, extra(불일치 아님: before에만)
        self.assertEqual(summary["elementMoved"], 1)
        self.assertEqual(summary["elementModified"], 1)
        self.assertEqual(summary["relationshipAdded"], 1)
        self.assertEqual(summary["relationshipRemoved"], 1)
        self.assertEqual(summary["relationshipChanged"], 2)
        self.assertEqual(summary["unchangedElements"], 1)  # sys
        self.assertEqual(summary["unchangedRelationships"], 1)  # keep
        identical = compare_models(before, before)
        self.assertEqual(identical["changes"], [])
        self.assertEqual(identical["summary"]["unchangedElements"], len(before["elements"]))
        self.assertEqual(identical["summary"]["unchangedRelationships"], len(before["relationships"]))

    def test_view_refs_keep_out_of_figure_changes_visible(self) -> None:
        before, after = base_models()
        result = compare_models(before, after)
        by_id = {change["id"]: change for change in result["changes"]}
        # old-sys는 어느 뷰에도 없다 — 그림 밖 변경. 표에서 사라지지 않는다.
        self.assertEqual(by_id["old-sys"]["viewRefs"], [])
        phases = [(ref["viewId"], ref["phase"]) for ref in by_id["db"]["viewRefs"]]
        self.assertIn(("v0", "before"), phases)
        self.assertIn(("v1", "after"), phases)
        titles = {ref["title"] for ref in by_id["db"]["viewRefs"]}
        self.assertIn("v0 제목", titles)

    def test_output_matches_comparison_schema(self) -> None:
        result = compare_models(*base_models())
        report = schema_report("comparison", result, REFS / "architecture-model-comparison.schema.json")
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_descriptions_are_korean_sentences(self) -> None:
        result = compare_models(*base_models())
        for change in result["changes"]:
            self.assertIsInstance(change["description"], str)
            self.assertGreater(len(change["description"]), 10)


class CompareCliTests(unittest.TestCase):
    def test_cli_writes_artifact_and_never_touches_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            before_path = tmp_path / "before.json"
            after_path = tmp_path / "after.json"
            output_path = tmp_path / "comparison.json"
            before, after = base_models()
            before_path.write_text(json.dumps(before, ensure_ascii=False), encoding="utf-8")
            after_path.write_text(json.dumps(after, ensure_ascii=False), encoding="utf-8")
            hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (before_path, after_path)}
            completed = subprocess.run(
                [sys.executable, "-B", str(ROOT / "scripts" / "compare_architecture_models.py"),
                 "--before", str(before_path), "--after", str(after_path), "--output", str(output_path)],
                capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(output_path.is_file())
            artifact = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact["matchBasis"], "canonicalId")
            self.assertEqual(artifact["before"]["modelRevision"], "0")
            self.assertEqual(artifact["after"]["modelRevision"], "1")
            # 원본 무변경 — 입력 파일은 한 바이트도 바뀌지 않는다.
            for path, digest in hashes.items():
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)

    def test_cli_rejects_invalid_input_and_same_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            before_path = tmp_path / "before.json"
            after_path = tmp_path / "after.json"
            before, _ = base_models()
            before["elements"][0].pop("type")  # 스키마 위반
            before_path.write_text(json.dumps(before, ensure_ascii=False), encoding="utf-8")
            after_path.write_text(json.dumps(make_model([], [], [])), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "-B", str(ROOT / "scripts" / "compare_architecture_models.py"),
                 "--before", str(before_path), "--after", str(after_path),
                 "--output", str(tmp_path / "out.json")], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 1)
            self.assertFalse((tmp_path / "out.json").exists())
            same = subprocess.run(
                [sys.executable, "-B", str(ROOT / "scripts" / "compare_architecture_models.py"),
                 "--before", str(after_path), "--after", str(after_path),
                 "--output", str(tmp_path / "out.json")], capture_output=True, text=True)
            self.assertEqual(same.returncode, 1)


class ComparisonValidatorTests(unittest.TestCase):
    def load_example(self) -> dict[str, Any]:
        return load_json(EXAMPLES / "ordering-system.architecture-comparison.json")

    def test_example_comparison_passes_with_model(self) -> None:
        model = load_json(EXAMPLES / "ordering-system.architecture-model.json")
        report = validate_model_comparison(self.load_example(), REFS / "architecture-model-comparison.schema.json", model)
        self.assertEqual(report.errors, [])

    def test_summary_mismatch_trips_cmp_002(self) -> None:
        data = self.load_example()
        data["summary"]["elementAdded"] += 1
        report = validate_model_comparison(data, REFS / "architecture-model-comparison.schema.json")
        codes = {finding.code for finding in report.errors}
        self.assertIn("CMP-002", codes)

    def test_snapshot_presence_and_subtype_rules(self) -> None:
        data = self.load_example()
        added = next(change for change in data["changes"] if change["kind"] == "added")
        added["before"] = copy.deepcopy(added["after"])  # added는 before가 null이어야 한다
        rewired = next(change for change in data["changes"] if change["kind"] == "rewired")
        rewired["subtype"] = None  # rewired는 subtype이 필요하다
        modified = next(change for change in data["changes"] if change["kind"] == "modified")
        modified["changedFields"] = []  # modified는 필드 목록이 필요하다
        report = validate_model_comparison(data, REFS / "architecture-model-comparison.schema.json")
        codes = {finding.code for finding in report.errors}
        self.assertIn("CMP-003", codes)
        self.assertIn("CMP-005", codes)
        self.assertIn("CMP-006", codes)

    def test_unmatched_requires_uncertainty(self) -> None:
        data = self.load_example()
        unmatched = next(change for change in data["changes"] if change["kind"] == "unmatched")
        unmatched["uncertain"] = False
        report = validate_model_comparison(data, REFS / "architecture-model-comparison.schema.json")
        self.assertIn("CMP-004", {finding.code for finding in report.errors})

    def test_after_side_ids_must_resolve_in_report_model(self) -> None:
        data = self.load_example()
        data["changes"][0]["id"] = "ghost-element"  # after 측 스냅샷이 있는 변경
        report = validate_model_comparison(
            data, REFS / "architecture-model-comparison.schema.json",
            load_json(EXAMPLES / "ordering-system.architecture-model.json"))
        self.assertIn("CMP-008", {finding.code for finding in report.errors})

    def test_after_phase_view_ref_must_contain_target(self) -> None:
        data = self.load_example()
        moved = next(change for change in data["changes"] if change["kind"] == "moved")
        moved["viewRefs"].append({"viewId": "ordering-context", "title": "Context", "phase": "after"})
        report = validate_model_comparison(
            data, REFS / "architecture-model-comparison.schema.json",
            load_json(EXAMPLES / "ordering-system.architecture-model.json"))
        self.assertIn("CMP-008", {finding.code for finding in report.errors})

    def test_bundle_loads_comparison_when_path_present(self) -> None:
        report_data = load_json(EXAMPLES / "html-report-data.example.json")
        bundle, reports = bundle_reports(ROOT, ROOT, report_data)
        self.assertIsNotNone(bundle.get("comparison"))
        combined = ValidationReport("combined")
        for item in reports:
            combined.merge(item)
        error_codes = {finding.code for finding in combined.errors}
        self.assertNotIn("CMP-002", error_codes)
        # 비교 경로를 없애면 번들에 비교가 없어도 기존 검증이 그대로 돈다.
        report_data["build"].pop("comparisonPath")
        bundle_without, _ = bundle_reports(ROOT, ROOT, report_data)
        self.assertIsNone(bundle_without.get("comparison"))


class HydrationTests(unittest.TestCase):
    def bundle_fixture(self, comparison: dict[str, Any] | None) -> dict[str, Any]:
        return {"session": {}, "model": {"elements": [], "relationships": [], "views": []},
                "ledger": {"sources": [], "claims": []},
                "coverage": {"completion": {"result": "NOT_RUN", "reason": "test"}},
                "understanding": None, "comparison": comparison}

    def minimal_report_data(self) -> dict[str, Any]:
        return {"meta": {}, "analysis": {}, "flows": [], "diagrams": [], "elementGroups": [],
                "glossary": [], "artifacts": [], "issueRefs": [], "overview": {},
                "audienceSections": [], "build": {}}

    def test_comparison_is_passed_through_without_invention(self) -> None:
        comparison = compare_models(*base_models())
        data = self.minimal_report_data()
        before = copy.deepcopy(data)
        result = hydrate_report(data, self.bundle_fixture(comparison), ValidationReport("test"))
        self.assertEqual(result["modelComparison"], comparison)
        self.assertEqual(data, before)  # 비교가 입력 데이터를 바꾸지 않는다

    def test_absent_comparison_keeps_report_unchanged(self) -> None:
        data = self.minimal_report_data()
        result = hydrate_report(data, self.bundle_fixture(None), ValidationReport("test"))
        self.assertNotIn("modelComparison", result)


@unittest.skipUnless(sync_playwright and Path(CHROME).is_file(), "local Chrome and Playwright required")
class ComparisonBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=CHROME, headless=True)
        cls.template = (ROOT / "assets" / "html-report-template.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.pw.stop()

    def setUp(self) -> None:
        self.page = self.browser.new_page(viewport={"width": 1440, "height": 1000}, offline=True)
        self.errors: list[str] = []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.page.close()
        self.tmp.cleanup()

    def write_report(self, comparison: dict[str, Any] | None) -> None:
        data = {"meta": {}, "analysis": {}, "flows": [], "diagrams": [], "elementGroups": [],
                "glossary": [], "artifacts": [], "issueRefs": [], "overview": {},
                "audienceSections": [], "build": {}}
        bundle = {"session": {}, "model": {"elements": [], "relationships": [], "views": []},
                  "ledger": {"sources": [], "claims": []},
                  "coverage": {"completion": {"result": "NOT_RUN", "reason": "test"}},
                  "understanding": None, "comparison": comparison}
        hydrated = hydrate_report(data, bundle, ValidationReport("test"))
        path = Path(self.tmp.name) / "report.html"
        path.write_text(inject(self.template, hydrated), encoding="utf-8")
        self.page.goto(path.as_uri())

    def test_comparison_view_shows_legend_table_and_out_of_figure_changes(self) -> None:
        comparison = compare_models(*base_models(), before_path="before.json", after_path="after.json")
        self.write_report(comparison)
        self.page.locator("#comparison").scroll_into_view_if_needed()
        self.assertFalse(self.page.locator("#comparison").is_hidden())
        # 범례는 색 + 기호 + 한글 라벨을 함께 제공한다(색상만으로 구분하지 않는다).
        chips = self.page.locator("#comparison .cmp-legend .cmp-chip").all_inner_texts()
        self.assertEqual(len(chips), 5)
        for symbol, label in (("＋", "추가"), ("－", "삭제"), ("⇄", "이동"), ("✎", "변경"), ("？", "미확정")):
            self.assertTrue(any(symbol in chip and label in chip for chip in chips), chips)
        # 표는 완전 목록 — 어느 뷰에도 없는 old-sys 변경도 그림 밖 표시로 남는다.
        rows = self.page.locator("#cmp-table tbody tr").count()
        self.assertEqual(rows, len(comparison["changes"]))
        outside_row = self.page.locator("#cmp-table tr[data-change-id='old-sys']")
        self.assertEqual(outside_row.locator(".cmp-outside").count(), 1)
        self.assertIn("그림 밖", outside_row.inner_text())
        # 미확정 행은 사유를 함께 표시한다.
        unmatched_row = self.page.locator("#cmp-table tr[data-kind='unmatched']").first
        self.assertIn("미확정", unmatched_row.inner_text())
        # 미확정 안내 콜아웃이 있다.
        self.assertGreaterEqual(self.page.locator("#comparison .callout").count(), 1)
        # 모바일 375px에서 표가 페이지를 가로로 깨지 않는다.
        self.page.set_viewport_size({"width": 375, "height": 900})
        self.page.locator("#comparison").scroll_into_view_if_needed()
        overflow = self.page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        self.assertLessEqual(overflow, 0)
        self.assertEqual(self.errors, [])

    def test_report_without_comparison_section_stays_hidden(self) -> None:
        self.write_report(None)
        self.assertTrue(self.page.locator("#comparison").is_hidden())
        self.assertEqual(self.page.locator("#top-nav a[href='#comparison']").count(), 0)
        self.assertEqual(self.page.locator("#cmp-table").count(), 0)
        self.assertEqual(self.errors, [])


if __name__ == "__main__":
    unittest.main()
