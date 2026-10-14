#!/usr/bin/env python3
"""두 canonical model 시점의 변경을 비교해 별도 산출물 JSON로 남긴다.

비교 규칙(문서화된 기준 — SKILL.md '변경 전후 비교'와 같은 내용):

1. ID 기준: 두 모델에 같은 id가 있으면 기본적으로 같은 대상으로 본다.
2. 요소(element) 분류
   - added   : 이후 시점에만 있는 요소
   - removed : 이전 시점에만 있는 요소
   - moved   : parentId가 바뀐 요소(계층 이동). 이름·설명 등 다른 필드도 함께
               바뀌었으면 changedFields에 parentId와 함께 남긴다.
   - modified: parentId는 같고 name·technology·description이 바뀐 요소
   - unmatched: 같은 id인데 type이 다른 요소. 같은 대상을 가리킨다고 단정할 수
               없어 이동·변경으로 분류하지 않고 미확정으로 표시한다.
3. 관계(relationship) 분류
   - added / removed: 한쪽 시점에만 있는 관계
   - rewired(subtype reversed)  : 출발·도착이 서로 맞바뀐 경우(방향 반전)
   - rewired(subtype redirected): 출발 또는 도착 한쪽이 다른 요소로 바뀐 경우
   - modified                   : 출발·도착은 같고 description·technology만 변경
   - unmatched: 출발·도착이 모두 다른 요소로 바뀐 관계. ID 재사용 가능성이
               커서 미확정으로 표시한다.
4. 미확정(uncertain) 전파: 이동 대상의 이전/이후 상위 요소, 관계의 출발·도착
   요소가 unmatched면 해당 이동·재연결도 미확정 사유를 달아 확정 분류하지 않는다.
5. 비교 필드는 화면 표시에 영향 주는 것으로 제한한다: 요소 name·type·parentId·
   technology·description, 관계 sourceId·destinationId·technology·description.
   environment·tags·derivation·confidence·claimIds는 근거 갱신이지 구조 변경이
   아니므로 비교하지 않는다. 뷰(view) 구성 자체는 독립 변경으로 분류하지 않고
   각 변경의 viewRefs(그림 참조)로만 남긴다.
6. 비교는 새 사실을 만들지 않는다. 두 입력에 있는 것만 담고, 원본 모델 파일은
   수정하지 않는다. 변경이 없으면 changes가 빈 배열로 나오며, 그때의 '변경 없음'
   은 요소·관계 전수를 ID로 대조한 결과다.
"""
from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from c4_validation import ValidationReport, load_json, print_report, schema_report, validate_model  # noqa: E402

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "references" / "architecture-model-comparison.schema.json"

# 비교 입력에서 근거 연결 여부(MOD-006/011)는 경고로만 남긴다. 비교 필드에 claimIds가
# 없어 결과에 영향주지 않고, 이전 시점 스냅샷의 원래 근거장은 비교 입력에 없다.
# 구조·시맨틱(ID·계층·뷰 참조) 오류는 그대로 차단한다.
EVIDENCE_PRESENCE_CODES = {"MOD-006", "MOD-011"}

ELEMENT_FIELDS = ("name", "technology", "description")
RELATIONSHIP_FIELDS = ("technology", "description")

KIND_ORDER = {"added": 0, "removed": 1, "moved": 2, "modified": 3, "rewired": 4, "unmatched": 5}


class ComparisonError(RuntimeError):
    pass


def element_snapshot(element: dict[str, Any], model_elements: dict[str, dict[str, Any]]) -> dict[str, Any]:
    parent_id = element.get("parentId")
    return {
        "name": element.get("name", ""),
        "type": element.get("type", ""),
        "parentId": parent_id,
        "parentName": model_elements[parent_id].get("name") if isinstance(parent_id, str) and parent_id in model_elements else None,
        "technology": element.get("technology"),
        "description": element.get("description", ""),
    }


