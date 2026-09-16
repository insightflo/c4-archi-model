"""Full visual report behavior: original-image focus, canonical joins and safe evidence.

All output is temporary; C4_REAL_PACKAGE is read-only. No downloaded code is used.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_html_report import hydrate_report, inject  # noqa: E402 (repo-local scripts)
from c4_validation import ValidationReport  # noqa: E402
from test_report_story import CHROME, sync_playwright  # noqa: E402


def uri(text: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(text.encode()).decode()


def fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    source = {"id": "source-z", "name": "Design <img src=x onerror=alert(1)>",
              "location": "sources/design.md", "contentHash": "sha256:original", "limitations": ["DOC_ONLY"]}
    claim = {"id": "claim-z", "statement": "Exact <script>window.pwned=1</script> statement",
             "targetIds": ["request"], "derivation": "explicit", "confidence": "DOC_ONLY",
             "supports": [{"sourceId": "source-z", "locator": "§ 4 / lines 12–19", "excerpt": "<b>literal evidence</b>"}],
             "contradictions": [{"sourceId": "source-z", "locator": "§ 9", "excerpt": None}],
             "usedBy": [], "notes": ["Not runtime verified"]}
    bundle = {"session": {}, "understanding": None,
              "model": {"elements": [
                  {"id": "sender", "name": "Sender", "description": "Owns input only", "claimIds": ["claim-z"], "confidence": "DOC_ONLY"},
                  {"id": "receiver", "name": "Receiver", "description": "Owns processing only", "claimIds": [], "confidence": "UNVERIFIED"}],
                  "relationships": [{"id": "request", "sourceId": "sender", "destinationId": "receiver", "description": "Send", "claimIds": ["claim-z"]}],
                  "views": [{"id": "scenario", "type": "dynamic", "title": "Repeated calls", "elementIds": ["sender", "receiver"],
                             "relationshipIds": ["request"], "steps": [
                                 {"id": "first", "order": 1, "relationshipId": "request", "note": "First detail"},
                                 {"id": "again", "order": 2, "relationshipId": "request", "note": "Second detail"}]},
                            {"id": "structure", "type": "container", "title": "Responsibilities", "elementIds": ["sender", "receiver"], "relationshipIds": ["request"]}]},
              "ledger": {"sources": [source], "claims": [claim]},
              "coverage": {"unknownRelevant": [
                  {"id": "unknown-a", "label": "Delivery not checked", "reason": "No runtime evidence", "impact": "blocks-change", "nextCheck": "Check delivery receipt", "claimIds": ["claim-z"], "affectedModelIds": ["request"], "affectedViewIds": [], "sourceIds": ["source-z"]},
                  {"id": "unknown-b", "label": "Absent follow-up", "reason": "Not specified", "claimIds": [], "sourceIds": []}]}}
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 600" data-view-id="scenario">
      <style>text{font:16px sans-serif}</style>
      <g data-canonical-id="sender"><rect x="50" y="20" width="180" height="70"/><text x="60" y="50">Sender</text></g>
      <g data-canonical-id="receiver"><rect x="650" y="20" width="180" height="70"/><text x="660" y="50">Receiver</text></g>
      <g data-step-id="first"><text x="250" y="170">First</text><path data-relation="request" d="M140 200 H740"/></g>
      <g data-step-id="again" transform="translate(0 230)"><text x="250" y="170">Again</text><path data-relation="request" d="M140 200 H740"/></g></svg>'''
    data = {"analysis": {}, "flows": [{"id": "calls", "viewId": "scenario", "kind": "normal"}],
            "diagrams": [{"id": "sequence", "viewId": "scenario", "dataUri": uri(svg), "mimeType": "image/svg+xml"},
                         {"id": "static", "viewId": "structure", "dataUri": uri(svg.replace('data-view-id="scenario"', 'data-view-id="structure"')), "mimeType": "image/svg+xml"}],
            "elementGroups": [{"id": "roles", "elements": [{"modelId": "sender"}, {"modelId": "receiver"}]}]}
    return data, bundle


class CompleteHydrationTests(unittest.TestCase):
    def test_exact_ledger_and_unknown_links_are_carried_without_invention(self) -> None:
        data, bundle = fixture()
        before = copy.deepcopy((data, bundle))
        result = hydrate_report(data, bundle, ValidationReport("test"))
        self.assertEqual(result.get("claims"), bundle["ledger"]["claims"])
        self.assertEqual(result["diagrams"][1].get("elementIds"), ["sender", "receiver"])
        self.assertEqual(result["issues"][0].get("claimIds"), ["claim-z"])
        self.assertEqual(result["issues"][0].get("affectedModelIds"), ["request"])
        self.assertEqual(result["issues"][1]["impact"], "")
        self.assertEqual(result["issues"][1]["candidates"], [])
        self.assertEqual((data, bundle), before)


@unittest.skipUnless(sync_playwright and Path(CHROME).is_file(), "local Chrome and Playwright required")
class CompleteVisualBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=CHROME, headless=True)
        cls.template = (ROOT / "assets/html-report-template.html").read_text()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.pw.stop()

    def setUp(self) -> None:
        self.page = self.browser.new_page(viewport={"width": 1440, "height": 1000}, offline=True)
        self.errors: list[str] = []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.page.close()
        self.tmp.cleanup()

    def load(self, data: dict[str, Any] | None = None, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
        if data is None:
            data, bundle = fixture()
        result = hydrate_report(data, bundle, ValidationReport("test"))
        path = Path(self.tmp.name) / "report.html"
        path.write_text(inject(self.template, result))
        self.page.goto(path.as_uri())
        self.page.locator("#flows").scroll_into_view_if_needed()
        return result

    def focus_frame(self, widget: Any) -> Any:
        self.assertEqual(widget.locator("iframe").count(), 1, "co-located original semantic diagram missing")
        widget.locator("iframe").scroll_into_view_if_needed()
        frame = widget.locator("iframe").element_handle().content_frame()
        return frame

    def test_repeated_relation_selects_only_exact_step_and_preserves_original_image(self) -> None:
        result = self.load()
        story = self.page.locator("#flow-panel-calls")
        widget = story.locator(".semantic-diagram")
        frame = self.focus_frame(widget)
        frame.wait_for_selector('[data-focus-step="first"]')
        self.assertEqual(frame.locator(".focus-step").count(), 1)
        self.assertEqual(frame.locator(".original-image").get_attribute("href"), result["diagrams"][0]["dataUri"])
        first_y = float(frame.locator(".focus-step").get_attribute("y"))
        story.locator('[data-step-nav="next"]').click()
        frame.wait_for_selector('[data-focus-step="again"]')
        self.assertEqual(frame.locator(".focus-step").count(), 1)
        self.assertEqual(frame.locator(".viewport-clip").count(), 1, "focus crop must clip original pixels, not leak adjacent messages")
        self.assertGreater(float(frame.locator(".focus-step").get_attribute("y")), first_y + 200)
        self.assertIn("Second detail", story.locator(".flow-step:not([hidden])").inner_text())
        widget.get_by_role("button", name="전체 그림", exact=True).click()
        self.assertEqual(frame.locator("svg.snapshot").get_attribute("viewBox"), "0 0 900 600")
        self.assertEqual(frame.locator(".viewport-clip").get_attribute("height"), "600")
        widget.get_by_role("button", name="선택 부분", exact=True).click()
        self.assertNotEqual(frame.locator("svg.snapshot").get_attribute("viewBox"), "0 0 900 600")
        self.page.set_viewport_size({"width": 360, "height": 800})
        self.page.wait_for_timeout(100)
        self.assertGreater(frame.locator("svg.snapshot").bounding_box()["width"], 360,
                           "resizing must recompute reading scale, not shrink the selected message")
        self.assertEqual(self.errors, [])

    def test_return_to_selection_restores_readable_rendered_dimensions(self) -> None:
        data, bundle = fixture()
        raw = base64.b64decode(data["diagrams"][0]["dataUri"].split(",", 1)[1]).decode()
        data["diagrams"][0]["dataUri"] = uri(raw.replace('900 600', '1800 600').replace('H740', 'H1540'))
        for width in (1440, 360):
            with self.subTest(viewport=width):
                self.page.set_viewport_size({"width": width, "height": 1000})
                self.load(data, bundle)
                widget = self.page.locator("#flow-panel-calls .semantic-diagram")
                frame = self.focus_frame(widget)
                frame.wait_for_selector('[data-focus-step="first"]')
                snapshot = frame.locator("svg.snapshot")
                selected_view = snapshot.get_attribute("viewBox")
                initial = snapshot.bounding_box()
                initial_focus = frame.locator(".focus-step").bounding_box()
                self.assertGreater(initial["width"], 1000, "long message must initially open at reading scale")
                widget.get_by_role("button", name="전체 그림", exact=True).click()
                frame.wait_for_function('document.querySelector("svg.snapshot").getAttribute("viewBox")==="0 0 1800 600"')
                self.assertLess(snapshot.bounding_box()["width"], initial["width"])
                widget.get_by_role("button", name="선택 부분", exact=True).click()
                frame.wait_for_function('(view)=>document.querySelector("svg.snapshot").getAttribute("viewBox")===view', arg=selected_view)
                restored = snapshot.bounding_box()
                restored_focus = frame.locator(".focus-step").bounding_box()
                for dimension in ("width", "height"):
                    self.assertAlmostEqual(restored[dimension], initial[dimension], delta=1,
                                           msg=f"returning to selection must restore readable {dimension}")
                    self.assertAlmostEqual(restored_focus[dimension], initial_focus[dimension], delta=1)
                self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), width)
        self.assertEqual(self.errors, [])

    def test_responsibility_comparison_uses_canonical_rows_and_focus(self) -> None:
        self.load()
        panel = self.page.locator("#group-panel-roles")
        rows = panel.locator(".responsibility-table tbody tr")
        self.assertEqual(rows.count(), 2, "comparison must contain both actual responsibilities")
        self.assertIn("Owns input only", rows.nth(0).inner_text())
        self.assertIn("Owns processing only", rows.nth(1).inner_text())
        connections = rows.nth(0).locator('.connection-details')
        self.assertEqual(connections.count(), 2, "connection detail must not drown out side-by-side responsibilities")
        self.assertNotIn("Sender → Receiver: Send", rows.nth(0).inner_text())
        connections.nth(1).locator('summary').click()
        self.assertIn("Sender → Receiver: Send (request)", rows.nth(0).inner_text())
        rows.nth(1).get_by_role("button", name="Receiver", exact=True).click()
        frame = self.focus_frame(panel.locator(".semantic-diagram"))
        frame.wait_for_selector('[data-focus-element="receiver"]')
        self.assertEqual(frame.locator(".focus-element").count(), 1)
        self.assertEqual(rows.nth(1).get_attribute("aria-selected"), "true")
        self.assertIn("기록 없음", rows.nth(1).inner_text())
        rows.nth(0).get_by_role("button", name="Sender", exact=True).click()
        self.assertFalse(frame.is_detached(), "same original diagram should not be repeatedly recreated")
        frame.wait_for_selector('[data-focus-element="sender"]')
        self.page.set_viewport_size({"width": 360, "height": 800})
        rows.nth(1).get_by_role("button", name="Receiver", exact=True).click()
        diagram_box = panel.locator('.responsibility-diagram').bounding_box()
        self.assertGreater(diagram_box['y'] + diagram_box['height'], 100,
                           "selecting a mobile responsibility must bring its offscreen diagram back")

    def test_claim_dialog_exact_locator_contradiction_safe_dom_focus_return_and_unknown_chain(self) -> None:
        result = self.load()
        claim = self.page.locator(".flow-step:not([hidden]) .claim-link").first
        self.assertEqual(claim.count(), 1, "step needs direct claim access")
        claim.click()
        dialog = self.page.locator("#claim-dialog")
        self.assertTrue(dialog.is_visible())
        dialog.get_by_text("주장 원장 전체 — 변경 없이 표시", exact=True).click()
        raw = json.loads(dialog.locator(".claim-raw").inner_text())
        self.assertEqual(raw, result["claims"][0])
        for text in ("§ 4 / lines 12–19", "§ 9", "<b>literal evidence</b>", "DOC_ONLY", "sha256:original"):
            self.assertIn(text, dialog.inner_text())
        self.assertEqual(dialog.locator("img, script, blockquote b").count(), 0)
        self.assertIsNone(self.page.evaluate("window.pwned"))
        self.page.keyboard.press("Escape")
        self.assertTrue(claim.evaluate("e => e === document.activeElement"))
        issue = self.page.locator('[data-issue-id="unknown-a"]')
        self.assertIn("blocks-change", issue.locator(".issue-impact").inner_text())
        self.assertIn("Check delivery receipt", issue.locator(".issue-next").inner_text())
        absent = self.page.locator('[data-issue-id="unknown-b"]')
        self.assertIn("기록 없음", absent.locator(".issue-impact").inner_text())
        self.assertIn("기록 없음", absent.locator(".issue-next").inner_text())
        self.assertEqual(self.errors, [])

    def test_claim_table_opens_by_exact_identity_not_ledger_order(self) -> None:
        data, bundle = fixture()
        decoy = copy.deepcopy(bundle["ledger"]["claims"][0])
        decoy.update(id="different-claim", statement="Unrelated first record")
        bundle["ledger"]["claims"].insert(0, decoy)
        self.load(data, bundle)
        self.page.locator('#evidence-tabs button').last.click()
        button = self.page.locator('#table-claims [data-claim-id="claim-z"]')
        self.assertEqual(button.count(), 1, "claim table must directly open the exact ledger claim")
        button.click()
        self.assertIn("Exact <script>", self.page.locator('#claim-dialog .claim-statement').inner_text())
        self.assertNotIn("Unrelated first record", self.page.locator('#claim-dialog').inner_text())

    def test_unmapped_or_ambiguous_step_never_falls_back_to_relation_or_coordinates(self) -> None:
        # A working baseline is exercised before each destructive mutation.
        data, bundle = fixture()
        self.load(data, bundle)
        frame = self.focus_frame(self.page.locator("#flow-panel-calls .semantic-diagram"))
        frame.wait_for_selector('[data-focus-step="first"]')
        original_svg = base64.b64decode(data["diagrams"][0]["dataUri"].split(",", 1)[1]).decode()
        mutations = {
            "missing-step": original_svg.replace('data-step-id="first"', 'data-step-id="wrong"'),
            "ambiguous-step": original_svg.replace('data-step-id="first"', 'data-step-id="again"'),
            "wrong-view": original_svg.replace('data-view-id="scenario"', 'data-view-id="other"'),
            "wrong-relation": original_svg.replace('data-relation="request"', 'data-relation="other"'),
            "mixed-relations": original_svg.replace('<path data-relation="request"', '<path data-relation="other" d="M1 1 H3"/><path data-relation="request"'),
        }
        for label, svg in mutations.items():
            with self.subTest(mutation=label):
                changed = copy.deepcopy(data)
                changed["diagrams"][0]["dataUri"] = uri(svg)
                self.load(changed, bundle)
                widget = self.page.locator("#flow-panel-calls .semantic-diagram")
                frame = self.focus_frame(widget)
                widget.locator('[data-focus-status="unavailable"]').wait_for()
                self.assertEqual(frame.locator(".focus-step, .focus-element").count(), 0)
                self.assertIn("강조하지 않습니다", widget.inner_text())
                if label == "ambiguous-step":
                    self.page.locator('#flow-panel-calls [data-step-nav="next"]').click()
                    widget.locator('[data-focus-status="unavailable"]').wait_for()
                    self.assertEqual(frame.locator(".focus-step").count(), 0)

    def test_svg_active_content_is_not_executed_and_mobile_print_remain_usable(self) -> None:
        data, bundle = fixture()
        raw = base64.b64decode(data["diagrams"][0]["dataUri"].split(",", 1)[1]).decode()
        raw = raw.replace('</svg>', '<script>parent.pwned=1</script><foreignObject><iframe src="https://example.com"/></foreignObject></svg>')
        data["diagrams"][0]["dataUri"] = uri(raw)
        self.page.set_viewport_size({"width": 360, "height": 800})
        self.load(data, bundle)
        widget = self.page.locator("#flow-panel-calls .semantic-diagram")
        frame = self.focus_frame(widget)
        frame.wait_for_selector('[data-focus-step="first"]')
        self.assertEqual(widget.locator("iframe").get_attribute("sandbox"), "allow-scripts")
        self.assertIsNone(self.page.evaluate("window.pwned"))
        self.assertEqual(frame.locator("foreignObject, iframe").count(), 0)
        self.assertGreater(frame.locator("svg.snapshot").bounding_box()["width"], 360,
                           "wide selected message must open at reading scale, not tiny fit scale")
        self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), 360)
        self.page.emulate_media(media="print")
        self.assertEqual(self.page.locator(".flow-step:visible").count(), 2)
        self.assertGreater(self.page.locator(".semantic-print:visible").count(), 0)
        self.assertEqual(self.errors, [])

    def test_svg_initialization_failure_shows_safe_original_and_disables_focus_controls(self) -> None:
        data, bundle = fixture()
        self.load(data, bundle)
        frame = self.focus_frame(self.page.locator("#flow-panel-calls .semantic-diagram"))
        frame.wait_for_selector('[data-focus-step="first"]')
        raw = base64.b64decode(data["diagrams"][0]["dataUri"].split(",", 1)[1]).decode()
        no_viewbox = raw.replace('viewBox="0 0 900 600"', 'width="900" height="600"')
        active = no_viewbox.replace('<svg ', '<svg onload="window.pwned=1" ', 1).replace(
            '</svg>', '<script>window.pwned=1;parent.postMessage("svg-executed","*")</script>'
            '<foreignObject><iframe src="https://example.com"/></foreignObject></svg>')
        self.page.add_init_script('window.svgExecuted=false;addEventListener("message",e=>{if(e.data==="svg-executed")window.svgExecuted=true})')
        for label, source in (("valid-no-viewbox", no_viewbox), ("active-no-viewbox", active)):
            with self.subTest(source=label):
                changed = copy.deepcopy(data)
                changed["diagrams"][0]["dataUri"] = uri(source)
                self.load(changed, bundle)
                widget = self.page.locator("#flow-panel-calls .semantic-diagram")
                widget.locator('[data-focus-status="unavailable"]').wait_for()
                fallback = widget.locator("img.semantic-fallback")
                self.assertEqual(fallback.count(), 1, "initialization failure must retain the original image")
                self.assertTrue(fallback.is_visible())
                self.assertEqual(fallback.get_attribute("src"), changed["diagrams"][0]["dataUri"])
                fallback.evaluate("img => img.decode()")
                self.assertEqual(fallback.evaluate("img => img.naturalWidth"), 900)
                self.assertGreater(fallback.bounding_box()["height"], 100)
                self.assertEqual(widget.locator(".semantic-tools:visible, .semantic-frame:visible, .semantic-help:visible").count(), 0)
                self.page.locator('#flow-panel-calls [data-step-nav="next"]').click()
                self.assertEqual(widget.locator('[data-focus-status="unavailable"]').count(), 1)
                self.assertFalse(self.page.evaluate("window.svgExecuted"))
                for context in self.page.frames:
                    self.assertIsNone(context.evaluate("window.pwned"))
                self.assertEqual(self.errors, [])

    def test_original_without_semantic_svg_is_visible_without_fabricated_focus(self) -> None:
        data, bundle = fixture()
        self.page.set_content('<p>Original static drawing</p>')
        data["diagrams"][0]["dataUri"] = "data:image/png;base64," + base64.b64encode(self.page.screenshot()).decode()
        data["diagrams"][0]["mimeType"] = "image/png"
        self.load(data, bundle)
        widget = self.page.locator("#flow-panel-calls .semantic-diagram")
        self.assertTrue(widget.locator(".semantic-fallback").is_visible())
        self.assertEqual(widget.locator('[data-focus-status="unavailable"]').count(), 1)
        self.assertEqual(widget.locator(".semantic-tools, .focus-step").count(), 0)
        self.assertEqual(self.errors, [])

    @unittest.skipUnless(os.environ.get("C4_REAL_PACKAGE"), "set C4_REAL_PACKAGE for read-only actual-source verification")
    def test_actual_source_preview_all_targets_and_bytes_preserved(self) -> None:
        root = Path(os.environ["C4_REAL_PACKAGE"])
        before = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in root.rglob("*") if p.is_file()}
        output = Path(self.tmp.name) / "actual-preview.html"
        run = subprocess.run([sys.executable, str(ROOT / "scripts/build_html_report.py"),
            "--root", str(root), "--data", "html/report-data.json", "--template", str(ROOT / "assets/html-report-template.html"),
            "--output", str(output)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.page.goto(output.as_uri())
        report = self.page.locator('#report-data').text_content()
        payload = json.loads(report)
        self.assertEqual(len({e.get_attribute('id') for e in self.page.locator('[id]').all()}), self.page.locator('[id]').count())
        for width in (1440, 360):
            self.page.set_viewport_size({"width": width, "height": 1000})
            for i, flow in enumerate(payload['flows']):
                self.page.locator('#flow-tabs button').nth(i).click()
                panel = self.page.locator('#flow-panels>.tab-panel:not([hidden])')
                frame = self.focus_frame(panel.locator('.semantic-diagram'))
                for j, step in enumerate(flow['steps']):
                    panel.locator('.flow-step-selector').nth(j).click()
                    frame.wait_for_function('(id)=>document.querySelector(".focus-step")?.dataset.focusStep===id', arg=step['id'])
                    self.assertEqual(frame.locator('.focus-step').count(), 1)
                    self.assertIn(step['text'], panel.locator('.flow-step:not([hidden])').inner_text())
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), width)
        for row in self.page.locator('.responsibility-table tbody tr').all():
            row.locator('.responsibility-select').click()
            frame = self.focus_frame(self.page.locator('.responsibility-diagram .semantic-diagram'))
            frame.wait_for_function('(id)=>document.querySelector(".focus-element")?.dataset.focusElement===id', arg=row.get_attribute('data-model-id'))
            self.assertEqual(frame.locator('.focus-element').count(), 1)
        self.page.emulate_media(media='print')
        self.assertEqual(self.page.locator('.flow-step:visible').count(), sum(len(f['steps']) for f in payload['flows']))
        after = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in root.rglob("*") if p.is_file()}
        self.assertEqual(after, before, "the actual package is read-only, including its existing report")
        self.assertEqual(self.errors, [])

    def test_real_native_renderer_repeated_relationships_in_generic_ordering_fixture(self) -> None:
        from generate_repo_flowmap_demo import make_model
        from repo_flowmap_adapter import project
        model = make_model()
        native = project(model, "model.json", "a" * 64, "ordering-sequence")
        tmp = Path(self.tmp.name)
        inp = tmp / "native.json"
        inp.write_text(json.dumps(native))
        html = tmp / "native.html"
        run = subprocess.run(["node", str(ROOT / "assets/repo-flowmap/scripts/build_flowmap.mjs"), str(inp),
                              str(ROOT / "assets/repo-flowmap/template.html"), str(html)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.page.goto(html.as_uri())
        self.page.wait_for_function("window.repoFlowmap && window.repoFlowmap.ready()")
        svg = self.page.evaluate("repoFlowmap.exportSvg()")
        data, bundle = fixture()
        bundle["model"] = model
        data["flows"] = [{"id": "generic", "viewId": "ordering-sequence", "kind": "normal"}]
        data["diagrams"] = [{"id": "native", "viewId": "ordering-sequence", "dataUri": uri(svg), "mimeType": "image/svg+xml"}]
        self.load(data, bundle)
        widget = self.page.locator("#flow-panel-generic .semantic-diagram")
        frame = self.focus_frame(widget)
        for i in range(5):
            self.page.locator("#flow-panel-generic .flow-step-selector").nth(i).click()
            frame.wait_for_selector(f'[data-focus-step="demo-step-{i+1}"]')
            self.assertEqual(frame.locator(".focus-step").count(), 1)
        self.assertEqual(self.errors, [])


if __name__ == "__main__":
    unittest.main()
