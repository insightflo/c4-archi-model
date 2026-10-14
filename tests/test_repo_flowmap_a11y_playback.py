"""D9 saved-SVG accessibility naming + A7 hidden/offscreen playback stop.

Browser cases run the SAME native renderer via real Chromium on file:// URLs.
The visibilitychange case injects the event with a redefined document.hidden —
this verifies renderer logic, not an actual OS tab hide (no such API in tests).
All generated files live in temporary directories; nothing is committed.
"""
from __future__ import annotations
import base64
import copy
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
from c4_validation import validate_svg_accessibility  # noqa: E402

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


def typed_fixture(view_id: str) -> tuple[dict, dict]:
    from generate_repo_flowmap_demo import make_model
    from repo_flowmap_adapter import project
    model = make_model()
    raw = json.dumps(model, ensure_ascii=False)
    return project(model, 'model/architecture-model.json',
                   hashlib.sha256(raw.encode()).hexdigest(), view_id), model


LEGACY_DATA = {
    "meta": {"project": "legacy-demo", "title": "Legacy 데모", "last_analyzed_commit": "demo000"},
    "layers": [{"id": "ui", "label": "UI", "color": "#365d91"},
               {"id": "svc", "label": "서비스", "color": "#7a5195"}],
    "nodes": [{"id": "web", "label": "웹 화면", "desc": "사용자 입력", "layer": "ui"},
              {"id": "api", "label": "주문 API", "desc": "주문 처리", "layer": "svc"},
              {"id": "db", "label": "주문 DB", "desc": "주문 보관", "layer": "svc"}],
    "flows": [
        {"id": "place-order", "group": "주문", "title": "주문 접수", "summary": "주문을 접수해 보관한다",
         "steps": [{"from": "web", "to": "api", "call": "POST /orders"},
                   {"from": "api", "to": "db", "call": "insert()"}]},
        {"id": "list-orders", "group": "주문", "title": "주문 조회", "summary": "저장된 주문을 조회한다",
         "steps": [{"from": "web", "to": "api", "call": "GET /orders"},
                   {"from": "api", "to": "db", "call": "query()"}]}],
}

GOOD_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" role="img" '
            'aria-labelledby="rfm-a-title rfm-a-desc">'
            '<title id="rfm-a-title">제목</title><desc id="rfm-a-desc">설명</desc>'
            '<g id="vp"><rect id="r1"/></g></svg>')


class ValidateSvgAccessibilityTests(unittest.TestCase):
    """Exported-SVG accessibility gate; hand-authored SVGs are NOT retroactively bound."""

    def test_wellformed_structure_passes(self):
        report = validate_svg_accessibility(GOOD_SVG, 'good.svg')
        self.assertEqual(report.result, 'PASS', report.to_dict())
        self.assertEqual([c.id for c in report.checks if c.result == 'PASS'], ['SVG-A11Y-000'])

    def test_each_mutation_fails_with_expected_codes(self):
        # A passing baseline is exercised before each destructive mutation.
        self.assertEqual(validate_svg_accessibility(GOOD_SVG).result, 'PASS')
        mutations = {
            'no-role': GOOD_SVG.replace(' role="img"', ''),
            'role-application': GOOD_SVG.replace('role="img"', 'role="application"'),
            'no-labelledby': GOOD_SVG.replace(' aria-labelledby="rfm-a-title rfm-a-desc"', ''),
            'dangling-ref': GOOD_SVG.replace('rfm-a-desc"', 'rfm-a-missing"', 1),
            'desc-not-referenced': GOOD_SVG.replace('aria-labelledby="rfm-a-title rfm-a-desc"',
                                                    'aria-labelledby="rfm-a-title"'),
            'duplicate-ids': GOOD_SVG.replace('id="r1"', 'id="rfm-a-title"'),
            'digit-first-id': GOOD_SVG.replace('rfm-a-title', '1rfm-a-title'),
            'empty-title': GOOD_SVG.replace('>제목<', '><'),
            'missing-desc': GOOD_SVG.replace('<desc id="rfm-a-desc">설명</desc>', ''),
            'not-svg-root': GOOD_SVG.replace('<svg ', '<div ', 1),
            'unparseable': GOOD_SVG + '<title>',
        }
        expected = {
            'no-role': {'SVG-A11Y-002'},
            'role-application': {'SVG-A11Y-002'},
            'no-labelledby': {'SVG-A11Y-005'},
            'dangling-ref': {'SVG-A11Y-005'},
            'desc-not-referenced': {'SVG-A11Y-005'},
            'duplicate-ids': {'SVG-A11Y-006'},
            'digit-first-id': {'SVG-A11Y-004'},
            'empty-title': {'SVG-A11Y-003'},
            'missing-desc': {'SVG-A11Y-003', 'SVG-A11Y-004', 'SVG-A11Y-005'},
            'not-svg-root': {'SVG-A11Y-001'},
            'unparseable': {'SVG-A11Y-001'},
        }
        for label, svg in mutations.items():
            with self.subTest(mutation=label):
                report = validate_svg_accessibility(svg, label + '.svg')
                self.assertEqual(report.result, 'FAIL', label)
                codes = {finding.code for finding in report.errors}
                self.assertEqual(codes, expected[label], label)

    def test_export_script_runs_the_accessibility_gate(self):
        export = (SCRIPTS / 'export_repo_flowmap_svg.py').read_text(encoding='utf-8')
        self.assertIn('validate_svg_accessibility', export,
                      'export must verify the accessibility naming structure it emits')


