"""Canonical C4 -> native repo-flowmap data mapping; NO layout/SVG/HTML rendering.

The typed-view extension is implemented inside the bundled repo-flowmap template.
This deterministic adapter never invents members, multiplicities or message kinds.
"""
from __future__ import annotations
import copy
import hashlib
from pathlib import Path

VIEW_MODES = {"systemLandscape": "structure", "systemContext": "structure", "container": "structure",
              "component": "structure", "code": "class", "dynamic": "sequence", "deployment": "deployment"}
RELATION_KINDS = {"inheritance", "realization", "association", "composition", "dependency"}

# D2: 화면 상세도는 모델 범위와 별개 축이다. 어떤 수준도 요소·관계를 삭제·병합하지 않는다.
PRESENTATION_DETAILS = {"full", "labels", "minimal"}
TYPE_LABELS = {"person": "사람", "softwareSystem": "소프트웨어 시스템", "container": "컨테이너",
               "component": "컴포넌트", "codeElement": "코드 요소", "deploymentNode": "배포 노드",
               "infrastructureNode": "인프라 노드"}
# D2 뷰 분리 제안은 references/visual-budgets.md에 문서화된 경고선만 쓴다(새 수치를 발명하지 않는다).
VIEW_ELEMENT_WARN = {"systemContext": 10, "container": 14, "component": 15}
DYNAMIC_STEP_WARN = 15
# D6: 축약 내역 각 항목의 이유 문구. 원문 위치를 정확히 가리킨다.
_REASON_SHORTENED = ("labels 상세도: 화면 설명을 종류·기술 요약으로 바꿨다. "
                     "원문은 노드 element.description에 그대로 있다.")
_REASON_DESC_OMITTED = ("minimal 상세도: 화면 설명을 비웠다. "
                        "원문은 노드 element.description에 그대로 있다.")
_REASON_NOTE_OMITTED = ("{} 상세도: 단계 부기(note)를 화면에서 뺐다. "
                        "원문은 relationship.rationale·canonicalStep(note·condition)에 그대로 있다.")
_REASON_ANNOTATION_OMITTED = ("minimal 상세도: 구간 기술(data)을 화면에서 뺐다. "
                              "원문은 relationship.technology에 그대로 있다.")


def _kind_summary(element: dict) -> str:
    """labels 수준의 노드 부제: 종류(·기술) 요약. 원문 설명을 대체하는 표시용 문자열이다."""
    summary = "종류: " + TYPE_LABELS[element["type"]]
    if element.get("technology"):
        summary += f" · 기술: {element['technology']}"
    return summary




