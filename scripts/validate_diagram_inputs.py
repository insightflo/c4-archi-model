#!/usr/bin/env python3
"""Cross-check diagram inputs (archify IR, repo-flowmap flowmaps) against the canonical model.

External review P0-1 (2026-09): nothing verified that rendered diagram inputs still
describe the canonical model — the pipeline relied on agent discipline only. This
validator re-derives, per discovered diagram source, the expected element ID set,
relationship identities, and dynamic step order from the canonical model, and
compares them with the diagram input. Element labels must equal canonical names
(case/whitespace normalization and known C4 type suffixes are allowed). Semantic
shortenings and arbitrary suffixes are not aliases. File stems retain their separate
human-friendly alias policy. Relationships resolve by relationshipId, a canonical
edge id, or an exact description; endpoints alone suffice only when unambiguous.
Canonical node IDs are preserved and their names verified. Renderer-local node IDs
resolve by name only when unambiguous within the View. This is structural identity
validation, not equality of all display prose when an identity is already explicit.

Discovered sources (under ``<root>/diagrams/``):
  * archify IR: ``*.architecture.json | *.sequence.json | *.workflow.json | *.dataflow.json | *.lifecycle.json``
  * flowmap:    ``*.flowmap.json``

A file stem removes only the recognized full source suffix, preserving embedded dots.
Raw View IDs take priority over normalized aliases and unique token-subset matches.
A leading numeric index prefix is stripped only as a fallback with no matches;
ambiguous aliases fail rather than falling through to another interpretation.

Checks (documented contract):
  DIA-001  ERROR  diagram source cannot be tied to a canonical view (unknown or
                   ambiguous stem, unparseable JSON, unrecognized IR structure, or no
                   canonical model available for cross-checking)
  DIA-002  ERROR  a canonical element of the view is missing from the diagram nodes
  DIA-003  ERROR  a diagram node label resolves to no (or ambiguously many) canonical
                   element names — an invented node
  DIA-004  ERROR  two or more diagram nodes resolve to the same canonical element
  DIA-005  ERROR  static view: relationship identities/directions differ, or an edge
                   cannot be unambiguously identified
  DIA-006  ERROR  dynamic view: diagram relationship sequence does not match canonical
                   steps sorted by numeric order, or an edge identity is ambiguous
  DIA-007  ERROR  a diagram edge references a node id that does not exist in the diagram

Packages without any diagram input (text-fallback path) PASS. A package may render a
subset of the views; every rendered view that is discovered is still checked in full.
"""
from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True

import argparse
import re
from collections import Counter
from pathlib import Path
from typing import Any

from c4_validation import ValidationReport, load_json, print_report, write_report

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent

ARCHIFY_IR_SUFFIXES = (".architecture.json", ".sequence.json", ".workflow.json", ".dataflow.json", ".lifecycle.json")
FLOWMAP_SUFFIX = ".flowmap.json"

_NODE_LIST_KEYS = ("components", "nodes", "participants", "actors")
_EDGE_LIST_KEYS = ("connections", "messages", "links", "edges", "flows", "interactions", "steps")
_FROM_KEYS = ("from", "source", "sender", "fromId")
_TO_KEYS = ("to", "target", "receiver", "toId")
_LABEL_KEYS = ("label", "name", "title")

_INDEX_PREFIX = re.compile(r"\d+[\s_-]+(.+)")
_BRACKETED = re.compile(r"\[[^\]]*\]|\([^)]*\)")
_SEPARATORS = re.compile(r"[·—–\-_/\\:;,|.]+")

FAMILY_ARCHIFY = "archify"
FAMILY_FLOWMAP = "flowmap"


def normalize_label(value: Any) -> str:
    """Lowercase, drop bracketed decorations, unify separators, collapse whitespace."""
    text = str(value).lower()
    text = _BRACKETED.sub(" ", text)
    text = _SEPARATORS.sub(" ", text)
    return " ".join(text.split())


def label_tokens(value: Any) -> frozenset:
    return frozenset(normalize_label(value).split())


def semantic_label(value: str) -> str:
    """Normalize presentation whitespace/case, not meaning or punctuation."""
    return " ".join(value.casefold().split())


_TYPE_SUFFIX = re.compile(
    r"\s+(?:\[(?:person|software\s*system|container|component|deployment\s*node|"
    r"infrastructure\s*node)\]|\((?:person|software\s*system|container|component|"
    r"deployment\s*node|infrastructure\s*node)\))$", re.IGNORECASE)


def name_matches(canonical: str, label: str) -> bool:
    a, b = semantic_label(canonical), semantic_label(label)
    return bool(a and b and (a == b or a == _TYPE_SUFFIX.sub("", b)))


