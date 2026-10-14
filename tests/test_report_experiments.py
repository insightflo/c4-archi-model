"""A2 가정 기반 설명용 실험: 스키마·하이드레이션·검증·렌더 계약.

- 실험은 모델 검증 사실이 아니다. 가정(assumptions)은 스키마가 1개 이상으로
  강제하고, 공개 라벨은 템플릿이 고정해 데이터 작성자가 지울 수 없다.
- targets의 modelId는 canonical 요소·관계 ID만 가리킨다(HTML-DATA-025,
  비유 대응 HTML-DATA-023과 같은 계약). 이름은 빌더가 canonical model에서 채운다.
- 실험 데이터가 없으면 렌더러가 experiment 블록을 숨긴다(기존 보고서 무변경).
브라우저 케이스 없음 — 렌더 검증은 템플릿 문자열과 실제 CLI 빌드로 충분하다.
"""
from __future__ import annotations

import copy
import json
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

SCHEMA_PATH = ROOT / "references/html-report-data.schema.json"
TEMPLATE_PATH = ROOT / "assets/html-report-template.html"


def experiment_fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    """실험 하나가 붙은 표현 데이터와 canonical 번들."""
    data = {
        "analysis": {},
        "experiments": [{
            "id": "EXP-relay",
            "question": "전달대가 사라지면 주문은 어떻게 될까?",
            "targets": [
                {"modelId": "receiver", "kind": "element"},
                {"modelId": "rel", "kind": "relationship",
                 "note": "요청이 마지막으로 거치는 연결"},
            ],
            "assumptions": [
                "요청은 항상 전달대를 거쳐 이동한다.",
                "전달대가 사라져도 발신자는 요청을 계속 보낸다.",
            ],
            "narrative": [
                "발신자가 요청을 보낸다.",
                "전달대가 요청을 받지 못한다.",
                "요청은 어디에도 기록되지 않은 채 사라진다.",
            ],
        }],
    }
    bundle = {"session": {}, "understanding": None, "coverage": {},
        "model": {"elements": [{"id": "sender", "name": "Sender"},
                                {"id": "receiver", "name": "Receiver"}],
            "relationships": [{"id": "rel", "sourceId": "sender", "destinationId": "receiver",
                "description": "Sends request"}],
            "views": []},
        "ledger": {"sources": [], "claims": []}}
    return data, bundle


def full_document(experiments: list) -> dict[str, Any]:
    return {"schemaVersion": "0.4.0",
            "meta": {"language": "ko", "titleOverride": None,
                     "generatedAt": "2026-10-14T00:00:00Z"},
            "build": {"sessionPath": "s", "canonicalModelPath": "m",
                      "evidenceLedgerPath": "l", "coveragePath": "c",
                      "understandingPath": None, "expectedFiles": []},
            "overview": {"problem": "p", "oneSentence": "s", "scopeSummary": "s",
                         "readingOrder": ["r"], "claimIds": ["CL-1"]},
            "diagrams": [], "flows": [], "elementGroups": [], "audienceSections": [],
            "analysis": {"benefits": [], "tradeoffs": [], "risks": []},
            "experiments": experiments,
            "issueRefs": [], "glossary": [], "artifacts": []}


class HydrationTests(unittest.TestCase):
    def test_targets_get_canonical_names_without_claim_links(self) -> None:
        data, bundle = experiment_fixture()
        # 하이드레이션에 필요한 최소 키만 채워 넣는다(나머지 경로는 관심 없음).
        data["meta"] = {"titleOverride": None}
        original = copy.deepcopy((data, bundle))
        result = hydrate_report(data, bundle, ValidationReport("story"))
        experiment = result["experiments"][0]
        self.assertEqual(experiment["id"], "EXP-relay")
        self.assertEqual(experiment["assumptions"], original[0]["experiments"][0]["assumptions"])
        # 요소 이름, 관계는 '출발 → 도착: 설명'으로 — canonical에서만 온다.
        self.assertEqual(experiment["targets"][0]["name"], "Receiver")
        self.assertEqual(experiment["targets"][1]["name"], "Sender → Receiver: Sends request")
        # 검증 사실로 위장하지 않는다 — claimIds·sourceIds를 만들지 않는다.
        self.assertNotIn("claimIds", experiment)
        self.assertNotIn("sourceIds", experiment)
        # 입력 데이터는 오염되지 않는다(기존 하이드레이션 계약).
        self.assertEqual((data, bundle), original)

    def test_absent_experiments_hydrate_to_empty_list(self) -> None:
        data, bundle = experiment_fixture()
        data.pop("experiments")
        result = hydrate_report(data, bundle, ValidationReport("story"))
        self.assertEqual(result["experiments"], [])