def relationship_snapshot(rel: dict[str, Any], model_elements: dict[str, dict[str, Any]]) -> dict[str, Any]:
    source_id, destination_id = rel.get("sourceId", ""), rel.get("destinationId", "")
    return {
        "sourceId": source_id,
        "destinationId": destination_id,
        "sourceName": model_elements.get(source_id, {}).get("name", source_id),
        "destinationName": model_elements.get(destination_id, {}).get("name", destination_id),
        "technology": rel.get("technology"),
        "description": rel.get("description", ""),
    }


def view_refs(target_id: str, target: str, views: list[dict[str, Any]], phase: str) -> list[dict[str, Any]]:
    key = "elementIds" if target == "element" else "relationshipIds"
    refs = []
    for view in views:
        if target_id in view.get(key, []):
            refs.append({"viewId": view["id"], "title": view.get("title", view["id"]), "phase": phase})
    return refs


def _field_diff(changes: list[dict[str, Any]], field: str, before_value: Any, after_value: Any) -> None:
    if before_value != after_value:
        changes.append({"field": field, "before": before_value, "after": after_value})


def _element_description(kind: str, item_id: str, before: dict[str, Any] | None, after: dict[str, Any] | None,
                         uncertain_reasons: list[str]) -> str:
    name_before = before.get("name") if before else None
    name_after = after.get("name") if after else None
    shown = name_after or name_before or item_id
    etype = (after or before or {}).get("type", "")
    if kind == "added":
        text = f"새 요소 '{shown}'({etype}). 이전 시점에는 없다."
    elif kind == "removed":
        text = f"요소 '{shown}'({etype})가 사라졌다. 이후 시점에는 없다."
    elif kind == "moved":
        old_parent = before.get("parentName") or before.get("parentId") or "없음"
        new_parent = after.get("parentName") or after.get("parentId") or "없음"
        text = f"요소 '{shown}'의 상위 경계가 '{old_parent}'에서 '{new_parent}'로 옮겨졌다."
    elif kind == "modified":
        text = f"요소 '{shown}'({etype})의 표시 속성이 바뀌었다."
        if name_before and name_after and name_before != name_after:
            text += f" 이름 '{name_before}' → '{name_after}'."
    else:  # unmatched
        text = (f"같은 ID '{item_id}'가 이전에는 {before.get('type')}, 이후에는 {after.get('type')}로 나타난다. "
                "같은 대상인지 확정할 수 없어 이동·변경으로 분류하지 않는다.")
    if uncertain_reasons:
        text += " (미확정: " + " · ".join(uncertain_reasons) + ")"
    return text


def _relationship_description(kind: str, subtype: str | None, item_id: str,
                               before: dict[str, Any] | None, after: dict[str, Any] | None,
                               uncertain_reasons: list[str]) -> str:
    def lane(snapshot: dict[str, Any] | None) -> str:
        if not snapshot:
            return "없음"
        return f"'{snapshot.get('sourceName')}' → '{snapshot.get('destinationName')}'"

    if kind == "added":
        text = f"새 관계 '{item_id}'({lane(after)}). 이전 시점에는 없다."
    elif kind == "removed":
        text = f"관계 '{item_id}'({lane(before)})가 사라졌다. 이후 시점에는 없다."
    elif kind == "rewired":
        action = "방향이 반전되었다" if subtype == "reversed" else "연결이 바뀌었다"
        text = f"관계 '{item_id}'의 {action}: {lane(before)}에서 {lane(after)}로."
    elif kind == "modified":
        text = f"관계 '{item_id}'({lane(after)})의 설명·기술 표시가 바뀌었다."
    else:  # unmatched
        text = (f"관계 ID '{item_id}'의 출발·도착이 모두 바뀌었다(이전 {lane(before)}, 이후 {lane(after)}). "
                "같은 관계인지 확정할 수 없다.")
    if uncertain_reasons:
        text += " (미확정: " + " · ".join(uncertain_reasons) + ")"
    return text


