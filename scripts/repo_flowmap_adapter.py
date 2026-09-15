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




def project(model: dict, model_path: str, model_sha256: str, view_id: str) -> dict:
    """Return a complete native flowmap input; checked for exact equality by DIA.

    Call validate_model first. A subset View is valid; an unmodelled projection is not.
    Ancestors are explicit canonical boundary context, not extra invented View nodes.
    """
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
    targets = {e["instanceOfId"]: elements[e["instanceOfId"]] for e in selected if e["instanceOfId"]}
    return {
        "meta": {"project": model["metadata"]["title"], "title": view["title"],
                 "last_analyzed_commit": "canonical-sha256-" + model_sha256[:12],
                 "basis": f"{model_path} · View {view_id} · canonical IDs preserved",
                 "subtitle": view["question"], "note": model["metadata"]["description"] or ""},
        "c4": {"extensionVersion": 1, "mode": mode,
               **({"deploymentPresentation": "logical-placement" if logical_placement else "physical-instances"} if mode == "deployment" else {}),
               "modelPath": model_path,
               "modelSha256": model_sha256, "viewId": view_id, "view": copy.deepcopy(view),
               "boundaries": [copy.deepcopy(ancestors[i]) for i in sorted(ancestors)],
               "targets": [copy.deepcopy(targets[i]) for i in sorted(targets)]},
        "layers": [{"id": "canonical", "label": view["type"], "color": "#365d91"}],
        "nodes": [{"id": e["id"], "label": e["name"], "desc": e["description"],
                   "layer": "canonical", "file": e["id"], "element": copy.deepcopy(e)} for e in selected],
        "flows": [{"id": "canonical-view", "group": view["type"], "title": view["title"],
                   "summary": view["description"] or view["question"], "steps": steps}],
    }


def implementation_hash(bundle: Path) -> str:
    """Native renderer/validator/build implementation fingerprint, not authenticity."""
    h = hashlib.sha256()
    for rel in ("template.html", "scripts/build_flowmap.mjs", "scripts/validate_flowmap.mjs"):
        h.update(rel.encode() + b"\0" + (bundle / rel).read_bytes() + b"\0")
    return h.hexdigest()