class ValidatorTests(unittest.TestCase):
    def validate(self, data: dict[str, Any]) -> ValidationReport:
        _, bundle = experiment_fixture()
        return validate_report_data(data, SCHEMA_PATH, model=bundle["model"], ledger=None)

    def test_valid_experiment_passes_with_target_check(self) -> None:
        data, _ = experiment_fixture()
        report = self.validate(full_document(data["experiments"]))
        self.assertFalse(report.errors, [f"{f.code} {f.path}: {f.message}" for f in report.errors])
        self.assertIn("HTML-DATA-025", [c.id for c in report.checks if c.result == "PASS"])

    def test_unknown_or_mismatched_target_fails(self) -> None:
        data, _ = experiment_fixture()
        document = full_document(data["experiments"])
        document["experiments"][0]["targets"][0]["modelId"] = "ghost"
        report = self.validate(document)
        self.assertTrue(any(f.code == "HTML-DATA-025" for f in report.errors))

        # 요소 ID를 관계 kind로 속여도 거부한다 — kind와 실제 대상이 일치해야 한다.
        data, _ = experiment_fixture()
        document = full_document(data["experiments"])
        document["experiments"][0]["targets"][0]["kind"] = "relationship"
        report = self.validate(document)
        self.assertTrue(any(f.code == "HTML-DATA-025" for f in report.errors))

    def test_duplicate_experiment_ids_fail(self) -> None:
        data, _ = experiment_fixture()
        document = full_document(data["experiments"] + data["experiments"])
        report = self.validate(document)
        self.assertTrue(any(f.code == "HTML-DATA-024" for f in report.errors))

    def test_assumption_less_experiment_rejected_by_schema(self) -> None:
        data, _ = experiment_fixture()
        document = full_document(data["experiments"])
        document["experiments"][0]["assumptions"] = []
        report = schema_report("no-assumptions", document, SCHEMA_PATH)
        self.assertTrue(report.errors)

    def test_missing_narrative_rejected_by_schema(self) -> None:
        data, _ = experiment_fixture()
        document = full_document(data["experiments"])
        del document["experiments"][0]["narrative"]
        report = schema_report("no-narrative", document, SCHEMA_PATH)
        self.assertTrue(report.errors)

    def test_document_without_experiments_still_passes_schema(self) -> None:
        document = full_document([])
        document.pop("experiments")
        report = schema_report("legacy", document, SCHEMA_PATH)
        self.assertFalse(report.errors, report.to_dict())


class TemplateContractTests(unittest.TestCase):
    """렌더러의 정적 계약 — 라벨은 템플릿이 고정하고 접힘·인쇄 동작을 잃지 않는다."""

    def setUp(self) -> None:
        self.template = TEMPLATE_PATH.read_text(encoding="utf-8")

    def test_disclosure_label_is_template_fixed(self) -> None:
        self.assertIn("가정 기반 실험 — 모델 검증 사실이 아님", self.template)
        self.assertIn("renderExperiments", self.template)
        # 실험은 details 접힘으로만 제공한다 — 새 위젯을 만들지 않는다.
        self.assertIn("make('details','experiment')", self.template)

    def test_experiment_host_and_print_behavior_wired(self) -> None:
        self.assertIn('id="experiment-body"', self.template)
        # 인쇄에서 펼침(화면 상태 복원)·인쇄 분할 회피가 실험에도 적용된다.
        self.assertIn("'.connection-details,.experiment'", self.template)
        self.assertIn(".term,.experiment{break-inside:avoid}", self.template)


class StrictExampleBuildTests(unittest.TestCase):
    def test_example_build_carries_experiments_with_assumption_label(self) -> None:
        # 실제 빌더 CLI가 예제 데이터의 실험을 HTML로 만드는지 확인한다(strict 모드).
        with tempfile.TemporaryDirectory(prefix="c4-experiments-build-") as temp:
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
                 "--template", str(TEMPLATE_PATH),
                 "--output", str(output),
                 "--skill-root", str(ROOT)],
                text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            html = output.read_text(encoding="utf-8")
            # 페이로드: 실험 데이터·canonical 이름(빌더가 채운 값)이 그대로 들어간다.
            for text in ['"id":"EXP-1"', '"question":"주문 저장 직후 이벤트 발행이 실패하면 무슨 일이 벌어질까?"',
                         '"modelId":"api-to-topic"',
                         '"name":"Order API → order-created topic: 주문 생성 이벤트를 발행한다."']:
                self.assertIn(text, html)
            # 렌더러: 공개 라벨·가정 목록·접힘 실험이 템플릿에 있다.
            self.assertIn("가정 기반 실험 — 모델 검증 사실이 아님", html)
            self.assertIn("이 실험의 가정", html)
            self.assertIn("가정에서 이어지는 흐름", html)
            self.assertNotIn("__REPORT_DATA_JSON__", html)
            self.assertFalse(re.search(r"__[A-Z0-9_]{2,}__", html))


if __name__ == "__main__":
    unittest.main()
