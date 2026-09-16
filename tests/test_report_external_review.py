"""External review regressions exercise generated HTML, not source-code strings."""
from __future__ import annotations

import base64
import copy
import io
from pathlib import Path
import tempfile
import unittest

import test_report_visual_complete as visual
from build_html_report import hydrate_report, inject
from c4_validation import ValidationReport


def scoped_fixture() -> tuple[dict, dict]:
    data, bundle = visual.fixture()
    for element in bundle["model"]["elements"]:
        element["type"] = "container"
    bundle["model"]["elements"].append({"id": "machine", "name": "Machine", "type": "deploymentNode"})
    bundle["model"]["relationships"].extend([
        {"id": "arbitrary-placement", "sourceId": "machine", "destinationId": "sender", "description": "Placement proposal"},
        {"id": "host-not-placement", "sourceId": "sender", "destinationId": "receiver", "description": "Other scenario call"},
    ])
    bundle["model"]["views"].extend([
        {"id": "physical", "type": "deployment", "title": "Proposed location", "elementIds": ["machine", "sender"], "relationshipIds": ["arbitrary-placement"]},
        {"id": "elsewhere", "type": "dynamic", "title": "Another scenario", "elementIds": ["sender", "receiver"], "relationshipIds": ["host-not-placement"]},
    ])
    return data, bundle


