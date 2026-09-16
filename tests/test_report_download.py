"""Native SVG downloads must work inside report sandboxes, not just serialize.

Run: python3 -B -m unittest discover -s tests -p test_report_download.py -v
C4_DOWNLOAD_EVIDENCE optionally retains generated fixtures/downloads outside the repo.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from typing import Any
import xml.etree.ElementTree as ET

import test_report_visual_complete as visual
from build_html_report import hydrate_report, inject
from c4_validation import ValidationReport
from generate_repo_flowmap_demo import make_model
from repo_flowmap_adapter import project


@unittest.skipUnless(visual.sync_playwright and Path(visual.CHROME).is_file(),
                     "local Chrome and Playwright required")
class ReportDownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        if os.environ.get("C4_DOWNLOAD_EVIDENCE"):
            cls.root = Path(os.environ["C4_DOWNLOAD_EVIDENCE"]).resolve()
            cls.root.mkdir(parents=True, exist_ok=True)
        cls.model = make_model()
        diagrams = []
        for view_id in ("ordering-context", "ordering-container"):
            native = project(cls.model, "model.json", "a" * 64, view_id)
            source = cls.root / f"{view_id}.json"
            source.write_text(json.dumps(native), encoding="utf-8")
            native_path = cls.root / f"{view_id}.html"
            run = subprocess.run([
                "node", str(visual.ROOT / "assets/repo-flowmap/scripts/build_flowmap.mjs"),
                str(source), str(visual.ROOT / "assets/repo-flowmap/template.html"),
                str(native_path),
            ], capture_output=True, text=True, timeout=30)
            if run.returncode:
                raise AssertionError(run.stdout + run.stderr)
            native_uri = "data:text/html;base64," + base64.b64encode(native_path.read_bytes()).decode()
            diagrams.append({"id": view_id, "viewId": view_id,
                             "dataUri": native_uri, "mimeType": "text/html"})
        cls.native_path = cls.root / "ordering-context.html"
        data, bundle = visual.fixture()
        bundle["model"] = cls.model
        data["flows"] = []
        data["elementGroups"] = [{"id": "roles", "elements": [{"modelId": "customer"}]}]
        data["diagrams"] = diagrams
        cls.report_path = cls.root / "report.html"
        cls.report_path.write_text(inject(
            (visual.ROOT / "assets/html-report-template.html").read_text(),
            hydrate_report(data, bundle, ValidationReport("download-regression"))), encoding="utf-8")
        cls.pw = visual.sync_playwright().start()
        cls.addClassCleanup(cls.pw.stop)
        cls.browser = cls.pw.chromium.launch(executable_path=visual.CHROME, headless=True)
        cls.addClassCleanup(cls.browser.close)

    def setUp(self) -> None:
        self.page = self.browser.new_page(accept_downloads=True, offline=True,
                                          viewport={"width": 1440, "height": 1000})
        self.addCleanup(self.page.close)
        self.page.set_default_timeout(5000)
        self.console: list[str] = []
        self.page.on("console", lambda message: self.console.append(message.text))

    def download_svg(self, frame: Any, label: str, view_id: str = "ordering-context",
                     relationship_ids: tuple[str, ...] = ("customer-to-system",)) -> None:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

        frame.wait_for_function("window.repoFlowmap && window.repoFlowmap.ready()")
        try:
            with self.page.expect_download(timeout=3000) as event:
                frame.locator("#download-svg").click()
        except PlaywrightTimeoutError as error:
            # Include Chromium's actual sandbox diagnostic rather than only a timeout.
            self.fail(f"Native download failed: {error}\nBrowser console: {self.console}")
        download = event.value
        self.assertIsNone(download.failure())
        self.assertTrue(download.suggested_filename.endswith(".svg"))
        target = self.root / f"{label}.svg"
        download.save_as(target)
        svg = ET.parse(target).getroot()
        self.assertEqual(svg.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertEqual(svg.get("data-view-id"), view_id)
        paths = [node for node in svg.iter("{http://www.w3.org/2000/svg}path")
                 if node.get("data-relation")]
        self.assertCountEqual([node.get("data-relation") for node in paths], relationship_ids,
                              "download must retain the canonical relationship paths")
        self.assertTrue(all(node.get("d") for node in paths))

    def report_frame(self, selector: str) -> tuple[Any, Any]:
        handle = self.page.locator(selector)
        handle.scroll_into_view_if_needed()
        frame = handle.element_handle().content_frame()
        self.assertIsNotNone(frame)
        return handle, frame

    def assert_restricted_sandbox(self, handle: Any, frame: Any) -> None:
        self.assertEqual(set(handle.get_attribute("sandbox").split()),
                         {"allow-scripts", "allow-downloads"})
        self.assertEqual(frame.evaluate("""() => {
            try { return parent.document.title; } catch (error) { return error.name; }
        }"""), "SecurityError", "HTML embed must remain isolated from report DOM")

    def test_standalone_native_download_control(self) -> None:
        self.page.goto(self.native_path.as_uri())
        self.download_svg(self.page, "standalone")

    def test_diagram_panel_native_download(self) -> None:
        self.page.goto(self.report_path.as_uri())
        handle, frame = self.report_frame("#diagram-panels .tab-panel:not([hidden]) iframe")
        self.download_svg(frame, "diagram-panel")
        self.assert_restricted_sandbox(handle, frame)

    def test_fullscreen_native_download(self) -> None:
        self.page.goto(self.report_path.as_uri())
        self.page.locator("#diagram-panels .tab-panel:not([hidden]) [data-full]").click()
        handle, frame = self.report_frame("#dialog-embed")
        self.download_svg(frame, "fullscreen")
        self.assert_restricted_sandbox(handle, frame)

    def test_fullscreen_reopen_different_views_has_geometry_and_downloads(self) -> None:
        # Readiness alone passed even when the reused dialog's second document was blank.
        views = (("ordering-context", ("customer-to-system",)),
                 ("ordering-container", ("customer-to-web", "web-to-api", "api-to-db",
                                         "api-to-topic", "worker-to-topic")))
        for width in (1440, 360):
            with self.subTest(width=width):
                self.page.set_viewport_size({"width": width, "height": 1000})
                self.page.goto(self.report_path.as_uri())
                for index, (view_id, relationship_ids) in enumerate(views):
                    self.page.locator("#diagram-tabs button").nth(index).click()
                    panel = self.page.locator("#diagram-panels .tab-panel").nth(index)
                    panel.locator("[data-full]").click()
                    handle, frame = self.report_frame("#dialog-embed")
                    frame.wait_for_function("""id => window.repoFlowmap && repoFlowmap.ready()
                        && document.querySelector('#map').dataset.viewId === id""", arg=view_id)
                    frame.evaluate("document.fonts.ready")
                    geometry = frame.evaluate("""() => {
                        const bbox = document.querySelector('#vp').getBBox();
                        const button = document.querySelector('#download-svg').getBoundingClientRect();
                        const doc = document.documentElement.getBoundingClientRect();
                        return {bbox: {width: bbox.width, height: bbox.height},
                                button: {width: button.width, height: button.height},
                                document: {width: doc.width, height: doc.height}};
                    }""")
                    label = f"reopen-{width}-{view_id}"
                    (self.root / f"{label}.json").write_text(json.dumps(geometry), encoding="utf-8")
                    for element, dimensions in geometry.items():
                        for axis, value in dimensions.items():
                            self.assertGreater(value, 0, f"{label}: {element}.{axis} must be laid out")
                    self.assert_restricted_sandbox(handle, frame)
                    self.download_svg(frame, label, view_id, relationship_ids)
                    self.page.locator("#dialog-close").click()
                    self.assertFalse(self.page.locator("#diagram-dialog").evaluate("node => node.open"))

    def test_html_fallback_native_download(self) -> None:
        self.page.goto(self.report_path.as_uri())
        handle, frame = self.report_frame(".responsibility-diagram iframe")
        self.download_svg(frame, "html-fallback")
        self.assert_restricted_sandbox(handle, frame)


if __name__ == "__main__":
    unittest.main()
