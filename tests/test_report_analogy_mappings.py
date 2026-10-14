"""A1 구성요소별 비유 대응표: 스키마·하이드레이션·렌더링·엄격 빌드.

- mappings의 modelId는 canonical 요소·관계 ID만 가리킨다(HTML-DATA-023).
- 빌더가 canonical 이름을 채워 비유가 모델 사실을 재정의하지 않게 한다.
- mappings가 없는 기존 데이터는 렌더링 결과가 그대로다(추가 DOM 노드 없음).
브라우저 케이스는 기존 테스트와 같은 선택적 로컬 Chrome/Playwright 설정을 쓴다.
"""
from __future__ import annotations

import base64
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_html_report import hydrate_report  # noqa: E402
from c4_validation import ValidationReport, schema_report, validate_report_data  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

CHROME = os.environ.get("C4_BROWSER") or shutil.which("chromium") or \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

SCHEMA_PATH = ROOT / "references/html-report-data.schema.json"


def mapped_fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    """stepNote·요소·용어집 세 표면에 mappings가 붙은 표현 데이터와 번들."""
    data = {"analysis": {}, "flows": [{"id": "story", "viewId": "scenario", "kind": "happy-path",
            "presentation": {"title": None, "description": None,
              "stepNotes": [{"stepId": "later", "explanation": "Full explanation",
                "attention": None, "analogy": "접수대에 주문서를 올리는 단계",
                "mappings": [
                    {"term": "주문서 전달", "modelId": "rel", "kind": "relationship",
                     "note": "종이가 아니라 요청이 이동한다"},
                    {"term": "접수대", "modelId": "receiver", "kind": "element"}],
                "limits": "접수대 위 주문서는 그대로 남지만 요청은 즉시 되돌아온다."}],
                "notes": []}}],
            "elementGroups": [{"id": "group", "title": "구성요소", "scopeModelId": None,
                "elements": [{"modelId": "receiver", "shortId": "E1",
                    "presentation": {"whyItMatters": "요청을 받는다", "withoutIt": None,
                        "analogy": "주문 접수 창구",
                        "mappings": [{"term": "주문 접수 창구", "modelId": "receiver",
                                      "kind": "element", "note": "받은 뒤 장부로 넘긴다"}],
                        "limits": "창구와 달리 동시에 여러 요청을 받는다.", "notes": []}}]}],
            "glossary": [{"term": "접수대", "definition": "요청이 잠시 머무는 자리.",
                "analogy": "주문서를 꽂아 두는 전달대",
                "mappings": [{"term": "전달대", "modelId": "order-board", "kind": "element"}],
                "limits": "전달 보장 정책은 기록에 없다."}]}
    bundle = {"session": {}, "understanding": None, "coverage": {},
        "model": {"elements": [{"id": "sender", "name": "Sender"},
                                {"id": "receiver", "name": "Receiver"},
                                {"id": "order-board", "name": "Order Board"}],
            "relationships": [{"id": "rel", "sourceId": "sender", "destinationId": "receiver",
                "description": "Sends request"}],
            "views": [{"id": "scenario", "title": "Scenario", "type": "dynamic", "steps": [
                {"id": "earlier", "order": 7, "relationshipId": "rel"},
                {"id": "later", "order": 40, "relationshipId": "rel"}]}]},
        "ledger": {"sources": [], "claims": []}}
    return data, bundle


class HydrationTests(unittest.TestCase):
    def test_mappings_get_canonical_names_in_all_three_surfaces(self) -> None:
        data, bundle = mapped_fixture()
        original = copy.deepcopy((data, bundle))
        result = hydrate_report(data, bundle, ValidationReport("story"))
        # 단계: 관계 대응은 '출발 → 도착' 이름으로, 요소 대응은 요소 이름으로.
        step = result["flows"][0]["steps"][1]
        self.assertEqual(step["analogy"], "접수대에 주문서를 올리는 단계")
        self.assertEqual(step["analogyLimits"], "접수대 위 주문서는 그대로 남지만 요청은 즉시 되돌아온다.")
        self.assertEqual([m["name"] for m in step["analogyMappings"]],
                         ["Sender → Receiver", "Receiver"])
        self.assertEqual([m["modelId"] for m in step["analogyMappings"]], ["rel", "receiver"])
        self.assertEqual(step["analogyMappings"][0]["note"], "종이가 아니라 요청이 이동한다")
        # 요소 카드: 원문 presentation.mappings는 hydrated 필드로만 전달된다.
        element = result["elementGroups"][0]["elements"][0]
        self.assertNotIn("mappings", element)
        self.assertEqual(element["analogyMappings"][0]["name"], "Receiver")
        self.assertEqual(element["analogyLimits"], "창구와 달리 동시에 여러 요청을 받는다.")
        # 용어집: 같은 구조로 바뀐다.
        term = result["glossary"][0]
        self.assertNotIn("mappings", term)
        self.assertEqual(term["analogyMappings"][0]["name"], "Order Board")
        self.assertEqual(term["analogyLimits"], "전달 보장 정책은 기록에 없다.")
        # 입력 데이터는 오염되지 않는다(기존 하이드레이션 계약).
        self.assertEqual((data, bundle), original)

    def test_absent_mappings_hydrate_without_new_dom_data(self) -> None:
        data, bundle = mapped_fixture()
        data["flows"][0]["presentation"]["stepNotes"][0].pop("mappings")
        data["flows"][0]["presentation"]["stepNotes"][0].pop("limits")
        data["elementGroups"][0]["elements"][0]["presentation"].pop("mappings")
        data["elementGroups"][0]["elements"][0]["presentation"].pop("limits")
        data["glossary"][0].pop("mappings")
        data["glossary"][0].pop("limits")
        result = hydrate_report(data, bundle, ValidationReport("story"))
        self.assertEqual(result["flows"][0]["steps"][1]["analogyMappings"], [])
        self.assertIsNone(result["flows"][0]["steps"][1]["analogyLimits"])
        self.assertEqual(result["elementGroups"][0]["elements"][0]["analogyMappings"], [])
        self.assertNotIn("analogyMappings", result["glossary"][0])


