"""W2 geometry checks: A10 near-connection mimics and D8 label occlusion.

Both checks live inside check_repo_flowmap_browser.GEOMETRY and share one
geometry basis (model-grounded relation endpoints, point/rect distance, and
document order). Tests run the exact evaluate string in real Chrome:

- a crafted C4-tagged SVG that plants each violation and each documented
  exception, so thresholds and exclusions are asserted individually;
- the bundled synthetic demo package as the clean baseline (no false positives);
- post-render DOM mutations on real renderer output for violation detection.
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
from check_repo_flowmap_browser import (
    GEOMETRY,
    GEOMETRY_CHECK_KEYS,
    LABEL_OCCLUSION_KEY,
    NEAR_CONNECTION_KEY,
    geometry_clean,
    label_occlusion_clean,
    near_connection_clean,
)

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
CHROME = os.environ.get('C4_BROWSER') or shutil.which('chromium') or '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
BROWSER_AVAILABLE = sync_playwright is not None and Path(CHROME).is_file()


class GeometryHelperTests(unittest.TestCase):
    """Python-side pass criteria shared by record() and the tests below."""

    def test_clean_helpers_require_ready_and_empty_results(self):
        base = {'ready': True}
        for key in GEOMETRY_CHECK_KEYS:
            g = dict(base, **{key: [{'x': 1}]})
            self.assertFalse(geometry_clean(g), key)
        self.assertTrue(geometry_clean(dict(base, **{k: [] for k in GEOMETRY_CHECK_KEYS})))
        self.assertFalse(geometry_clean({'ready': False, **{k: [] for k in GEOMETRY_CHECK_KEYS}}))
        self.assertFalse(near_connection_clean({**base, NEAR_CONNECTION_KEY: [{'relation': 'r'}]}))
        self.assertTrue(near_connection_clean({**base, NEAR_CONNECTION_KEY: []}))
        self.assertFalse(label_occlusion_clean({**base, LABEL_OCCLUSION_KEY: [{'kind': 'soft-border'}]}))
        self.assertTrue(label_occlusion_clean({**base, LABEL_OCCLUSION_KEY: []}))

    def test_evaluate_exposes_both_w2_fields_and_thresholds(self):
        # The checks must stay inside the shared evaluate string; dropping a
        # field would silently turn every record into a KeyError-free pass.
        for token in (NEAR_CONNECTION_KEY, LABEL_OCCLUSION_KEY, 'NEAR_LINK_PX',
                      'SHARED_CORRIDOR_PX', 'BADGE_OCCUPY_PX', 'LABEL_INSIDE_FRACTION',
                      'DOCUMENT_POSITION_FOLLOWING'):
            self.assertIn(token, GEOMETRY, token)


def node(id_: str, x, y, w, h, marks=()):
    parts = ['<g class="c4-node" data-node="%s" data-canonical-id="%s">' % (id_, id_),
             '<rect class="c4-body" x="%s" y="%s" width="%s" height="%s" fill="#ffffff"/>' % (x, y, w, h)]
    parts.extend(marks)
    parts.append('</g>')
    return ''.join(parts)


def message(step, relation, line, bg, label_text):
    return ('<g class="c4-message" data-step-id="%s" data-order="1" data-self="false">'
            '<rect class="c4-label-bg" x="%s" y="%s" width="%s" height="%s"/>'
            '<text class="c4-message-label" x="%s" y="%s" font-size="12">%s</text>'
            '<path class="c4-message-line" data-relation="%s" d="%s"/></g>'
            % (step, bg[0], bg[1], bg[2], bg[3], bg[0] + 2, bg[1] + 14, label_text, relation, line))


def crafted_page() -> str:
    """One crafted C4-tagged SVG planting every violation and exception.

    Violations: r4 near c1 (line), r5 near c4b (line), m1 label near el1.
    Exceptions: r1 endpoints (distance 0 on own borders), r2/r3 shared corridor
    near c2, r5 badge-covered span near c4, m4 label near its own endpoint ed8,
    m2/m5 labels on their own endpoints gd8/hd8, the lifeline through c (never
    a check subject), and kd8 drawn before m2 (label over node is not
    occlusion). D8 kinds: gd8 fully covers m2's label (hard-text), hd8 grazes
    m5's label corner (soft-border), id8's tab overlaps m3's background (mark).
    """
    steps = [
        {'id': 's-r1', 'order': 1, 'relationshipId': 'r1', 'from': 'a', 'to': 'b'},
        {'id': 's-r2', 'order': 2, 'relationshipId': 'r2', 'from': 'e', 'to': 'f'},
        {'id': 's-r3', 'order': 3, 'relationshipId': 'r3', 'from': 'e', 'to': 'f'},
        {'id': 's-r4', 'order': 4, 'relationshipId': 'r4', 'from': 'gg', 'to': 'hh'},
        {'id': 's-r5', 'order': 5, 'relationshipId': 'r5', 'from': 'c', 'to': 'd'},
        {'id': 'm1', 'order': 6, 'relationshipId': 'm1', 'from': 'a', 'to': 'b'},
        {'id': 'm2', 'order': 7, 'relationshipId': 'm2', 'from': 'kd8', 'to': 'gd8'},
        {'id': 'm3', 'order': 8, 'relationshipId': 'm3', 'from': 'kd8', 'to': 'id8'},
        {'id': 'm4', 'order': 9, 'relationshipId': 'm4', 'from': 'kd8', 'to': 'ed8'},
        {'id': 'm5', 'order': 10, 'relationshipId': 'm5', 'from': 'kd8', 'to': 'hd8'},
    ]
    flow = json.dumps({'c4': {'viewId': 'craft-geometry'}, 'flows': [{'id': 'craft', 'steps': steps}]},
                      ensure_ascii=False)
    svg = [
        # Document order inside #vp matters for D8: kd8 precedes m2 (label wins),
        # every other node is drawn after the messages (node wins).
        '<line class="c4-lifeline" data-participant="customer" x1="55" y1="60" x2="55" y2="430"/>',
        message('m1', 'm1', 'M120,75 H320', (600, 100, 60, 20), '관계1'),
        node('kd8', 140, 600, 120, 30),
        message('m2', 'm2', 'M60,610 H140', (150, 600, 120, 24), '메시지2'),
        message('m3', 'm3', 'M60,700 H360', (365, 692, 100, 20), '메시지3'),
        message('m4', 'm4', 'M520,700 H640', (520, 692, 80, 20), '메시지4'),
        message('m5', 'm5', 'M60,755 H100', (105, 745, 60, 20), '메시지5'),
        node('a', 20, 20, 100, 40),
        node('b', 320, 20, 100, 40),
        node('e', 20, 100, 100, 60),
        node('f', 400, 100, 100, 60),
        node('el1', 662, 110, 40, 40),
        node('c1', 200, 240, 100, 60),
        node('c2', 200, 330, 100, 50),
        node('gg', 20, 220, 100, 40),
        node('hh', 400, 220, 100, 40),
        node('c', 20, 380, 100, 40),
        node('d', 400, 380, 100, 40),
        node('c4', 245, 400, 10, 60),
        node('c4b', 350, 400, 10, 60),
        node('gd8', 140, 590, 200, 80),
        node('hd8', 30, 740, 80, 40),
        node('id8', 398, 720, 100, 60, marks=['<rect class="c4-tab" x="380" y="710" width="85" height="10"/>']),
        node('ed8', 602, 690, 100, 50),
        '<path class="c4-edge" data-relation="r1" d="M120,40 H320"/>',
        '<path class="c4-edge" data-relation="r2" d="M120,130 H160 V328.5 H460 V160"/>',
        '<path class="c4-edge" data-relation="r3" d="M120,140 H160 V329.5 H460 V160"/>',
        '<path class="c4-edge" data-relation="r4" d="M120,238.5 H400"/>',
        '<path class="c4-edge" data-relation="r5" d="M120,398.5 H400"/>',
        # r9-unknown is absent from flow-data: the geometric endpoint snap is
        # the only endpoint source, so touching a/b borders must not flag it.
        '<path class="c4-edge" data-relation="r9-unknown" d="M120,30 H320"/>',
        '<g class="badge"><circle cx="250" cy="398.5" r="12"/><text x="250" y="402">5</text></g>',
    ]
    return ('<!doctype html><meta charset="utf-8"><body>'
            '<svg id="map" xmlns="http://www.w3.org/2000/svg" width="720" height="800" '
            'data-content-width="720" data-content-height="800" data-view-kind="sequence" '
            'data-view-id="craft-geometry"><g id="vp">' + ''.join(svg) + '</g></svg>'
            '<script id="flow-data" type="application/json">' + flow + '</script>'
            '<script>window.repoFlowmap={ready:function(){return true;},'
            'exportSvg:function(){return new XMLSerializer().serializeToString(document.getElementById("map"));}};</script>'
            '</body>')


@unittest.skipUnless(BROWSER_AVAILABLE, 'actual Chrome and Playwright required')
class CraftedGeometryCheckTests(unittest.TestCase):
    """Assert each planted violation is reported and each exception is not."""

    def test_crafted_svg_reports_exactly_the_planted_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'craft.html'
            path.write_text(crafted_page(), encoding='utf-8')
            with sync_playwright() as pw:
                browser = pw.chromium.launch(executable_path=CHROME, headless=True)
                page = browser.new_page()
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(path.as_uri())
                g = page.evaluate(GEOMETRY)
                browser.close()
            self.assertFalse(errors, errors)
            self.assertTrue(g['ready'])

            lines = {(m['relation'], m['node']) for m in g[NEAR_CONNECTION_KEY] if m['kind'] == 'line'}
            self.assertEqual(lines, {('r4', 'c1'), ('r5', 'c4b')}, g[NEAR_CONNECTION_KEY])
            for m in g[NEAR_CONNECTION_KEY]:
                self.assertLessEqual(m['distance'], 2.5, m)
            # r1 touches its own endpoints at distance 0, r2/r3 share a corridor
            # near c2, r5's span near c4 is badge-covered, and the lifeline
            # through c never becomes a subject (no '' relation entries).
            labels = {(m['step'], m['node']) for m in g[NEAR_CONNECTION_KEY] if m['kind'] == 'label'}
            self.assertEqual(labels, {('m1', 'el1')}, g[NEAR_CONNECTION_KEY])
            # The unknown relation still resolves its endpoints geometrically.
            self.assertNotIn('r9-unknown', {m['relation'] for m in g[NEAR_CONNECTION_KEY]})

            occlusions = g[LABEL_OCCLUSION_KEY]
            hard = {(o['node'], o['where']) for o in occlusions if o['kind'] == 'hard-text'}
            self.assertEqual(hard, {('gd8', 'screen'), ('gd8', 'export')}, occlusions)
            soft = {(o['node'], o['where']) for o in occlusions if o['kind'] == 'soft-border'}
            self.assertEqual(soft, {('gd8', 'screen'), ('gd8', 'export'),
                                    ('hd8', 'screen'), ('hd8', 'export')}, occlusions)
            marks = {(o['node'], o['kind']) for o in occlusions if o['kind'] == 'mark'}
            self.assertEqual(marks, {('id8', 'mark')}, occlusions)
            # kd8 is drawn before m2 (the label covers the node, not the
            # reverse) and ed8 never overlaps m4's label.
            touched = {o['node'] for o in occlusions}
            self.assertNotIn('kd8', touched)
            self.assertNotIn('ed8', touched)


class DemoPackage:
    """Build the synthetic demo package once for the browser tests below."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        # Demo authoring refuses to overwrite; generate into the empty root.
        script = ROOT / 'scripts/generate_repo_flowmap_demo.py'
        result = subprocess.run([sys.executable, '-B', str(script), '--output', str(cls.root)],
                                capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.diagrams = sorted((cls.root / 'diagrams').glob('*.flowmap.html'))


@unittest.skipUnless(BROWSER_AVAILABLE and shutil.which('node'),
                     'actual Chrome, Playwright and Node required')
class DemoCleanBaselineTests(DemoPackage, unittest.TestCase):
    """Real renderer output must produce zero false positives on both checks."""

    def test_all_demo_views_report_no_mimics_and_no_occlusions(self):
        self.assertGreaterEqual(len(self.diagrams), 6)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=CHROME, headless=True)
            for fixture in self.diagrams:
                for width in (1440, 360):
                    with self.subTest(view=fixture.stem, width=width):
                        page = browser.new_page(viewport={'width': width, 'height': 1000}, offline=True)
                        errors = []
                        page.on('pageerror', lambda e: errors.append(str(e)))
                        try:
                            page.goto(fixture.as_uri())
                            page.evaluate('document.fonts.ready')
                            page.wait_for_function(
                                'window.repoFlowmap && document.querySelector("#map").dataset.renderStatus',
                                timeout=10000)
                            g = page.evaluate(GEOMETRY)
                            self.assertTrue(g['ready'], g.get('renderError'))
                            self.assertEqual(g[NEAR_CONNECTION_KEY], [], g[NEAR_CONNECTION_KEY])
                            self.assertEqual(g[LABEL_OCCLUSION_KEY], [], g[LABEL_OCCLUSION_KEY])
                            self.assertFalse(errors, errors)
                        finally:
                            page.close()
            browser.close()


