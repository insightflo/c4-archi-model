"""Canonical story hydration and real-template interaction regressions.

Run: python3 -m unittest discover -s tests -p test_report_story.py -v
Browser cases use the same optional local Chrome/Playwright setup as existing tests.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import sys
import unittest
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_html_report import hydrate_report
from c4_validation import ValidationReport

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

CHROME = os.environ.get("C4_BROWSER") or shutil.which("chromium") or \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def hydrated_fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    data = {"analysis": {}, "flows": [{"id": "story", "viewId": "scenario", "kind": "normal",
            "presentation": {"stepNotes": [{"stepId": "later", "explanation": "Full explanation",
                "attention": "Do not retry blindly", "analogy": "A receipt"}],
                "notes": [{"title": "Scope note", "text": "Not operationally verified",
                           "claimIds": ["step-claim"]}]}}]}
    bundle = {"session": {}, "understanding": None, "coverage": {},
        "model": {"elements": [{"id": "sender", "name": "Sender"},
                                {"id": "receiver", "name": "Receiver"}],
            "relationships": [{"id": "rel", "sourceId": "sender", "destinationId": "receiver",
                "description": "Sends request", "claimIds": ["rel-claim"]}],
            "views": [{"id": "scenario", "title": "Scenario", "steps": [
                {"id": "later", "order": 40, "relationshipId": "rel", "condition": "if accepted",
                 "claimIds": ["step-claim", "rel-claim"], "note": "Canonical note"},
                {"id": "earlier", "order": 7, "relationshipId": "rel"}]}]},
        "ledger": {"sources": [], "claims": [
            {"id": "rel-claim", "supports": [{"sourceId": "source-a"}]},
            {"id": "step-claim", "contradictions": [{"sourceId": "source-b"}]}]}}
    return data, bundle


class HydrationTests(unittest.TestCase):
    def test_canonical_identity_claims_order_and_inputs_preserved(self) -> None:
        data, bundle = hydrated_fixture()
        original = copy.deepcopy((data, bundle))
        result = hydrate_report(data, bundle, ValidationReport("story"))
        steps = result["flows"][0]["steps"]
        self.assertEqual([s["number"] for s in steps], [7, 40])
        self.assertEqual(steps[1].get("relationshipId"), "rel")
        self.assertEqual(steps[1].get("sourceId"), "sender")
        self.assertEqual(steps[1].get("destinationId"), "receiver")
        self.assertEqual(steps[1].get("claimIds"), ["rel-claim", "step-claim"])
        self.assertEqual(steps[1]["sourceIds"], ["source-a", "source-b"])
        self.assertEqual(steps[1]["condition"], "if accepted")
        self.assertEqual(steps[1]["text"], "Full explanation")
        self.assertEqual(steps[1]["attention"], "Do not retry blindly")
        self.assertEqual(steps[1]["analogy"], "A receipt")
        self.assertEqual(result["flows"][0]["notes"][0]["sourceIds"], ["source-b"])
        self.assertEqual((data, bundle), original)

    def test_empty_flows_and_missing_optional_claims(self) -> None:
        data, bundle = hydrated_fixture()
        bundle["model"]["relationships"][0].pop("claimIds")
        result = hydrate_report(data, bundle, ValidationReport("story"))
        self.assertEqual(result["flows"][0]["steps"][0].get("claimIds"), [])
        data["flows"] = []
        self.assertEqual(hydrate_report(data, bundle, ValidationReport("story"))["flows"], [])


@unittest.skipUnless(sync_playwright and Path(CHROME).is_file(), "local Chrome and Playwright required")
class StoryTemplateTests(unittest.TestCase):
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
        self.page = self.browser.new_page()
        self.errors: list[str] = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))

    def tearDown(self) -> None:
        self.page.close()

    def load(self, data: dict[str, Any]) -> None:
        self.page.set_content(self.template.replace("__REPORT_DATA_JSON__", json.dumps(data)))

    def story_data(self) -> dict[str, Any]:
        data, bundle = hydrated_fixture()
        result = hydrate_report(data, bundle, ValidationReport("story"))
        result["flows"].extend([
            {"id": "single", "title": "Single", "viewId": "absent", "steps": [
                {"id": "only", "number": 99, "title": "Only step", "text": "Only detail"}]},
            {"id": "empty", "title": "Empty", "steps": []}])
        result["diagrams"] = [{"id": "unrelated", "viewId": "other", "title": "Other diagram"},
                              {"id": "original", "viewId": "scenario", "title": "Original diagram"}]
        return result

    def test_step_navigation_keyboard_and_related_original_diagram(self) -> None:
        self.load(self.story_data())
        story = self.page.locator("#flow-panel-story")
        selectors = story.locator(".flow-step-selector")
        self.assertEqual(selectors.count(), 2)
        self.assertEqual(selectors.nth(0).get_attribute("aria-selected"), "true")
        self.assertTrue(story.locator('[data-step-nav="prev"]').is_disabled())
        story.locator('[data-step-nav="next"]').click()
        detail = story.locator(".flow-step:not([hidden])")
        self.assertEqual(detail.count(), 1)
        self.assertIn("40", detail.inner_text())
        for text in ["Full explanation", "if accepted", "Do not retry blindly", "A receipt", "source-b"]:
            self.assertIn(text, detail.inner_text())
        self.assertTrue(story.locator('[data-step-nav="next"]').is_disabled())
        selectors.nth(1).focus()
        self.page.keyboard.press("ArrowLeft")
        self.assertEqual(selectors.nth(0).get_attribute("aria-selected"), "true")
        self.page.keyboard.press("End")
        self.assertEqual(selectors.nth(1).get_attribute("aria-selected"), "true")
        self.page.keyboard.press("Home")
        self.assertEqual(selectors.nth(0).get_attribute("aria-selected"), "true")
        self.assertIn("Not operationally verified", story.inner_text())
        story.locator(".flow-related-diagram").click()
        self.assertTrue(self.page.locator("#diagram-panel-original").is_visible())
        self.assertFalse(self.page.locator("#diagram-panel-unrelated").is_visible())
        self.assertEqual(self.errors, [])

    def test_independent_single_empty_and_print_all_steps(self) -> None:
        self.load(self.story_data())
        self.page.locator('#flow-panel-story [data-step-nav="next"]').click()
        self.page.get_by_role("tab", name="Single", exact=True).click()
        single = self.page.locator("#flow-panel-single")
        self.assertTrue(single.locator('[data-step-nav="prev"]').is_disabled())
        self.assertTrue(single.locator('[data-step-nav="next"]').is_disabled())
        self.assertEqual(single.locator(".flow-related-diagram").count(), 0)
        self.page.get_by_role("tab", name="Empty", exact=True).click()
        empty = self.page.locator("#flow-panel-empty")
        self.assertEqual(empty.locator(".flow-step-selector").count(), 0)
        self.assertTrue(empty.locator(".flow-empty").is_visible())
        self.page.get_by_role("tab", name="Scenario", exact=True).click()
        self.assertIn("40", self.page.locator("#flow-panel-story .flow-step:not([hidden])").inner_text())
        self.page.emulate_media(media="print")
        self.assertEqual(self.page.locator(".flow-step:visible").count(), 3)
        self.assertEqual(self.page.locator(".flow-step-selector:visible").count(), 0)
        self.assertEqual(self.page.locator(".flow-related-diagram:visible").count(), 0)
        self.assertEqual(self.errors, [])

    def test_no_flows_mobile_long_text_and_element_plain_text(self) -> None:
        self.load({"flows": []})
        self.assertFalse(self.page.locator("#flows").is_visible())
        data = self.story_data()
        text = "Portal — Board — History Loop <b>literal</b> " + "VeryLongResponsibility" * 30
        data["elementGroups"] = [{"id": "components", "elements": [{"name": "Worker", "description": text}]}]
        data["flows"][0]["steps"][0]["title"] = text
        data["meta"] = {"mode": "both"}
        data["audienceSections"] = [{"audience": "both", "title": "Explanation",
                                     "items": ["AnUnbrokenCanonicalIdentifier" * 20]}]
        self.page.set_viewport_size({"width": 360, "height": 800})
        self.load(data)
        self.assertEqual(self.page.locator(".element-desc").inner_text(), text)
        self.assertEqual(self.page.locator(".element-desc .hl, .element-desc b").count(), 0)
        self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), 360)
        self.assertEqual(self.errors, [])


if __name__ == "__main__":
    unittest.main()
