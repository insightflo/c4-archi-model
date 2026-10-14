"""A3 report guided playback + A4 C4 edge progress mark + A6 readout/announce split.

Browser cases run the SAME native renderer and the SAME report template through real
Chromium on file:// URLs. Nothing is mocked; every generated file is temporary.
The A4 state cases inject the schema-documented steps[].state field into a typed
flowmap input — that is a recorded-input display test, not an invented semantic.
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
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / 'tests'))

CHROME = os.environ.get('C4_BROWSER') or shutil.which('chromium') or '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

BROWSER_NEEDED = sync_playwright and Path(CHROME).is_file() and shutil.which('node')


def typed_projection(view_id: str) -> dict:
    from generate_repo_flowmap_demo import make_model
    from repo_flowmap_adapter import project
    model = make_model()
    raw = json.dumps(model, ensure_ascii=False)
    return project(model, 'model/architecture-model.json',
                   hashlib.sha256(raw.encode()).hexdigest(), view_id)


def build_view_html(data: dict, target: Path) -> Path:
    source = target.with_suffix('.json')
    source.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    result = subprocess.run(
        ['node', str(ROOT / 'assets/repo-flowmap/scripts/build_flowmap.mjs'),
         str(source), str(ROOT / 'assets/repo-flowmap/template.html'), str(target)],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return target


def marker_facts(page):
    return page.evaluate('''() => {
      const mark = document.querySelector('g.c4-flow-mark');
      const dash = mark && mark.querySelector('.c4-flow-dash');
      const head = mark && mark.querySelector('.c4-flow-head');
      const edge = mark && document.querySelector('path.c4-edge[data-i="' + mark.getAttribute('data-step-index') + '"]');
      const computed = dash && getComputedStyle(dash);
      return {
        count: document.querySelectorAll('g.c4-flow-mark').length,
        index: mark && mark.getAttribute('data-step-index'),
        state: mark && mark.getAttribute('data-state'),
        samePath: !!(dash && edge && dash.getAttribute('d') === edge.getAttribute('d')),
        pathLength: dash && dash.getAttribute('pathLength'),
        animation: computed && computed.animationName,
        iteration: computed && computed.animationIterationCount,
        head: head && head.getAttribute('transform'),
      };
    }''')


def edge_point(page, index: int, fraction: float):
    return page.evaluate('''([index, fraction]) => {
      const edge = document.querySelector('path.c4-edge[data-i="' + index + '"]');
      const len = edge.getTotalLength();
      const point = edge.getPointAtLength(len * fraction);
      const ahead = edge.getPointAtLength(Math.min(len, len * fraction + 2));
      return {x: point.x, y: point.y, angle: Math.atan2(ahead.y - point.y, ahead.x - point.x) * 180 / Math.PI};
    }''', [index, fraction])


@unittest.skipUnless(BROWSER_NEEDED, 'actual Chrome, Playwright and Node required')
class A4FlowMarkBrowserTests(unittest.TestCase):
    """A4: progress mark on the active structural edge only; export keeps plain edges."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        cls.classes_html = build_view_html(typed_projection('ordering-classes'), base / 'classes.html')
        # Recorded-state input: the flowmap schema documents steps[].state
        # (failover/blocked/cond). The standard projection never emits it for typed
        # structure views, so injecting it here tests display of RECORDED input only.
        recorded = typed_projection('ordering-classes')
        steps = recorded['flows'][0]['steps']
        steps[0]['state'] = 'failover'
        steps[1]['state'] = 'blocked'
        steps[2]['state'] = 'cond'
        cls.recorded_html = build_view_html(recorded, base / 'recorded.html')
        cls.sequence_html = build_view_html(typed_projection('ordering-sequence'), base / 'sequence.html')
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=CHROME, headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.tmp.cleanup()

    def open(self, path: Path, reduced_motion: bool = False):
        page = self.browser.new_page(viewport={'width': 1440, 'height': 1000}, offline=True)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        if reduced_motion:
            page.emulate_media(reduced_motion='reduce')
        page.goto(path.as_uri())
        page.evaluate('document.fonts.ready')
        page.wait_for_function('window.repoFlowmap && window.repoFlowmap.ready()')
        return page, errors

    def test_mark_follows_active_edge_forward_and_export_keeps_plain_edges(self):
        page, errors = self.open(self.classes_html)
        page.evaluate("window.postMessage({type:'repo-flowmap-step',viewId:'ordering-classes',stepIndex:1},'*')")
        page.wait_for_timeout(150)
        facts = marker_facts(page)
        self.assertEqual(facts['count'], 1, 'exactly one mark, on the active edge')
        self.assertEqual(facts['index'], '1')
        self.assertTrue(facts['samePath'], 'mark overlays the original edge path')
        self.assertEqual(facts['pathLength'], '100')
        self.assertEqual(facts['animation'], 'c4-flow-dash')
        self.assertEqual(facts['iteration'], 'infinite')
        # Forward direction: dashoffset keeps decreasing (toward the destination).
        first = float(page.evaluate("getComputedStyle(document.querySelector('g.c4-flow-mark .c4-flow-dash')).strokeDashoffset")[:-2])
        page.wait_for_timeout(300)
        second = float(page.evaluate("getComputedStyle(document.querySelector('g.c4-flow-mark .c4-flow-dash')).strokeDashoffset")[:-2])
        self.assertLess(second, first, 'marker must travel from source toward destination')
        # Static direction chevron sits on the same path at the representative frame.
        expected = edge_point(page, 1, 0.58)
        self.assertIn(f"translate({expected['x']},{expected['y']})", facts['head'])
        self.assertIn(f"rotate({expected['angle']})", facts['head'])
        # Switching steps moves the mark; clearing the step removes it.
        page.evaluate("window.postMessage({type:'repo-flowmap-step',viewId:'ordering-classes',stepIndex:3},'*')")
        page.wait_for_timeout(150)
        self.assertEqual(marker_facts(page)['index'], '3')
        page.evaluate("window.postMessage({type:'repo-flowmap-step',viewId:'ordering-classes',stepIndex:-1},'*')")
        page.wait_for_timeout(150)
        self.assertEqual(page.evaluate("document.querySelectorAll('g.c4-flow-mark').length"), 0)
        # Export: no mark elements, all original edges kept, UML dasharrays preserved.
        root = ET.fromstring(page.evaluate('window.repoFlowmap.exportSvg()'))
        marks = [e for e in root.iter() if 'c4-flow-mark' in (e.get('class') or '').split()]
        edges = [e for e in root.iter() if e.tag.endswith('}path') and 'c4-edge' in (e.get('class') or '').split()]
        self.assertEqual(len(marks), 0, 'static export must not carry the motion overlay')
        self.assertEqual(len(edges), 5)
        dashed = [(e.get('data-kind'), e.get('stroke-dasharray')) for e in edges
                  if e.get('data-kind') in ('dependency', 'realization')]
        self.assertTrue(dashed and all(v == '8 5' for _, v in dashed), dashed)
        self.assertEqual(errors, [])
        page.close()

    def test_reduced_motion_freezes_mark_into_static_direction(self):
        page, errors = self.open(self.classes_html, reduced_motion=True)
        page.evaluate("window.postMessage({type:'repo-flowmap-step',viewId:'ordering-classes',stepIndex:2},'*')")
        page.wait_for_timeout(150)
        frozen = page.evaluate('''() => {
          const dash = document.querySelector('g.c4-flow-mark .c4-flow-dash');
          const computed = getComputedStyle(dash);
          return {animation: computed.animationName, offset: computed.strokeDashoffset,
                  head: !!document.querySelector('g.c4-flow-mark .c4-flow-head')};
        }''')
        self.assertEqual(frozen['animation'], 'none')
        self.assertEqual(frozen['offset'], '-58px', 'everyone must see the same representative frame')
        self.assertTrue(frozen['head'], 'static direction chevron must remain')
        self.assertEqual(errors, [])
        page.close()

    def test_recorded_states_recolor_mark_and_blocked_clamps_like_cut_line(self):
        page, errors = self.open(self.recorded_html)
        legend = page.locator('.legend').inner_text()
        for row in ('장애(failover)', '차단(blocked)', '조건'):
            self.assertIn(row, legend)
        colors = {}
        for index, expected_state in ((0, 'failover'), (1, 'blocked'), (2, 'cond'), (3, None)):
            page.evaluate(f"window.postMessage({{type:'repo-flowmap-step',viewId:'ordering-classes',stepIndex:{index}}},'*')")
            page.wait_for_timeout(120)
            facts = marker_facts(page)
            self.assertEqual(facts['state'], expected_state, f'step {index}')
            colors[index] = page.evaluate("getComputedStyle(document.querySelector('g.c4-flow-mark .c4-flow-dash')).stroke")
        self.assertNotEqual(colors[0], colors[3], 'recorded failover must recolor the mark')
        self.assertNotEqual(colors[2], colors[3], 'recorded cond must recolor the mark')
        # blocked: same accent as failover (stop color) and the 62% cut metaphor.
        self.assertEqual(colors[1], colors[0])
        page.evaluate("window.postMessage({type:'repo-flowmap-step',viewId:'ordering-classes',stepIndex:1},'*')")
        page.wait_for_timeout(120)
        self.assertEqual(marker_facts(page)['animation'], 'c4-flow-dash-blocked')
        expected = edge_point(page, 1, 0.45)
        self.assertIn(f"translate({expected['x']},{expected['y']})", marker_facts(page)['head'])
        # The plain projection shows no state rows: no recorded field, no invented meaning.
        page2, errors2 = self.open(self.classes_html)
        self.assertNotIn('장애(failover)', page2.locator('.legend').inner_text())
        self.assertEqual(errors, [])
        self.assertEqual(errors2, [])
        page.close()
        page2.close()

    def test_sequence_view_has_no_edge_mark(self):
        page, errors = self.open(self.sequence_html)
        page.evaluate("window.postMessage({type:'repo-flowmap-step',viewId:'ordering-sequence',stepIndex:1},'*')")
        page.wait_for_timeout(150)
        self.assertEqual(page.evaluate("document.querySelectorAll('g.c4-flow-mark').length"), 0,
                         'sequence keeps its numbered hot messages; no c4-edge overlay')
        self.assertEqual(page.evaluate("document.querySelectorAll('g.c4-message.c4-hot').length"), 1)
        self.assertEqual(errors, [])
        page.close()