def stem_key(stem: str) -> str:
    """'01-system-context' -> 'system-context'; 'context' stays 'context'."""
    match = _INDEX_PREFIX.match(stem.strip())
    return match.group(1).strip() if match else stem.strip()


def source_stem(path: Path) -> str:
    """Remove a recognized full diagram-source suffix without truncating dotted IDs."""
    for suffix in (FLOWMAP_SUFFIX, *ARCHIFY_IR_SUFFIXES):
        if path.name.endswith(suffix):
            return path.name[:-len(suffix)]
    return path.name


def _alias_candidates(stem: str, candidates: list[str]) -> list[str]:
    if stem in candidates:
        return [stem]
    target = normalize_label(stem)
    exact = sorted({c for c in candidates if normalize_label(c) == target})
    if exact:
        return exact
    target_tokens = set(target.split())
    matches = []
    for candidate in candidates:
        candidate_tokens = set(normalize_label(candidate).split())
        if target_tokens and candidate_tokens and (target_tokens <= candidate_tokens or candidate_tokens <= target_tokens):
            matches.append(candidate)
    return sorted(set(matches))


def alias_match(stem: str, candidates: list[str]) -> str | None:
    """Resolve raw ID first, then an unambiguous normalized or token-subset alias."""
    matches = _alias_candidates(stem, candidates)
    return matches[0] if len(matches) == 1 else None


def resolve_view(stem: str, view_ids: list[str]) -> str | None:
    """Shared DIA/RCP View resolution; ambiguity never triggers a fallback."""
    for candidate_stem in dict.fromkeys((stem, stem_key(stem))):
        matches = _alias_candidates(candidate_stem, view_ids)
        if matches:
            return matches[0] if len(matches) == 1 else None
    return None


def discover_inputs(root: Path) -> list:
    """Return [(path, family)] for diagram sources under <root>/diagrams/."""
    diagrams = root / "diagrams"
    found: list = []
    if not diagrams.is_dir():
        return found
    for path in sorted(diagrams.iterdir()):
        if not path.is_file():
            continue
        name = path.name
        if name.endswith(FLOWMAP_SUFFIX):
            found.append((path, FAMILY_FLOWMAP))
        elif any(name.endswith(suffix) for suffix in ARCHIFY_IR_SUFFIXES):
            found.append((path, FAMILY_ARCHIFY))
    return found


def qa_dirs(root: Path) -> list:
    """Receipt directories: <root>/qa and, for out-of-tree builds, <root>/../qa."""
    dirs: list = []
    for candidate in (root / "qa", root.parent / "qa"):
        if candidate.is_dir() and candidate not in dirs:
            dirs.append(candidate)
    return dirs


def _first_list(data: dict, keys) -> list | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, list) and value:
            return value
    return None


def _endpoint(edge: dict, keys) -> str | None:
    for key in keys:
        value = edge.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _node_label(node: dict) -> str | None:
    for key in _LABEL_KEYS:
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _parse_archify(data: dict):
    nodes = _first_list(data, _NODE_LIST_KEYS)
    edges = _first_list(data, _EDGE_LIST_KEYS)
    return nodes or [], edges or []


def _parse_flowmap(data: dict):
    """flowmap.json: nodes[] + flows[] with nested ordered steps[]."""
    nodes = data.get("nodes") if isinstance(data.get("nodes"), list) else []
    ordered_edges: list = []
    flows = data.get("flows")
    for flow in flows if isinstance(flows, list) else []:
        if not isinstance(flow, dict):
            continue
        steps = flow.get("steps")
        for step in steps if isinstance(steps, list) else []:
            if isinstance(step, dict):
                ordered_edges.append(step)
    return nodes or [], ordered_edges


def _view_signature(view: dict) -> tuple[Counter[str], Counter[str], list[str | None]]:
    expected_counts = Counter(view.get("elementIds", []))
    relationships = Counter(view.get("relationshipIds", []))
    steps = [step for step in view.get("steps", []) if isinstance(step, dict)]
    ordered_steps = sorted(steps, key=lambda step: step.get("order", 0))
    return expected_counts, relationships, [step.get("relationshipId") for step in ordered_steps]


def _edge_label(edge: dict, family: str) -> str | None:
    # Native flowmaps display call, not label. A present but unusable call must
    # not be rescued by unused label metadata. Keep legacy label-only inputs.
    if family == FAMILY_FLOWMAP and "call" in edge:
        value = edge["call"]
        return value.strip() if isinstance(value, str) and value.strip() else None
    return _node_label(edge)


