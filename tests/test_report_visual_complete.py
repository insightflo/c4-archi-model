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
import time
import unittest
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_html_report import hydrate_report, inject  # noqa: E402 (repo-local scripts)
from c4_validation import ValidationReport  # noqa: E402
from test_report_story import CHROME, sync_playwright  # noqa: E402


def uri(text: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(text.encode()).decode()


def _collapse(items: list) -> list:
    """Fold consecutive duplicate narration records (guidance retries re-announce)."""
    out: list = []
    for item in items:
        if not out or out[-1] != item:
            out.append(item)
    return out


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
        # 리사이즈 반영(프레임 문서 폭이 좁아짐) + 읽기 배율 재계산(선택 메시지가 뷰포트보다
        # 넓게 유지됨)을 목표 상태로 기다린다 — 고정 sleep은 부하에서 재계산 전에 읽게 한다.
        # 이 프레임은 nonce CSP 문서라 wait_for_function의 페이지 내부 eval이 간헐적으로
        # 막히므로, 같은 목표 상태를 파이썬 쪽에서 frame.evaluate 폴링으로 기다린다.
        resize_goal = (
            "(() => document.documentElement.clientWidth <= 360"
            " && document.querySelector('svg.snapshot').getBoundingClientRect().width > 360)()")
        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            if frame.evaluate(resize_goal):
                break
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
        # 선택 클릭은 즉시 스크롤·갱신되지만 부하에서 읽기가 앞설 수 있으므로, 목표
        # 상태(그림이 화면 안으로 돌아옴)를 긍정형으로 기다린 뒤 위치를 읽는다.
        self.page.wait_for_function(
            "()=>{const r=document.querySelector('#group-panel-roles .responsibility-diagram')"
            ".getBoundingClientRect();return r.bottom>100;}", timeout=12000)
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


@unittest.skipUnless(sync_playwright and Path(CHROME).is_file(), "local Chrome and Playwright required")
class ReportChronologyTests(unittest.TestCase):
    """A9: 전환 중간·취소 직후의 시간순 검증(보고서 관점).

    기존 클릭·반복 열기 검사(CompleteVisualBrowserTests)는 그대로 두고, 안내 재생(A3)
    도입 뒤의 중간 개입·탭 전환·다이어그랬로그 닫기·재열기, 그리고 안내 각 단계에서
    설명과 그림(ack)이 같은 단계를 가리키는지를 하나의 시간순 기록으로 남긴다.
    """

    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT / "tests"))
        from timeline_recorder import TOLERANCE_MS, Timeline, assert_guide_figure_agreement, guide_cycles
        from test_report_guided_playback import build_view_html, typed_projection
        cls.TOLERANCE_MS = TOLERANCE_MS
        cls.Timeline = Timeline
        cls.assert_agreement = staticmethod(assert_guide_figure_agreement)
        cls.guide_cycles = staticmethod(guide_cycles)
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        renderer = build_view_html(typed_projection("ordering-sequence"), base / "sequence.html").read_text(encoding="utf-8")
        # 임베드 렌더러의 viewId를 보고서 흐름(scenario)에 맞춘다(W3-1 픽스처와 같은 방식).
        cls.renderer_uri = "data:text/html;base64," + base64.b64encode(
            renderer.replace('"viewId": "ordering-sequence"', '"viewId": "scenario"').encode()).decode()
        cls.template = (ROOT / "assets/html-report-template.html").read_text(encoding="utf-8")
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=CHROME, headless=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.pw.stop()
        cls.tmp.cleanup()

    def report_path(self, steps: int, name: str) -> Path:
        notes = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth"]
        data, bundle = fixture()
        view = next(v for v in bundle["model"]["views"] if v["id"] == "scenario")
        view["steps"] = [{"id": "s%d" % i, "order": i + 1, "relationshipId": "request",
                           "note": notes[i] + " detail"} for i in range(steps)]
        data["diagrams"][0] = dict(data["diagrams"][0], mimeType="text/html", dataUri=self.renderer_uri)
        hydrated = hydrate_report(data, bundle, ValidationReport("test"))
        path = Path(self.tmp.name) / name
        path.write_text(inject(self.template, hydrated), encoding="utf-8")
        return path

    def open_report(self, steps: int, name: str):
        page = self.browser.new_page(viewport={"width": 1440, "height": 1000}, offline=True)
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        timeline = self.Timeline()
        self.Timeline.install(page)
        page.goto(self.report_path(steps, name).as_uri())
        page.locator("#flows").scroll_into_view_if_needed()
        # 정착용 고정 sleep 대신 흐름 패널이 조작 가능한 상태(안내 버튼·알림 영역
        # 존재)라는 목표 상태를 긍정형으로 기다린다. 시간순 기록은 문서 시작부터
        # 녹화되므로 이 대기 전 이벤트도 놓치지 않는다.
        page.wait_for_function(
            "()=>!!document.querySelector('#flow-panel-calls .flow-guide-btn')"
            "&&!!document.querySelector('#flow-panel-calls .flow-step-announce')", timeout=12000)
        self.addCleanup(page.close)
        return page, timeline, errors

    @staticmethod
    def renderer_frames(page):
        return [frame for frame in page.frames
                if frame != page.main_frame and frame.evaluate("!!window.repoFlowmap")]

    def start_guide(self, page, until: str, timeout: int = 15000, pressed: str | None = None) -> None:
        """안내 시작 클릭 → 목표 상태 대기. pressed를 주면 안내 버튼의 aria-pressed까지
        목표 상태에 포함한다(시작='true', 종료='false'). 안내 버튼은 토글이라 재클릭은
        하지 않는다 — 클릭은 Playwright가 조작 가능을 보장하고, 목표 상태 predicate가
        도달을 판별한다."""
        page.locator("#flow-panel-calls").get_by_role("button", name="안내 재생").click()
        page.wait_for_function(
            "(args) => {const a = document.querySelector('#flow-panel-calls .flow-step-announce');"
            "const b = document.querySelector('#flow-panel-calls .flow-guide-btn');"
            "return a.textContent.includes(args[0]) && (args[1] === null || b.getAttribute('aria-pressed') === args[1]);}",
            arg=[until, pressed], timeout=timeout)

    def announce_now(self, page) -> str:
        return page.evaluate("document.querySelector('#flow-panel-calls .flow-step-announce').textContent")

    def test_mid_playback_manual_intervention_is_recorded_in_order(self) -> None:
        page, timeline, errors = self.open_report(3, "chrono-intervention.html")
        story = page.locator("#flow-panel-calls")
        self.start_guide(page, "2/3단계", pressed='true')
        # 수동 선택은 같은 단계를 다시 고르는 것도 무해하므로(멱등), 클릭이 닿지 않은
        # 경우만 재클릭 1회로 흡수한다(LESSONS.md).
        selector = story.locator(".flow-step-selector").nth(0)
        selector.click()
        try:
            page.wait_for_function(
                "document.querySelector('#flow-panel-calls .flow-step-announce').textContent === '1/3단계 · Send'",
                timeout=8000)
        except Exception:
            selector.click()
            page.wait_for_function(
                "document.querySelector('#flow-panel-calls .flow-step-announce').textContent === '1/3단계 · Send'",
                timeout=12000)
        timeline.collect(page, "intervened")
        # 안내 진행(1→2) → 개입 클릭 → 안내 정지 → 선택 단계 반영 순서가 한 기록에 남는다.
        start_click = next(c for c in timeline.clicks() if "flow-guide-btn" in c["control"])
        intervene = next(c for c in timeline.clicks() if "flow-step-selector" in c["control"])
        self.assertLess(start_click["nt"], intervene["nt"])
        self.assertIn("2/3단계", intervene["state"].get("announce", ""),
                      "개입 기록은 개입 직전 안내 상태를 담아야 합니다")
        self.assertEqual(intervene["state"].get("guidePressed"), "true")
        pressures = [record["pressed"] for record in timeline.guide_pressures()]
        self.assertEqual(pressures, ["true", "false"], timeline.render())
        stop_record = timeline.guide_pressures()[-1]
        self.assertGreaterEqual(stop_record["nt"], intervene["nt"] - self.TOLERANCE_MS,
                                "정지가 개입보다 먼저 기록되면 안 됩니다(역전)\n" + timeline.render())
        self.assertLessEqual(stop_record["nt"], intervene["nt"] + 1500,
                             "정지가 개입보다 지나치게 늦으면 안 됩니다\n" + timeline.render())
        self.assertEqual(_collapse([record["text"] for record in timeline.announces()]), [
            "1/3단계 · Send", "안내 재생을 시작합니다. 1/3단계 · Send",
            "2/3단계 · Send", "1/3단계 · Send"], timeline.render())
        self.assertFalse([record for record in timeline.announces() if "3/3단계" in record["text"]],
                         "개입 뒤 안내가 스스로 진행되면 안 됩니다\n" + timeline.render())
        late_sends = [send for send in timeline.sends() if send["nt"] > intervene["nt"] + self.TOLERANCE_MS]
        self.assertEqual(late_sends, [], "개입 뒤에는 그림에 단계 지시를 더 보내면 안 됩니다\n" + timeline.render())
        self.assertEqual([record["text"] for record in timeline.where("readout")][-1], "1 / 3 단계")
        # 수동 선택은 보고서 설명을 옮긴다. 그림 구동은 안내 전용 계약(그림은 마지막 안내 단계에 머문다).
        for frame in self.renderer_frames(page):
            self.assertEqual(frame.evaluate("window.repoFlowmap.state().step"), 1)
        announce_count = len(timeline.announces())
        page.wait_for_timeout(3600)  # 안내 간격(2800ms)보다 길게: 자동 재개 금지
        timeline.collect(page, "no-resume")
        self.assertEqual(len(timeline.announces()), announce_count,
                         "개입 뒤 자동 재개 기록이 남으면 안 됩니다\n" + timeline.render())
        # 같은 화면에서 다시 시작한 뒤 이전/다음 버튼 개입도 같은 순서 규칙을 지킨다.
        # (다음 단추는 재클릭 시 단계가 두 번 넘어가 멱등이 아니므로 재클릭 없이 목표
        # 상태 predicate만으로 기다린다.)
        self.start_guide(page, "안내 재생을 시작합니다", timeout=8000, pressed='true')
        story.locator('[data-step-nav="next"]').click()
        page.wait_for_function(
            "document.querySelector('#flow-panel-calls .flow-step-announce').textContent === '2/3단계 · Send'",
            timeout=12000)
        timeline.collect(page, "next-intervened")
        next_click = [record for record in timeline.where("click") if record.get("label") == "다음 단계"][-1]
        self.assertEqual([record["pressed"] for record in timeline.guide_pressures()],
                         ["true", "false", "true", "false"], timeline.render())
        second_stop = timeline.guide_pressures()[-1]
        self.assertGreaterEqual(second_stop["nt"], next_click["nt"] - self.TOLERANCE_MS)
        self.assertLessEqual(second_stop["nt"], next_click["nt"] + 1500)
        self.assertFalse([record for record in timeline.announces() if "3/3단계" in record["text"]],
                         timeline.render())
        self.assertEqual([send for send in timeline.sends() if send["nt"] > next_click["nt"] + self.TOLERANCE_MS], [],
                         timeline.render())
        self.assertEqual(errors, [], timeline.render())

    def test_tab_switch_and_zoom_stops_are_recorded_in_order(self) -> None:
        page, timeline, errors = self.open_report(3, "chrono-tabs.html")
        story = page.locator("#flow-panel-calls")
        self.start_guide(page, "안내 재생을 시작합니다", pressed='true')
        # 부하가 높은 전체 스위트 실행에서는 드물게 클릭 이벤트가 애플리케이션에
        # 닿지 않는다(격리 실행 3/3 통과·제품 결함 아님 — LESSONS.md). 긍정형 조건
        # (정지 안내 + aria-pressed=false)과 재활성화 한 번으로만 흡수한다.
        # 탭 전환은 실제 마우스 클릭으로 활성화한다: 자동 스크롤이 흐름 패널을 화면
        # 밖으로 밀어 IO '화면 밖' 정지가 먼저 확정돼도, 템플릿의 offscreen→사유
        # 보정이 'tab' 사유까지 덮으므로 기다리는 '다른 탭' 안내가 그대로 온다.
        tab = page.locator('#diagram-tabs [role="tab"]').nth(1)
        stopped_js = (
            "(t) => document.querySelector('#flow-panel-calls .flow-step-announce').textContent.includes(t)"
            "&&document.querySelector('#flow-panel-calls .flow-guide-btn').getAttribute('aria-pressed')==='false'")
        def activate_tab() -> None:
            tab.click()
        activate_tab()
        try:
            page.wait_for_function(stopped_js, arg="다른 탭을 선택해", timeout=8000)
        except Exception:
            activate_tab()
            page.wait_for_function(stopped_js, arg="다른 탭을 선택해", timeout=12000)
        timeline.collect(page, "tab-switched")
        tab_click = [record for record in timeline.where("click") if record.get("label") == "Responsibilities"][-1]
        tab_stop = [record for record in timeline.announces() if "다른 탭을 선택해" in record["text"]][-1]
        self.assertGreaterEqual(tab_stop["nt"], tab_click["nt"] - self.TOLERANCE_MS,
                                "탭 전환 정지가 클릭보다 먼저 기록되면 안 됩니다\n" + timeline.render())
        self.assertLessEqual(tab_stop["nt"], tab_click["nt"] + 1500, timeline.render())
        self.assertEqual([send for send in timeline.sends() if send["nt"] > tab_click["nt"] + self.TOLERANCE_MS], [],
                         "탭 전환 뒤에는 단계 지시가 더 가면 안 됩니다\n" + timeline.render())
        # 원래 탭으로 돌아와도 자동 재개는 없다(버튼으로만).
        page.locator('#diagram-tabs [role="tab"]').nth(0).click()
        announce_count = len(timeline.announces())
        page.wait_for_timeout(3600)
        timeline.collect(page, "returned")
        self.assertEqual(len(timeline.announces()), announce_count,
                         "원래 탭 복귀만으로 안내가 재개되면 안 됩니다\n" + timeline.render())
        self.assertEqual(story.get_by_role("button", name="안내 재생").get_attribute("aria-pressed"), "false")
        # 다시 시작한 뒤 같은 그림 확대(+) 조작도 정지한다 — 카메라 지시 기록과 함께.
        # 확대 재클릭은 멱등하므로(같은 정지 경로만 다시 밟는다) 재클릭 1회를 허용하고,
        # 대기는 부정형(안내로 시작 안 함)이 아니라 목표 상태(사용자 조용 정지 안내 +
        # aria-pressed=false)를 긍정형으로 뒤집는다. 부정형이면 단계 안내가 '안내'로
        # 시작하지 않는 순간 통과해버려 정지 안내 전에 기록을 읽을 수 있었다.
        self.start_guide(page, "안내 재생을 시작합니다", timeout=8000, pressed='true')
        zoom = page.locator('#diagram-panels [data-zoom="in"]').first
        zoom.click()
        zoomed_js = (
            "() => document.querySelector('#flow-panel-calls .flow-step-announce').textContent.includes('사용자 조작으로')"
            "&&document.querySelector('#flow-panel-calls .flow-guide-btn').getAttribute('aria-pressed')==='false'")
        try:
            page.wait_for_function(zoomed_js, timeout=8000)
        except Exception:
            zoom.click()
            page.wait_for_function(zoomed_js, timeout=12000)
        timeline.collect(page, "zoomed")
        zoom_click = [record for record in timeline.where("click") if record.get("label") == "＋"][-1]
        zoom_stop = [record for record in timeline.announces() if "사용자 조작으로" in record["text"]][-1]
        self.assertGreaterEqual(zoom_stop["nt"], zoom_click["nt"] - self.TOLERANCE_MS, timeline.render())
        self.assertLessEqual(zoom_stop["nt"], zoom_click["nt"] + 1500, timeline.render())
        camera_records = [record for record in timeline.where("msg:repo-flowmap-camera")
                          if record["nt"] >= zoom_click["nt"] - self.TOLERANCE_MS]
        self.assertGreaterEqual(len(camera_records), 1,
                                "확대 조작은 그림 카메라 지시와 같은 시점에 기록되어야 합니다\n" + timeline.render())
        self.assertEqual([record for record in timeline.announces() if record["nt"] > zoom_stop["nt"] + self.TOLERANCE_MS], [],
                         timeline.render())
        self.assertEqual([send for send in timeline.sends() if send["nt"] > zoom_click["nt"] + self.TOLERANCE_MS], [],
                         timeline.render())
        self.assertEqual(errors, [], timeline.render())

    def test_dialog_close_and_reopen_on_one_screen_is_chronological(self) -> None:
        page, timeline, errors = self.open_report(3, "chrono-dialog.html")
        story = page.locator("#flow-panel-calls")
        self.start_guide(page, "2/3단계", pressed='true')
        embeds_before = [(frame, frame.evaluate("window.repoFlowmap.state()"))
                         for frame in self.renderer_frames(page)]
        self.assertEqual(len(embeds_before), 2, "흐름 임베드 + 다이어그램 카드 두 그림이 안내를 따른다")
        self.assertEqual([state["step"] for _, state in embeds_before], [1, 1])
        page.locator("#diagram-panels [data-full]").first.click()
        # 대화상자 열기 클릭은 모달이 배경을 가리므로 재클릭하지 않는다(LESSONS.md:
        # 정지 사유 귀속 경합). 목표 상태(사용자 조작 정지 안내 + aria-pressed=false)만
        # 긍정형으로 기다린다.
        page.wait_for_function(
            "document.querySelector('#flow-panel-calls .flow-step-announce').textContent.includes('사용자 조작으로')"
            "&&document.querySelector('#flow-panel-calls .flow-guide-btn').getAttribute('aria-pressed')==='false'",
            timeout=12000)
        dialog_frame = page.locator("#dialog-embed").element_handle().content_frame()
        dialog_frame.wait_for_function("window.repoFlowmap && window.repoFlowmap.ready()", timeout=10000)
        timeline.collect(page, "dialog-open")
        full_click = [record for record in timeline.where("click") if record.get("label") == "전체 화면"][-1]
        open_stop = [record for record in timeline.announces() if "사용자 조작으로" in record["text"]][-1]
        self.assertGreaterEqual(open_stop["nt"], full_click["nt"] - self.TOLERANCE_MS, timeline.render())
        self.assertLessEqual(open_stop["nt"], full_click["nt"] + 1500, timeline.render())
        self.assertEqual([send for send in timeline.sends() if send["nt"] > full_click["nt"] + self.TOLERANCE_MS], [],
                         "다이어그랬로그를 연 뒤에는 단계 지시가 더 가면 안 됩니다\n" + timeline.render())
        # 임베드 그림의 단계·카메라는 다이어그랬로그 주기에도 그대로 이어진다.
        for frame, before in embeds_before:
            after = frame.evaluate("window.repoFlowmap.state()")
            self.assertEqual(after["step"], 1)
            self.assertEqual(after["camera"], before["camera"])
            self.assertFalse(after["playing"])
        page.locator("#dialog-close").click()
        page.wait_for_function("!document.querySelector('#diagram-dialog').open")
        timeline.collect(page, "after-close")
        dialog_stop = [record for record in timeline.where("msg:repo-flowmap-playback")
                       if record["src"].endswith("/dialog")]
        self.assertEqual(len(dialog_stop), 1,
                         "닫기 이벤트는 다이어그랬로그 그림에 재생 정지 지시를 보내야 합니다\n" + timeline.render())
        self.assertEqual(dialog_stop[0]["payload"].get("action"), "stop")
        # 다시 열기: 같은 화면에서(재시작 아님). 다이어그랬로그 그림은 새 사본이라 자동 재생이 없고,
        # 어떤 단계 지시도 받지 않는다. 임베드 그림은 단계·카메라가 그대로다.
        page.locator("#diagram-panels [data-full]").first.click()
        reopened = page.locator("#dialog-embed").element_handle().content_frame()
        reopened.wait_for_function("window.repoFlowmap && window.repoFlowmap.ready()", timeout=10000)
        timeline.collect(page, "reopened")
        fresh = reopened.evaluate("window.repoFlowmap.state()")
        self.assertFalse(fresh["playing"], "다시 열린 그림이 자동으로 재생을 시작하면 안 됩니다")
        self.assertEqual(reopened.evaluate(
            "window.__timeline.filter(record => String(record.kind).includes('repo-flowmap')"
            " && !String(record.kind).includes('repo-flowmap-profile')).length"), 0,
            "다시 연 다이어그랬로그 그림은 어떤 단계·재생 지시도 받지 않습니다"
            "(시각 역할 값만 전달하는 repo-flowmap-profile 메시지는 제외 — D5)")
        for frame, before in embeds_before:
            after = frame.evaluate("window.repoFlowmap.state()")
            self.assertEqual(after["step"], 1)
            self.assertEqual(after["camera"], before["camera"],
                             "임베드 그림 상태(단계·카메라)는 닫기·재열기에도 이어져야 합니다")
        box = reopened.locator("#map").bounding_box()
        self.assertTrue(box and box["width"] > 100,
                        "반복 열기 뒤에도 그림이 살아 있어야 합니다(LESSONS: repeated dialogs)")
        page.locator("#dialog-close").click()
        page.wait_for_function("!document.querySelector('#diagram-dialog').open")
        announce_count = len(timeline.announces())
        page.wait_for_timeout(3600)
        timeline.collect(page, "no-auto-restart")
        self.assertEqual(len(timeline.announces()), announce_count,
                         "닫기·재열기 뒤 안내가 자동 재개되면 안 됩니다\n" + timeline.render())
        self.assertEqual(story.get_by_role("button", name="안내 재생").get_attribute("aria-pressed"), "false")
        self.assertEqual(errors, [], timeline.render())

    def test_guidance_narration_and_figures_agree_at_every_step(self) -> None:
        page, timeline, errors = self.open_report(3, "chrono-agree.html")
        self.start_guide(page, "끝났습니다", timeout=20000, pressed='false')
        timeline.collect(page, "done")
        cycles = self.assert_agreement(timeline)
        self.assertEqual([cycle["n"] for cycle in cycles], [1, 2, 3])
        for cycle in cycles:
            self.assertEqual(len(cycle["sends"]), 2, "임베드 그림 2개에 모두 단계 지시가 갑니다")
            self.assertEqual(len(cycle["acks"]), 2)
            self.assertEqual([ack["payload"]["step"] for ack in cycle["acks"]], [cycle["n"] - 1] * 2)
        for frame in self.renderer_frames(page):
            self.assertEqual(frame.evaluate("window.repoFlowmap.state().step"), 2)
        self.assertEqual(errors, [], timeline.render())

    def test_agreement_checker_exposes_injected_description_figure_mismatch(self) -> None:
        # 일부러 어긋남을 만드는 변이: 보고서는 6단계, 그림 흐름은 5단계다. 마지막 단계에서
        # 그림은 index 5를 받지 못해 step=-1로 잘리고, 같은 검사기가 이 어긋남을 잡아야 한다.
        page, timeline, errors = self.open_report(6, "chrono-mismatch.html")
        self.start_guide(page, "끝났습니다", timeout=30000, pressed='false')
        timeline.collect(page, "done")
        with self.assertRaises(AssertionError) as caught:
            self.assert_agreement(timeline)
        message = str(caught.exception)
        self.assertIn("6/6", message)
        self.assertIn("-1", message)
        self.assertIn("시간순 기록", message, "실패 메시지가 시간순 로그로 원인을 설명해야 합니다")
        last_cycle = self.guide_cycles(timeline)[-1]
        self.assertEqual(last_cycle["n"], 6)
        self.assertEqual([ack["payload"]["step"] for ack in last_cycle["acks"]], [-1, -1])
        self.assertEqual(errors, [], timeline.render())


if __name__ == "__main__":
    unittest.main()