class ValidatorTests(unittest.TestCase):
    def full_document(self, flows: list, element_groups: list, glossary: list) -> dict[str, Any]:
        return {"schemaVersion": "0.4.0", "meta": {"language": "ko", "titleOverride": None,
                "generatedAt": "2026-10-14T00:00:00Z"},
                "build": {"sessionPath": "s", "canonicalModelPath": "m", "evidenceLedgerPath": "l",
                          "coveragePath": "c", "understandingPath": None, "expectedFiles": []},
                "overview": {"problem": "p", "oneSentence": "s", "scopeSummary": "s",
                             "readingOrder": ["r"], "claimIds": ["CL-1"]},
                "diagrams": [], "flows": flows, "elementGroups": element_groups,
                "audienceSections": [], "analysis": {"benefits": [], "tradeoffs": [], "risks": []},
                "issueRefs": [], "glossary": glossary, "artifacts": []}

    def validate(self, data: dict[str, Any]) -> ValidationReport:
        _, bundle = mapped_fixture()
        full = self.full_document(data["flows"], data["elementGroups"], data["glossary"])
        return validate_report_data(full, SCHEMA_PATH, model=bundle["model"], ledger=None)

    def test_valid_mappings_pass_and_unknown_ids_fail(self) -> None:
        data, _ = mapped_fixture()
        report = self.validate(data)
        self.assertFalse(report.errors, [f"{f.code} {f.path}" for f in report.errors])
        self.assertIn("HTML-DATA-023", [c.id for c in report.checks if c.result == "PASS"])

        data, _ = mapped_fixture()
        data["glossary"][0]["mappings"][0]["modelId"] = "ghost-element"
        report = self.validate(data)
        self.assertIn("HTML-DATA-023", [f.code for f in report.errors if f.code == "HTML-DATA-023"])

        data, _ = mapped_fixture()
        # 요소 ID를 관계 kind로 속여도 거부한다 — kind와 실제 대상이 일치해야 한다.
        data["glossary"][0]["mappings"][0]["kind"] = "relationship"
        report = self.validate(data)
        self.assertTrue(any(f.code == "HTML-DATA-023" for f in report.errors))

        data, _ = mapped_fixture()
        data["flows"][0]["presentation"]["stepNotes"][0]["mappings"][0]["modelId"] = "no-such-rel"
        report = self.validate(data)
        self.assertTrue(any(f.code == "HTML-DATA-023" for f in report.errors))

    def test_analogy_only_data_passes_schema_unchanged(self) -> None:
        # 기존 analogy 문장만 있는 데이터는 새 선택 필드 없이 그대로 통과한다.
        step_only = self.full_document(
            [{"id": "story", "viewId": "scenario", "kind": "happy-path",
              "presentation": {"title": None, "description": None,
                "stepNotes": [{"stepId": "later", "explanation": None, "attention": None,
                               "analogy": "비유 문장"}], "notes": []}}], [], [])
        element_only = self.full_document(
            [], [{"id": "group", "title": "구성요소", "scopeModelId": None,
                  "elements": [{"modelId": "receiver", "shortId": None,
                    "presentation": {"whyItMatters": None, "withoutIt": None,
                                      "analogy": "비유 문장", "notes": []}}]}], [])
        glossary_only = self.full_document([], [],
            [{"term": "T", "definition": "D", "analogy": "비유 문장"}])
        for document in (step_only, element_only, glossary_only):
            report = schema_report("analogy-only", document, SCHEMA_PATH)
            self.assertFalse(report.errors, report.to_dict())


