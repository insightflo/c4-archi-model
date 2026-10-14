"""Chrome file:// regressions. C4_REAL_PACKAGE enables read-only real-input coverage.

C4_BROWSER may select a Chromium executable; no browser is mocked. Real package
inputs are read only and every generated file is placed in a temporary directory.
"""
from __future__ import annotations
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
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
from check_repo_flowmap_browser import (
    GEOMETRY,
    LABEL_OCCLUSION_KEY,
    NEAR_CONNECTION_KEY,
    read_flow_data,
    sequence_checks,
)
from timeline_recorder import TOLERANCE_MS, Timeline, record_step_index

CHROME = os.environ.get('C4_BROWSER') or shutil.which('chromium') or '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None


class CheckerInputTests(unittest.TestCase):
    def test_zero_one_many_self_calls_and_missing_message(self):
        for count in (0, 1, 3):
            steps = [{'id': 'read-' + str(i), 'order': i + 1, 'from': 'a', 'to': 'a'} for i in range(count)]
            steps.append({'id': 'finish', 'order': count + 1, 'from': 'a', 'to': 'b'})
            g = {'messages': [{'id': s['id'], 'order': s['order']} for s in steps],
                 'self': [{'id': s['id'], 'labelRight': 80, 'box': {'x': 20, 'y': 20, 'right': 80, 'bottom': 80}} for s in steps[:-1]],
                 'exportedViewBox': '0 0 100 100'}
            self.assertEqual(sequence_checks(g, steps), (True, True))
            if count:
                g['self'].pop()
                self.assertEqual(sequence_checks(g, steps), (True, False))
            g['messages'].pop()
            self.assertFalse(sequence_checks(g, steps)[0])

    def test_dynamic_type_not_view_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'read-flow.html'
            source = {'c4': {'viewId': 'read-flow', 'view': {'type': 'dynamic'}}}
            path.write_text('<script id="flow-data" type="application/json">' + json.dumps(source) + '</script>')
            self.assertEqual(read_flow_data(path)['c4']['view']['type'], 'dynamic')