def compare_models(before: dict[str, Any], after: dict[str, Any], *,
                   before_path: str | None = None, after_path: str | None = None,
                   generated_at: str | None = None) -> dict[str, Any]:
    """순수 비교 함수 — 입력을 수정하지 않고 비교 산출물 dict를 반환한다."""
    elements_b = {item["id"]: item for item in before.get("elements", [])}
    elements_a = {item["id"]: item for item in after.get("elements", [])}
    rels_b = {item["id"]: item for item in before.get("relationships", [])}
    rels_a = {item["id"]: item for item in after.get("relationships", [])}
    views_b = before.get("views", [])
    views_a = after.get("views", [])

    element_ids = sorted(set(elements_b) | set(elements_a))
    rel_ids = sorted(set(rels_b) | set(rels_a))

    # 같은 ID가 서로 다른 type을 가리키면 요소 미확정(불일치).
    unmatched_elements = {
        item_id for item_id in set(elements_b) & set(elements_a)
        if elements_b[item_id].get("type") != elements_a[item_id].get("type")
    }

    changes: list[dict[str, Any]] = []
    unchanged_elements = 0
    for item_id in element_ids:
        in_before, in_after = item_id in elements_b, item_id in elements_a
        if in_before and in_after and item_id in unmatched_elements:
            changes.append({
                "id": item_id, "target": "element", "kind": "unmatched", "subtype": None,
                "uncertain": True,
                "uncertainReasons": [
                    f"같은 ID의 type이 '{elements_b[item_id].get('type')}' → '{elements_a[item_id].get('type')}'로 다르다"],
                "before": element_snapshot(elements_b[item_id], elements_b),
                "after": element_snapshot(elements_a[item_id], elements_a),
                "changedFields": [],
                "viewRefs": view_refs(item_id, "element", views_b, "before") + view_refs(item_id, "element", views_a, "after"),
                "description": _element_description("unmatched", item_id,
                                                    elements_b[item_id], elements_a[item_id],
                                                    [f"같은 ID의 type이 '{elements_b[item_id].get('type')}' → "
                                                     f"'{elements_a[item_id].get('type')}'로 다르다"]),
            })
            continue
        if not in_before:
            changes.append({
                "id": item_id, "target": "element", "kind": "added", "subtype": None,
                "uncertain": False, "uncertainReasons": [],
                "before": None,
                "after": element_snapshot(elements_a[item_id], elements_a),
                "changedFields": [],
                "viewRefs": view_refs(item_id, "element", views_a, "after"),
                "description": _element_description("added", item_id, None, elements_a[item_id], []),
            })
            continue
        if not in_after:
            changes.append({
                "id": item_id, "target": "element", "kind": "removed", "subtype": None,
                "uncertain": False, "uncertainReasons": [],
                "before": element_snapshot(elements_b[item_id], elements_b),
                "after": None,
                "changedFields": [],
                "viewRefs": view_refs(item_id, "element", views_b, "before"),
                "description": _element_description("removed", item_id, elements_b[item_id], None, []),
            })
            continue

        element_before, element_after = elements_b[item_id], elements_a[item_id]
        field_changes: list[dict[str, Any]] = []
        _field_diff(field_changes, "parentId", element_before.get("parentId"), element_after.get("parentId"))
        for field in ELEMENT_FIELDS:
            _field_diff(field_changes, field, element_before.get(field), element_after.get(field))
        if not field_changes:
            unchanged_elements += 1
            continue

        kind = "moved" if any(item["field"] == "parentId" for item in field_changes) else "modified"
        reasons: list[str] = []
        # 이동의 미확정 전파: 이전/이후 상위 요소가 ID 불일치 요소면 확정하지 않는다.
        for parent_id, phase in ((element_before.get("parentId"), "이전"), (element_after.get("parentId"), "이후")):
            if isinstance(parent_id, str) and parent_id in unmatched_elements:
                reasons.append(f"{phase} 상위 경계 '{parent_id}'가 ID 불일치(type 변경) 요소다")
        snapshot_before = element_snapshot(element_before, elements_b)
        snapshot_after = element_snapshot(element_after, elements_a)
        changes.append({
            "id": item_id, "target": "element", "kind": kind, "subtype": None,
            "uncertain": bool(reasons), "uncertainReasons": reasons,
            "before": snapshot_before, "after": snapshot_after,
            "changedFields": field_changes,
            "viewRefs": view_refs(item_id, "element", views_b, "before") + view_refs(item_id, "element", views_a, "after"),
            "description": _element_description(kind, item_id, snapshot_before, snapshot_after, reasons),
        })

    unchanged_relationships = 0
    for item_id in rel_ids:
        in_before, in_after = item_id in rels_b, item_id in rels_a
        if not in_before:
            changes.append({
                "id": item_id, "target": "relationship", "kind": "added", "subtype": None,
                "uncertain": False, "uncertainReasons": [],
                "before": None,
                "after": relationship_snapshot(rels_a[item_id], elements_a),
                "changedFields": [],
                "viewRefs": view_refs(item_id, "relationship", views_a, "after"),
                "description": _relationship_description("added", None, item_id, None,
                                                           relationship_snapshot(rels_a[item_id], elements_a), []),
            })
            continue
        if not in_after:
            changes.append({
                "id": item_id, "target": "relationship", "kind": "removed", "subtype": None,
                "uncertain": False, "uncertainReasons": [],
                "before": relationship_snapshot(rels_b[item_id], elements_b),
                "after": None,
                "changedFields": [],
                "viewRefs": view_refs(item_id, "relationship", views_b, "before"),
                "description": _relationship_description("removed", None, item_id,
                                                           relationship_snapshot(rels_b[item_id], elements_b), None, []),
            })
            continue

        rel_before, rel_after = rels_b[item_id], rels_a[item_id]
        pair_before = (rel_before.get("sourceId"), rel_before.get("destinationId"))
        pair_after = (rel_after.get("sourceId"), rel_after.get("destinationId"))
        shared = set(pair_before) & set(pair_after)
        reasons: list[str] = []

        if not shared and pair_before != pair_after:
            kind, subtype = "unmatched", None
            reasons.append("출발·도착이 모두 다른 요소로 바뀌어 같은 ID가 다른 관계를 가리킬 수 있다")
        elif pair_before == pair_after:
            kind, subtype = "modified", None
        elif set(pair_before) == set(pair_after):
            kind, subtype = "rewired", "reversed"
        else:
            kind, subtype = "rewired", "redirected"

        # 관계의 미확정 전파: 출발·도착 요소 자체가 ID 불일치면 확정하지 않는다.
        for endpoint in set(pair_before) | set(pair_after):
            if endpoint in unmatched_elements:
                reasons.append(f"연결 요소 '{endpoint}'가 ID 불일치(type 변경) 요소다")

        field_changes: list[dict[str, Any]] = []
        _field_diff(field_changes, "sourceId", pair_before[0], pair_after[0])
        _field_diff(field_changes, "destinationId", pair_before[1], pair_after[1])
        for field in RELATIONSHIP_FIELDS:
            _field_diff(field_changes, field, rel_before.get(field), rel_after.get(field))
        if kind == "modified" and not field_changes:
            unchanged_relationships += 1
            continue

        snapshot_before = relationship_snapshot(rel_before, elements_b)
        snapshot_after = relationship_snapshot(rel_after, elements_a)
        changes.append({
            "id": item_id, "target": "relationship", "kind": kind, "subtype": subtype,
            "uncertain": bool(reasons), "uncertainReasons": reasons,
            "before": snapshot_before, "after": snapshot_after,
            "changedFields": field_changes,
            "viewRefs": view_refs(item_id, "relationship", views_b, "before") + view_refs(item_id, "relationship", views_a, "after"),
            "description": _relationship_description(kind, subtype, item_id, snapshot_before, snapshot_after, reasons),
        })

    def sort_key(change: dict[str, Any]) -> tuple[int, int, str]:
        return (0 if change["target"] == "element" else 1, KIND_ORDER[change["kind"]], change["id"])

    changes.sort(key=sort_key)

    def count(target: str, kind: str) -> int:
        return sum(1 for item in changes if item["target"] == target and item["kind"] == kind)

    def model_ref(model: dict[str, Any], path: str | None) -> dict[str, Any]:
        meta = model.get("metadata", {})
        return {
            "path": path,
            "title": meta.get("title", ""),
            "modelRevision": meta.get("modelRevision", ""),
            "sourceSnapshotId": meta.get("sourceSnapshotId"),
            "elementCount": len(model.get("elements", [])),
            "relationshipCount": len(model.get("relationships", [])),
        }

    return {
        "schemaVersion": "0.4.0",
        "generatedAt": generated_at,
        "matchBasis": "canonicalId",
        "before": model_ref(before, before_path),
        "after": model_ref(after, after_path),
        "summary": {
            "elementAdded": count("element", "added"),
            "elementRemoved": count("element", "removed"),
            "elementMoved": count("element", "moved"),
            "elementModified": count("element", "modified"),
            "relationshipAdded": count("relationship", "added"),
            "relationshipRemoved": count("relationship", "removed"),
            "relationshipChanged": count("relationship", "rewired") + count("relationship", "modified"),
            "unmatched": count("element", "unmatched") + count("relationship", "unmatched"),
            "unchangedElements": unchanged_elements,
            "unchangedRelationships": unchanged_relationships,
        },
        "changes": changes,
        "notes": [
            "비교는 canonical ID 기준이며 두 입력 모델에 있는 사실만 담는다(새 사실을 만들지 않는다).",
            "뷰(view) 구성의 변화는 독립 변경으로 분류하지 않고 각 변경의 그림 참조로만 남긴다.",
            "같은 ID가 서로 다른 대상을 가리킬 가능성이 큰 변화는 미확정으로 표시하고 확정 분류하지 않는다.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="두 canonical model을 비교해 변경 산출물 JSON를 만든다")
    parser.add_argument("--before", type=Path, required=True, help="이전 시점 canonical model JSON")
    parser.add_argument("--after", type=Path, required=True, help="이후 시점 canonical model JSON")
    parser.add_argument("--output", type=Path, required=True, help="비교 결과 JSON 출력 경로")
    parser.add_argument("--skill-root", type=Path, default=SCRIPT_DIR.parent,
                        help="c4-archi-model skill root containing references/")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    before_path = args.before.resolve()
    after_path = args.after.resolve()
    output_path = args.output.resolve()
    refs = args.skill_root.resolve() / "references"
    try:
        if before_path == after_path:
            raise ComparisonError("--before와 --after가 같은 파일이다: 서로 다른 시점을 지정한다.")
        if output_path in (before_path, after_path):
            raise ComparisonError("--output은 입력 모델 파일과 달라야 한다(원본은 수정하지 않는다).")
        before_model = load_json(before_path)
        after_model = load_json(after_path)

        failed = False
        for label, model, path in (("before", before_model, before_path), ("after", after_model, after_path)):
            report = schema_report(f"architecture-model-{label}", model, refs / "architecture-model.schema.json")
            if not report.errors:
                semantic = validate_model(model, refs / "architecture-model.schema.json")
                for item in semantic.findings:
                    if item.code in EVIDENCE_PRESENCE_CODES:
                        report.warning(item.code, item.path,
                                       item.message + " (비교 입력: 근거 연결은 비교 결과에 반영하지 않는다)")
                    else:
                        report.findings.append(item)
                report.checks.extend(semantic.checks)
            if report.errors:
                failed = True
                print(f"[{label}] 입력 모델 검증 실패: {path}", file=_sys.stderr)
                print_report(report)

        if failed:
            return 1

        comparison = compare_models(
            before_model, after_model,
            before_path=str(args.before), after_path=str(args.after),
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        )
        output_report = schema_report("architecture-model-comparison", comparison, refs / "architecture-model-comparison.schema.json")
        if output_report.errors:
            print_report(output_report)
            raise ComparisonError("비교 결과가 스키마 검증에 실패했다(내부 오류).")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary = comparison["summary"]
        print(f"Created: {output_path}")
        print("요소: +{elementAdded} / -{elementRemoved} / 이동 {elementMoved} / 변경 {elementModified} · "
              "관계: +{relationshipAdded} / -{relationshipRemoved} / 변경 {relationshipChanged} · "
              "미확정 {unmatched}".format(**summary))
        return 0
    except (ComparisonError, OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=_sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
