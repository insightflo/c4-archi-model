"""D7 기존 Mermaid 다이어그램 변환: 파서·원장 조각·경고 보존·EVD-019 규칙.

계약: 텍스트 파싱만(비실행), 결과는 "출처가 그림인 주장"뿐이며 VERIFIED가 될 수
없다, 읽지 못한 줄은 경고로 보존한다, 원본 문자열은 excerpt에 그대로 남는다.
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from c4_validation import load_json, validate_ledger  # noqa: E402 (repo-local scripts)
from convert_mermaid_input import (  # noqa: E402
    convert_file,
    merge_into_ledger,
    parse_mermaid,
)

REFS = ROOT / "references"
EXAMPLES = ROOT / "examples"
CAPTURED_AT = "2026-10-14T00:00:00Z"

FLOWCHART_MMD = """\
%% 이 다이어그램은 테스트 픽스처다
flowchart LR
  customer([고객])
  web[웹 스토어프론트]
  api("주문 API")
  db[(주문 DB)]
  queue{{주문 큐}}
  customer --> web
  web -->|주문 생성| api
  api -.-> db
  api == 주문 발행 ==> queue
  web & admin ==> api
  subgraph internal [내부 시스템]
    api
    db
  end
  style api fill:#eee
  ???알 수 없는 문장???
"""

SEQUENCE_MMD = """\
sequenceDiagram
  autonumber
  actor Customer as 고객
  participant Web as 웹 스토어프론트
  Customer->>Web: 주문 요청
  Web->>API: POST /orders
  API-->>Web: 주문 확인
  Note over Web,API: 비동기 응답 관례
  loop 재시도
    API->>API: 재시도
  end
  activate API