def project(model: dict, model_path: str, model_sha256: str, view_id: str,
           presentation_detail: str = "full") -> dict:
    """Return a complete native flowmap input; checked for exact equality by DIA.

    Call validate_model first. A subset View is valid; an unmodelled projection is not.
    Ancestors are explicit canonical boundary context, not extra invented View nodes.
    presentation_detail(full 기본)은 라벨·설명의 화면 밀도만 조절하는 표시용 축이다:
    canonical 사실(요소·관계·step·뷰 포함 목록)은 어느 수준에서도 그대로 복제된다.
    """
    if presentation_detail not in PRESENTATION_DETAILS:
        raise ValueError(f"unsupported presentation detail: {presentation_detail}")
    view = next((v for v in model["views"] if v["id"] == view_id), None)
    if view is None:
        raise ValueError(f"unknown exact View ID: {view_id}")
    mode = VIEW_MODES.get(view["type"])
    if mode is None:
        raise ValueError(f"unsupported View type: {view['type']}")
    elements = {e["id"]: e for e in model["elements"]}
    relations = {r["id"]: r for r in model["relationships"]}
    selected = [elements[i] for i in view["elementIds"]]
    if not selected:
        raise ValueError("typed repo-flowmap needs a nonempty View")
    if len(selected) > 24 or len(view["relationshipIds"]) > 32 or len(view["steps"]) > 40:
        raise ValueError("typed View exceeds 24 elements / 32 relationships / 40 steps; split the View")
    if mode == "sequence" and len(selected) > 12:
        raise ValueError("sequence exceeds 12 participants; split the scenario")
    if mode == "class":
        for e in selected:
            details = e.get("codeDetails")
            if e["type"] != "codeElement" or not details:
                raise ValueError(f"class View needs codeElement with explicit codeDetails: {e['id']}")
        for rid in view["relationshipIds"]:
            if not relations[rid].get("codeRelation"):
                raise ValueError(f"UML relationship kind requires codeRelation evidence: {rid}")
    logical_placement = mode == "deployment" and any(e["type"] in {"softwareSystem", "container"} for e in selected)
    if mode == "deployment":
        for e in selected:
            allowed = {"deploymentNode", "infrastructureNode"} | ({"softwareSystem", "container"} if logical_placement else set())
            if e["type"] not in allowed:
                raise ValueError(f"unsupported deployment element: {e['id']}")
            if e["type"] in {"softwareSystem", "container"} and e["instanceOfId"]:
                raise ValueError(f"logical placement must not masquerade as an instance: {e['id']}")
            if e["instanceOfId"] and elements[e["instanceOfId"]]["type"] not in {"softwareSystem", "container"}:
                raise ValueError(f"unsupported deployment target: {e['id']}")
    if mode == "sequence":
        for s in view["steps"]:
            if s["kind"] != "interaction":
                raise ValueError(f"decision/failure/recovery fragments are not supported by the linear sequence extension: {s['id']}")
    # Cycles cannot become an infinite renderer recursion, even when unused elsewhere.
    ancestors = {}
    if mode != "sequence" and mode != "class":
        for e in selected:
            parent, seen = e["parentId"], {e["id"]}
            while parent:
                if parent in seen or parent not in elements:
                    raise ValueError(f"cyclic/unresolved containment for {e['id']}")
                seen.add(parent)
                if parent not in view["elementIds"]:
                    ancestors[parent] = elements[parent]
                parent = elements[parent]["parentId"]
    all_display = {e["id"]: e for e in selected} | ancestors
    boundary_ids = {e["parentId"] for e in all_display.values() if e["parentId"] in all_display}
    boundary_ids |= {e["id"] for e in selected if e["type"] == "deploymentNode"}
    if mode in {"structure", "deployment"} and not logical_placement:
        for rid in view["relationshipIds"]:
            r = relations[rid]
            if r["sourceId"] in boundary_ids or r["destinationId"] in boundary_ids:
                raise ValueError(f"expanded boundary endpoint {rid}: split the View or target a concrete element")
    def edge(r: dict, step: dict | None, index: int) -> dict:
        note = step["note"] if step else r["rationale"]
        if step and step["condition"]:
            # A message guard is not an alt/opt frame or a scenario-wide condition.
            # Preserve the original step below; expose the literal guard through
            # the existing native message label, panel and SVG export path.
            note = f"조건: {step['condition']}" + (f"\n{note}" if note else "")
        item = {"id": step["id"] if step else r["id"], "relationshipId": r["id"],
                "from": r["sourceId"], "to": r["destinationId"], "call": r["description"],
                "data": r["technology"] or "기술 미확인", "note": note,
                "relationship": copy.deepcopy(r), "canonicalStep": copy.deepcopy(step), "order": index + 1}
        if item["from"] == item["to"]:
            item["kind"] = "self"
        return item
    steps = ([edge(relations[s["relationshipId"]], s, i)
              for i, s in enumerate(sorted(view["steps"], key=lambda s: s["order"]))]
             if mode == "sequence" else
             [edge(relations[rid], None, i) for i, rid in enumerate(view["relationshipIds"])])
    nodes = [{"id": e["id"], "label": e["name"], "desc": e["description"],
              "layer": "canonical", "file": e["id"], "element": copy.deepcopy(e)} for e in selected]
    log_entries: list[dict] | None = None
    if presentation_detail != "full":
        # D6: 화면 표시만 바뀐 모든 지점을 원본 값 → 표시 값 + 이유로 기록한다.
        # 요소·관계·step은 하나도 삭제·병합하지 않는다(아래 counts가 그 증거다).
        log_entries = []
        for n in nodes:
            n["desc"] = _kind_summary(n["element"]) if presentation_detail == "labels" else ""
            log_entries.append({
                "kind": "description-shortened" if presentation_detail == "labels" else "description-omitted",
                "id": n["id"], "original": n["element"]["description"], "displayed": n["desc"],
                "reason": _REASON_SHORTENED if presentation_detail == "labels" else _REASON_DESC_OMITTED})
        for item in steps:
            if item["note"] is not None:
                log_entries.append({"kind": "note-omitted", "id": item["id"],
                                    "original": item["note"], "displayed": None,
                                    "reason": _REASON_NOTE_OMITTED.format(presentation_detail)})
            item["note"] = None
        if presentation_detail == "minimal":
            for item in steps:
                if item["data"] is not None:
                    log_entries.append({"kind": "annotation-omitted", "id": item["id"],
                                        "original": item["data"], "displayed": None,
                                        "reason": _REASON_ANNOTATION_OMITTED})
                item["data"] = None
        if view["type"] == "dynamic":
            density, limit, unit = len(view["steps"]), DYNAMIC_STEP_WARN, "단계"
        else:
            limit = VIEW_ELEMENT_WARN.get(view["type"])
            density, unit = (len(view["elementIds"]), "요소") if limit else (None, "요소")
        if limit is not None and density is not None and density > limit:
            log_entries.append({
                "kind": "view-split-proposal", "id": view_id, "original": None, "displayed": None,
                "reason": (f"이 View는 visual-budgets.md 경고선({view['type']} {limit} {unit})을 넘었다"
                           f"(현재 {density} {unit}). 표시 상세도를 낮추기 전에 같은 추상화 수준의 View 분리와"
                           " nextViewIds 연결을 먼저 검토하라. 이 투영은 뷰를 자동으로 분리하지 않는다.")})
    targets = {e["instanceOfId"]: elements[e["instanceOfId"]] for e in selected if e["instanceOfId"]}
    presentation = ({} if log_entries is None else {
        "presentationDetail": presentation_detail,
        "presentationLog": {
            "detail": presentation_detail,
            "counts": {"elements": {"canonical": len(view["elementIds"]), "displayed": len(nodes)},
                       "relationships": {"canonical": len(view["relationshipIds"]),
                                         "displayed": len({s["relationshipId"] for s in steps})},
                       "steps": {"canonical": len(view["steps"]), "displayed": len(steps)}},
            "entries": log_entries}})
    return {
        "meta": {"project": model["metadata"]["title"], "title": view["title"],
                 "last_analyzed_commit": "canonical-sha256-" + model_sha256[:12],
                 "basis": f"{model_path} · View {view_id} · canonical IDs preserved",
                 "subtitle": view["question"], "note": model["metadata"]["description"] or ""},
        "c4": {"extensionVersion": 1, "mode": mode,
               **({"deploymentPresentation": "logical-placement" if logical_placement else "physical-instances"} if mode == "deployment" else {}),
               "modelPath": model_path,
               "modelSha256": model_sha256, "viewId": view_id, "view": copy.deepcopy(view),
               **presentation,
               "boundaries": [copy.deepcopy(ancestors[i]) for i in sorted(ancestors)],
               "targets": [copy.deepcopy(targets[i]) for i in sorted(targets)]},
        "layers": [{"id": "canonical", "label": view["type"], "color": "#365d91"}],
        "nodes": nodes,
        "flows": [{"id": "canonical-view", "group": view["type"], "title": view["title"],
                   "summary": view["description"] or view["question"], "steps": steps}],
    }


def implementation_hash(bundle: Path) -> str:
    """Native renderer/validator/build implementation fingerprint, not authenticity."""
    h = hashlib.sha256()
    for rel in ("template.html", "scripts/build_flowmap.mjs", "scripts/validate_flowmap.mjs"):
        h.update(rel.encode() + b"\0" + (bundle / rel).read_bytes() + b"\0")
    return h.hexdigest()
