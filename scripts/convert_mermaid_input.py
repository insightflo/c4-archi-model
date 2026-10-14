#!/usr/bin/env python3
"""기존 Mermaid 다이어그램(.mmd)을 근거 원장 조각으로 변환한다 (D7 최소 구현).

계약 (references/mermaid-import.md 참조):
- 텍스트 파싱만 한다. Mermaid 렌더러·자바스크립트를 실행하지 않고,
  원본 문자열은 excerpt에 그대로 보존한다(비실행 보존).
- 변환 결과는 "출처가 그림인 주장"일 뿐이며 정규 모델의 검증된 사실이 아니다.
  사람이 주장을 검토한 뒤 기존 작성 모드로 모델을 만든다.
- 그림에서 읽은 주장의 confidence는 절대 VERIFIED가 될 수 없다
  (validate_evidence_ledger의 EVD-019 규칙이 강제한다).
- 파싱 실패·무시된 줄은 warnings에 남기고 조용히 버리지 않는다.
- draw.io·Excalidraw 변환은 이번 범위가 아니다(지연).

지원 하위집합: flowchart/graph (TD/TB/BT/LR/RL), sequenceDiagram.
다른 다이어그램 유형은 지원하지 않으며 경고로만 기록한다.
"""
from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent

MERMAID_ID = r"[A-Za-z0-9_][A-Za-z0-9_\-]*"

# 노드 모양: 긴 패턴부터 시도한다(중첩 괄호 오인 방지).
SHAPES: list[tuple[str, str]] = [
    ("circle", r"\(\((?P<label>[^()]*)\)\)"),
    ("cylinder", r"\[\((?P<label>[^()]*)\)\]"),
    ("stadium", r"\(\[(?P<label>[^\[\]]*)\]\)"),
    ("subroutine", r"\[\[(?P<label>[^\[\]]*)\]\]"),
    ("hexagon", r"\{\{(?P<label>[^{}]*)\}\}"),
    ("parallelogram", r"\[/(?P<label>[^/\[\]]*)/\]"),
    ("parallelogram-alt", r"\[\\(?P<label>[^\\\[\]]*)\\\]"),
    ("round", r"\((?P<label>[^()]*)\)"),
    ("square", r"\[(?P<label>[^\[\]]*)\]"),
    ("diamond", r"\{(?P<label>[^{}]*)\}"),
    ("asymmetric", r">(?P<label>[^\]]*)\]"),
]
_SHAPE_RES = [(name, re.compile(rf"^(?P<id>{MERMAID_ID})\s*{pattern}$")) for name, pattern in SHAPES]
_BARE_NODE_RE = re.compile(rf"^(?P<id>{MERMAID_ID})$")

# 엣지 화살표: 라벨 파이프형 → 라벨 텍스트형 → 무라벨 순서로 시도한다.
_EDGE_RE = re.compile(
    r"\s*(?:"
    r"(?:-->\|(?P<pipe_dotted_solid>[^|]+)\|)"
    r"|(?:-\.\->\|(?P<pipe_dashed>[^|]+)\|)"
    r"|(?:==>\|(?P<pipe_thick>[^|]+)\|)"
    r"|(?P<text_solid>--\s+(?P<text_solid_label>[^|]+?)\s+-->)"
    r"|(?P<text_dashed>-\.\s*(?P<text_dashed_label>[^|]+?)\s*\.->)"
    r"|(?P<text_thick>==\s*(?P<text_thick_label>[^|]+?)\s+==>)"
    r"|(?P<plain><-->|--o|--x>|-->|---|-\.\->|-\.->|-\.|==>|===)"
    r")\s*"
)
_PLAIN_ARROW_KIND = {
    "<-->": "bidirectional",
    "--o": "circle-arrow",
    "--x": "cross-arrow",
    "-->": "solid-arrow",
    "---": "solid-line",
    "-.->": "dashed-arrow",
    "-.-": "dashed-line",
    "==>": "thick-arrow",
    "===": "thick-line",
}
_LABELED_ARROW_KIND = {
    "pipe_dotted_solid": "solid-arrow",
    "pipe_dashed": "dashed-arrow",
    "pipe_thick": "thick-arrow",
    "text_solid": "solid-arrow",
    "text_dashed": "dashed-arrow",
    "text_thick": "thick-arrow",
}
_PIPE_KEYS = {"pipe_dotted_solid", "pipe_dashed", "pipe_thick"}