"""


def write_fixture(directory: Path, name: str, content: str) -> Path:
    path = directory / name
    path.write_text(content, encoding="utf-8")
    return path


class FlowchartParsing(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = write_fixture(Path(self.tmp.name), "flow.mmd", FLOWCHART_MMD)

    def test_direction_nodes_edges_shapes(self) -> None:
        result = convert_file(self.path, captured_at=CAPTURED_AT)
        flow = result["parsed"]["flowchart"]
        self.assertEqual(result["parsed"]["diagramType"], "flowchart")
        self.assertEqual(flow["directionDeclared"], "LR")
        self.assertEqual(flow["direction"], "LR")
        nodes = {node["id"]: node for node in flow["nodes"]}
        self.assertEqual(nodes["customer"]["label"], "고객")
        self.assertEqual(nodes["customer"]["shape"], "stadium")
        self.assertEqual(nodes["api"]["label"], "주문 API")
        self.assertEqual(nodes["api"]["shape"], "round")
        self.assertEqual(nodes["db"]["shape"], "cylinder")
        self.assertEqual(nodes["queue"]["shape"], "hexagon")
        self.assertIn("admin", nodes)
        edges = {(e["sourceId"], e["destinationId"]): e for e in flow["edges"]}
        self.assertIn(("customer", "web"), edges)
        web_api_labels = [e["label"] for e in flow["edges"]
                          if e["sourceId"] == "web" and e["destinationId"] == "api"]
        self.assertIn("주문 생성", web_api_labels)  # 파이프 라벨
        self.assertEqual(edges[("api", "db")]["arrow"]["kind"], "dashed-arrow")
        self.assertIsNotNone(edges.get(("admin", "api")))  # & 다중 끝점
        thick = edges[("api", "queue")]
        self.assertEqual(thick["arrow"]["kind"], "thick-arrow")
        self.assertEqual(thick["label"], "주문 발행")

    def test_subgraph_membership_and_end_line(self) -> None:
        result = convert_file(self.path, captured_at=CAPTURED_AT)
        flow = result["parsed"]["flowchart"]
        subgraph = flow["subgraphs"][0]
        self.assertEqual(subgraph["id"], "internal")
        self.assertEqual(subgraph["title"], "내부 시스템")
        self.assertEqual(subgraph["memberNodeIds"], ["api", "db"])
        self.assertIsNotNone(subgraph["endLine"])
        nodes = {node["id"]: node for node in flow["nodes"]}
        self.assertIn("internal", nodes["api"]["subgraphs"])
        self.assertNotIn("internal", nodes["customer"]["subgraphs"])

    def test_style_and_unknown_lines_become_warnings_comments_do_not(self) -> None:
        result = convert_file(self.path, captured_at=CAPTURED_AT)
        warning_lines = {item["line"] for item in result["warnings"]}
        raw_lines = FLOWCHART_MMD.splitlines()
        style_line = next(i + 1 for i, line in enumerate(raw_lines) if line.strip().startswith("style "))
        unknown_line = next(i + 1 for i, line in enumerate(raw_lines) if line.strip().startswith("???"))
        self.assertIn(style_line, warning_lines)   # 읽지 못한/무시된 줄 보존
        self.assertIn(unknown_line, warning_lines)
        comment_lines = {item["line"] for item in result["parsed"]["comments"]}
        self.assertEqual(comment_lines, {1})       # 주석은 경고가 아니라 주석으로 기록
        style_warning = next(w for w in result["warnings"] if w["line"] == style_line)
        self.assertEqual(style_warning["text"], raw_lines[style_line - 1])  # 원문 그대로

    def test_unsupported_diagram_type_produces_warning_without_claims(self) -> None:
        result = convert_file(
            write_fixture(Path(self.tmp.name), "class.mmd", "classDiagram\n  class Order\n"),
            captured_at=CAPTURED_AT,
        )
        self.assertIsNone(result["parsed"]["diagramType"])
        self.assertEqual(result["ledgerFragment"]["claims"], [])
        reasons = " / ".join(item["reason"] for item in result["warnings"])
        self.assertIn("지원하지 않는 다이어그램 유형('classDiagram')", reasons)

    def test_unknown_direction_token_is_preserved_with_warning(self) -> None:
        result = convert_file(
            write_fixture(Path(self.tmp.name), "dir.mmd", "flowchart XY\n  a --> b\n"),
            captured_at=CAPTURED_AT,
        )
        self.assertEqual(result["parsed"]["flowchart"]["direction"], "XY")
        self.assertTrue(any("방향 표기" in item["reason"] for item in result["warnings"]))


class ExtendedFlowchartSyntax(unittest.TestCase):
    """D7 지연 항목이었던 문법 확장: 열린 링크 라벨·중첩 subgraph·& 갭.

    열린 링크(화살표 없는 링크)의 텍스트·파이프 라벨과 괄호 안 `&` 는
    Mermaid 유효 문법이므로 경고 없이 해석한다. 중첩 subgraph·양쪽 다중
    끝점은 이미 동작하는 동작을 회귀 테스트로 고정한다.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def convert_snippet(self, body: str):
        path = write_fixture(Path(self.tmp.name), "ext.mmd", "flowchart LR\n" + body)
        return convert_file(path, captured_at=CAPTURED_AT)

    def test_open_link_text_labels(self) -> None:
        result = self.convert_snippet(
            "  a-- 주문 ---b\n"
            "  c-. 대기 .-d\n"
            "  e== 알림 ===f\n"
            "  g--text---h\n"  # 공백 없는 변형도 Mermaid 유효
        )
        flow = result["parsed"]["flowchart"]
        edges = {(e["sourceId"], e["destinationId"]): e for e in flow["edges"]}
        self.assertEqual(edges[("a", "b")]["label"], "주문")
        self.assertEqual(edges[("a", "b")]["arrow"]["kind"], "solid-line")
        self.assertEqual(edges[("c", "d")]["label"], "대기")
        self.assertEqual(edges[("c", "d")]["arrow"]["kind"], "dashed-line")
        self.assertEqual(edges[("e", "f")]["label"], "알림")
        self.assertEqual(edges[("e", "f")]["arrow"]["kind"], "thick-line")
        self.assertEqual(edges[("g", "h")]["label"], "text")
        self.assertEqual(edges[("g", "h")]["arrow"]["token"], "--text---")
        self.assertEqual(result["warnings"], [])  # 조용한 오독·누락 금지

    def test_open_link_pipe_labels(self) -> None:
        result = self.convert_snippet("  a---|결제|b\n  c-.-|실패|d\n")
        flow = result["parsed"]["flowchart"]
        edges = {(e["sourceId"], e["destinationId"]): e for e in flow["edges"]}
        self.assertEqual(edges[("a", "b")]["label"], "결제")
        self.assertEqual(edges[("a", "b")]["arrow"]["kind"], "solid-line")
        self.assertEqual(edges[("c", "d")]["label"], "실패")
        self.assertEqual(edges[("c", "d")]["arrow"]["kind"], "dashed-line")
        self.assertEqual(result["warnings"], [])

    def test_arrow_labels_still_win_over_open_links(self) -> None:
        # 화살표 라벨과 열린 링크가 같은 줄에 섞여도 체인으로 해석한다.
        result = self.convert_snippet("  a -- x --> b -- y --- c\n")
        edges = {(e["sourceId"], e["destinationId"]): e for e in result["parsed"]["flowchart"]["edges"]}
        self.assertEqual(edges[("a", "b")]["label"], "x")
        self.assertEqual(edges[("a", "b")]["arrow"]["kind"], "solid-arrow")
        self.assertEqual(edges[("b", "c")]["label"], "y")
        self.assertEqual(edges[("b", "c")]["arrow"]["kind"], "solid-line")

    def test_nested_subgraph_membership_and_end(self) -> None:
        result = self.convert_snippet(
            "  subgraph outer [외부]\n"
            "    a\n"
            "    subgraph inner [내부]\n"
            "      b\n"
            "      a --> b\n"
            "    end\n"
            "    c\n"
            "  end\n"
            "  d\n"
        )
        flow = result["parsed"]["flowchart"]
        subs = {s["id"]: s for s in flow["subgraphs"]}
        self.assertEqual(subs["outer"]["memberNodeIds"], ["a", "b", "c"])  # 내부 subgraph 노드도 외부 멤버십 유지
        self.assertEqual(subs["inner"]["memberNodeIds"], ["a", "b"])  # inner 안 엣지 언급도 멤버십에 누적된다(Mermaid 동작과 부합)
        self.assertEqual(subs["inner"]["endLine"], 7)
        self.assertEqual(subs["outer"]["endLine"], 9)
        nodes = {n["id"]: n for n in flow["nodes"]}
        self.assertEqual(nodes["b"]["subgraphs"], ["outer", "inner"])
        self.assertEqual(nodes["d"]["subgraphs"], [])
        inner_edge = next(e for e in flow["edges"] if (e["sourceId"], e["destinationId"]) == ("a", "b"))
        self.assertEqual(inner_edge["subgraphs"], ["outer", "inner"])

    def test_direction_inside_subgraph_recorded_as_layout(self) -> None:
        result = self.convert_snippet(
            "  subgraph s1 [그룹]\n"
            "    direction LR\n"
            "    a --> b\n"
            "  end\n"
        )
        subgraph = result["parsed"]["flowchart"]["subgraphs"][0]
        self.assertEqual(subgraph["direction"], "LR")  # 배치 정보로 parsed에 기록
        self.assertFalse(any("direction" in w["reason"] for w in result["warnings"]))

    def test_ampersand_inside_label_is_not_a_separator(self) -> None:
        result = self.convert_snippet("  a[알파 & 베타] --> b\n  c[x & y] & d --> e\n")
        flow = result["parsed"]["flowchart"]
        nodes = {n["id"]: n for n in flow["nodes"]}
        self.assertEqual(nodes["a"]["label"], "알파 & 베타")
        self.assertEqual(nodes["c"]["label"], "x & y")
        edges = {(e["sourceId"], e["destinationId"]) for e in flow["edges"]}
        self.assertEqual(edges, {("a", "b"), ("c", "e"), ("d", "e")})
        self.assertEqual(result["warnings"], [])

    def test_documented_plain_tokens_parse(self) -> None:
        # 문서가 지원으로 명시한 무라벨 토큰(-.-, --x)이 실제로 해석되는지 확인한다.
        result = self.convert_snippet("  a -.- b\n  c --x d\n")
        kinds = {(e["sourceId"], e["destinationId"]): e["arrow"]["kind"]
                 for e in result["parsed"]["flowchart"]["edges"]}
        self.assertEqual(kinds[("a", "b")], "dashed-line")
        self.assertEqual(kinds[("c", "d")], "cross-arrow")
        self.assertEqual(result["warnings"], [])

    def test_ampersand_multipoint_regression(self) -> None:
        result = self.convert_snippet("  a & b --> c & d\n  e[하나] & f[둘] --> g\n")
        edges = {(e["sourceId"], e["destinationId"]) for e in result["parsed"]["flowchart"]["edges"]}
        self.assertEqual(edges, {
            ("a", "c"), ("a", "d"), ("b", "c"), ("b", "d"),
            ("e", "g"), ("f", "g"),
        })


