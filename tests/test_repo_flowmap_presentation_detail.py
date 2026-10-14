"""D2/D6: presentation detail is a display-only axis; the abbreviation log traces it.

Model scope (View elementIds/relationshipIds/steps) and 화면 상세도 are separate axes.
No level drops or merges elements/relationships; every display change is logged with
the canonical ID, original value, displayed value and a reason. The native Node
validator mirrors the same rules, so an adapter-only relaxation cannot pass.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from c4_validation import validate_model, validate_session
from generate_repo_flowmap_demo import make_model
from repo_flowmap_adapter import project

MODEL_SCHEMA = ROOT / "references/architecture-model.schema.json"
SESSION_SCHEMA = ROOT / "references/architecture-session.schema.json"
NODE = shutil.which("node")


class PresentationDetailProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = make_model()
        report = validate_model(self.model, MODEL_SCHEMA)
        self.assertFalse(report.errors, report.errors)
        self.sequence = next(v for v in self.model["views"] if v["id"] == "ordering-sequence")
        self.sequence["steps"][0]["condition"] = "게시가 기존 정책상 허용된 경우"
        self.sequence["steps"][0]["note"] = "기존 승인 정책은 그대로입니다."

    def project(self, view_id: str = "ordering-sequence", detail: str = "full") -> dict:
        return project(self.model, "model/architecture-model.json", "a" * 64, view_id,
                       presentation_detail=detail)

    def test_full_is_the_default_and_adds_no_new_keys(self) -> None:
        for view_id in (v["id"] for v in self.model["views"]):
            with self.subTest(view=view_id):
                default = project(self.model, "model/architecture-model.json", "a" * 64, view_id)
                explicit = self.project(view_id, "full")
                self.assertEqual(json.dumps(default, ensure_ascii=False),
                                 json.dumps(explicit, ensure_ascii=False))
                self.assertNotIn("presentationDetail", default["c4"])
                self.assertNotIn("presentationLog", default["c4"])
                for node in default["nodes"]:
                    self.assertEqual(node["desc"], node["element"]["description"])

    def test_labels_keeps_the_whole_view_inclusion_list(self) -> None:
        for view_id in ("ordering-container", "ordering-sequence", "ordering-deployment"):
            view = next(v for v in self.model["views"] if v["id"] == view_id)
            data = self.project(view_id, "labels")
            # D2: 요소·관계·단계는 상세도와 무관하게 하나도 사라지지 않는다.
            self.assertEqual([n["id"] for n in data["nodes"]], view["elementIds"])
            self.assertEqual([s["relationshipId"] for s in data["flows"][0]["steps"]],
                             [v for v in ([s["relationshipId"] for s in sorted(view["steps"], key=lambda s: s["order"])]
                                          if view["type"] == "dynamic" else view["relationshipIds"])])
            self.assertEqual(data["c4"]["presentationDetail"], "labels")
            log = data["c4"]["presentationLog"]
            self.assertEqual(log["detail"], "labels")
            self.assertEqual(log["counts"]["elements"], {"canonical": len(view["elementIds"]),
                                                         "displayed": len(data["nodes"])})
            self.assertEqual(log["counts"]["relationships"]["canonical"], len(view["relationshipIds"]))
            self.assertEqual(log["counts"]["relationships"]["displayed"],
                             len({s["relationshipId"] for s in data["flows"][0]["steps"]}))
            for node in data["nodes"]:
                self.assertEqual(node["desc"], "종류: " + {
                    "person": "사람", "softwareSystem": "소프트웨어 시스템", "container": "컨테이너",
                    "component": "컴포넌트", "codeElement": "코드 요소", "deploymentNode": "배포 노드",
                    "infrastructureNode": "인프라 노드"}[node["element"]["type"]]
                                 + (f" · 기술: {node['element']['technology']}" if node["element"]["technology"] else ""))
                self.assertEqual(node["label"], node["element"]["name"])  # 이름변경은 없다

    def test_labels_drops_notes_but_preserves_canonical_steps(self) -> None:
        data = self.project("ordering-sequence", "labels")
        steps = data["flows"][0]["steps"]
        self.assertEqual(steps[0]["note"], None)
        self.assertEqual(steps[0]["canonicalStep"]["condition"], "게시가 기존 정책상 허용된 경우")
        self.assertEqual(steps[0]["canonicalStep"]["note"], "기존 승인 정책은 그대로입니다.")
        self.assertEqual(steps[0]["relationship"]["description"], steps[0]["call"])
        entry = next(e for e in data["c4"]["presentationLog"]["entries"]
                     if e["id"] == steps[0]["id"] and e["kind"] == "note-omitted")
        self.assertEqual(entry["original"], "조건: 게시가 기존 정책상 허용된 경우\n기존 승인 정책은 그대로입니다.")
        self.assertIsNone(entry["displayed"])
        self.assertTrue(entry["reason"])

    def test_minimal_shows_labels_only_and_logs_every_omission(self) -> None:
        data = self.project("ordering-sequence", "minimal")
        self.assertEqual([n["desc"] for n in data["nodes"]], [""] * len(data["nodes"]))
        for step in data["flows"][0]["steps"]:
            self.assertIsNone(step["note"])
            self.assertIsNone(step["data"])
            self.assertEqual(step["call"], step["relationship"]["description"])
        kinds = {e["kind"] for e in data["c4"]["presentationLog"]["entries"]}
        self.assertEqual(kinds, {"description-omitted", "note-omitted", "annotation-omitted"})
        for entry in data["c4"]["presentationLog"]["entries"]:
            self.assertTrue(entry["id"] and entry["reason"])
            self.assertIn("original", entry)
            self.assertIn("displayed", entry)

    def test_unknown_detail_is_rejected(self) -> None:
        for detail in ("tiny", "", None, 3):
            with self.subTest(detail=detail):
                with self.assertRaisesRegex(ValueError, "unsupported presentation detail"):
                    self.project("ordering-container", detail)  # type: ignore[arg-type]

    def test_view_split_proposal_uses_documented_density_lines_only(self) -> None:
        # ordering-components는 3요소라 경고선(component 15) 밑이다 → 제안 없음.
        data = self.project("ordering-components", "labels")
        self.assertFalse([e for e in data["c4"]["presentationLog"]["entries"]
                          if e["kind"] == "view-split-proposal"])
        # 요소를 16개로 늘리면 문서화된 경고선을 넘는다 → 뷰 분리 제안 1건(자동 분리 아님).
        view = next(v for v in self.model["views"] if v["id"] == "ordering-components")
        for i in range(13):
            self.model["elements"].append({
                "id": f"dense-component-{i}", "type": "component", "name": f"밀도 검증 컴포넌트 {i}",
                "description": f"밀도 경고선 검증용 가상 컴포넌트 {i}의 책임 설명이다.",
                "technology": "Python", "parentId": "order-api", "environment": None,
                "tags": ["synthetic-sample"], "derivation": "explicit", "confidence": "DOC_ONLY",
                "rationale": "테스트를 위해 추가한 가상 요소다.", "claimIds": view["claimIds"],
                "instanceOfId": None})
            view["elementIds"].append(f"dense-component-{i}")
        self.assertFalse(validate_model(self.model, MODEL_SCHEMA).errors)
        dense = self.project("ordering-components", "labels")
        self.assertEqual([n["id"] for n in dense["nodes"]], view["elementIds"])  # 그래도 전부 표시
        proposals = [e for e in dense["c4"]["presentationLog"]["entries"]
                     if e["kind"] == "view-split-proposal"]
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["id"], "ordering-components")
        self.assertIn("경고선", proposals[0]["reason"])

    def test_projection_never_mutates_the_model(self) -> None:
        before = copy.deepcopy(self.model)
        self.project("ordering-sequence", "minimal")
        self.assertEqual(self.model, before)

    def assert_native(self, data: dict, error: str | None = None) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "input.json"
            source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                ["node", str(ROOT / "assets/repo-flowmap/scripts/validate_flowmap.mjs"), str(source)],
                capture_output=True, text=True, check=False)
            if error:
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(error, result.stderr)
            else:
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(NODE, "Node required for the native validator")
    def test_native_validator_accepts_reduced_detail_and_rejects_tampering(self) -> None:
        for detail in ("labels", "minimal"):
            with self.subTest(detail=detail):
                data = self.project("ordering-sequence", detail)
                self.assert_native(data)
                # desc를 원문 설명으로 되돌리면(몰래 상세도 올리기) 거부.
                bad = copy.deepcopy(data)
                bad["nodes"][0]["desc"] = bad["nodes"][0]["element"]["description"]
                self.assert_native(bad, "description mismatch")
                # note를 몰래 남기면 거부.
                bad = copy.deepcopy(data)
                bad["flows"][0]["steps"][0]["note"] = "몰래 넣은 부기"
                self.assert_native(bad, "display note")
                # 축약 내역을 지우면 되짚을 수 없으므로 거부.
                bad = copy.deepcopy(data)
                bad["c4"].pop("presentationLog")
                self.assert_native(bad, "presentationLog")
                # full에는 축약 내역이 없어야 한다(기본 무변경).
        full = self.project("ordering-sequence", "full")
        self.assert_native(full)
        bad = copy.deepcopy(full)
        bad["c4"]["presentationLog"] = {"detail": "full", "counts": {}, "entries": []}
        self.assert_native(bad, "presentationLog")
        # 표시 수를 낮춰 적으면(요소를 준 것처럼) 거부.
        reduced = self.project("ordering-sequence", "labels")
        reduced["c4"]["presentationLog"]["counts"]["elements"]["displayed"] = 1
        self.assert_native(reduced, "counts.elements")

    @unittest.skipUnless(NODE, "Node required for the native validator")
    def test_minimal_data_must_stay_empty_in_native_input(self) -> None:
        data = self.project("ordering-container", "minimal")
        self.assert_native(data)
        data["flows"][0]["steps"][0]["data"] = "SQL"
        self.assert_native(data, "minimal detail must not display step data")


class PresentationDetailSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = json.loads((ROOT / "examples/ordering-system.architecture-session.json").read_text())
        self.model = json.loads((ROOT / "examples/ordering-system.architecture-model.json").read_text())

    def validate(self, session: dict):
        return validate_session(session, SESSION_SCHEMA, self.model)

    def test_absent_field_keeps_existing_behaviour(self) -> None:
        report = self.validate(self.session)
        self.assertFalse(report.errors)
        self.assertFalse([c for c in report.checks if "SES-005" in str(c)])

    def test_valid_values_pass_and_invalid_values_are_rejected(self) -> None:
        for detail in ("full", "labels", "minimal"):
            with self.subTest(detail=detail):
                session = copy.deepcopy(self.session)
                session["presentationDetail"] = detail
                report = self.validate(session)
                self.assertFalse(report.errors)
                self.assertIn("SES-005", str(report.checks))
        session = copy.deepcopy(self.session)
        session["presentationDetail"] = "dense"
        report = self.validate(session)
        self.assertTrue(report.errors)


@unittest.skipUnless(NODE and shutil.which(sys.executable), "Node required for real CLI builds")
class PresentationDetailBuildTests(unittest.TestCase):
    def setUp(self) -> None:
        from generate_repo_flowmap_demo import generate
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "demo"
        generate(self.root, False)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def build(self, *args: str):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts/build_repo_flowmap.py"), "--root", str(self.root), *args],
            capture_output=True, text=True, check=False)

    def test_cli_stamp_receipt_and_legacy_revalidation(self) -> None:
        result = self.build("--model", "model/architecture-model.json", "--view", "ordering-context",
                            "--presentation-detail", "labels")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads((self.root / "diagrams/ordering-context.flowmap.json").read_text())
        self.assertEqual(data["c4"]["presentationDetail"], "labels")
        receipt = json.loads((self.root / "qa/repo-flowmap-build-ordering-context.json").read_text())
        self.assertEqual(receipt["presentation"]["detail"], "labels")
        self.assertEqual(receipt["presentation"]["counts"]["elements"], {"canonical": 2, "displayed": 2})
        self.assertEqual(receipt["presentation"]["logEntries"],
                         len(data["c4"]["presentationLog"]["entries"]))
        # 스탬프된 입력은 legacy 재검증에서 같은 상세도로 DIA-008 재투영을 통과한다.
        again = self.build("--input", "diagrams/ordering-context.flowmap.json",
                           "--output", "diagrams/ordering-context.flowmap.html")
        self.assertEqual(again.returncode, 0, again.stderr)
        # 위조된 상세도 스탬프는 재투영 자체가 실패한다.
        data["c4"]["presentationDetail"] = "tiny"
        (self.root / "diagrams/ordering-context.flowmap.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        forged = self.build("--input", "diagrams/ordering-context.flowmap.json",
                            "--output", "diagrams/ordering-context.flowmap.html")
        self.assertNotEqual(forged.returncode, 0)
        self.assertIn("unsupported presentation detail", forged.stderr)

    def test_default_build_is_unchanged_and_flag_requires_model(self) -> None:
        result = self.build("--model", "model/architecture-model.json", "--view", "ordering-context")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads((self.root / "diagrams/ordering-context.flowmap.json").read_text())
        self.assertNotIn("presentationDetail", data["c4"])
        receipt = json.loads((self.root / "qa/repo-flowmap-build-ordering-context.json").read_text())
        self.assertNotIn("presentation", receipt)
        legacy = self.build("--input", "diagrams/ordering-context.flowmap.json",
                            "--output", "diagrams/ordering-context.flowmap.html",
                            "--presentation-detail", "minimal")
        self.assertNotEqual(legacy.returncode, 0)
        self.assertIn("--presentation-detail", legacy.stderr)


if __name__ == "__main__":
    unittest.main()
