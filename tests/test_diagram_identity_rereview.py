"""Regressions for external-review P1-01/02/03; no renderer or receipts required."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validate_diagram_inputs as dia


class DiagramIdentityRereviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = {
            "elements": [
                {"id": "web-app", "name": "Web App"},
                {"id": "fulfilment-worker", "name": "Worker"},
                {"id": "order-api", "name": "Order API"},
            ],
            "relationships": [
                {"id": "web-to-api", "sourceId": "web-app", "destinationId": "order-api",
                 "description": "Create order"},
            ],
            "views": [{"id": "ordering-container", "type": "container",
                       "elementIds": ["web-app", "fulfilment-worker", "order-api"],
                       "relationshipIds": ["web-to-api"], "steps": []}],
        }
        self.source = {
            "nodes": [{"id": "web-app", "label": "Web App"},
                      {"id": "fulfilment-worker", "label": "Worker"},
                      {"id": "order-api", "label": "Order API"}],
            "edges": [{"from": "web-app", "to": "order-api", "relationshipId": "web-to-api"}],
        }

    def validate(self, *, stem: str = "container", flowmap: bool = True) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "diagrams").mkdir()
            model_path = root / "model.json"
            model_path.write_text(json.dumps(self.model), encoding="utf-8")
            source = copy.deepcopy(self.source)
            if flowmap:
                source["flows"] = [{"id": "order", "steps": source.pop("edges")}]
            suffix = "flowmap" if flowmap else "architecture"
            (root / "diagrams" / f"{stem}.{suffix}.json").write_text(json.dumps(source), encoding="utf-8")
            return [finding.code for finding in dia.run(root, model_path=model_path).errors]

    def duplicate_names(self) -> None:
        for element, node in zip(self.model["elements"][:2], self.source["nodes"][:2]):
            element["name"] = node["label"] = "Service"

    def local_ids(self) -> None:
        for node in self.source["nodes"]:
            node["id"] = "local-" + node["id"]
        for edge in self.source["edges"]:
            edge["from"] = "local-" + edge["from"]
            edge["to"] = "local-" + edge["to"]

    def parallel_calls(self, *, dynamic: bool = False) -> None:
        self.model["relationships"].append({
            "id": "cancel", "sourceId": "web-app", "destinationId": "order-api",
            "description": "Cancel order"})
        self.model["views"][0]["relationshipIds"].append("cancel")
        self.source["edges"] = [
            {"from": "web-app", "to": "order-api", "call": "Create order"},
            {"from": "web-app", "to": "order-api", "call": "Cancel order"},
        ]
        if dynamic:
            self.model["views"][0].update(type="dynamic", steps=[
                {"order": 1, "relationshipId": "web-to-api"},
                {"order": 2, "relationshipId": "cancel"}])

    def context_and_detail(self) -> None:
        context = copy.deepcopy(self.model["views"][0])
        context.update(id="ordering-context", type="context", elementIds=["web-app", "order-api"])
        self.model["views"][0]["id"] = "ordering-context-detail"
        self.model["views"].append(context)

    def test_shared_source_stem_preserves_dots_and_removes_full_known_suffix(self) -> None:
        resolver = getattr(dia, "source_stem", None)
        self.assertTrue(callable(resolver), "shared source_stem API is missing")
        for suffix in ("flowmap", "architecture", "sequence", "workflow", "dataflow", "lifecycle"):
            with self.subTest(suffix=suffix):
                self.assertEqual("ordering.context.detail", resolver(Path(f"nested/ordering.context.detail.{suffix}.json")))
        self.assertEqual("ordering.context.json", resolver(Path("ordering.context.json")))

    def test_shared_view_resolution_priority_and_ambiguity(self) -> None:
        resolver = getattr(dia, "resolve_view", None)
        self.assertTrue(callable(resolver), "shared resolve_view API is missing")
        cases = [
            ("ordering.context", ["ordering.context", "ordering-context"], "ordering.context"),
            ("ordering-context", ["ordering.context", "ordering-context"], "ordering-context"),
            ("ORDERING CONTEXT", ["ordering.context", "ordering-context"], None),
            ("ordering.context.detail", ["ordering-context", "ordering-context-detail"], "ordering-context-detail"),
            ("01-container", ["ordering-container"], "ordering-container"),
            ("01-container", ["01-container", "container"], "01-container"),
            ("01-container", ["01_container", "01 container", "container"], None),
            ("container", ["ordering-container", "billing-container"], None),
            ("other", ["ordering-context"], None),
        ]
        for stem, view_ids, expected in cases:
            with self.subTest(stem=stem, view_ids=view_ids):
                self.assertEqual(expected, resolver(stem, view_ids))
                self.assertEqual(expected, resolver(stem, list(reversed(view_ids))))

    def test_dotted_filename_uses_detail_view_not_first_dot_prefix(self) -> None:
        self.context_and_detail()
        self.assertEqual([], self.validate(stem="ordering-context.detail"))

    def test_dotted_filename_rejects_short_context_content_for_detail(self) -> None:
        self.context_and_detail()
        self.source["nodes"].pop(1)
        self.assertIn("DIA-002", self.validate(stem="ordering-context.detail"))

    def test_exact_view_id_wins_over_normalization_collision(self) -> None:
        other = copy.deepcopy(self.model["views"][0])
        other.update(id="ordering_container", elementIds=["web-app", "order-api"])
        self.model["views"].append(other)
        self.assertEqual([], self.validate(stem="ordering-container"))

    def test_numbered_filename_alias_is_accepted(self) -> None:
        self.assertEqual([], self.validate(stem="01-container"))

    def test_ambiguous_filename_is_rejected(self) -> None:
        other = copy.deepcopy(self.model["views"][0])
        other["id"] = "billing-container"
        self.model["views"].append(other)
        self.assertIn("DIA-001", self.validate(stem="container"))

    def test_duplicate_names_with_canonical_node_ids_are_valid(self) -> None:
        self.duplicate_names()
        for flowmap in (False, True):
            with self.subTest(flowmap=flowmap):
                self.assertEqual([], self.validate(flowmap=flowmap))

    def test_wrong_endpoint_with_same_name_is_rejected(self) -> None:
        self.duplicate_names()
        self.assertEqual([], self.validate())
        self.source["edges"][0]["from"] = "fulfilment-worker"
        for flowmap in (False, True):
            with self.subTest(flowmap=flowmap):
                self.assertIn("DIA-005", self.validate(flowmap=flowmap))

    def test_wrong_same_name_endpoint_without_relationship_id_is_rejected(self) -> None:
        self.duplicate_names()
        del self.source["edges"][0]["relationshipId"]
        self.assertEqual([], self.validate())
        self.source["edges"][0]["from"] = "fulfilment-worker"
        self.assertIn("DIA-005", self.validate())

    def test_canonical_node_id_must_match_its_own_name(self) -> None:
        self.source["nodes"][0]["label"], self.source["nodes"][1]["label"] = "Worker", "Web App"
        self.source["edges"][0]["from"] = "fulfilment-worker"
        self.assertIn("DIA-003", self.validate())

    def test_canonical_node_id_outside_view_cannot_alias_by_name(self) -> None:
        self.model["elements"].append({"id": "other-app", "name": "Web App"})
        self.source["nodes"][0]["id"] = "other-app"
        self.source["edges"][0]["from"] = "other-app"
        self.assertIn("DIA-003", self.validate())

    def test_unambiguous_local_node_ids_are_accepted(self) -> None:
        self.local_ids()
        for flowmap in (False, True):
            with self.subTest(flowmap=flowmap):
                self.assertEqual([], self.validate(flowmap=flowmap))

    def test_duplicate_names_with_local_node_ids_are_ambiguous(self) -> None:
        self.duplicate_names()
        self.local_ids()
        for flowmap in (False, True):
            with self.subTest(flowmap=flowmap):
                self.assertIn("DIA-003", self.validate(flowmap=flowmap))

    def test_canonical_duplicate_names_do_not_allow_duplicate_identity(self) -> None:
        self.duplicate_names()
        self.source["nodes"][1]["id"] = "web-app"
        errors = self.validate()
        self.assertIn("DIA-002", errors)
        self.assertIn("DIA-004", errors)

    def test_canonical_id_disambiguates_names_with_same_normalization(self) -> None:
        self.model["elements"][0]["name"] = self.source["nodes"][0]["label"] = "Service"
        self.model["elements"][1]["name"] = self.source["nodes"][1]["label"] = "SERVICE"
        self.assertEqual([], self.validate())

    def test_native_parallel_calls_resolve_static_and_dynamic_relationships(self) -> None:
        self.parallel_calls()
        self.assertEqual([], self.validate())
        self.model["views"][0].update(type="dynamic", steps=[
            {"order": 1, "relationshipId": "web-to-api"}, {"order": 2, "relationshipId": "cancel"}])
        self.assertEqual([], self.validate())

    def test_native_parallel_calls_wrong_displayed_label_is_rejected(self) -> None:
        self.parallel_calls()
        self.assertEqual([], self.validate())
        self.source["edges"][1]["call"] = "Cancel some order"
        self.assertIn("DIA-005", self.validate())

    def test_native_call_takes_priority_over_unused_label(self) -> None:
        self.parallel_calls(dynamic=True)
        for edge, unused_label in zip(self.source["edges"], ("Cancel order", "Create order")):
            edge["label"] = unused_label
        self.assertEqual([], self.validate())
        self.source["edges"].reverse()
        self.assertIn("DIA-006", self.validate())

    def test_native_invalid_call_cannot_be_hidden_by_correct_unused_label(self) -> None:
        self.parallel_calls()
        for edge in self.source["edges"]:
            edge["label"] = edge["call"]
        for call in ("Wrong action", "", None):
            with self.subTest(call=call):
                self.source["edges"][1]["call"] = call
                self.assertIn("DIA-005", self.validate())

    def test_archify_uses_label_instead_of_flowmap_call(self) -> None:
        self.parallel_calls(dynamic=True)
        for edge in self.source["edges"]:
            edge["label"] = edge["call"]
            edge["call"] = "Unused native metadata"
        self.assertEqual([], self.validate(flowmap=False))
        self.source["edges"][1]["label"] = "Wrong action"
        self.assertIn("DIA-006", self.validate(flowmap=False))

    def test_explicit_identity_does_not_impose_all_prose_equality(self) -> None:
        self.parallel_calls()
        for edge, rid in zip(self.source["edges"], ("web-to-api", "cancel")):
            edge.update(relationshipId=rid, call="Custom display wording")
        self.assertEqual([], self.validate())


if __name__ == "__main__":
    unittest.main()