@unittest.skipUnless(sync_playwright and Path(CHROME).is_file() and shutil.which('node'),
                     'actual Chrome, Playwright and Node required')
class ExportAccessibilityBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        dotted, model = typed_fixture('ordering-sequence')
        # Exact original viewId keeps its dot in data; only derived SVG ids sanitize it.
        for view in model['views']:
            if view['id'] == 'ordering-sequence':
                view['id'] = 'ordering.sequence.v2'
        from repo_flowmap_adapter import project
        raw = json.dumps(model, ensure_ascii=False)
        dotted = project(model, 'model/architecture-model.json',
                         hashlib.sha256(raw.encode()).hexdigest(), 'ordering.sequence.v2')
        cls.sequence_html = build_view_html(dotted, base / 'sequence.html')
        cls.sequence_data = dotted
        context, _ = typed_fixture('ordering-context')
        cls.context_html = build_view_html(context, base / 'context.html')
        cls.legacy_html = build_view_html(copy.deepcopy(LEGACY_DATA), base / 'legacy.html')
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=CHROME, headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.tmp.cleanup()

    def page_for(self, path: Path):
        page = self.browser.new_page(viewport={'width': 1440, 'height': 1000}, offline=True)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(path.as_uri())
        page.evaluate('document.fonts.ready')
        page.wait_for_function('window.repoFlowmap && window.repoFlowmap.ready()')
        self.assertFalse(errors)
        return page, errors

    @staticmethod
    def export_root(page):
        return ET.fromstring(page.evaluate('window.repoFlowmap.exportSvg()'))

    def test_export_carries_role_title_desc_and_labelledby(self):
        page, _ = self.page_for(self.sequence_html)
        root = self.export_root(page)
        view = self.sequence_data['c4']['view']
        self.assertEqual(root.get('role'), 'img')
        title = next(c for c in root if c.tag.endswith('}title'))
        desc = next(c for c in root if c.tag.endswith('}desc'))
        self.assertEqual(title.get('id'), 'rfm-ordering-sequence-v2-title')
        self.assertEqual(desc.get('id'), 'rfm-ordering-sequence-v2-desc')
        self.assertEqual(root.get('aria-labelledby'), 'rfm-ordering-sequence-v2-title rfm-ordering-sequence-v2-desc')
        # Name text comes from the canonical View, not an invented label.
        self.assertEqual(title.text, view['title'])
        self.assertIn(view['question'], desc.text)
        self.assertIn(view['description'], desc.text)
        # <title>/<desc> are the first children of the exported root.
        self.assertEqual([child.tag.rsplit('}', 1)[-1] for child in root][:3], ['title', 'desc', 'style'])
        page.close()

    def test_distinct_view_ids_never_collide_when_combined(self):
        names = {}
        for name, path in (('sequence', self.sequence_html), ('context', self.context_html)):
            page, _ = self.page_for(path)
            root = self.export_root(page)
            title = next(c for c in root if c.tag.endswith('}title'))
            desc = next(c for c in root if c.tag.endswith('}desc'))
            self.assertEqual(root.get('aria-labelledby'), title.get('id') + ' ' + desc.get('id'))
            names[name] = {title.get('id'), desc.get('id')}
            page.close()
        # Combining both figures into one document keeps name references unambiguous.
        self.assertEqual(names['sequence'] & names['context'], set())
        self.assertEqual(names['sequence'], {'rfm-ordering-sequence-v2-title', 'rfm-ordering-sequence-v2-desc'})

    def test_live_map_updates_names_on_flow_switch(self):
        page, _ = self.page_for(self.legacy_html)
        seen = []
        for selector in ('[data-flow="place-order"]', '[data-flow="list-orders"]'):
            page.locator(selector).first.click()
            page.wait_for_timeout(150)
            live = page.evaluate('''() => { const m = document.getElementById('map');
                const t = m.querySelector(':scope > title'), d = m.querySelector(':scope > desc');
                return {labelledby: m.getAttribute('aria-labelledby'), title: t.textContent,
                        desc: d.textContent, first: m.firstElementChild.localName}; }''')
            seen.append(live)
            export = self.export_root(page)
            self.assertEqual(export.get('role'), 'img')
            self.assertEqual(next(c for c in export if c.tag.endswith('}title')).text, live['title'])
            self.assertEqual(export.get('aria-labelledby'), live['labelledby'])
        self.assertEqual([item['title'] for item in seen], ['주문 접수', '주문 조회'])
        self.assertEqual([item['desc'] for item in seen], ['주문을 접수해 보관한다', '저장된 주문을 조회한다'])
        self.assertEqual([item['first'] for item in seen], ['title', 'title'])
        self.assertNotEqual(seen[0]['labelledby'], seen[1]['labelledby'])
        page.close()

    def test_step_navigation_keeps_naming_structure(self):
        page, _ = self.page_for(self.sequence_html)
        page.evaluate('document.getElementById("next").click()')
        page.wait_for_timeout(150)
        root = self.export_root(page)
        self.assertEqual(root.get('role'), 'img')
        self.assertEqual(root.get('aria-labelledby'), 'rfm-ordering-sequence-v2-title rfm-ordering-sequence-v2-desc')
        page.close()

    def test_export_script_accessibility_gate_pass_and_violation(self):
        """Real export run: gate passes on the real renderer, fails on a mutated one."""
        import importlib.util
        if importlib.util.find_spec('playwright') is None:
            self.skipTest('playwright module required')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run([sys.executable, str(SCRIPTS / 'generate_repo_flowmap_demo.py'),
                            '--output', str(root), '--inputs-only'], capture_output=True, text=True)
            baseline = subprocess.run([sys.executable, str(SCRIPTS / 'build_repo_flowmap.py'),
                                       '--root', str(root), '--model', 'model/architecture-model.json',
                                       '--view', 'ordering-context'], capture_output=True, text=True)
            self.assertEqual(baseline.returncode, 0, baseline.stderr)
            common = ['--root', str(root), '--html', 'diagrams/ordering-context.flowmap.html',
                      '--chromium', CHROME]
            ok = subprocess.run([sys.executable, str(SCRIPTS / 'export_repo_flowmap_svg.py'), *common],
                                capture_output=True, text=True)
            self.assertEqual(ok.returncode, 0, ok.stderr + ok.stdout)
            svg = (root / 'diagrams/ordering-context.flowmap.svg').read_text(encoding='utf-8')
            self.assertEqual(validate_svg_accessibility(svg).result, 'PASS')
            # Mutation: strip the export role attribute, rebuild, re-export — the gate must fail.
            template = root / 'assets/repo-flowmap/template.html'
            template.parent.mkdir(parents=True, exist_ok=True)
            source = (ROOT / 'assets/repo-flowmap/template.html').read_text(encoding='utf-8')
            template.write_text(source.replace("clone.setAttribute('role', 'img');", ''), encoding='utf-8')
            data = json.loads((root / 'diagrams/ordering-context.flowmap.json').read_text(encoding='utf-8'))
            html_path = root / 'diagrams/mutated.flowmap.html'
            mutated_input = root / 'diagrams/mutated.flowmap.json'
            mutated_input.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            built = subprocess.run(['node', str(ROOT / 'assets/repo-flowmap/scripts/build_flowmap.mjs'),
                                    str(mutated_input), str(template), str(html_path)],
                                   capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            bad = subprocess.run([sys.executable, str(SCRIPTS / 'export_repo_flowmap_svg.py'),
                                  '--root', str(root), '--html', 'diagrams/mutated.flowmap.html',
                                  '--chromium', CHROME], capture_output=True, text=True)
            self.assertNotEqual(bad.returncode, 0, bad.stdout)
            self.assertIn('SVG-A11Y-002', bad.stderr)


@unittest.skipUnless(sync_playwright and Path(CHROME).is_file(),
                     'actual Chrome and Playwright required')
class PlaybackControlBrowserTests(unittest.TestCase):
    """A7: hidden/offscreen/dialog-closed playback stops; resume stays manual."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        dotted, model = typed_fixture('ordering-sequence')
        from repo_flowmap_adapter import project
        for view in model['views']:
            if view['id'] == 'ordering-sequence':
                view['id'] = 'ordering.sequence.v2'
        raw = json.dumps(model, ensure_ascii=False)
        dotted = project(model, 'model/architecture-model.json',
                         hashlib.sha256(raw.encode()).hexdigest(), 'ordering.sequence.v2')
        cls.html = build_view_html(dotted, Path(cls.tmp.name) / 'sequence.html')
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=CHROME, headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.tmp.cleanup()

    def open_playing(self, reduced_motion=None):
        page = self.browser.new_page(viewport={'width': 1440, 'height': 1000}, offline=True)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        if reduced_motion:
            page.emulate_media(reduced_motion='reduce')
        page.goto(self.html.as_uri())
        page.evaluate('document.fonts.ready')
        page.wait_for_function('window.repoFlowmap && window.repoFlowmap.ready()')
        page.evaluate('document.getElementById("play").click()')
        return page, errors

    def test_hidden_visibilitychange_stops_without_catching_up(self):
        # Event injection, not a real tab hide: document.hidden is redefined so the
        # renderer's visibilitychange logic is what gets verified here.
        page, errors = self.open_playing()
        self.assertTrue(page.evaluate('window.repoFlowmap.state().playing'))
        before_step = page.evaluate('window.repoFlowmap.state().step')
        page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});"
                     "document.dispatchEvent(new Event('visibilitychange'))")
        state = page.evaluate('window.repoFlowmap.state()')
        self.assertFalse(state['playing'])
        self.assertEqual(state['stopNotice'], '화면이 숨겨져 재생을 멈췄습니다. 다시 보이면 재생 버튼으로 이어서 보세요.')
        self.assertEqual(page.locator('.stopnote').count(), 1)
        self.assertIn('재생을 멈췄습니다', page.locator('.stopnote').inner_text())
        page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});"
                     "document.dispatchEvent(new Event('visibilitychange'))")
        page.wait_for_timeout(2000)
        after = page.evaluate('window.repoFlowmap.state()')
        # No auto-resume and no fast-forward of skipped time.
        self.assertFalse(after['playing'])
        self.assertLessEqual(after['step'], before_step + 1)
        page.evaluate('document.getElementById("play").click()')
        self.assertTrue(page.evaluate('window.repoFlowmap.state().playing'))
        self.assertEqual(errors, [])
        page.close()

    def test_playback_stop_message_stops_and_start_message_is_ignored(self):
        page, errors = self.open_playing()
        # In a top-level page window.parent === window, so this mirrors the report dialog path.
        page.evaluate("window.postMessage({type:'repo-flowmap-playback',action:'stop'},'*')")
        page.wait_for_function('window.repoFlowmap.state().playing===false')
        state = page.evaluate('window.repoFlowmap.state()')
        self.assertEqual(state['stopNotice'], '전체 화면이 닫혀 재생을 멈췄습니다. 재생 버튼으로 이어서 보세요.')
        self.assertEqual(page.locator('.stopnote').count(), 1)
        page.evaluate("window.postMessage({type:'repo-flowmap-playback',action:'start'},'*')")
        page.wait_for_timeout(300)
        self.assertFalse(page.evaluate('window.repoFlowmap.state().playing'),
                         'no start action exists: auto-resume is forbidden')
        page.evaluate('document.getElementById("play").click()')
        self.assertTrue(page.evaluate('window.repoFlowmap.state().playing'))
        self.assertEqual(errors, [])
        page.close()

    def test_offscreen_stage_stops_via_intersection_observer(self):
        page, errors = self.open_playing()
        page.evaluate("document.getElementById('stage').style.display='none'")
        page.wait_for_function('window.repoFlowmap.state().playing===false', timeout=5000)
        state = page.evaluate('window.repoFlowmap.state()')
        self.assertEqual(state['stopNotice'], '그림이 화면 밖에 있어 재생을 멈췄습니다. 그림을 화면에 둔 뒤 재생 버튼으로 이어서 보세요.')
        page.evaluate("document.getElementById('stage').style.display=''")
        page.wait_for_timeout(1800)
        self.assertFalse(page.evaluate('window.repoFlowmap.state().playing'),
                         'coming back on screen must not resume playback by itself')
        self.assertEqual(errors, [])
        page.close()

    def test_reduced_motion_gives_guidance_instead_of_autoplay(self):
        page, errors = self.open_playing(reduced_motion=True)
        state = page.evaluate('window.repoFlowmap.state()')
        self.assertFalse(state['playing'])
        self.assertIn('움직임 줄이기', state['stopNotice'])
        self.assertIn('한 단계씩', state['stopNotice'])
        self.assertEqual(page.locator('.stopnote').count(), 1)
        # Manual stepping still works for reduced-motion users.
        before = page.evaluate('window.repoFlowmap.state().step')
        page.keyboard.press('ArrowRight')
        self.assertGreaterEqual(page.evaluate('window.repoFlowmap.state().step'), before)
        self.assertEqual(errors, [])
        page.close()

    def test_reduced_motion_switch_mid_playback_stops(self):
        page, errors = self.open_playing()
        self.assertTrue(page.evaluate('window.repoFlowmap.state().playing'))
        page.emulate_media(reduced_motion='reduce')
        page.wait_for_function('window.repoFlowmap.state().playing===false', timeout=5000)
        self.assertIn('움직임 줄이기', page.evaluate('window.repoFlowmap.state().stopNotice'))
        self.assertEqual(errors, [])
        page.close()


@unittest.skipUnless(sync_playwright and Path(CHROME).is_file(),
                     'actual Chrome and Playwright required')
class ReportDialogPlaybackStopTests(unittest.TestCase):
    """Report diagram-dialog close must stop the embed's playback (A7)."""

    @classmethod
    def setUpClass(cls):
        from build_html_report import hydrate_report, inject
        from c4_validation import ValidationReport
        from test_report_visual_complete import fixture
        dotted, model = typed_fixture('ordering-sequence')
        from repo_flowmap_adapter import project
        for view in model['views']:
            if view['id'] == 'ordering-sequence':
                view['id'] = 'ordering.sequence.v2'
        raw = json.dumps(model, ensure_ascii=False)
        dotted = project(model, 'model/architecture-model.json',
                         hashlib.sha256(raw.encode()).hexdigest(), 'ordering.sequence.v2')
        cls.tmp = tempfile.TemporaryDirectory()
        renderer = build_view_html(dotted, Path(cls.tmp.name) / 'sequence.html').read_text(encoding='utf-8')
        uri = 'data:text/html;base64,' + base64.b64encode(renderer.encode()).decode()
        data, bundle = fixture()
        data['diagrams'][0] = dict(data['diagrams'][0], mimeType='text/html', dataUri=uri)
        template = (ROOT / 'assets/html-report-template.html').read_text(encoding='utf-8')
        cls.report_path = Path(cls.tmp.name) / 'report.html'
        cls.report_path.write_text(inject(template, hydrate_report(data, bundle, ValidationReport('test'))),
                                   encoding='utf-8')
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=CHROME, headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.tmp.cleanup()

    def test_dialog_close_stops_embed_playback_and_reopen_stays_manual(self):
        page = self.browser.new_page(viewport={'width': 1440, 'height': 1000}, offline=True)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(self.report_path.as_uri())
        page.locator('#diagrams').scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        page.locator('#diagram-panels [data-full]').first.click()
        self.assertIsNotNone(page.locator('#diagram-dialog').get_attribute('open'))
        embed = page.locator('#dialog-embed').element_handle().content_frame()
        embed.wait_for_function('window.repoFlowmap && window.repoFlowmap.ready()')
        embed.evaluate('document.getElementById("play").click()')
        self.assertTrue(embed.evaluate('window.repoFlowmap.state().playing'))
        # Close button AND the dialog 'close' event path both funnel into the stop message.
        page.locator('#dialog-close').click()
        page.wait_for_timeout(300)
        state = embed.evaluate('window.repoFlowmap.state()')
        self.assertFalse(state['playing'])
        self.assertEqual(state['stopNotice'], '전체 화면이 닫혀 재생을 멈췄습니다. 재생 버튼으로 이어서 보세요.')
        self.assertIsNone(page.locator('#diagram-dialog').get_attribute('open'))
        # Repeated open on one page load must keep working (LESSONS: show before srcdoc).
        page.locator('#diagram-panels [data-full]').first.click()
        page.wait_for_timeout(400)
        reopened = page.locator('#dialog-embed').element_handle().content_frame()
        reopened.wait_for_function('window.repoFlowmap && window.repoFlowmap.ready()')
        self.assertFalse(reopened.evaluate('window.repoFlowmap.state().playing'),
                         'reopening must not resume playback automatically')
        self.assertEqual(errors, [])
        page.close()


if __name__ == '__main__':
    unittest.main()