# 시퀀스 참가자 ID는 뒤가 대시로 끝나지 않는다('-->>' 화살표 오인 방지).
_SEQ_ID = r"[A-Za-z0-9_](?:[A-Za-z0-9_\-]*[A-Za-z0-9_])?"
_SEQ_ARROW_RE = re.compile(
    r"^(?P<from>" + _SEQ_ID + r")\s*"
    r"(?P<arrow>-->>|--x|-->|->>|-x|->)"
    r"\s*(?P<to>" + _SEQ_ID + r")\s*:\s*(?P<text>.*)$"
)
_SEQ_PARTICIPANT_RE = re.compile(
    r"^(?P<kind>participant|actor)\s+(?P<id>" + MERMAID_ID + r")"
    r"(?:\s+as\s+(?P<label>.+))?$"
)
_SEQ_NOTE_RE = re.compile(
    r"^Note\s+(?P<pos>over|left of|right of)\s+"
    r"(?P<targets>" + MERMAID_ID + r"(?:\s*,\s*" + MERMAID_ID + r")*)"
    r"\s*:\s*(?P<text>.*)$"
)
_SEQ_BLOCK_OPEN = {"alt", "opt", "loop", "par", "critical", "break", "rect"}
_SEQ_BLOCK_BRANCH = {"else", "and", "option"}

_STYLE_PREFIXES = ("style ", "classDef ", "class ", "linkStyle ", "click ", "clickCallback ")

FLOWCHART_DIRECTIONS = {"TD", "TB", "BT", "LR", "RL"}