class SequenceParsing(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = write_fixture(Path(self.tmp.name), "seq.mmd", SEQUENCE_MMD)

    def test_participants_actors_and_message_order(self) -> None:
        result = convert_file(self.path, captured_at=CAPTURED_AT)
        seq = result["parsed"]["sequence"]
        self.assertTrue(seq["autonumber"])
        participants = {item["id"]: item for item in seq["participants"]}
        self.assertEqual(participants["Customer"]["label"], "고객")
        self.assertTrue(participants["Customer"]["actor"])
        self.assertFalse(participants["Web"]["actor"])
        messages = [(m["fromId"], m["arrow"], m["toId"], m["text"]) for m in seq["messages"]]
        self.assertEqual(messages, [
            ("Customer", "->>", "Web", "주문 요청"),
            ("Web", "->>", "API", "POST /orders"),
            ("API", "-->>", "Web", "주문 확인"),
            ("API", "->>", "API", "재시도"),
        ])
        self.assertEqual([m["order"] for m in seq["messages"]], [1, 2, 3, 4])

    def test_notes_blocks_and_activate_warning(self) -> None:
        result = convert_file(self.path, captured_at=CAPTURED_AT)
        seq = result["parsed"]["sequence"]
        note = seq["notes"][0]
        self.assertEqual(note["position"], "over")
        self.assertEqual(note["targetIds"], ["Web", "API"])
        block = seq["blocks"][0]
        self.assertEqual(block["type"], "loop")
        self.assertEqual(block["label"], "재시도")
        self.assertEqual(block["endLine"], block["line"] + 2)
        reasons = " / ".join(item["reason"] for item in result["warnings"])
        self.assertIn("activate", reasons)  # 무시된 줄 보존

    def test_implicit_participant_registered_with_warning(self) -> None:
        result = convert_file(
            write_fixture(Path(self.tmp.name), "implicit.mmd", "sequenceDiagram\n  A->>B: 안녕\n"),
            captured_at=CAPTURED_AT,
        )
        participants = {item["id"] for item in result["parsed"]["sequence"]["participants"]}
        self.assertEqual(participants, {"A", "B"})
        self.assertTrue(any("암묵 참가자" in item["reason"] for item in result["warnings"]))


class LedgerContract(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = write_fixture(Path(self.tmp.name), "flow.mmd", FLOWCHART_MMD)
        self.result = convert_file(self.path, captured_at=CAPTURED_AT)

    def test_confidence_mapping_and_no_verified(self) -> None:
        claims = self.result["ledgerFragment"]["claims"]
        self.assertTrue(claims)
        confidences = {c["confidence"] for c in claims}
        self.assertNotIn("VERIFIED", confidences)
        explicit = [c for c in claims if c["derivation"] == "explicit"]
        inferred = [c for c in claims if c["derivation"] == "inferred"]
        self.assertTrue(explicit)
        self.assertTrue(inferred)
        for claim in explicit:
            self.assertEqual(claim["confidence"], "DOC_ONLY")
        for claim in inferred:
            self.assertEqual(claim["confidence"], "UNVERIFIED")
        for claim in claims:
            for support in claim["supports"]:
                self.assertEqual(support["evidenceClass"], "diagram")

    def test_hash_matches_file_bytes(self) -> None:
        digest = "sha256:" + hashlib.sha256(self.path.read_bytes()).hexdigest()
        source = self.result["ledgerFragment"]["source"]
        self.assertEqual(source["kind"], "existing-diagram")
        self.assertEqual(source["immutableRef"], digest)
        self.assertEqual(source["contentHash"], digest)
        self.assertEqual(self.result["input"]["contentHash"], digest)

    def test_original_lines_preserved_verbatim_in_excerpts(self) -> None:
        raw_lines = FLOWCHART_MMD.splitlines()
        for claim in self.result["ledgerFragment"]["claims"]:
            support = claim["supports"][0]
            line_no = int(support["locator"].split()[-1])
            self.assertEqual(support["excerpt"], raw_lines[line_no - 1])  # 비실행 보존

    def test_targets_and_candidates(self) -> None:
        claims = self.result["ledgerFragment"]["claims"]
        for claim in claims:
            self.assertTrue(claim["targetIds"])
        element_ids = {item["proposedId"] for item in self.result["candidates"]["elements"]}
        relationship_ids = {item["proposedId"] for item in self.result["candidates"]["relationships"]}
        self.assertIn("customer", element_ids)
        self.assertIn("customer-to-web", relationship_ids)
        for candidate in self.result["candidates"]["elements"] + self.result["candidates"]["relationships"]:
            self.assertIn(candidate["claimId"], {c["id"] for c in claims})

    def test_merge_into_example_ledger_validates(self) -> None:
        ledger = load_json(EXAMPLES / "ordering-system.evidence-ledger.json")
        merged = merge_into_ledger(ledger, self.result)
        report = validate_ledger(merged, REFS / "evidence-ledger.schema.json")
        self.assertEqual(report.errors, [], report.errors)
        source_id = self.result["ledgerFragment"]["source"]["id"]
        self.assertIn(source_id, merged["snapshot"]["sourceIds"])
        self.assertEqual(ledger["claims"], load_json(EXAMPLES / "ordering-system.evidence-ledger.json")["claims"])  # 원본 불변

    def test_merge_rejects_duplicate_ids(self) -> None:
        result = convert_file(self.path, source_id="S1", captured_at=CAPTURED_AT)
        ledger = load_json(EXAMPLES / "ordering-system.evidence-ledger.json")
        with self.assertRaises(ValueError):
            merge_into_ledger(ledger, result)
        duplicate_claims = convert_file(self.path, captured_at=CAPTURED_AT)
        original_ids = {claim["id"] for claim in ledger["claims"]}
        duplicate_claims["ledgerFragment"]["claims"][0]["id"] = sorted(original_ids)[0]
        with self.assertRaises(ValueError):
            merge_into_ledger(ledger, duplicate_claims)


class EVD019Rule(unittest.TestCase):
    """그림 근거만 있는 claim은 VERIFIED가 될 수 없다."""

    @staticmethod
    def ledger_with(confidence: str, evidence_classes: list[str]) -> dict:
        ledger = load_json(EXAMPLES / "ordering-system.evidence-ledger.json")
        template = ledger["claims"][0]["supports"][0]
        supports = []
        for index, klass in enumerate(evidence_classes):
            support = copy.deepcopy(template)
            support["evidenceClass"] = klass
            support["locator"] = f"line {index + 1}"
            supports.append(support)
        ledger["claims"][0]["confidence"] = confidence
        ledger["claims"][0]["derivation"] = "explicit"
        ledger["claims"][0]["supports"] = supports
        return ledger

    def test_diagram_only_verified_rejected(self) -> None:
        report = validate_ledger(self.ledger_with("VERIFIED", ["diagram"]), REFS / "evidence-ledger.schema.json")
        self.assertTrue(any(item.code == "EVD-019" for item in report.errors))

    def test_diagram_only_doc_only_accepted(self) -> None:
        report = validate_ledger(self.ledger_with("DOC_ONLY", ["diagram"]), REFS / "evidence-ledger.schema.json")
        self.assertFalse(any(item.code == "EVD-019" for item in report.errors))

    def test_mixed_code_and_diagram_verified_not_flagged(self) -> None:
        ledger = self.ledger_with("VERIFIED", ["diagram", "code"])
        report = validate_ledger(ledger, REFS / "evidence-ledger.schema.json")
        self.assertFalse(any(item.code == "EVD-019" for item in report.errors))


class CLIEndToEnd(unittest.TestCase):
    def test_cli_produces_valid_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            mmd = tmp_path / "legacy.mmd"
            mmd.write_text("flowchart TD\n  a[알파] -->|요청| b(베타)\n", encoding="utf-8")
            ledger = tmp_path / "ledger.json"
            ledger.write_text((EXAMPLES / "ordering-system.evidence-ledger.json").read_text(encoding="utf-8"), encoding="utf-8")
            merged = tmp_path / "merged.json"
            output = tmp_path / "conversion.json"
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts/convert_mermaid_input.py"),
                 "--input", str(mmd), "--output", str(output),
                 "--ledger", str(ledger), "--ledger-output", str(merged),
                 "--captured-at", CAPTURED_AT],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["parsed"]["flowchart"]["direction"], "TD")
            self.assertEqual(result["stats"]["claims"], 4)  # 노드 2 + 엣지 1 + 방향 해석 1
            report = validate_ledger(json.loads(merged.read_text(encoding="utf-8")), REFS / "evidence-ledger.schema.json")
            self.assertEqual(report.errors, [])

    def test_example_files_in_repo_stay_consistent(self) -> None:
        # 예시 출력은 실제 변환 결과와 동일해야 한다(상대 경로·고정 capturedAt 기준).
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "conversion.json"
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts/convert_mermaid_input.py"),
                 "--input", "examples/mermaid-import/legacy-order-flow.mmd",
                 "--output", str(output), "--captured-at", CAPTURED_AT],
                capture_output=True, text=True, cwd=ROOT,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            committed = json.loads((EXAMPLES / "mermaid-import/legacy-order-flow.conversion.json").read_text(encoding="utf-8"))
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), committed)

    def test_ledger_without_ledger_output_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mmd = Path(tmp) / "x.mmd"
            mmd.write_text("flowchart TD\n  a --> b\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts/convert_mermaid_input.py"),
                 "--input", str(mmd), "--output", str(Path(tmp) / "out.json"),
                 "--ledger", str(mmd)],
                capture_output=True, text=True,
            )
            self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