def _resolve_relationship(edge: dict, source_id: str, destination_id: str,
                          rels_by_id: dict, family: str) -> str | None:
    # Search the entire model: a parallel relationship outside this View must not
    # silently become the relationship inside it simply because endpoints match.
    candidates = [rid for rid, relationship in rels_by_id.items()
                  if relationship.get("sourceId") == source_id
                  and relationship.get("destinationId") == destination_id]
    if "relationshipId" in edge:
        rid = edge["relationshipId"]
        return rid if isinstance(rid, str) and rid in candidates else None
    edge_id = edge.get("id")
    if isinstance(edge_id, str) and edge_id in rels_by_id:
        return edge_id if edge_id in candidates else None
    if len(candidates) == 1:
        return candidates[0]
    label = _edge_label(edge, family)
    if label:
        matches = []
        for rid in candidates:
            relationship = rels_by_id[rid]
            description = relationship.get("description")
            if not isinstance(description, str) or not description.strip():
                continue
            labels = [description]
            technology = relationship.get("technology")
            if isinstance(technology, str) and technology.strip():
                labels.append(f"{description} [{technology}]")
            if semantic_label(label) in [semantic_label(value) for value in labels]:
                matches.append(rid)
        if len(matches) == 1:
            return matches[0]
    return None


def _check_source(report: ValidationReport, path: Path, family: str, view: dict,
                  elements_by_id: dict, rels_by_id: dict) -> None:
    rel = path.relative_to(path.parents[1]).as_posix() if len(path.parents) > 1 else path.name
    try:
        data = load_json(path)
    except (OSError, ValueError, RuntimeError) as exc:
        report.error("DIA-001", rel, f"unparseable diagram input: {exc}")
        return

    view_type = view.get("type")
    expected_counts, expected_relationships, expected_steps = _view_signature(view)
    names_by_id = {eid: elements_by_id[eid]["name"] for eid in expected_counts
                   if eid in elements_by_id and isinstance(elements_by_id[eid].get("name"), str)}

    if family == FAMILY_FLOWMAP:
        nodes, edges = _parse_flowmap(data)
    else:
        nodes, edges = _parse_archify(data)
        if view_type == "dynamic" and edges is data.get("messages"):
            # Archify draws messages at their y coordinate; JSON storage order
            # does not define the visible sequence. Flowmaps retain step order.
            if all(isinstance(edge, dict) and type(edge.get("y")) in (int, float)
                   for edge in edges):
                edges = sorted(edges, key=lambda edge: edge["y"])
            else:
                report.error("DIA-006", rel, "sequence messages require numeric y coordinates")

    # Preserve identity through endpoint checks; names alone cannot identify twins.
    canonical_id_by_node: dict[str, str | None] = {}
    element_counts: Counter[str] = Counter()
    for index, node in enumerate(nodes):
        node_path = f"{rel}:nodes[{index}]"
        if not isinstance(node, dict):
            report.error("DIA-003", node_path, "node entry is not an object")
            continue
        node_id = node.get("id")
        label = _node_label(node)
        if not isinstance(node_id, str) or not label:
            report.error("DIA-003", node_path, "node has no usable id or label")
            continue
        if node_id in canonical_id_by_node:
            report.error("DIA-004", node_path, f"duplicate renderer node id {node_id!r}")
            canonical_id_by_node[node_id] = None
            continue
        if node_id in elements_by_id:
            # A known canonical ID is authoritative, never a renderer-local alias.
            matched = ([node_id] if node_id in names_by_id
                       and name_matches(names_by_id[node_id], label) else [])
        else:
            matched = [eid for eid, name in names_by_id.items()
                       if semantic_label(name) == semantic_label(label)]
            if not matched:
                matched = [eid for eid, name in names_by_id.items() if name_matches(name, label)]
        if len(matched) != 1:
            detail = ("ambiguous canonical identity" if len(matched) > 1
                      else "id/name does not match a canonical element in this View")
            report.error("DIA-003", node_path, f"node {node_id!r} ({label!r}): {detail}")
            canonical_id_by_node[node_id] = None
            continue
        canonical_id_by_node[node_id] = matched[0]
        element_counts[matched[0]] += 1

    for eid, expected in expected_counts.items():
        actual = element_counts.get(eid, 0)
        if actual < expected:
            report.error("DIA-002", rel,
                         f"canonical element {eid!r} ({names_by_id.get(eid)!r}) is missing from the diagram nodes "
                         f"(found {actual}, expected {expected})")
        elif actual > expected:
            report.error("DIA-004", rel, f"canonical element {eid!r} appears {actual}x in the diagram (expected {expected})")

    # Resolve relationship identity as well as direction (DIA-007 guards node ids).
    ordered_relationships: list = []
    for index, edge in enumerate(edges):
        edge_path = f"{rel}:edges[{index}]"
        if not isinstance(edge, dict):
            report.error("DIA-007", edge_path, "edge entry is not an object")
            continue
        source_id = _endpoint(edge, _FROM_KEYS)
        destination_id = _endpoint(edge, _TO_KEYS)
        if source_id is None or destination_id is None:
            report.error("DIA-007", edge_path, "edge has no resolvable from/to endpoints")
            continue
        if source_id not in canonical_id_by_node or destination_id not in canonical_id_by_node:
            report.error("DIA-007", edge_path,
                         f"edge references unknown node id(s): "
                         f"{[i for i in (source_id, destination_id) if i not in canonical_id_by_node]}")
            continue
        canonical_source = canonical_id_by_node[source_id]
        canonical_destination = canonical_id_by_node[destination_id]
        if canonical_source is None or canonical_destination is None:
            continue  # already reported as DIA-003/004; pair comparison would cascade
        relationship_id = _resolve_relationship(edge, canonical_source, canonical_destination, rels_by_id, family)
        if relationship_id is None:
            report.error("DIA-006" if view_type == "dynamic" else "DIA-005", edge_path,
                         f"relationship {canonical_source!r} -> {canonical_destination!r} is unknown or ambiguous; "
                         "provide a canonical relationshipId or an exact distinguishing relationship label")
            continue
        ordered_relationships.append(relationship_id)

    if view_type == "dynamic":
        if ordered_relationships != expected_steps:
            report.error("DIA-006", rel,
                         f"dynamic relationship order/count mismatch: canonical {expected_steps!r}, "
                         f"diagram {ordered_relationships!r}")
    else:
        actual_relationships = Counter(ordered_relationships)
        missing = expected_relationships - actual_relationships
        extra = actual_relationships - expected_relationships
        if missing:
            report.error("DIA-005", rel, f"missing canonical relationship(s): {dict(missing)!r}")
        if extra:
            report.error("DIA-005", rel, f"diagram relationship(s) not in the view: {dict(extra)!r}")