# 이번에 지원하지 않는 mermaid 유형 선언 — 경고 이유를 구체화한다.
KNOWN_UNSUPPORTED_TYPES = {
    "classDiagram", "erDiagram", "stateDiagram", "stateDiagram-v2",
    "journey", "gantt", "pie", "quadrantChart", "requirementDiagram",
    "gitGraph", "mindmap", "timeline", "sankey-beta", "xychart-beta",
    "block-beta", "packet-beta", "architecture-beta", "kanban",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _proposed_element_id(node_id: str) -> str:
    """다이어그램 ID를 원장 targetIds에 쓸 제안 ID로 정규화한다(모델 확정 전 임시)."""
    cleaned = re.sub(r"[^A-Za-z0-9._:\-]", "-", node_id)
    return cleaned or f"node-{abs(hash(node_id)) % 10000}"


def parse_node_token(token: str) -> dict[str, Any] | None:
    """한쪽 엣지 토큰에서 (id, label, shape)를 읽는다. 해석 불가면 None."""
    token = token.strip()
    if not token:
        return None
    bare = _BARE_NODE_RE.match(token)
    if bare:
        return {"id": bare.group("id"), "label": None, "shape": None}
    for shape, pattern in _SHAPE_RES:
        match = pattern.match(token)
        if match:
            label = match.group("label").strip().strip('"') or None
            return {"id": match.group("id"), "label": label, "shape": shape}
    return None


def _arrow_of(match: re.Match[str]) -> dict[str, Any]:
    groups = match.groupdict()
    for key, kind in _LABELED_ARROW_KIND.items():
        if groups.get(key):
            label_group = key if key in _PIPE_KEYS else f"{key}_label"
            return {"kind": kind, "token": match.group(0).strip(), "label": groups[label_group].strip()}
    plain = groups.get("plain")
    if plain:
        return {"kind": _PLAIN_ARROW_KIND.get(plain, plain), "token": plain, "label": None}
    return {"kind": "unknown", "token": match.group(0).strip(), "label": None}


def parse_mermaid(text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Mermaid 텍스트를 실행 없이 파싱한다. 결과는 parsed·warnings 구조로 반환."""
    warnings: list[dict[str, Any]] = []
    parsed: dict[str, Any] = {
        "diagramType": None,
        "rawLineCount": len(text.splitlines()),
        "comments": [],
        "flowchart": None,
        "sequence": None,
    }

    lines = text.splitlines()
    # 마크다운 코드 펜스(```mermaid ... ```)로 감싼 입력도 허용한다.
    stripped = [line for line in lines if line.strip() not in ("```", "```mermaid")]
    if len(stripped) != len(lines):
        lines = stripped

    header: str | None = None
    for index, raw in enumerate(lines):
        candidate = raw.strip()
        if not candidate:
            continue
        if candidate.startswith("%%"):
            parsed["comments"].append({"line": index + 1, "text": candidate})
            continue
        match = re.match(r"^(?P<kw>flowchart|graph)\s+(?P<dir>[A-Za-z]{2})$", candidate)
        seq_match = re.match(r"^sequenceDiagram$", candidate, re.IGNORECASE)
        if match or seq_match:
            header = candidate
            if seq_match:
                parsed["diagramType"] = "sequence"
                parsed["sequence"] = {"autonumber": False, "participants": [], "messages": [], "notes": [], "blocks": []}
            else:
                direction = match.group("dir").upper()
                if direction not in FLOWCHART_DIRECTIONS:
                    warnings.append({"line": index + 1, "text": raw, "reason": f"알 수 없는 방향 표기('{match.group('dir')}') — TD/TB/BT/LR/RL 외 값은 그대로 보존만 한다"})
                parsed["diagramType"] = "flowchart"
                parsed["flowchart"] = {
                    "direction": direction,
                    "directionDeclared": match.group("dir"),
                    "nodes": [],
                    "edges": [],
                    "subgraphs": [],
                }
            break
        keyword = candidate.split()[0].rstrip(":")
        if keyword in KNOWN_UNSUPPORTED_TYPES:
            warnings.append({"line": index + 1, "text": raw, "reason": f"지원하지 않는 다이어그램 유형('{keyword}') — 이번 지원 범위는 flowchart/graph·sequenceDiagram"})
        else:
            warnings.append({"line": index + 1, "text": raw, "reason": "지원하는 다이어그램 선언(flowchart/graph/sequenceDiagram)이 없다"})
        break

    if header is None:
        return parsed, warnings

    if parsed["diagramType"] == "flowchart":
        _parse_flowchart_body(lines, parsed, warnings)
    else:
        _parse_sequence_body(lines, parsed, warnings)
    return parsed, warnings


def _parse_flowchart_body(lines: list[str], parsed: dict[str, Any], warnings: list[dict[str, Any]]) -> None:
    flow = parsed["flowchart"]
    nodes: dict[str, dict[str, Any]] = {}
    subgraph_stack: list[dict[str, Any]] = []

    def register_node(token_info: dict[str, Any], line_no: int) -> str:
        node_id = token_info["id"]
        if node_id not in nodes:
            nodes[node_id] = {
                "id": node_id,
                "label": token_info["label"],
                "shape": token_info["shape"],
                "line": line_no,
                "subgraphs": [entry["id"] for entry in subgraph_stack],
            }
        else:
            if token_info["label"] and not nodes[node_id]["label"]:
                nodes[node_id]["label"] = token_info["label"]
                nodes[node_id]["shape"] = token_info["shape"]
            for entry in subgraph_stack:
                if entry["id"] not in nodes[node_id]["subgraphs"]:
                    nodes[node_id]["subgraphs"].append(entry["id"])
        return node_id

    # 헤더 이후 줄만 해석한다.
    header_line = None
    for i, raw in enumerate(lines):
        if raw.strip().startswith(("flowchart ", "graph ", "sequenceDiagram")):
            header_line = i
            break
    body = list(enumerate(lines, start=1))
    if header_line is not None:
        body = body[header_line + 1:]

    for line_no, raw in body:
        line = raw.strip()
        if not line or line.startswith("%%"):
            if line.startswith("%%"):
                parsed["comments"].append({"line": line_no, "text": line})
            continue
        if line == "end":
            if subgraph_stack:
                subgraph_stack.pop()["endLine"] = line_no
            else:
                warnings.append({"line": line_no, "text": raw, "reason": "대응하는 subgraph 없는 end"})
            continue
        sub_match = re.match(rf"^subgraph\s+(?P<rest>.+)$", line)
        if sub_match:
            rest = sub_match.group("rest").strip()
            sid_match = re.match(rf"^(?P<sid>{MERMAID_ID})(?:\s+(?P<title>.+))?$", rest)
            title_match = re.match(rf"^(?P<sid>{MERMAID_ID})\s*\[(?P<title>[^\]]*)\]$", rest)
            if title_match:
                sub_id, title = title_match.group("sid"), title_match.group("title").strip().strip('"') or None
            elif sid_match:
                sub_id = sid_match.group("sid")
                title = (sid_match.group("title") or "").strip().strip('"') or None
            else:
                sub_id = f"subgraph-{len(flow['subgraphs']) + 1}"
                title = rest or None
            entry = {"id": sub_id, "title": title, "line": line_no, "endLine": None, "direction": None, "memberNodeIds": []}
            flow["subgraphs"].append(entry)
            subgraph_stack.append(entry)
            continue
        direction_match = re.match(r"^direction\s+(?P<dir>[A-Za-z]{2})$", line)
        if direction_match:
            if subgraph_stack:
                subgraph_stack[-1]["direction"] = direction_match.group("dir").upper()
            else:
                warnings.append({"line": line_no, "text": raw, "reason": "subgraph 밖의 direction 선언은 무시된다"})
            continue
        if line.startswith(_STYLE_PREFIXES) or line.startswith("init "):
            warnings.append({"line": line_no, "text": raw, "reason": "스타일·인터랙션 지시문은 의미 정보가 없어 무시된다"})
            continue

        arrow_matches = list(_EDGE_RE.finditer(line))
        if arrow_matches:
            sides: list[list[dict[str, Any]]] = []
            arrows: list[dict[str, Any]] = []
            position = 0
            ok = True
            for arrow_match in arrow_matches:
                left = line[position:arrow_match.start()].strip()
                infos = [parse_node_token(part) for part in left.split("&")]
                if any(info is None for info in infos) or not infos:
                    ok = False
                    break
                sides.append([info for info in infos if info])  # type: ignore[misc]
                arrows.append(_arrow_of(arrow_match))
                position = arrow_match.end()
            tail = line[position:].strip()
            if ok:
                tail_infos = [parse_node_token(part) for part in tail.split("&")]
                if any(info is None for info in tail_infos) or not tail_infos:
                    ok = False
            else:
                ok = False
            if ok and sides and arrows:
                tail_side = [info for info in tail_infos if info]  # type: ignore[misc]
                all_sides = sides + [tail_side]
                for index in range(len(all_sides) - 1):
                    for source in all_sides[index]:
                        for destination in all_sides[index + 1]:
                            source_id = register_node(source, line_no)
                            destination_id = register_node(destination, line_no)
                            flow["edges"].append({
                                "sourceId": source_id,
                                "destinationId": destination_id,
                                "label": arrows[index]["label"],
                                "arrow": {"kind": arrows[index]["kind"], "token": arrows[index]["token"]},
                                "line": line_no,
                                "subgraphs": [entry["id"] for entry in subgraph_stack],
                            })
                continue
            warnings.append({"line": line_no, "text": raw, "reason": "엣지 문장을 끝까지 해석하지 못했다(노드 토큰 인식 실패)"})
            continue

        node_info = parse_node_token(line)
        if node_info:
            register_node(node_info, line_no)
            continue
        warnings.append({"line": line_no, "text": raw, "reason": "flowchart 문장으로 해석하지 못했다"})

    for entry in flow["subgraphs"]:
        entry["memberNodeIds"] = sorted(nid for nid, node in nodes.items() if entry["id"] in node["subgraphs"])
    flow["nodes"] = list(nodes.values())
    parsed.pop("_header_line", None)


def _parse_sequence_body(lines: list[str], parsed: dict[str, Any], warnings: list[dict[str, Any]]) -> None:
    seq = parsed["sequence"]
    participants: dict[str, dict[str, Any]] = {}
    block_stack: list[dict[str, Any]] = []

    header_line = next((i for i, raw in enumerate(lines) if raw.strip().lower() == "sequencediagram"), 0)
    body = list(enumerate(lines, start=1))[header_line + 1:]

    for line_no, raw in body:
        line = raw.strip()
        if not line or line.startswith("%%"):
            if line.startswith("%%"):
                parsed["comments"].append({"line": line_no, "text": line})
            continue
        if line == "autonumber" or line.startswith("autonumber "):
            seq["autonumber"] = True
            continue
        participant = _SEQ_PARTICIPANT_RE.match(line)
        if participant:
            pid = participant.group("id")
            label = (participant.group("label") or "").strip() or None
            if pid in participants:
                warnings.append({"line": line_no, "text": raw, "reason": f"참가자 '{pid}'가 중복 선언되었다(첫 선언 유지)"})
            else:
                participants[pid] = {
                    "id": pid,
                    "label": label,
                    "actor": participant.group("kind") == "actor",
                    "line": line_no,
                }
            continue
        note = _SEQ_NOTE_RE.match(line)
        if note:
            seq["notes"].append({
                "position": note.group("pos"),
                "targetIds": [item.strip() for item in note.group("targets").split(",")],
                "text": note.group("text").strip(),
                "line": line_no,
            })
            continue
        keyword = line.split(None, 1)[0] if line else ""
        if keyword in _SEQ_BLOCK_OPEN or (keyword == "rect"):
            block_stack.append({"type": keyword, "label": line[len(keyword):].strip() or None, "line": line_no, "endLine": None})
            seq["blocks"].append(block_stack[-1])
            continue
        if keyword in _SEQ_BLOCK_BRANCH:
            if block_stack:
                block_stack[-1].setdefault("branches", []).append({"keyword": keyword, "label": line[len(keyword):].strip() or None, "line": line_no})
            else:
                warnings.append({"line": line_no, "text": raw, "reason": f"블록 없는 '{keyword}' 분기"})
            continue
        if line == "end":
            if block_stack:
                block_stack.pop()["endLine"] = line_no
            else:
                warnings.append({"line": line_no, "text": raw, "reason": "대응하는 블록 없는 end"})
            continue
        if keyword in {"activate", "deactivate"}:
            warnings.append({"line": line_no, "text": raw, "reason": "activate/deactivate는 활성 범위 표기일 뿐 구조 정보가 없어 무시된다"})
            continue
        message = _SEQ_ARROW_RE.match(line)
        if message:
            from_id, to_id = message.group("from"), message.group("to")
            for pid in (from_id, to_id):
                if pid not in participants:
                    participants[pid] = {"id": pid, "label": None, "actor": False, "line": line_no}
                    warnings.append({"line": line_no, "text": raw, "reason": f"참가자 '{pid}'가 선언 없이 메시지에 등장해 암묵 참가자로 등록했다"})
            seq["messages"].append({
                "fromId": from_id,
                "toId": to_id,
                "arrow": message.group("arrow"),
                "text": message.group("text").strip(),
                "line": line_no,
                "order": len(seq["messages"]) + 1,
            })
            continue
        warnings.append({"line": line_no, "text": raw, "reason": "sequenceDiagram 문장으로 해석하지 못했다"})

    seq["participants"] = list(participants.values())


_ARROW_DESCRIPTION = {
    "solid-arrow": "실선 화살표",
    "solid-line": "실선(화살표 없음)",
    "dashed-arrow": "점선 화살표",
    "dashed-line": "점선(화살표 없음)",
    "thick-arrow": "굵은 화살표",
    "thick-line": "굵은 선(화살표 없음)",
    "bidirectional": "양방향 화살표",
    "circle-arrow": "원형 끝 화살표",
    "cross-arrow": "십자 끝 화살표",
    "unknown": "알 수 없는 화살표 표기",
}
_SEQ_ARROW_DESCRIPTION = {
    "->>": "실선 열린 화살표",
    "-->>": "점선 열린 화살표",
    "->": "실선 화살표",
    "-->": "점선 화살표",
    "-x": "실선 십자 끝",
    "--x": "점선 십자 끝",
}


def build_ledger_fragment(
    parsed: dict[str, Any],
    warnings: list[dict[str, Any]],
    *,
    input_name: str,
    content_hash: str,
    source_id: str,
    claim_prefix: str,
    captured_at: str,
) -> dict[str, Any]:
    """파싱 결과를 source(existing-diagram) + claims 조각으로 만든다.

    매핑 규칙:
    - 그림에 명시된 항목(노드·참가자·엣지·메시지) → derivation=explicit, confidence=DOC_ONLY
    - 레이아웃·방향 해석 → derivation=inferred, confidence=UNVERIFIED
    - VERIFIED는 절대 생성하지 않는다(EVD-019).
    """
    claims: list[dict[str, Any]] = []
    candidates: dict[str, list[dict[str, Any]]] = {"elements": [], "relationships": []}
    rel_counter: dict[str, int] = {}

    def next_claim_id() -> str:
        return f"{claim_prefix}-{len(claims) + 1:03d}"

    def support(line_no: int, excerpt: str) -> dict[str, Any]:
        return {
            "sourceId": source_id,
            "locator": f"line {line_no}",
            "excerpt": excerpt,
            "evidenceClass": "diagram",
            "capturedAt": captured_at,
            "immutableRef": content_hash,
            "contentHash": content_hash,
        }

    def add_claim(statement: str, target_ids: list[str], derivation: str, confidence: str,
                  line_no: int, excerpt: str, notes: list[str]) -> str:
        claim_id = next_claim_id()
        claims.append({
            "id": claim_id,
            "statement": statement,
            "targetIds": target_ids,
            "derivation": derivation,
            "confidence": confidence,
            "supports": [support(line_no, excerpt)],
            "contradictions": [],
            "usedBy": [],
            "notes": notes,
        })
        return claim_id

    proposed_note = "targetIds는 그림 ID에서 제안한 임시 ID다 — canonical model 확정 시 사람이 다시 연결한다"
    explicit_note = "그림에 명시된 항목 — 코드 근거 검증 전이므로 VERIFIED가 될 수 없다"

    def proposed_relationship_id(source_id_: str, destination_id_: str) -> str:
        base = f"{source_id_}-to-{destination_id_}"
        count = rel_counter.get(base, 0) + 1
        rel_counter[base] = count
        return base if count == 1 else f"{base}-{count}"

    flow = parsed["flowchart"]
    if flow:
        for node in flow["nodes"]:
            name = node["label"] or node["id"]
            shape_note = f", 모양 표기: {node['shape']}" if node["shape"] else ""
            label_note = f"(라벨 '{node['label']}')" if node["label"] else "(라벨 없음)"
            claim_id = add_claim(
                f"기존 그림에 노드 '{node['id']}'{label_note}{shape_note}가 그려져 있다.",
                [_proposed_element_id(node["id"])],
                "explicit", "DOC_ONLY", node["line"], parsed["_raw_lines"][node["line"] - 1],
                [explicit_note, proposed_note],
            )
            candidates["elements"].append({
                "proposedId": _proposed_element_id(node["id"]),
                "name": name,
                "origin": "flowchart-node",
                "claimId": claim_id,
            })
        for edge in flow["edges"]:
            source_prop = _proposed_element_id(edge["sourceId"])
            destination_prop = _proposed_element_id(edge["destinationId"])
            rel_prop = proposed_relationship_id(source_prop, destination_prop)
            label_note = f" 라벨 '{edge['label']}'." if edge["label"] else ""
            arrow_desc = _ARROW_DESCRIPTION.get(edge["arrow"]["kind"], edge["arrow"]["kind"])
            claim_id = add_claim(
                f"기존 그림에서 '{edge['sourceId']}'에서 '{edge['destinationId']}'로 향하는 관계가 "
                f"{arrow_desc}({edge['arrow']['token']})로 표시되어 있다.{label_note}",
                [source_prop, destination_prop, rel_prop],
                "explicit", "DOC_ONLY", edge["line"], parsed["_raw_lines"][edge["line"] - 1],
                [explicit_note, proposed_note, "화살표 종류는 표기 그대로 읽었다 — 동기·비동기 해석은 사람이 추가 근거로 판단한다"],
            )
            candidates["relationships"].append({
                "proposedId": rel_prop,
                "sourceProposedId": source_prop,
                "destinationProposedId": destination_prop,
                "label": edge["label"],
                "arrow": edge["arrow"],
                "origin": "flowchart-edge",
                "claimId": claim_id,
            })
        if flow["nodes"] and flow["direction"]:
            direction = flow["direction"]
            add_claim(
                f"그림의 배치 방향 표기('{flow['directionDeclared']}')는 레이아웃 해석일 뿐 "
                f"요소 간 구조·의존 방향을 확정하지 않는다.",
                sorted({_proposed_element_id(node["id"]) for node in flow["nodes"]}),
                "inferred", "UNVERIFIED", 1, parsed["_raw_lines"][0],
                ["방향 해석 주장 — 그림 명시 항목이 아니므로 inferred/UNVERIFIED로 구분한다", proposed_note],
            )

    seq = parsed["sequence"]
    if seq:
        for participant in seq["participants"]:
            name = participant["label"] or participant["id"]
            kind_note = "actor" if participant["actor"] else "participant"
            label_note = f"(라벨 '{participant['label']}')" if participant["label"] else "(라벨 없음)"
            claim_id = add_claim(
                f"기존 시퀀스 그림에 참가자 '{participant['id']}'{label_note}가 {kind_note}로 표시되어 있다.",
                [_proposed_element_id(participant["id"])],
                "explicit", "DOC_ONLY", participant["line"], parsed["_raw_lines"][participant["line"] - 1],
                [explicit_note, proposed_note],
            )
            candidates["elements"].append({
                "proposedId": _proposed_element_id(participant["id"]),
                "name": name,
                "origin": "sequence-participant",
                "claimId": claim_id,
            })
        for message in seq["messages"]:
            source_prop = _proposed_element_id(message["fromId"])
            destination_prop = _proposed_element_id(message["toId"])
            rel_prop = proposed_relationship_id(source_prop, destination_prop)
            arrow_desc = _SEQ_ARROW_DESCRIPTION.get(message["arrow"], message["arrow"])
            claim_id = add_claim(
                f"기존 시퀀스 그림에서 '{message['fromId']}'이(가) '{message['toId']}'에게 "
                f"메시지 '{message['text']}'를 {arrow_desc}({message['arrow']})로 보내며 "
                f"그림에서 {message['order']}번째 순서다.",
                [source_prop, destination_prop, rel_prop],
                "explicit", "DOC_ONLY", message["line"], parsed["_raw_lines"][message["line"] - 1],
                [explicit_note, proposed_note, "순서는 그림에 그려진 배열 순서다"],
            )
            candidates["relationships"].append({
                "proposedId": rel_prop,
                "sourceProposedId": source_prop,
                "destinationProposedId": destination_prop,
                "label": message["text"],
                "arrow": {"kind": message["arrow"], "token": message["arrow"]},
                "origin": "sequence-message",
                "claimId": claim_id,
            })

    if not claims:
        warnings.append({
            "line": 1,
            "text": "",
            "reason": "원장에 추가할 주장이 없다(빈 다이어그램이거나 지원하지 않는 유형)",
        })

    source = {
        "id": source_id,
        "name": input_name,
        "kind": "existing-diagram",
        "location": input_name,
        "version": None,
        "readScope": "파일 전체 — Mermaid 텍스트 파싱(렌더러·JS 비실행)",
        "limitations": [
            "Mermaid 하위집합(flowchart/graph, sequenceDiagram)만 해석한다",
            "스타일·인터랙션 지시문은 의미 없이 무시된다(warnings 참조)",
            "코드 근거 검증 전이므로 이 원장 조각의 주장은 VERIFIED가 될 수 없다",
        ],
        "immutableRef": content_hash,
        "contentHash": content_hash,
        "capturedAt": captured_at,
    }
    return {"source": source, "claims": claims, "candidates": candidates}


def convert_file(
    input_path: Path,
    *,
    source_id: str | None = None,
    claim_prefix: str = "CL-DIAG",
    captured_at: str | None = None,
) -> dict[str, Any]:
    """파일을 읽어 변환 결과 JSON을 만든다. 파싱은 텍스트로만 한다."""
    raw_bytes = input_path.read_bytes()
    content_hash = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
    text = raw_bytes.decode("utf-8")
    parsed, warnings = parse_mermaid(text)
    parsed["_raw_lines"] = text.splitlines()

    resolved_source_id = source_id or f"S-DIAG-{content_hash[len('sha256:'):][:8]}"
    fragment = build_ledger_fragment(
        parsed, warnings,
        input_name=str(input_path),
        content_hash=content_hash,
        source_id=resolved_source_id,
        claim_prefix=claim_prefix,
        captured_at=captured_at or _now_iso(),
    )
    parsed.pop("_raw_lines", None)
    flow_nodes = len(parsed["flowchart"]["nodes"]) if parsed["flowchart"] else 0
    flow_edges = len(parsed["flowchart"]["edges"]) if parsed["flowchart"] else 0
    participants = len(parsed["sequence"]["participants"]) if parsed["sequence"] else 0
    messages = len(parsed["sequence"]["messages"]) if parsed["sequence"] else 0
    return {
        "$schema": "../references/evidence-ledger.schema.json",
        "tool": "convert_mermaid_input.py",
        "contract": {
            "textOnlyParsing": True,
            "rendersOrExecutesMermaid": False,
            "claimsAreModelTruth": False,
            "confidenceCeiling": "DOC_ONLY(explicit) / UNVERIFIED(inferred) — VERIFIED 불가",
        },
        "input": {
            "path": str(input_path),
            "contentHash": content_hash,
            "byteLength": len(raw_bytes),
        },
        "parsed": parsed,
        "candidates": fragment["candidates"],
        "ledgerFragment": {"source": fragment["source"], "claims": fragment["claims"]},
        "warnings": warnings,
        "stats": {
            "nodes": flow_nodes,
            "edges": flow_edges,
            "participants": participants,
            "messages": messages,
            "claims": len(fragment["claims"]),
            "warnings": len(warnings),
        },
    }


def merge_into_ledger(ledger: dict[str, Any], fragment: dict[str, Any]) -> dict[str, Any]:
    """변환 조각을 기존 원장에 병합한다. ID 충돌이면 ValueError."""
    source = fragment["ledgerFragment"]["source"]
    claims = fragment["ledgerFragment"]["claims"]
    existing_sources = {item["id"] for item in ledger["sources"]}
    existing_claims = {item["id"] for item in ledger["claims"]}
    if source["id"] in existing_sources:
        raise ValueError(f"source id '{source['id']}' already exists in ledger")
    collisions = existing_claims & {claim["id"] for claim in claims}
    if collisions:
        raise ValueError(f"claim id collision: {sorted(collisions)} — --claim-prefix 로 다시 시도한다")

    merged = json.loads(json.dumps(ledger))  # 원본 변형 금지
    merged["sources"] = list(merged["sources"]) + [json.loads(json.dumps(source))]
    merged["claims"] = list(merged["claims"]) + json.loads(json.dumps(claims))
    # EVD-004: snapshot.sourceIds는 등록된 source와 정확히 일치해야 한다.
    merged["snapshot"] = dict(merged["snapshot"])
    merged["snapshot"]["sourceIds"] = list(merged["snapshot"]["sourceIds"]) + [source["id"]]
    merged["snapshot"]["notes"] = list(merged["snapshot"]["notes"]) + [
        f"source {source['id']}는 기존 Mermaid 다이어그램 변환(convert_mermaid_input.py)으로 추가되었다",
    ]
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="기존 Mermaid 다이어그램(.mmd)을 근거 원장 조각으로 변환한다(비실행·텍스트 파싱만)")
    parser.add_argument("--input", type=Path, required=True, help="입력 .mmd 파일")
    parser.add_argument("--output", type=Path, required=True, help="변환 결과 JSON 출력 경로")
    parser.add_argument("--source-id", help="원장 source id(기본: S-DIAG-<hash8>)")
    parser.add_argument("--claim-prefix", default="CL-DIAG", help="claim id 접두어(기본 CL-DIAG)")
    parser.add_argument("--captured-at", help="capturedAt 시각(ISO 8601, 예: 2026-10-14T00:00:00Z)")
    parser.add_argument("--ledger", type=Path, help="병합할 기존 근거 원장 JSON")
    parser.add_argument("--ledger-output", type=Path, help="병합 결과 원장 JSON 출력 경로(--ledger와 세트)")
    args = parser.parse_args()

    if (args.ledger is None) != (args.ledger_output is None):
        parser.error("--ledger 와 --ledger-output 는 함께 지정한다")

    result = convert_file(
        args.input,
        source_id=args.source_id,
        claim_prefix=args.claim_prefix,
        captured_at=args.captured_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.ledger is not None and args.ledger_output is not None:
        ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
        merged = merge_into_ledger(ledger, result)
        args.ledger_output.parent.mkdir(parents=True, exist_ok=True)
        args.ledger_output.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Merged ledger: {args.ledger_output} (source={result['ledgerFragment']['source']['id']}, +{len(result['ledgerFragment']['claims'])} claims)")

    print(
        f"Converted: {args.input} -> {args.output} "
        f"(type={result['parsed']['diagramType']}, claims={result['stats']['claims']}, warnings={result['stats']['warnings']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
