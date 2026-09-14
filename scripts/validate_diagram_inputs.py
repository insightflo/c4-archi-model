#!/usr/bin/env python3
"""Cross-check diagram inputs (archify IR, repo-flowmap flowmaps) against the canonical model.

External review P0-1 (2026-09): nothing verified that rendered diagram inputs still
describe the canonical model — the pipeline relied on agent discipline only. This
validator re-derives, per discovered diagram source, the expected element name set,
relationship direction pairs, and dynamic step order from the canonical model, and
compares them with the diagram input. Matching is name-based (renderer-local IDs are
irrelevant), so it works for every renderer that consumes the documented source
formats. Node labels may carry renderer decorations ("공개 독자 [Person]") or human
shortenings ("CMS 논리 DB" for canonical "CMS 전용 논리 DB"); a label resolves to the
unique canonical name it equals, contains, is contained by, or is a token subset of.

Discovered sources (under ``<root>/diagrams/``):
  * archify IR: ``*.architecture.json | *.sequence.json | *.workflow.json | *.dataflow.json | *.lifecycle.json``
  * flowmap:    ``*.flowmap.json``

A file stem (name up to the first ``.``) maps to a canonical view by name: a leading
numeric index prefix is stripped (``01-system-context`` -> ``system-context``) and the
result must resolve to exactly one view id (exact match or unique token-subset match).

Checks (documented contract):
  DIA-001  ERROR  diagram source cannot be tied to a canonical view (unknown or
                   ambiguous stem, unparseable JSON, unrecognized IR structure, or no
                   canonical model available for cross-checking)
  DIA-002  ERROR  a canonical element of the view is missing from the diagram nodes
  DIA-003  ERROR  a diagram node label resolves to no (or ambiguously many) canonical
                   element names — an invented node
  DIA-004  ERROR  two or more diagram nodes resolve to the same canonical element
  DIA-005  ERROR  static view: directed relationship (source name, destination name)
                   pairs differ from the diagram edges (missing or extra pairs)
  DIA-006  ERROR  dynamic view: diagram edge sequence does not match the canonical
                   step order (the relationshipId order of view.steps)
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


def name_matches(canonical: str, label: str) -> bool:
    a, b = normalize_label(canonical), normalize_label(label)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    ta, tb = label_tokens(canonical), label_tokens(label)
    return bool(ta and tb and (ta <= tb or tb <= ta))


def stem_key(stem: str) -> str:
    """'01-system-context' -> 'system-context'; 'context' stays 'context'."""
    match = _INDEX_PREFIX.match(stem.strip())
    return match.group(1).strip() if match else stem.strip()


def alias_match(stem: str, candidates: list) -> str | None:
    """Resolve `stem` to the one candidate that is equal or a unique token-subset match."""
    target = normalize_label(stem)
    exact = [c for c in candidates if normalize_label(c) == target]
    if len(exact) == 1:
        return exact[0]
    target_tokens = set(target.split())
    matches = []
    for candidate in candidates:
        candidate_tokens = set(normalize_label(candidate).split())
        if target_tokens and candidate_tokens and (target_tokens <= candidate_tokens or candidate_tokens <= target_tokens):
            matches.append(candidate)
    unique = sorted(set(matches))
    return unique[0] if len(unique) == 1 else None


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
    flows = data.get("flows") if isinstance(data.get("flows"), list) else []
    for flow in flows:
        if not isinstance(flow, dict):
            continue
        steps = flow.get("steps") if isinstance(flow.get("steps"), list) else []
        for step in steps:
            if isinstance(step, dict):
                ordered_edges.append(step)
    return nodes or [], ordered_edges


def _view_signature(view: dict, elements_by_id: dict, rels_by_id: dict):
    names: list = []
    for eid in view.get("elementIds", []):
        element = elements_by_id.get(eid)
        if isinstance(element, dict) and isinstance(element.get("name"), str):
            names.append(element["name"])
    expected_counts = Counter(names)
    rel_pairs: Counter = Counter()
    for rid in view.get("relationshipIds", []):
        rel = rels_by_id.get(rid)
        if not isinstance(rel, dict):
            continue
        source = elements_by_id.get(rel.get("sourceId"))
        destination = elements_by_id.get(rel.get("destinationId"))
        if (isinstance(source, dict) and isinstance(destination, dict)
                and isinstance(source.get("name"), str) and isinstance(destination.get("name"), str)):
            rel_pairs[(source["name"], destination["name"])] += 1
    step_pairs: list = []
    for step in view.get("steps", []):
        if not isinstance(step, dict):
            continue
        rel = rels_by_id.get(step.get("relationshipId"))
        if not isinstance(rel, dict):
            continue
        source = elements_by_id.get(rel.get("sourceId"))
        destination = elements_by_id.get(rel.get("destinationId"))
        if (isinstance(source, dict) and isinstance(destination, dict)
                and isinstance(source.get("name"), str) and isinstance(destination.get("name"), str)):
            step_pairs.append((source["name"], destination["name"]))
    return expected_counts, rel_pairs, step_pairs


def _resolve_view(stem: str, views_by_id: dict):
    return alias_match(stem, list(views_by_id.keys()))


def _check_source(report: ValidationReport, path: Path, family: str, view: dict,
                  elements_by_id: dict, rels_by_id: dict) -> None:
    rel = path.relative_to(path.parents[1]).as_posix() if len(path.parents) > 1 else path.name
    try:
        data = load_json(path)
    except (OSError, ValueError, RuntimeError) as exc:
        report.error("DIA-001", rel, f"unparseable diagram input: {exc}")
        return

    view_type = view.get("type")
    expected_counts, rel_pairs, step_pairs = _view_signature(view, elements_by_id, rels_by_id)
    unique_names = sorted(expected_counts)

    if family == FAMILY_FLOWMAP:
        nodes, edges = _parse_flowmap(data)
    else:
        nodes, edges = _parse_archify(data)

    # Resolve every node label to a canonical element name (DIA-003/DIA-004).
    node_name_by_id: dict = {}
    label_counts: Counter = Counter()
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
        matched = [name for name in unique_names if name_matches(name, label)]
        if len(matched) != 1:
            detail = "ambiguous with canonical names" if len(matched) > 1 else "no canonical element name matches"
            report.error("DIA-003", node_path, f"invented node {label!r}: {detail}")
            node_name_by_id[node_id] = None
            continue
        node_name_by_id[node_id] = matched[0]
        label_counts[matched[0]] += 1

    for name, expected in expected_counts.items():
        actual = label_counts.get(name, 0)
        if actual == 0:
            report.error("DIA-002", rel, f"canonical element {name!r} is missing from the diagram nodes")
        elif actual > expected:
            report.error("DIA-004", rel, f"canonical element {name!r} appears {actual}x in the diagram (expected {expected})")

    # Collect directed name pairs from the edges (DIA-007 guards endpoint ids).
    ordered_pairs: list = []
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
        if source_id not in node_name_by_id or destination_id not in node_name_by_id:
            report.error("DIA-007", edge_path,
                         f"edge references unknown node id(s): "
                         f"{[i for i in (source_id, destination_id) if i not in node_name_by_id]}")
            continue
        source_name = node_name_by_id[source_id]
        destination_name = node_name_by_id[destination_id]
        if source_name is None or destination_name is None:
            continue  # already reported as DIA-003; pair comparison would cascade
        ordered_pairs.append((source_name, destination_name))

    if view_type == "dynamic":
        if len(ordered_pairs) != len(step_pairs):
            report.error("DIA-006", rel,
                         f"dynamic step count mismatch: canonical {len(step_pairs)}, diagram {len(ordered_pairs)}")
        else:
            for index, (expected_pair, actual_pair) in enumerate(zip(step_pairs, ordered_pairs)):
                if expected_pair != actual_pair:
                    report.error("DIA-006", rel,
                                 f"dynamic step order diverges at step {index + 1}: "
                                 f"canonical {expected_pair[0]!r} -> {expected_pair[1]!r}, "
                                 f"diagram {actual_pair[0]!r} -> {actual_pair[1]!r}")
                    break
    else:
        actual_pairs: Counter = Counter(ordered_pairs)
        missing = rel_pairs - actual_pairs
        extra = actual_pairs - rel_pairs
        if missing:
            detail = ", ".join(f"{s!r}->{d!r}" for s, d in sorted(missing))
            report.error("DIA-005", rel, f"missing canonical relationship pair(s): {detail}")
        if extra:
            detail = ", ".join(f"{s!r}->{d!r}" for s, d in sorted(extra))
            report.error("DIA-005", rel, f"diagram edge(s) not in the view: {detail}")


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

    views_by_id = {v.get("id"): v for v in model.get("views", []) if isinstance(v, dict) and isinstance(v.get("id"), str)}
    elements_by_id = {e.get("id"): e for e in model.get("elements", []) if isinstance(e, dict)}
    rels_by_id = {r.get("id"): r for r in model.get("relationships", []) if isinstance(r, dict)}

    checked = 0
    for path, family in sources:
        stem = path.name.split(".")[0]
        rel = path.relative_to(root).as_posix()
        view_id = _resolve_view(stem, views_by_id)
        if view_id is None:
            report.error("DIA-001", rel, f"stem {stem!r} does not resolve to exactly one canonical view")
            continue
        _check_source(report, root / rel, family, views_by_id[view_id], elements_by_id, rels_by_id)
        checked += 1
    if checked:
        report.pass_check("DIA-001", "diagram inputs cross-checked against the canonical model",
                          f"{checked} source(s), name-based matching")
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