@unittest.skipUnless(sync_playwright and Path(CHROME).is_file(), "local Chrome and Playwright required")
class AnalogyMapRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=CHROME, headless=True)
        cls.template = (ROOT / "assets/html-report-template.html").read_text()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.pw.stop()

    def setUp(self) -> None:
        self.page = self.browser.new_page()
        self.errors: list[str] = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))

    def tearDown(self) -> None:
        self.page.close()

    def load(self, data: dict[str, Any]) -> None:
        self.page.set_content(self.template.replace("__REPORT_DATA_JSON__", json.dumps(data)))

    def test_mapping_table_renders_in_step_element_and_glossary(self) -> None:
        data, bundle = mapped_fixture()
        result = hydrate_report(data, bundle, ValidationReport("story"))
        self.load(result)
        # 단계 카드: 두 번째 단계(order 40)를 선택하면 대응 표가 보인다.
        self.page.locator('#flow-panel-story [data-step-nav="next"]').click()
        step_text = self.page.locator("#flow-panel-story .flow-step:not([hidden])").inner_text()
        for text in ["비유 대응", "주문서 전달", "Sender → Receiver", "(rel)",
                     "종이가 아니라 요청이 이동한다", "접수대", "Receiver", "(receiver)",
                     "비유가 맞지 않는 범위: 접수대 위 주문서는 그대로 남지만 요청은 즉시 되돌아온다."]:
            self.assertIn(text, step_text)
        # 요소 카드: details를 펼치면 canonical 이름과 modelId가 표에 함께 보인다.
        self.page.locator(".responsibility-details summary").click()
        element_text = self.page.locator(".element-card").first.inner_text()
        for text in ["비유 대응", "주문 접수 창구", "Receiver", "(receiver)",
                     "받은 뒤 장부로 넘긴다", "창구와 달리 동시에 여러 요청을 받는다."]:
            self.assertIn(text, element_text)
        # 용어집 카드도 같은 구조로 렌더링한다.
        term_text = self.page.locator(".term").first.inner_text()
        for text in ["전달대", "Order Board", "(order-board)", "전달 보장 정책은 기록에 없다."]:
            self.assertIn(text, term_text)
        self.assertEqual(self.page.locator(".analogy-map").count(), 3)
        self.assertEqual(self.errors, [])

    def test_without_mappings_no_analogy_map_nodes_are_added(self) -> None:
        # mappings가 없으면 기존 출력과 동일 — 비유 문구는 그대로, 표는 생기지 않는다.
        data, bundle = mapped_fixture()
        for presentation in [data["flows"][0]["presentation"]["stepNotes"][0],
                             data["elementGroups"][0]["elements"][0]["presentation"],
                             data["glossary"][0]]:
            presentation.pop("mappings")
            presentation.pop("limits")
        result = hydrate_report(data, bundle, ValidationReport("story"))
        self.load(result)
        self.page.locator('#flow-panel-story [data-step-nav="next"]').click()
        step_text = self.page.locator("#flow-panel-story .flow-step:not([hidden])").inner_text()
        self.assertIn("비유: 접수대에 주문서를 올리는 단계", step_text)
        self.assertEqual(self.page.locator(".analogy-map").count(), 0)
        self.assertEqual(self.errors, [])


class StrictExampleBuildTests(unittest.TestCase):
    def test_example_build_substitutes_mappings_without_placeholder_residue(self) -> None:
        # 실제 빌더 CLI가 예제 데이터의 대응 표를 HTML에 치환하는지, 자리표시자가
        # 남지 않는지 확인한다(strict 모드 — HTML-STATIC-002 자리표시자 검사 포함).
        with tempfile.TemporaryDirectory(prefix="c4-analogy-build-") as temp:
            temp_root = Path(temp)
            report_data = json.loads((ROOT / "examples/html-report-data.example.json").read_text())
            report_data["diagrams"] = []
            for relative_path in report_data["build"]["expectedFiles"]:
                target = temp_root / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative_path, target)
            (temp_root / "examples/html-report-data.example.json").write_text(
                json.dumps(report_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            output = temp_root / "index.html"
            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts/build_html_report.py"),
                 "--root", str(temp_root),
                 "--data", "examples/html-report-data.example.json",
                 "--template", str(ROOT / "assets/html-report-template.html"),
                 "--output", str(output),
                 "--skill-root", str(ROOT)],
                text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            html = output.read_text(encoding="utf-8")
            # 정적 HTML은 JSON 페이로드 + 템플릿 렌더러로 구성된다 — 치환 증거는
            # 페이로드의 해석된 매핑(이름 포함)과 템플릿의 렌더러에 있다.
            for text in ["비유 대응", '"term":"주문 접수 창구"', '"modelId":"order-api"',
                         '"name":"Order API"', '"kind":"element"',
                         '"term":"전달대에 주문서 올리기"', '"modelId":"api-to-topic"',
                         '"kind":"relationship"',
                         "접수 창구와 달리 Order API는 한 창구에서 동시에 여러 주문 요청을 받아 처리한다."]:
                self.assertIn(text, html)
            self.assertNotIn("__REPORT_DATA_JSON__", html)
            self.assertFalse(re.search(r"__[A-Z0-9_]{2,}__", html))


if __name__ == "__main__":
    unittest.main()