@unittest.skipUnless(BROWSER_AVAILABLE and shutil.which('node'),
                     'actual Chrome, Playwright and Node required')
class MutationDetectionTests(DemoPackage, unittest.TestCase):
    """Fault injection on real renderer output must be detected with reasons."""

    def test_component_node_pushed_against_a_relation_is_reported(self):
        # ordering-context has exactly two nodes (every node is an endpoint),
        # so the mutation needs a view with a genuinely unrelated node.
        fixture = self.root / 'diagrams/ordering-components.flowmap.html'
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=CHROME, headless=True)
            page = browser.new_page()
            page.goto(fixture.as_uri())
            page.wait_for_function('window.repoFlowmap && document.querySelector("#map").dataset.renderStatus',
                                   timeout=10000)
            planted = page.evaluate('''() => {
              const data = JSON.parse(document.getElementById('flow-data').textContent);
              const pairs = {};
              data.flows.forEach(f => f.steps.forEach(s => pairs[s.relationshipId] = [s.from, s.to]));
              const badges = [...document.querySelectorAll('#vp g.badge')].map(b => {
                const bb = b.getBBox(); return {x: bb.x + bb.width / 2, y: bb.y + bb.height / 2};
              });
              const nodes = [...document.querySelectorAll('#vp .c4-node')];
              for (const p of document.querySelectorAll('#vp path.c4-edge')) {
                const ends = new Set(pairs[p.dataset.relation] || []);
                const len = p.getTotalLength();
                for (let s = len * 0.2; s <= len * 0.8; s += len * 0.05) {
                  const q = p.getPointAtLength(s);
                  if (badges.some(b => Math.hypot(b.x - q.x, b.y - q.y) < 16)) continue;
                  for (const n of nodes) {
                    if (ends.has(n.dataset.canonicalId)) continue;
                    const body = n.querySelector('.c4-body');
                    const w = +body.getAttribute('width'), h = +body.getAttribute('height');
                    body.setAttribute('x', String(q.x - w - 1.5));
                    body.setAttribute('y', String(q.y - h / 2));
                    return {relation: p.dataset.relation, node: n.dataset.canonicalId};
                  }
                }
              }
              return null;
            }''')
            self.assertIsNotNone(planted)
            g = page.evaluate(GEOMETRY)
            browser.close()
        hit = [m for m in g[NEAR_CONNECTION_KEY]
               if m['kind'] == 'line' and m['relation'] == planted['relation'] and m['node'] == planted['node']]
        self.assertTrue(hit, g[NEAR_CONNECTION_KEY])
        self.assertLessEqual(hit[0]['distance'], 2.5, hit)

    def test_sequence_node_moved_over_a_label_reports_hard_occlusion(self):
        fixture = self.root / 'diagrams/ordering-sequence.flowmap.html'
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=CHROME, headless=True)
            page = browser.new_page()
            page.goto(fixture.as_uri())
            page.wait_for_function('window.repoFlowmap && document.querySelector("#map").dataset.renderStatus',
                                   timeout=10000)
            planted = page.evaluate('''() => {
              const msg = document.querySelector('#vp g.c4-message');
              const boxes = [...msg.querySelectorAll('text.c4-message-label')].map(e => e.getBBox());
              if (!boxes.length) return null;
              const u = {
                x: Math.min(...boxes.map(b => b.x)), y: Math.min(...boxes.map(b => b.y)),
                right: Math.max(...boxes.map(b => b.x + b.width)),
                bottom: Math.max(...boxes.map(b => b.y + b.height)),
              };
              const nodes = [...document.querySelectorAll('#vp .c4-node')];
              const n = nodes[nodes.length - 1];
              const body = n.querySelector('.c4-body');
              body.setAttribute('x', String(u.x - 2));
              body.setAttribute('y', String(u.y - 2));
              body.setAttribute('width', String(u.right - u.x + 4));
              body.setAttribute('height', String(u.bottom - u.y + 4));
              return {node: n.dataset.canonicalId, step: msg.dataset.stepId};
            }''')
            self.assertIsNotNone(planted)
            g = page.evaluate(GEOMETRY)
            browser.close()
        hard = [o for o in g[LABEL_OCCLUSION_KEY]
                if o['kind'] == 'hard-text' and o['node'] == planted['node']]
        self.assertTrue(hard, g[LABEL_OCCLUSION_KEY])
        self.assertEqual({o['where'] for o in hard}, {'screen', 'export'}, hard)


if __name__ == '__main__':
    unittest.main()
