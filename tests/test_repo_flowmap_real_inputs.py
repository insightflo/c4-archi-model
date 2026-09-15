"""Regressions for the real publishing package's guard and logical deployment.

The portable fixtures transplant the observed input shapes into the existing
schema-valid demo, not inferred runtime instances. Actual package bytes are never
written by these tests. A Node validator integration test is intentionally part
of this module so an adapter-only relaxation cannot masquerade as a working fix.
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
from c4_validation import validate_model
from generate_repo_flowmap_demo import make_model
from repo_flowmap_adapter import project

GUARD = "게시가 기존 정책상 허용된 경우"
NOTE = "기존 승인 정책은 그대로입니다. 이 흐름은 게시가 허용된 경우입니다."


class RealInputProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = make_model()
        self.view = next(v for v in self.model["views"] if v["id"] == "ordering-sequence")
        self.view["steps"][0]["condition"] = GUARD
        self.view["steps"][0]["note"] = NOTE
        report = validate_model(self.model, ROOT / "references/architecture-model.schema.json")
        self.assertFalse(report.errors, report.errors)

    def projection(self, view_id: str = "ordering-sequence") -> dict:
        return project(self.model, "model/architecture-model.json", "a" * 64, view_id)

    def test_interaction_guard_visible_without_rewriting_canonical_step(self) -> None:
        before = copy.deepcopy(self.model)
        step = self.projection()["flows"][0]["steps"][0]
        self.assertEqual(step["note"], f"조건: {GUARD}\n{NOTE}")
        self.assertEqual(step["canonicalStep"]["condition"], GUARD)
        self.assertEqual(step["canonicalStep"]["note"], NOTE)
        self.assertEqual(step["call"], step["relationship"]["description"])
        self.assertEqual(self.model, before)
        self.assertNotIn("alt", step)
        self.assertNotIn("return", step)

    def test_guard_remains_visible_without_note(self) -> None:
        self.view["steps"][0]["note"] = None
        step = self.projection()["flows"][0]["steps"][0]
        self.assertEqual(step["note"], f"조건: {GUARD}")
        self.assertIsNone(step["canonicalStep"]["note"])

    def test_unguarded_notes_unchanged(self) -> None:
        for condition in (None, ""):
            with self.subTest(condition=condition):
                self.view["steps"][0]["condition"] = condition
                step = self.projection()["flows"][0]["steps"][0]
                self.assertEqual(step["note"], NOTE)
                self.assertEqual(step["canonicalStep"]["condition"], condition)

    def test_guard_follows_step_identity_after_storage_reordering(self) -> None:
        guarded_id = self.view["steps"][0]["id"]
        self.view["steps"].reverse()
        steps = self.projection()["flows"][0]["steps"]
        self.assertEqual(steps[0]["id"], guarded_id)
        self.assertEqual(steps[0]["note"], f"조건: {GUARD}\n{NOTE}")
        self.assertEqual([s["order"] for s in steps], [1, 2, 3, 4, 5])
        self.assertEqual(steps[1]["relationshipId"], steps[3]["relationshipId"])
        self.assertEqual(steps[-1]["kind"], "self")

    def test_decision_failure_recovery_are_not_relabelled_as_guarded_messages(self) -> None:
        # A passing guarded interaction is the baseline before each mutation.
        self.projection()
        for kind in ("decision", "failure", "recovery"):
            with self.subTest(kind=kind):
                self.view["steps"][0]["kind"] = kind
                with self.assertRaisesRegex(ValueError, "fragments.*not supported"):
                    self.projection()
        self.view["steps"][0]["kind"] = "interaction"

    def test_guard_changes_are_source_bound_not_discarded(self) -> None:
        first = self.projection()
        self.view["steps"][0]["condition"] = "승인 후에만"
        second = self.projection()
        self.assertNotEqual(first, second)
        self.assertEqual(second["flows"][0]["steps"][0]["note"], f"조건: 승인 후에만\n{NOTE}")
        self.assertEqual(first["flows"][0]["steps"][0]["canonicalStep"]["condition"], GUARD)

    def test_logical_hosting_edges_do_not_invent_runtime_instances(self) -> None:
        # Start with the supported explicit instance model, then model the real
        # package shape: a selected logical container, still owned by its system,
        # plus a host -> logical relationship (no fabricated instanceOfId).
        self.projection("ordering-deployment")
        view = next(v for v in self.model["views"] if v["id"] == "ordering-deployment")
        view["elementIds"].append("order-api")
        host = next(e for e in self.model["elements"] if e["id"] == "app-host")
        relation = copy.deepcopy(self.model["relationships"][0])
        relation.update(id="host-logical", sourceId=host["id"], destinationId="order-api",
                        description="앱 실행 위치로 제안한다")
        relation.pop("codeRelation", None)
        self.model["relationships"].append(relation)
        view["relationshipIds"].append(relation["id"])
        report = validate_model(self.model, ROOT / "references/architecture-model.schema.json")
        self.assertFalse(report.errors, report.errors)
        before = copy.deepcopy(self.model)
        data = self.projection("ordering-deployment")
        self.assertEqual(data['c4']['deploymentPresentation'], 'logical-placement')
        self.assertEqual([n['element'] for n in data['nodes']],
                         [next(e for e in self.model['elements'] if e['id'] == i) for i in view['elementIds']])
        self.assertEqual(data['flows'][0]['steps'][-1]['relationship'], relation)
        self.assertEqual(data['flows'][0]['steps'][-1]['call'], relation['description'])
        self.assertEqual(self.model, before)
        self.assert_native(data)
        bad = copy.deepcopy(data)
        bad['c4']['deploymentPresentation'] = 'physical-instances'
        self.assert_native(bad, 'explicit deployment')
        bad = copy.deepcopy(data)
        bad['c4'].pop('deploymentPresentation')
        self.assert_native(bad, 'explicit deployment')

    def assert_native(self, data: dict, error: str | None = None) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'input.json'
            source.write_text(json.dumps(data, ensure_ascii=False))
            result = subprocess.run(['node', str(ROOT / 'assets/repo-flowmap/scripts/validate_flowmap.mjs'), str(source)], capture_output=True, text=True)
            if error:
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(error, result.stderr)
            else:
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_native_guard_note_cannot_be_discarded_or_changed(self) -> None:
        data = self.projection()
        self.assert_native(data)
        for note in (NOTE, '조건: invented', None):
            bad = copy.deepcopy(data)
            bad['flows'][0]['steps'][0]['note'] = note
            self.assert_native(bad, 'display note')

    def test_physical_deployment_stays_strict(self) -> None:
        data = self.projection('ordering-deployment')
        self.assertEqual(data['c4']['deploymentPresentation'], 'physical-instances')
        self.assert_native(data)
        for presentation in ('invented', 'logical-placement'):
            bad = copy.deepcopy(data)
            bad['c4']['deploymentPresentation'] = presentation
            self.assert_native(bad, 'deploymentPresentation')

    def test_native_guard_does_not_authorize_control_flow_fragments(self) -> None:
        data = self.projection()
        self.assert_native(data)
        for kind in ('decision', 'failure', 'recovery'):
            bad = copy.deepcopy(data)
            bad['c4']['view']['steps'][0]['kind'] = kind
            bad['flows'][0]['steps'][0]['canonicalStep']['kind'] = kind
            self.assert_native(bad, 'fragments unsupported')

    def test_physical_boundary_endpoints_remain_rejected_by_adapter(self) -> None:
        self.projection('ordering-deployment')
        view = next(v for v in self.model['views'] if v['id']=='ordering-deployment')
        relation = next(r for r in self.model['relationships'] if r['id']==view['relationshipIds'][0])
        relation['sourceId'] = 'app-host'
        with self.assertRaisesRegex(ValueError, 'expanded boundary endpoint'):
            self.projection('ordering-deployment')

    @unittest.skipUnless(shutil.which("node"), "Node required for the real native validator")
    def test_guarded_projection_passes_native_validator(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "guard.flowmap.json"
            source.write_text(json.dumps(self.projection(), ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                ["node", str(ROOT / "assets/repo-flowmap/scripts/validate_flowmap.mjs"), str(source)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