@unittest.skipUnless(visual.sync_playwright and Path(visual.CHROME).is_file(), "local Chrome and Playwright required")
class ExternalReviewBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pw = visual.sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=visual.CHROME, headless=True)
        cls.template = (visual.ROOT / "assets/html-report-template.html").read_text()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.pw.stop()

    def setUp(self) -> None:
        self.page = self.browser.new_page(viewport={"width": 1440, "height": 1000}, offline=True)
        self.page.set_default_timeout(5000)
        self.errors: list[str] = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.page.close()
        self.tmp.cleanup()

    def load(self, data: dict | None = None, bundle: dict | None = None) -> dict:
        if data is None:
            data, bundle = visual.fixture()
        hydrated = hydrate_report(data, bundle, ValidationReport("external-review"))
        path = Path(self.tmp.name) / "report.html"
        path.write_text(inject(self.template, hydrated))
        self.page.goto(path.as_uri())
        return hydrated

    def test_script_data_literal_roundtrip_and_real_initialization(self) -> None:
        samples = ["일반 한국어 원문", "</script><script>window.pwned=1</script>",
                   "문서에서 <!-- <script> 이후 텍스트", "<!-- <ScRiPt > mixed case"]
        for sample in samples:
            with self.subTest(sample=sample):
                data, bundle = visual.fixture()
                bundle["ledger"]["claims"][0]["statement"] = sample
                data["artifacts"] = [{"id": "html", "content": sample + "<p>HTML 원문</p>"}]
                self.load(data, bundle)
                self.assertEqual(self.page.locator("#page-title").inner_text(), "C4 Architecture Report",
                                 "must initialize the app, not merely have no pageerrors")
                self.assertEqual(self.page.locator("#flow-panel-calls .flow-step-selector").count(), 2)
                parsed = self.page.locator("#report-data").evaluate("e => JSON.parse(e.textContent)")
                self.assertEqual(parsed["claims"][0]["statement"], sample)
                self.assertEqual(parsed["artifacts"][0]["content"], sample + "<p>HTML 원문</p>")
                self.assertEqual(self.page.locator(".codebox").text_content(), sample + "<p>HTML 원문</p>")
                self.assertIsNone(self.page.evaluate("window.pwned"))
                self.assertEqual(self.errors, [])

    def test_print_relationship_bodies_and_table_structure_restore_screen_state(self) -> None:
        self.load()
        details = self.page.locator(".responsibility-table .connection-details")
        details.nth(0).evaluate("e => e.open=true")
        before = details.evaluate_all("els=>els.map(e=>e.open)")
        # A4 is narrower than the old mobile breakpoint; actual print must still be a table.
        self.page.set_viewport_size({"width": 700, "height": 900})
        self.page.emulate_media(media="print")
        self.page.evaluate("dispatchEvent(new Event('beforeprint'))")
        self.assertTrue(all(details.evaluate_all("els=>els.map(e=>e.open)")), "print must expand relationship bodies")
        self.assertEqual(self.page.locator(".responsibility-table").evaluate("e=>getComputedStyle(e).display"), "table")
        self.assertEqual(self.page.locator(".responsibility-table thead").evaluate("e=>getComputedStyle(e).display"), "table-header-group")
        row = self.page.locator(".responsibility-table tbody tr").first
        self.assertEqual(row.evaluate("e=>getComputedStyle(e).display"), "table-row")
        self.assertEqual(row.evaluate("e=>getComputedStyle(e).breakInside"), "avoid")
        self.assertGreaterEqual(float(row.locator('td').first.evaluate("e=>parseFloat(getComputedStyle(e).fontSize)")), 11)
        self.assertEqual(row.locator('th').evaluate("e=>getComputedStyle(e).verticalAlign"), "top")
        self.assertIn("Sender → Receiver: Send (request)", row.inner_text())
        self.page.evaluate("dispatchEvent(new Event('afterprint'))")
        self.assertEqual(details.evaluate_all("els=>els.map(e=>e.open)"), before)
        # Native print events (not just synthetic dispatch) must include body text in the PDF.
        from pypdf import PdfReader
        pdf = self.page.pdf(format="A4")
        text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
        self.assertIn("Send (request)", text)
        self.assertEqual(details.evaluate_all("els=>els.map(e=>e.open)"), before)

    def test_png_original_is_visible_in_print_without_inferred_focus(self) -> None:
        data, bundle = visual.fixture()
        self.page.set_content("<h1>Provided original PNG</h1>")
        image = "data:image/png;base64," + base64.b64encode(self.page.screenshot()).decode()
        data["diagrams"][0].update(dataUri=image, mimeType="image/png")
        self.load(data, bundle)
        widget = self.page.locator("#flow-panel-calls .semantic-diagram")
        self.assertTrue(widget.locator(".semantic-fallback").is_visible())
        self.page.emulate_media(media="print")
        images = widget.locator("img:visible")
        self.assertEqual(images.count(), 1, "provided PNG must survive print")
        self.assertEqual(images.first.get_attribute("src"), image)
        images.first.evaluate("e=>e.decode()")
        self.assertGreater(images.first.evaluate("e=>e.naturalWidth"), 0)
        self.assertEqual(widget.locator(".semantic-tools, .focus-element, .focus-step").count(), 0)

    def test_issue_connects_only_canonical_view_elements_not_inferred_steps(self) -> None:
        data, bundle = visual.fixture()
        issue = bundle["coverage"]["unknownRelevant"][0]
        issue.update(affectedModelIds=["receiver", "request", "unresolved-id"], affectedViewIds=["scenario", "missing-view"])
        self.load(data, bundle)
        card = self.page.locator('[data-issue-id="unknown-a"]')
        self.assertEqual(card.locator('[data-issue-view="scenario"]').count(), 1, "unknown needs its explicit view link")
        card.locator('[data-issue-view="scenario"]').click()
        card.locator('.focus-status:not([data-focus-status="loading"])').wait_for()
        self.assertEqual(card.locator('.focus-status').get_attribute('data-focus-status'), 'view',
                         'a valid view-only link is not a missing semantic mapping')
        self.assertIn("Repeated calls (scenario)", card.inner_text())
        self.assertIn("Receiver (receiver)", card.inner_text())
        self.assertIn("unresolved-id", card.inner_text())
        self.assertEqual(card.locator('[data-issue-element="unresolved-id"], [data-issue-view="missing-view"]').count(), 0)
        button = card.locator('[data-issue-element="receiver"]')
        self.assertEqual(button.count(), 1)
        button.click()
        frame = card.locator(".semantic-frame").element_handle().content_frame()
        frame.wait_for_selector('[data-focus-element="receiver"]')
        self.assertEqual(frame.locator(".focus-step").count(), 0, "affected IDs do not justify a specific failed step")
        self.assertTrue(card.locator(".issue-diagram").evaluate("e=>e.contains(document.activeElement)"))
        self.assertEqual(self.errors, [])

    def test_mobile_selected_responsibility_and_focus_stay_beside_diagram(self) -> None:
        data, bundle = visual.fixture()
        data["elementGroups"][0]["elements"][1]["presentation"] = {"whyItMatters": "Required receiver reason", "withoutIt": "Recorded receiver consequence"}
        self.page.set_viewport_size({"width": 360, "height": 800})
        self.load(data, bundle)
        row_button = self.page.locator('.responsibility-table [data-model-id="receiver"] .responsibility-select')
        row_button.focus()
        self.page.keyboard.press("Enter")
        selected = self.page.locator(".responsibility-selection")
        self.assertEqual(selected.count(), 1, "selected responsibility must be colocated, not left far down the table")
        for exact in ("Owns processing only", "Required receiver reason", "Recorded receiver consequence"):
            self.assertIn(exact, selected.inner_text())
        diagram = self.page.locator(".responsibility-diagram .semantic-diagram").bounding_box()
        detail = selected.bounding_box()
        self.assertLessEqual(abs(detail["y"] - (diagram["y"] + diagram["height"])), 32)
        active = self.page.evaluate("(()=>{const e=document.activeElement,b=e.getBoundingClientRect();return {within:!!e.closest('.responsibility-diagram'),y:b.y,h:b.height}})()")
        self.assertTrue(active["within"])
        self.assertGreaterEqual(active["y"], 80)
        self.assertLess(active["y"], 800)
        self.page.locator(".responsibility-return").click()
        self.assertTrue(row_button.evaluate("e=>document.activeElement===e"))
        self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), 360)

    def test_relationship_scope_uses_view_membership_and_model_types_not_id_prefix(self) -> None:
        data, bundle = scoped_fixture()
        before = copy.deepcopy(bundle)
        self.load(data, bundle)
        row = self.page.locator('.responsibility-table [data-model-id="sender"]')
        row.locator("details").evaluate_all("els=>els.forEach(e=>e.open=true)")
        current = row.locator(".connection-current")
        self.assertEqual(current.count(), 1, "current-view communication needs an explicit scope")
        self.assertIn("Send (request)", current.inner_text())
        self.assertNotIn("arbitrary-placement", current.inner_text())
        self.assertNotIn("host-not-placement", current.inner_text())
        self.assertIn("Placement proposal (arbitrary-placement)", row.locator(".connection-deployment").inner_text())
        self.assertIn("Other scenario call (host-not-placement)", row.locator(".connection-other").inner_text())
        self.assertIn("physical", row.locator(".connection-deployment").inner_text())
        self.assertIn("elsewhere", row.locator(".connection-other").inner_text())
        self.assertEqual(bundle, before)

    def test_overview_highlight_preserves_every_delimiter_and_restriction(self) -> None:
        data, bundle = visual.fixture()
        text = "문서 기반 제안 — 게시 흐름 설명 — 운영 검증은 미실행"
        data["overview"] = {"problem": text, "oneSentence": text}
        self.load(data, bundle)
        paragraphs = self.page.locator("#overview-grid .overview-card > p")
        self.assertEqual(paragraphs.nth(0).text_content(), text)
        self.assertEqual(paragraphs.nth(1).text_content(), text)

    def test_reduced_motion_actual_jump_is_immediate(self) -> None:
        self.page.emulate_media(reduced_motion="reduce")
        self.load()
        self.page.evaluate("scrollTo({top:0,behavior:'instant'})")
        self.page.locator('[data-jump="flows"]').click()
        samples = self.page.evaluate("""async()=>{const ys=[scrollY];for(let i=0;i<6;i++){await new Promise(r=>requestAnimationFrame(r));ys.push(scrollY);}return ys;}""")
        self.assertGreater(samples[0], 100, "jump must already have occurred on click")
        self.assertLessEqual(max(samples)-min(samples), 1, f"reduce must not animate: {samples}")

    def test_historical_qa_is_scoped_and_original_record_unchanged(self) -> None:
        data, bundle = visual.fixture()
        data["meta"] = {"generatedAt": "2026-01-01T00:00:00Z"}
        data["build"] = {"coveragePath": "qa/coverage.json", "understandingPath": "qa/understanding.json", "canonicalModelPath": "model/canonical.json"}
        data["overview"] = {"scopeSummary": "최신 증거: qa/old-check/ — NOT_RUN"}
        bundle["coverage"].update(generatedAt="2026-01-02T00:00:00Z", modelRevision="r3", completion={"result": "NOT_RUN", "reason": "Original historical reason"})
        original = copy.deepcopy((data, bundle))
        self.load(data, bundle)
        label = self.page.locator("#overview-detail .historical-scope")
        self.assertEqual(label.count(), 1, "old current/latest prose must be explicitly scoped")
        self.assertIn("과거", label.inner_text())
        self.assertIn("2026-01-01T00:00:00Z", label.inner_text())
        history = self.page.locator("#qa .qa-history")
        self.assertEqual(history.count(), 1)
        for expected in ("2026-01-02T00:00:00Z", "qa/coverage.json", "r3", "현재 HTML"):
            self.assertIn(expected, history.inner_text())
        self.assertIn("최신 증거: qa/old-check/ — NOT_RUN", self.page.locator("#overview-grid").inner_text())
        self.assertIn("Original historical reason", self.page.locator("#qa").inner_text())
        self.assertEqual((data, bundle), original)


if __name__ == "__main__":
    unittest.main()