def run(root: Path, model_path: Path | None = None, data_path: Path | None = None,
        skill_root: Path | None = None) -> ValidationReport:
    """Validate diagram inputs against the canonical model. `data_path` is accepted for
    pipeline symmetry with validate_all but intentionally unused here."""
    report = ValidationReport("diagram-inputs")
    root = Path(root).resolve()
    sources = discover_inputs(root)
    if not sources:
        report.pass_check("DIA-001", "no diagram input sources; text-fallback path allowed", str(root / "diagrams"))
        return report

    model = None
    if model_path is not None and Path(model_path).is_file():
        try:
            model = load_json(Path(model_path))
        except (OSError, ValueError, RuntimeError) as exc:
            report.error("DIA-001", str(model_path), f"canonical model unreadable: {exc}")
    if model is None:
        report.error("DIA-001", str(root),
                     "diagram inputs exist but no canonical model is available (--model); "
                     "diagram inputs cannot be cross-checked")
        return report

    views_by_id = {v["id"]: v for v in model.get("views", []) if isinstance(v, dict) and isinstance(v.get("id"), str)}
    elements_by_id = {e.get("id"): e for e in model.get("elements", []) if isinstance(e, dict)}
    rels_by_id = {r.get("id"): r for r in model.get("relationships", []) if isinstance(r, dict)}

    checked = 0
    for path, family in sources:
        stem = source_stem(path)
        rel = path.relative_to(root).as_posix()
        view_id = resolve_view(stem, list(views_by_id))
        if view_id is None:
            report.error("DIA-001", rel, f"stem {stem!r} does not resolve to exactly one canonical view")
            continue
        _check_source(report, root / rel, family, views_by_id[view_id], elements_by_id, rels_by_id)
        checked += 1
    if checked:
        report.pass_check("DIA-001", "diagram inputs cross-checked against the canonical model",
                          f"{checked} source(s), canonical identity matching")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-check diagram inputs (archify IR / flowmap) against the canonical model")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--data", type=Path, default=Path("html/report-data.json"),
                        help="report-data path relative to --root; accepted for pipeline symmetry")
    parser.add_argument("--model", type=Path, default=Path("model/architecture-model.json"))
    parser.add_argument("--skill-root", type=Path, default=SKILL_ROOT)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    model_path = args.model if args.model.is_absolute() else root / args.model
    report = run(root, model_path=model_path, data_path=root / args.data, skill_root=args.skill_root.resolve())
    print_report(report)
    if args.output_json:
        write_report(args.output_json, report)
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
