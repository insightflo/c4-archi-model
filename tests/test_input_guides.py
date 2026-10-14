"""A8 입력 장치에 맞는 조작 안내: 렌더러 문구 분기·동적 전환·기능 불변 + 보고서 그림 안내.

- 문구만 장치(주 포인터)에 맞게 분기한다 — 터치에서 마우스/hover·키보드 전용
  안내를 보여주지 않는다. 조작 기능(팬·줌·탭·키보드)은 전 장치에서 불변이다.
- matchMedia 변경(장치 전환·에뮬레이션)마다 문구가 갱신된다.
실제 Chromium에서 file:// 렌더러와 보고서 템플릿을 띄워 검증한다.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))

CHROME = os.environ.get('C4_BROWSER') or shutil.which('chromium') or '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


def build_view_html(data: dict, target: Path) -> Path:
    source = target.with_suffix('.json')
    source.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    result = subprocess.run(
        ['node', str(ROOT / 'assets/repo-flowmap/scripts/build_flowmap.mjs'),
         str(source), str(ROOT / 'assets/repo-flowmap/template.html'), str(target)],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return target


LEGACY_DATA = {
    "meta": {"project": "guide-demo", "title": "조작 안내 데모", "last_analyzed_commit": "demo000"},
    "layers": [{"id": "ui", "label": "UI", "color": "#365d91"},
               {"id": "svc", "label": "서비스", "color": "#7a5195"}],
    "nodes": [{"id": "web", "label": "웹 화면", "desc": "사용자 입력", "layer": "ui"},
              {"id": "api", "label": "주문 API", "desc": "주문 처리", "layer": "svc"}],
    "flows": [
        {"id": "place-order", "group": "주문", "title": "주문 접수", "summary": "주문을 접수한다",
         "steps": [{"from": "web", "to": "api", "call": "POST /orders"}]},
    ],
}

SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 20">'
       '<rect width="40" height="20" fill="#ffffff"/></svg>')
SVG_DATA_URI = 'data:image/svg+xml;base64,' + base64.b64encode(SVG.encode()).decode('ascii')

REPORT_DATA = {
    "flows": [{"id": "story", "viewId": "scenario", "title": "주문 흐름", "steps": [
        {"id": "later", "number": 1, "title": "요청 전송", "text": "Web App이 요청을 보낸다."}]}],
    "diagrams": [{"id": "original", "viewId": "scenario", "title": "원본 그림",
                  "dataUri": SVG_DATA_URI, "mimeType": "image/svg+xml"}],
}


@unittest.skipUnless(sync_playwright and Path(CHROME).is_file(), 'actual Chrome and Playwright required')
class InputGuideBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=CHROME, headless=True)
        cls.temp = tempfile.TemporaryDirectory(prefix='c4-input-guides-')
        cls.legacy_html = build_view_html(LEGACY_DATA, Path(cls.temp.name) / 'legacy.html')

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()
        cls.browser.close()
        cls.pw.stop()

    def errors_of(self, page) -> list[str]:
        errors: list[str] = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        return errors

    def test_desktop_shows_mouse_and_keyboard_guides(self) -> None:
        page = self.browser.new_page(viewport={'width': 1280, 'height': 900}, offline=True)
        try:
            errors = self.errors_of(page)
            page.goto(self.legacy_html.as_uri())
            page.wait_for_function("document.documentElement.dataset.inputGuide")
            self.assertEqual(page.evaluate("document.documentElement.dataset.inputGuide"), 'mouse')
            legend_text = page.locator('.legend').inner_text()
            self.assertIn('드래그로 이동', legend_text)
            self.assertIn('휠 확대/축소', legend_text)
            self.assertIn('단계 이동', legend_text)  # 키보드 안내는 기본 보임
            self.assertNotIn('한 손가락 드래그', legend_text)
            self.assertNotIn('두 손가락 벌리기', legend_text)
            hint = page.locator('#hint').inner_text()
            self.assertIn('휠로 확대/축소', hint)
            self.assertNotIn('두 손가락', hint)
            self.assertIn('(0)', page.locator('#zfit').get_attribute('title'))
            self.assertEqual(errors, [])
        finally:
            page.close()

    def _touch_context(self):
        return self.browser.new_context(has_touch=True, is_mobile=True,
                                        viewport={'width': 360, 'height': 800})

    def test_touch_shows_touch_guides_without_mouse_or_keyboard_wording(self) -> None:
        context = self._touch_context()
        page = context.new_page()
        try:
            errors = self.errors_of(page)
            page.goto(self.legacy_html.as_uri())
            page.wait_for_function("document.documentElement.dataset.inputGuide")
            self.assertTrue(page.evaluate("matchMedia('(pointer: coarse)').matches"))
            self.assertEqual(page.evaluate("document.documentElement.dataset.inputGuide"), 'touch')
            legend_text = page.locator('.legend').inner_text()
            self.assertIn('한 손가락 드래그 · 두 손가락 이동', legend_text)
            self.assertIn('두 손가락 벌리기 · 오므리기로 확대/축소', legend_text)
            # 터치 기기에서 마우스/휠·키보드 전용 문구는 보이지 않는다.
            self.assertNotIn('휠', legend_text)
            self.assertNotIn('드래그로 이동', legend_text)
            self.assertNotIn('단계 이동', legend_text)
            self.assertNotIn('전체 맞춤 (0)', legend_text)
            hint = page.locator('#hint').inner_text()
            self.assertIn('한 손가락 드래그로 이동, 두 손가락으로 확대/축소', hint)
            self.assertNotIn('휠', hint)
            self.assertEqual(page.locator('#zfit').get_attribute('title'), '전체 맞춤')
            # 실제 키보드 입력이 들어오면 키보드 안내가 다시 보인다(기능은 계속 동작).
            page.keyboard.press('Tab')
            self.assertEqual(page.evaluate("document.documentElement.dataset.keyboardActive"), '1')
            self.assertIn('단계 이동', page.locator('.legend').inner_text())
            self.assertEqual(errors, [])
        finally:
            page.close()
            context.close()

    def test_pointer_change_updates_guide_wording_dynamically(self) -> None:
        context = self._touch_context()
        page = context.new_page()
        try:
            page.goto(self.legacy_html.as_uri())
            page.wait_for_function("document.documentElement.dataset.inputGuide === 'touch'")
            self.assertIn('두 손가락으로 확대/축소', page.locator('#hint').inner_text())
            # 장치 전환(에뮬레이션 변경) — matchMedia change가 문구를 갱신한다.
            cdp = context.new_cdp_session(page)
            cdp.send('Emulation.setTouchEmulationEnabled', {'enabled': False})
            page.wait_for_function("document.documentElement.dataset.inputGuide === 'mouse'")
            hint = page.locator('#hint').inner_text()
            self.assertIn('휠로 확대/축소', hint)
            self.assertNotIn('두 손가락', hint)
            legend_text = page.locator('.legend').inner_text()
            self.assertIn('드래그로 이동', legend_text)
            self.assertNotIn('한 손가락', legend_text)
            # 다시 터치로 돌아오면 터치 문구로 되돌아간다.
            cdp.send('Emulation.setTouchEmulationEnabled', {'enabled': True, 'maxPoints': 5})
            page.wait_for_function("document.documentElement.dataset.inputGuide === 'touch'")
            self.assertIn('두 손가락으로 확대/축소', page.locator('#hint').inner_text())
        finally:
            page.close()
            context.close()

    def test_touch_pan_zoom_and_tap_still_work(self) -> None:
        # A8은 문구만 바꾼다 — 터치에서도 팬·줌·탭 선택 기능이 그대로 동작한다.
        context = self._touch_context()
        page = context.new_page()
        try:
            page.goto(self.legacy_html.as_uri())
            page.wait_for_function("window.repoFlowmap && window.repoFlowmap.ready()")
            before = page.evaluate("window.repoFlowmap.state().camera")
            stage = page.locator('#stage')
            box = stage.bounding_box()
            # 포인터 드래그(터치 팬과 같은 pointer 경로)로 카메라가 이동한다.
            page.mouse.move(box['x'] + box['width'] * 0.6, box['y'] + box['height'] * 0.6)
            page.mouse.down()
            page.mouse.move(box['x'] + box['width'] * 0.6 - 90, box['y'] + box['height'] * 0.6 - 40, steps=6)
            page.mouse.up()
            after_pan = page.evaluate("window.repoFlowmap.state().camera")
            self.assertNotEqual((after_pan['tx'], after_pan['ty']), (before['tx'], before['ty']))
            # 줌 버튼(탭 대상)도 그대로 동작한다. 360px에서는 플로우 패널이 버튼 위에
            # 겹치는 기존 레이아웃 조건이므로(force) 핸들러 동작만 검증한다.
            page.locator('#zin').click(force=True)
            after_zoom = page.evaluate("window.repoFlowmap.state().camera")
            self.assertGreater(after_zoom['k'], before['k'])
            # 터치 탭으로 노드를 선택할 수 있다.
            page.touchscreen.tap(box['x'] + box['width'] * 0.5, box['y'] + box['height'] * 0.5)
            page.wait_for_timeout(200)
            self.assertIsNotNone(page.evaluate("window.repoFlowmap.state().step"))
        finally:
            page.close()
            context.close()

    def test_typed_view_legend_and_hint_follow_input_mode(self) -> None:
        from generate_repo_flowmap_demo import make_model
        from repo_flowmap_adapter import project
        model = make_model()
        raw = json.dumps(model, ensure_ascii=False)
        flowmap = project(model, 'model/architecture-model.json',
                          hashlib.sha256(raw.encode()).hexdigest(), 'ordering-context')
        html = build_view_html(flowmap, Path(self.temp.name) / 'typed.html')
        page = self.browser.new_page(viewport={'width': 1280, 'height': 900}, offline=True)
        try:
            errors = self.errors_of(page)
            page.goto(html.as_uri())
            page.wait_for_function("document.documentElement.dataset.inputGuide")
            legend_text = page.locator('.legend').inner_text()
            self.assertIn('드래그 이동 · 휠 확대', legend_text)
            self.assertNotIn('두 손가락', legend_text)
            hint = page.locator('#hint').inner_text()
            self.assertIn('휠 확대', hint)
            self.assertEqual(errors, [])
        finally:
            page.close()
        context = self._touch_context()
        page = context.new_page()
        try:
            page.goto(html.as_uri())
            page.wait_for_function("document.documentElement.dataset.inputGuide === 'touch'")
            legend_text = page.locator('.legend').inner_text()
            self.assertIn('한 손가락 드래그 · 두 손가락으로 확대/축소', legend_text)
            self.assertNotIn('휠', legend_text)
            self.assertIn('핀치 확대', page.locator('#hint').inner_text())
        finally:
            page.close()
            context.close()


@unittest.skipUnless(sync_playwright and Path(CHROME).is_file(), 'actual Chrome and Playwright required')
class ReportFigureGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=CHROME, headless=True)
        cls.template = (ROOT / 'assets/html-report-template.html').read_text()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.pw.stop()

    def load(self, page) -> None:
        page.set_content(self.template.replace('__REPORT_DATA_JSON__', json.dumps(REPORT_DATA)))
        page.locator('#flows').scroll_into_view_if_needed()

    def test_desktop_keeps_keyboard_clause_and_frame_label(self) -> None:
        page = self.browser.new_page(viewport={'width': 1280, 'height': 900})
        try:
            errors: list[str] = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            self.load(page)
            help_text = page.locator('.semantic-help').inner_text()
            self.assertIn('그림에 초점을 두고 방향키로 이동', help_text)
            self.assertTrue(page.locator('.kbd-clause').is_visible())
            srcdoc = page.locator('.semantic-frame').get_attribute('srcdoc') or ''
            self.assertIn('확대 시 방향키로 이동', srcdoc)
            self.assertEqual(errors, [])
        finally:
            page.close()

    def test_touch_hides_keyboard_clause_and_switches_frame_label(self) -> None:
        context = self.browser.new_context(has_touch=True, is_mobile=True,
                                           viewport={'width': 360, 'height': 800})
        page = context.new_page()
        try:
            errors: list[str] = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            self.load(page)
            # 터치 기기에서는 실행할 수 없는 키보드 안내 문구를 숨긴다.
            self.assertFalse(page.locator('.kbd-clause').is_visible())
            help_text = page.locator('.semantic-help').inner_text()
            self.assertNotIn('방향키', help_text)
            self.assertIn('스크롤', help_text)
            srcdoc = page.locator('.semantic-frame').get_attribute('srcdoc') or ''
            self.assertIn('확대 시 화면을 밀어 이동', srcdoc)
            self.assertNotIn('방향키', srcdoc)
            self.assertEqual(errors, [])
        finally:
            page.close()
            context.close()


if __name__ == '__main__':
    unittest.main()