@unittest.skipUnless(BROWSER_NEEDED, 'actual Chrome, Playwright and Node required')
class ReportGuidedPlaybackTests(unittest.TestCase):
    """A3 report-driven guidance + A6 visual readout / screen-reader announce split."""

    @classmethod
    def setUpClass(cls):
        from build_html_report import hydrate_report, inject
        from c4_validation import ValidationReport
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        # Align the embedded renderer's viewId with the fixture flow so camera/step
        # messages match; the report is what drives the steps during guidance.
        renderer = build_view_html(typed_projection('ordering-sequence'), base / 'sequence.html') \
            .read_text(encoding='utf-8')
        cls.renderer_uri = 'data:text/html;base64,' + base64.b64encode(
            renderer.replace('"viewId": "ordering-sequence"', '"viewId": "scenario"').encode()).decode()
        # A silent decoy: claims native-camera via marker string but never answers
        # step messages — guidance must survive it through the ack timeout.
        cls.decoy_uri = 'data:text/html;base64,' + base64.b64encode(
            '<!doctype html><meta charset="utf-8"><!-- repo-flowmap-camera marker only -->'
            '<p>원본 그림을 표시할 수 없습니다</p>'.encode()).decode()
        cls.template = (ROOT / 'assets/html-report-template.html').read_text(encoding='utf-8')
        cls.hydrate = staticmethod(hydrate_report)
        cls.inject = staticmethod(inject)
        cls.report_cls = ValidationReport
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=CHROME, headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.tmp.cleanup()

    def write_report(self, decoy: bool = False) -> Path:
        from test_report_visual_complete import fixture
        data, bundle = fixture()
        data['diagrams'][0] = dict(data['diagrams'][0], mimeType='text/html',
                                   dataUri=self.decoy_uri if decoy else self.renderer_uri)
        hydrated = self.hydrate(data, bundle, self.report_cls('test'))
        path = Path(self.tmp.name) / ('report-decoy.html' if decoy else 'report.html')
        path.write_text(self.inject(self.template, hydrated), encoding='utf-8')
        return path

    def load(self, decoy: bool = False):
        page = self.browser.new_page(viewport={'width': 1440, 'height': 1000}, offline=True)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(self.write_report(decoy).as_uri())
        page.locator('#flows').scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        return page, errors

    def observe_announce(self, page):
        page.evaluate('''() => {
          window.__announce = [];
          const region = document.querySelector('#flow-panel-calls .flow-step-announce');
          new MutationObserver(records => records.forEach(() => window.__announce.push(region.textContent)))
            .observe(region, {childList: true, characterData: true, subtree: true});
        }''')

    def renderer_frames(self, page):
        return [frame for frame in page.frames
                if frame != page.main_frame and frame.evaluate('!!window.repoFlowmap')]

    def test_guidance_syncs_steps_figure_and_progress_then_ends(self):
        page, errors = self.load()
        story = page.locator('#flow-panel-calls')
        # A6 split: number readout is visual-only; the live region announces meaning.
        progress = story.locator('.flow-progress')
        self.assertEqual(progress.get_attribute('aria-hidden'), 'true')
        self.assertIsNone(progress.get_attribute('role'))
        announce = story.locator('.flow-step-announce')
        self.assertEqual(announce.get_attribute('role'), 'status')
        self.assertEqual(announce.get_attribute('aria-live'), 'polite')
        self.assertGreater(len(self.renderer_frames(page)), 0, 'live renderer figure must be embedded')
        self.observe_announce(page)
        story.get_by_role('button', name='안내 재생').click()
        page.wait_for_function(
            "document.querySelector('#flow-panel-calls .flow-step-announce').textContent.includes('끝났습니다')",
            timeout=15000)
        self.assertEqual(page.evaluate('window.__announce'), [
            '안내 재생을 시작합니다. 1/2단계 · Send',
            '2/2단계 · Send',
            '안내 재생이 끝났습니다.'])
        self.assertEqual(progress.inner_text(), '2 / 2 단계')
        button = story.get_by_role('button', name='안내 재생')
        self.assertEqual(button.get_attribute('aria-pressed'), 'false')
        # Both live figures ended on the last guided step (report drove them via ack).
        for frame in self.renderer_frames(page):
            self.assertEqual(frame.evaluate('repoFlowmap.state().step'), 1)
        self.assertIn('Second detail', story.locator('.flow-step:not([hidden])').inner_text())
        page.emulate_media(media='print')
        self.assertFalse(button.is_visible(), 'print must not show guidance controls')
        self.assertEqual(errors, [])
        page.close()

    def test_manual_step_selection_stops_guidance_without_resume(self):
        page, errors = self.load()
        story = page.locator('#flow-panel-calls')
        self.observe_announce(page)
        story.get_by_role('button', name='안내 재생').click()
        page.wait_for_function(
            "document.querySelector('#flow-panel-calls .flow-step-announce').textContent.includes('2/2단계')",
            timeout=10000)
        story.locator('.flow-step-selector').first.click()
        self.assertEqual(page.evaluate('window.__announce')[-1], '1/2단계 · Send')
        self.assertEqual(story.get_by_role('button', name='안내 재생').get_attribute('aria-pressed'), 'false')
        announce_now = page.evaluate("document.querySelector('#flow-panel-calls .flow-step-announce').textContent")
        page.wait_for_timeout(3600)  # longer than one guided interval: nothing may advance
        self.assertEqual(page.evaluate("document.querySelector('#flow-panel-calls .flow-step-announce').textContent"),
                         announce_now, 'no auto-resume after the user takes over')
        self.assertEqual(len(page.evaluate('window.__announce')), 3)
        self.assertEqual(errors, [])
        page.close()

    def test_tab_switch_and_zoom_controls_stop_guidance(self):
        page, errors = self.load()
        story = page.locator('#flow-panel-calls')
        self.observe_announce(page)
        story.get_by_role('button', name='안내 재생').click()
        page.wait_for_function("document.querySelector('#flow-panel-calls .flow-step-announce').textContent.startsWith('안내 재생을 시작합니다')", timeout=10000)
        # 부하가 높은 전체 스위트 실행에서 클릭이 닿지 않는 경우(LESSONS.md) — 긍정형
        # 조건 + 재클릭 한 번으로만 흡수한다. 재클릭은 stopGuides만 다시 부르므로 무해하다.
        def click_and_wait_stop(locator, expect_text: str) -> None:
            locator.click()
            try:
                page.wait_for_function(
                    "(t) => document.querySelector('#flow-panel-calls .flow-step-announce').textContent.includes(t)",
                    arg=expect_text, timeout=8000)
            except Exception as exc:
                locator.click()
                page.wait_for_function(
                    "(t) => document.querySelector('#flow-panel-calls .flow-step-announce').textContent.includes(t)",
                    arg=expect_text, timeout=15000)

        click_and_wait_stop(page.locator('#diagram-tabs [role="tab"]').nth(1), '다른 탭을 선택해')
        # Restart on the first diagram tab, then zoom that same view: also a stop.
        page.locator('#diagram-tabs [role="tab"]').nth(0).click()
        story.get_by_role('button', name='안내 재생').click()
        page.wait_for_function("document.querySelector('#flow-panel-calls .flow-step-announce').textContent.startsWith('안내 재생을 시작합니다')", timeout=10000)
        click_and_wait_stop(page.locator('#diagram-panels [data-zoom="in"]').first, '사용자 조작으로')
        self.assertEqual(story.get_by_role('button', name='안내 재생').get_attribute('aria-pressed'), 'false')
        self.assertEqual(errors, [])
        page.close()

    def test_unresponsive_figure_does_not_deadlock_guidance(self):
        page, errors = self.load(decoy=True)
        story = page.locator('#flow-panel-calls')
        self.assertEqual(page.locator('#flow-panel-calls iframe[data-native-camera="1"]').count(), 1)
        self.observe_announce(page)
        story.get_by_role('button', name='안내 재생').click()
        page.wait_for_function(
            "document.querySelector('#flow-panel-calls .flow-step-announce').textContent.includes('끝났습니다')",
            timeout=15000)
        # Ack timeout (1.5s per step) bounded the wait; guidance still finished.
        self.assertEqual(page.evaluate('window.__announce'), [
            '안내 재생을 시작합니다. 1/2단계 · Send',
            '2/2단계 · Send',
            '안내 재생이 끝났습니다.'])
        self.assertEqual(errors, [])
        page.close()

    def test_single_step_flow_has_no_guidance_control(self):
        from test_report_visual_complete import fixture
        data, bundle = fixture()
        data['diagrams'][0] = dict(data['diagrams'][0], mimeType='text/html', dataUri=self.renderer_uri)
        model = bundle['model']
        for view in model['views']:
            if view['id'] == 'scenario':
                view['steps'] = view['steps'][:1]
        hydrated = self.hydrate(data, bundle, self.report_cls('test'))
        path = Path(self.tmp.name) / 'report-one-step.html'
        path.write_text(self.inject(self.template, hydrated), encoding='utf-8')
        page = self.browser.new_page(viewport={'width': 1440, 'height': 1000}, offline=True)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(path.as_uri())
        page.locator('#flows').scroll_into_view_if_needed()
        self.assertEqual(page.locator('#flow-panel-calls .flow-guide-btn').count(), 1)
        self.assertTrue(page.locator('#flow-panel-calls .flow-guide-btn').is_hidden(),
                        'a one-step flow has nothing to guide: no control is offered')
        self.assertEqual(errors, [])
        page.close()


if __name__ == '__main__':
    unittest.main()
