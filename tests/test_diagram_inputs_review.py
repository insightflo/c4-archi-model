"""External-review regressions; run: python3 -m unittest discover -s tests -p test_diagram_inputs_review.py -v."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate_diagram_inputs import alias_match, run


class DiagramInputsReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = {
            "elements": [{"id": "a", "name": "Web App"}, {"id": "b", "name": "Order API"},
                         {"id": "c", "name": "Database"}],
            "relationships": [
                {"id": "send", "sourceId": "a", "destinationId": "b", "description": "Send order"},
                {"id": "save", "sourceId": "b", "destinationId": "c", "description": "Save order"}],
            "views": [{"id": "ordering-container", "type": "container", "elementIds": ["a", "b", "c"],
                       "relationshipIds": ["send", "save"], "steps": []}],
        }
        self.source = {"nodes": [{"id": "local-a", "label": "Web App"},
                                 {"id": "local-b", "label": "Order API"},
                                 {"id": "local-c", "label": "Database"}],
                       "edges": [{"from": "local-a", "to": "local-b"},
                                 {"from": "local-b", "to": "local-c"}]}

    def validate(self, *, flowmap: bool = False, stem: str = "container") -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "diagrams").mkdir()
            model_path = root / "model.json"
            model_path.write_text(json.dumps(self.model), encoding="utf-8")
            source = copy.deepcopy(self.source)
            if flowmap:
                source["flows"] = [{"id": "flow", "steps": source.pop("edges")}]
            suffix = "flowmap" if flowmap else ("sequence" if "messages" in source else "architecture")
            (root / "diagrams" / f"{stem}.{suffix}.json").write_text(json.dumps(source), encoding="utf-8")
            return [finding.code for finding in run(root, model_path=model_path).errors]

    def dynamic(self) -> None:
        self.model["views"][0].update(type="dynamic", steps=[
            {"id": "step-1", "order": 1, "relationshipId": "send"},
            {"id": "step-2", "order": 2, "relationshipId": "save"}])

    def sequence(self) -> None:
        self.dynamic()
        self.source["schema_version"] = 1
        self.source["diagram_type"] = "sequence"
        self.source["participants"] = self.source.pop("nodes")
        self.source["messages"] = self.source.pop("edges")
        for message, y in zip(self.source["messages"], (180, 240)):
            message["y"] = y

    def test_sequence_reversed_visual_order_is_rejected(self) -> None:
        self.sequence()
        self.assertEqual([], self.validate())
        self.source["messages"][0]["y"] = 300
        self.assertIn("DIA-006", self.validate())

    def test_sequence_shuffled_array_with_correct_visual_order_is_accepted(self) -> None:
        self.sequence()
        self.source["messages"].reverse()
        self.assertEqual([], self.validate())

    def test_sequence_without_numeric_y_is_rejected(self) -> None:
        self.sequence()
        for y in (None, "180", True):
            with self.subTest(y=y):
                self.source["messages"][0]["y"] = y
                self.assertIn("DIA-006", self.validate())
        del self.source["messages"][0]["y"]
        self.assertIn("DIA-006", self.validate())

    def test_flowmap_order_is_array_order_even_with_y_coordinates(self) -> None:
        self.dynamic()
        for edge, y in zip(self.source["edges"], (300, 180)):
            edge["y"] = y
        self.assertEqual([], self.validate(flowmap=True))
        self.source["edges"].reverse()
        self.assertIn("DIA-006", self.validate(flowmap=True))

    def test_missing_same_name_node_is_rejected(self) -> None:
        self.model["elements"].append({"id": "a2", "name": "Web App"})
        self.model["views"][0]["elementIds"].append("a2")
        for flowmap in (False, True):
            with self.subTest(flowmap=flowmap):
                self.assertIn("DIA-002", self.validate(flowmap=flowmap))
        # Duplicate names require canonical IDs, not ambiguous renderer-local IDs.
        self.source["nodes"][0]["id"] = "a"
        self.source["edges"][0]["from"] = "a"
        self.source["nodes"].append({"id": "a2", "label": "Web App"})
        for flowmap in (False, True):
            with self.subTest(flowmap=flowmap):
                self.assertEqual([], self.validate(flowmap=flowmap))

    def parallel(self) -> None:
        self.model["relationships"][1].update(sourceId="a", destinationId="b", description="Cancel order")
        self.source["edges"][1].update({"from": "local-a", "to": "local-b"})
        for edge, rid in zip(self.source["edges"], ["send", "save"]):
            edge["relationshipId"] = rid

    def test_exact_names_do_not_collide_with_longer_names(self) -> None:
        self.model["elements"][0]["name"] = "API"
        self.source["nodes"][0]["label"] = "API"
        self.assertEqual([], self.validate())

    def test_invented_suffix_and_shortening_are_rejected(self) -> None:
        self.assertEqual([], self.validate())
        for label in ("Order API Backup", "API", "Order API [Backup]"):
            with self.subTest(label=label):
                self.source["nodes"][1]["label"] = label
                self.assertIn("DIA-003", self.validate())

    def test_known_type_decoration_is_allowed(self) -> None:
        self.source["nodes"][1]["label"] = "Order API [Container]"
        self.assertEqual([], self.validate())

    def test_file_stem_alias_remains_unambiguous(self) -> None:
        self.assertEqual([], self.validate())
        self.assertEqual([], self.validate(stem="01-container"))
        self.assertEqual("ordering-container", alias_match("container", ["ordering-container"]))
        self.assertIsNone(alias_match("container", ["ordering-container", "billing-container"]))

    def test_dynamic_canonical_order_not_storage_order(self) -> None:
        self.dynamic()
        self.assertEqual([], self.validate())
        self.model["views"][0]["steps"].reverse()
        for flowmap in (False, True):
            with self.subTest(flowmap=flowmap):
                self.assertEqual([], self.validate(flowmap=flowmap))

    def test_dynamic_reversed_diagram_is_rejected(self) -> None:
        self.dynamic()
        self.assertEqual([], self.validate())
        self.source["edges"].reverse()
        self.assertIn("DIA-006", self.validate())

    def test_dynamic_parallel_relationship_swap_is_rejected(self) -> None:
        self.dynamic()
        self.parallel()
        self.assertEqual([], self.validate())
        self.source["edges"].reverse()
        for flowmap in (False, True):
            with self.subTest(flowmap=flowmap):
                self.assertIn("DIA-006", self.validate(flowmap=flowmap))

    def test_static_parallel_relationship_duplicate_is_rejected(self) -> None:
        self.parallel()
        self.assertEqual([], self.validate())
        self.source["edges"][1]["relationshipId"] = "send"
        self.assertIn("DIA-005", self.validate())

    def test_parallel_without_identity_fails_closed(self) -> None:
        self.parallel()
        self.assertEqual([], self.validate())
        for edge in self.source["edges"]:
            del edge["relationshipId"]
        self.assertIn("DIA-005", self.validate())

    def test_exact_relationship_labels_disambiguate_parallel_edges(self) -> None:
        self.dynamic()
        self.parallel()
        for edge, label in zip(self.source["edges"], ["Send order", "Cancel order"]):
            del edge["relationshipId"]
            edge["label"] = label
        self.assertEqual([], self.validate())
        self.source["edges"].reverse()
        self.assertIn("DIA-006", self.validate())

    def test_canonical_edge_ids_disambiguate_parallel_relationships(self) -> None:
        self.dynamic()
        self.parallel()
        for edge in self.source["edges"]:
            edge["id"] = edge.pop("relationshipId")
        self.assertEqual([], self.validate())
        self.source["edges"].reverse()
        self.assertIn("DIA-006", self.validate())

    def test_exact_description_with_technology_disambiguates(self) -> None:
        self.dynamic()
        self.parallel()
        for relationship in self.model["relationships"]:
            relationship["description"] = "Send order"
        self.model["relationships"][0]["technology"] = "HTTPS"
        self.model["relationships"][1]["technology"] = "AMQP"
        for edge, label in zip(self.source["edges"], ["Send order [HTTPS]", "Send order [AMQP]"]):
            del edge["relationshipId"]
            edge["label"] = label
        self.assertEqual([], self.validate())
        self.source["edges"].reverse()
        self.assertIn("DIA-006", self.validate())

    def test_real_ordering_model_views_with_local_renderer_ids(self) -> None:
        example = Path(__file__).resolve().parents[1] / "examples/ordering-system.architecture-model.json"
        original = json.loads(example.read_text(encoding="utf-8"))
        elements = {element["id"]: element for element in original["elements"]}
        relationships = {relationship["id"]: relationship for relationship in original["relationships"]}
        for view in original["views"]:
            self.model = copy.deepcopy(original)
            local_ids = {eid: f"local-{index}" for index, eid in enumerate(view["elementIds"])}
            ids = ([step["relationshipId"] for step in sorted(view["steps"], key=lambda step: step["order"])]
                   if view["type"] == "dynamic" else view["relationshipIds"])
            self.source = {"nodes": [{"id": local_ids[eid], "label": elements[eid]["name"]}
                                     for eid in view["elementIds"]],
                           "edges": [{"from": local_ids[relationships[rid]["sourceId"]],
                                      "to": local_ids[relationships[rid]["destinationId"]]}
                                     for rid in ids]}
            for flowmap in (False, True):
                with self.subTest(view=view["id"], flowmap=flowmap):
                    self.assertEqual([], self.validate(stem=view["id"], flowmap=flowmap))

    def test_explicit_unknown_or_wrong_endpoint_identity_is_rejected(self) -> None:
        self.assertEqual([], self.validate())
        for rid in ("unknown", "save"):
            with self.subTest(rid=rid):
                self.source["edges"][0]["relationshipId"] = rid
                self.assertIn("DIA-005", self.validate())

    def test_same_endpoint_relationship_outside_view_is_rejected(self) -> None:
        self.parallel()
        self.model["views"][0]["relationshipIds"] = ["send"]
        self.source["edges"] = self.source["edges"][:1]
        self.assertEqual([], self.validate())
        self.source["edges"][0]["relationshipId"] = "save"
        self.assertIn("DIA-005", self.validate())


if __name__ == "__main__":
    unittest.main()