@unittest.skipUnless(sync_playwright and Path(CHROME).is_file(), 'actual Chrome and Playwright required')
class ChromeGeometryTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('C4_REAL_PACKAGE'), 'set C4_REAL_PACKAGE for actual iframe pan regression')
    def test_real_container_pan_selects_hit_tested_background(self):
        import check_repo_flowmap_browser as checker
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=CHROME, headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 1000}, offline=True)
            page.goto((Path(os.environ['C4_REAL_PACKAGE']) / 'index.html').as_uri())
            page.locator('#diagrams').scroll_into_view_if_needed()
            page.locator('#diagram-tabs [role=tab]').nth(1).click()
            handle = page.locator('#diagram-panels iframe').nth(1)
            handle.scroll_into_view_if_needed()
            frame = handle.element_handle().content_frame()
            frame.wait_for_function('window.repoFlowmap && window.repoFlowmap.ready()')
            frame.evaluate('document.fonts.ready')
            handle.locator('xpath=ancestor::*[contains(concat(" ",normalize-space(@class)," ")," diagram-card ")][1]').locator('[data-zoom=in]').click()
            page.wait_for_timeout(400)
            stage = frame.locator('#stage').bounding_box()
            before = frame.evaluate('repoFlowmap.state().camera')
            # Demonstrate the original false failure on the actual node.
            x, y = stage['x'] + 12, stage['y'] + stage['height'] - 70
            page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x+54, y-40, steps=8); page.mouse.up()
            self.assertEqual(frame.evaluate('repoFlowmap.state().camera'), before)
            self.assertTrue(hasattr(checker, 'pan_background'), 'checker needs hit-tested background selection')
            detail = checker.pan_background(page, frame)
            self.assertIn(detail['target'], ('map', 'stage'))
            self.assertTrue(abs(detail['after']['tx']-detail['before']['tx']) > 20 or
                            abs(detail['after']['ty']-detail['before']['ty']) > 20, detail)
            browser.close()

    def test_badge_in_outer_route_gutter_chooses_safe_slot(self):
        # Reproduce the real container failure: the route itself is valid at x=10,
        # but a centered 12px badge at its midpoint extends to x=-2.
        template = (ROOT / 'assets/repo-flowmap/template.html').read_text()
        function = template.split('  function c4PlaceBadges(L) {', 1)[1].split('  function renderTypedMap()', 1)[0]
        script = 'function c4PlaceBadges(L) {' + function
        html = '<svg id="map" width="400" height="400"><path class="c4-edge" data-i="0" d="M100,100 H10 V300 H100"/><g class="badges"></g></svg>'
        html += '<script>var el={map:document.querySelector("#map")},state={step:-1};' + script + 'c4PlaceBadges({routePos:{}});</script>'
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
            path = Path(tmp) / 'gutter.html'; path.write_text(html)
            browser = pw.chromium.launch(executable_path=CHROME, headless=True)
            page = browser.new_page(); errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(path.as_uri())
            result = page.evaluate('''() => {let e=document.querySelector('.badge'),b=e.getBBox();return {x:b.x,y:b.y,count:document.querySelectorAll('.badge').length}}''')
            self.assertEqual(result['count'], 1)
            self.assertGreaterEqual(result['x'], 0)
            self.assertGreaterEqual(result['y'], 0)
            self.assertFalse(errors)
            self.assertTrue(page.url.startswith('file:'))
            browser.close()

    def test_logical_deployment_boundary_endpoints_export_without_instances(self):
        from generate_repo_flowmap_demo import make_model
        from repo_flowmap_adapter import project
        model = make_model()
        view = next(v for v in model['views'] if v['id']=='ordering-deployment')
        view['elementIds'].append('order-api')
        import copy
        relation = copy.deepcopy(model['relationships'][0])
        relation.update(id='host-logical',sourceId='app-host',destinationId='order-api',description='앱 실행 위치로 제안한다')
        model['relationships'].append(relation)
        view['relationshipIds'].append(relation['id'])
        data = project(model,'model/architecture-model.json','a'*64,view['id'])
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
            source=Path(tmp)/'input.json'; source.write_text(json.dumps(data,ensure_ascii=False))
            output=Path(tmp)/'view.html'
            result=subprocess.run(['node',str(ROOT/'assets/repo-flowmap/scripts/build_flowmap.mjs'),str(source),str(ROOT/'assets/repo-flowmap/template.html'),str(output)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            browser=pw.chromium.launch(executable_path=CHROME,headless=True)
            page=browser.new_page(); page.goto(output.as_uri()); page.evaluate('document.fonts.ready')
            page.wait_for_function('document.querySelector("#map").dataset.renderStatus')
            self.assertTrue(page.evaluate('window.repoFlowmap.ready()'))
            self.assertEqual(page.locator('.c4-edge').count(),len(view['relationshipIds']))
            self.assertEqual(page.locator('[data-boundary="app-host"]').count(),1)
            svg=page.evaluate('window.repoFlowmap.exportSvg()')
            self.assertIn('실제 인스턴스 배치 아님',svg)
            self.assertIn(relation['description'],svg)
            self.assertEqual(page.locator('[data-canonical-id="order-api"]').get_attribute('data-type'),'container')
            browser.close()

    @unittest.skipUnless(os.environ.get('C4_REAL_PACKAGE'), 'set C4_REAL_PACKAGE for all five actual canonical Views')
    def test_real_all_five_views_file_chrome(self):
        source = Path(os.environ['C4_REAL_PACKAGE'])
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=CHROME, headless=True)
            from repo_flowmap_adapter import project
            import hashlib
            raw=(source/'model/architecture-model.json').read_bytes()
            model=json.loads(raw)
            for vid in ('context', 'containers', 'publish-flow', 'read-flow', 'deployment'):
                output = Path(tmp) / (vid + '.html')
                native=Path(tmp)/(vid+'.json')
                native.write_text(json.dumps(project(model,'model/architecture-model.json',hashlib.sha256(raw).hexdigest(),vid),ensure_ascii=False))
                result = subprocess.run(['node', str(ROOT / 'assets/repo-flowmap/scripts/build_flowmap.mjs'),
                    str(native),
                    str(ROOT / 'assets/repo-flowmap/template.html'), str(output)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                data = read_flow_data(output)
                for width in (1440, 390):
                    with self.subTest(view=vid, width=width):
                        page = browser.new_page(viewport={'width': width, 'height': 1000}, offline=True)
                        errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
                        page.goto(output.as_uri()); page.evaluate('document.fonts.ready')
                        page.wait_for_function('document.querySelector("#map").dataset.renderStatus')
                        g = page.evaluate(GEOMETRY)
                        self.assertTrue(page.url.startswith('file:'))
                        self.assertTrue(g['ready'], g.get('renderError'))
                        for key in ('clipped', 'textOverlaps', 'nodeOverflow', 'pathTextCollisions', 'pathNodeCollisions'):
                            self.assertEqual(g[key], [], (key, g[key]))
                        for key in (NEAR_CONNECTION_KEY, LABEL_OCCLUSION_KEY):
                            self.assertIn(key, g)
                            self.assertEqual(g[key], [], (key, g[key]))
                        self.assertGreaterEqual(g['bbox']['x'], 0)
                        self.assertGreaterEqual(g['bbox']['y'], 0)
                        self.assertLessEqual(g['documentWidth'], width + 1)
                        if data['c4']['view']['type'] == 'dynamic':
                            self.assertEqual(sequence_checks(g, data['flows'][0]['steps']), (True, True))
                        else:
                            self.assertEqual(page.locator('.c4-edge').count(),len(data['c4']['view']['relationshipIds']))
                        if vid=='deployment':
                            svg=page.evaluate('window.repoFlowmap.exportSvg()')
                            self.assertIn('실제 인스턴스 배치 아님',svg)
                            for element in data['c4']['boundaries']:
                                self.assertEqual(page.locator('[data-boundary="'+element['id']+'"]').count(),1)
                        self.assertFalse(errors)
                        page.close()
            browser.close()


@unittest.skipUnless(sync_playwright and Path(CHROME).is_file() and shutil.which('node'),
                     'actual Chrome, Playwright and Node required')
class RendererChronologyTests(unittest.TestCase):
    """A9: 진행 표시(A4) 수명 주기와 취소 직후 내보내기를 시간순으로 검증한다."""

    @classmethod
    def setUpClass(cls):
        from test_report_guided_playback import build_view_html, typed_projection
        cls.tmp = tempfile.TemporaryDirectory()
        cls.view = build_view_html(typed_projection('ordering-classes'), Path(cls.tmp.name) / 'classes.html')
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=CHROME, headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.tmp.cleanup()

    def open_view(self):
        page = self.browser.new_page(viewport={'width': 1440, 'height': 1000}, offline=True)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        timeline = Timeline()
        Timeline.install(page)
        page.goto(self.view.as_uri())
        page.evaluate('document.fonts.ready')
        page.wait_for_function('window.repoFlowmap && window.repoFlowmap.ready()')
        self.addCleanup(page.close)
        return page, timeline, errors

    @staticmethod
    def request_step(page, index):
        page.evaluate("window.postMessage({type:'repo-flowmap-step',viewId:'ordering-classes',"
                      "stepIndex:%d},'*')" % index)

    def test_step_selection_mark_lifecycle_is_chronological(self):
        page, timeline, errors = self.open_view()
        self.request_step(page, 1)
        page.wait_for_function("document.querySelectorAll('g.c4-flow-mark').length===1 && "
                               "document.querySelector('g.c4-flow-mark').getAttribute('data-step-index')==='1'")
        self.request_step(page, 3)
        page.wait_for_function("document.querySelectorAll('g.c4-flow-mark').length===1 && "
                               "document.querySelector('g.c4-flow-mark').getAttribute('data-step-index')==='3'")
        self.request_step(page, -1)
        page.wait_for_function("document.querySelectorAll('g.c4-flow-mark').length===0")
        timeline.collect(page, 'lifecycle')
        # 단계 선택 → 마커 생성 → 다른 단계 → 이전 마커 제거+새 마커 생성(제거·추가는
        # 같은 동기 태스크에서 일어나지만 MutationObserver 배치 경계에서 관측 순서는
        # 뒤집힐 수 있다 — 실측 40회 중 4회 add→remove 순서로 관측, 최종 상태 불변식
        # (마커 1개·이전 마커 소멸)은 항상 유지됐다. 따라서 지시 경계 안에서마저 두 변이의
        # 순서는 관측 계약이 아니므로, 지시별 그룹의 내용과 지시 선행 순서만 검증한다.
        # → 해제 → 마커 제거(신규 없음)의 실제 변이 내용은 그대로 기록·검증된다.
        ordered = sorted(timeline.sends() + timeline.marks(), key=lambda r: r['nt'])
        # 경계는 post 지시(postMessage 호출) 시점으로 잡는다 — 수신(msg) 기록은 observer
        # 마이크로태스크와 경합해 변이보다 늦게 push될 수 있어 경계로 안정적이지 않다.
        boundaries = [record['nt'] for record in timeline.where('post:repo-flowmap-step')]
        groups = [[], [], []]
        for record in ordered:
            if record['kind'] != 'mark-add' and record['kind'] != 'mark-remove':
                continue
            group_index = max(0, sum(1 for start in boundaries if record['nt'] >= start) - 1)
            groups[group_index].append((record['kind'], record_step_index(record)))
        self.assertEqual(groups[0], [('mark-add', '1')], timeline.render())
        self.assertEqual(sorted(groups[1]), [('mark-add', '3'), ('mark-remove', '1')], timeline.render())
        self.assertEqual(groups[2], [('mark-remove', '3')], timeline.render())
        # 각 지시는 적용 직전 그림 상태를 함께 남긴다(이전 단계 → 지시 → 반영).
        received = timeline.where('msg:repo-flowmap-step')
        self.assertEqual([record['state']['step'] for record in received], [-1, 1, 3], timeline.render())
        self.assertEqual([record_step_index(record) for record in timeline.sends()], [1, 3, -1])
        self.assertEqual(page.evaluate('window.repoFlowmap.state().step'), -1)
        self.assertEqual(errors, [], timeline.render())

    def test_playback_stop_request_clears_mark_and_is_quiet(self):
        page, timeline, errors = self.open_view()
        page.evaluate('document.getElementById("play").click()')
        page.wait_for_function('window.repoFlowmap.state().playing===true')
        page.wait_for_function("document.querySelectorAll('g.c4-flow-mark').length===1")
        self.request_step(page, -1)  # 보고서 안내(A3)의 취소 경로: 조용한 정지 + 단계 해제
        page.wait_for_function("window.repoFlowmap.state().step===-1 && "
                               "document.querySelectorAll('g.c4-flow-mark').length===0")
        timeline.collect(page, 'cancelled')
        play_click = timeline.clicks('#play')[0]
        cancel = timeline.where('msg:repo-flowmap-step')[-1]
        self.assertTrue(cancel['state']['playing'], '취소 지시 직전 상태가 재생 중이었음을 기록해야 합니다')
        removal = sorted(timeline.where('mark-remove'), key=lambda r: r['nt'])[-1]
        self.assertGreaterEqual(removal['nt'], cancel['nt'] - TOLERANCE_MS,
                                '마커 제거는 취소 지시보다 먼저 기록되면 안 됩니다\n' + timeline.render())
        first_mark = sorted(timeline.where('mark-add'), key=lambda r: r['nt'])[0]
        self.assertGreaterEqual(first_mark['nt'], play_click['nt'] - TOLERANCE_MS, timeline.render())
        state = page.evaluate('window.repoFlowmap.state()')
        self.assertFalse(state['playing'])
        self.assertIsNone(state['stopNotice'],
                          '안내 경로 정지는 조용해야 합니다(보고서 낭독과 이중 안내 방지)')
        self.assertEqual(errors, [], timeline.render())

    def test_cancel_then_immediate_export_carries_no_mark_overlay(self):
        page, timeline, errors = self.open_view()
        self.assertTrue(page.evaluate('window.__timelineWrapExport()'),
                        '내보내기 계측은 준비된 렌더러에 설치되어야 합니다')
        page.evaluate('document.getElementById("play").click()')
        page.wait_for_function("document.querySelectorAll('g.c4-flow-mark').length===1")
        page.evaluate('document.getElementById("play").click()')  # 재생 중 정지 — 단계(및 강조)는 유지, 마커도 화면엔 남는다
        page.wait_for_function('window.repoFlowmap.state().playing===false')
        first = page.evaluate('window.repoFlowmap.exportSvg()')
        page.wait_for_timeout(250)
        second = page.evaluate('window.repoFlowmap.exportSvg()')
        timeline.collect(page, 'exported')
        exports = timeline.exports()
        self.assertEqual(len(exports), 2, timeline.render())
        stop_click = timeline.clicks('#play')[-1]
        self.assertGreaterEqual(exports[0]['nt'], stop_click['nt'] - TOLERANCE_MS,
                                '내보내기는 정지 이후에 기록되어야 합니다\n' + timeline.render())
        self.assertEqual(exports[0]['state']['markCount'], 1,
                        '내보내기 순간 화면에는 진행 마커가 살아 있었음을 기록으로 남긴다')
        self.assertFalse(exports[0]['state']['playing'])
        root = ET.fromstring(first)
        marks = [e for e in root.iter() if 'c4-flow-mark' in (e.get('class') or '').split()]
        overlays = [e for e in root.iter()
                    if {'c4-flow-dash', 'c4-flow-head'} & set((e.get('class') or '').split())]
        edges = [e for e in root.iter() if e.tag.endswith('}path') and 'c4-edge' in (e.get('class') or '').split()]
        self.assertEqual(marks, [], '정지 직후 내보내기에도 진행 마커는 남지 않습니다')
        self.assertEqual(overlays, [])
        self.assertNotIn('data-step-index', first)
        self.assertEqual(len(edges), 5, '원본 관계선은 모두 보존됩니다')
        self.assertEqual(first, second, '정지 뒤 내보내기는 시점과 무관하게 같아야 합니다')
        # 단계 강조(hot)는 정적 한 장으로 읽히는 저장 계약(W3-1 결정)대로 유지된다.
        self.assertIn('c4-edge hot', first)
        self.assertEqual(errors, [], timeline.render())


if __name__ == '__main__':
    unittest.main()
