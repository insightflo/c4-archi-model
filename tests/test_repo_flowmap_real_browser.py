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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_repo_flowmap_browser import GEOMETRY, read_flow_data, sequence_checks

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


if __name__ == '__main__':
    unittest.main()
