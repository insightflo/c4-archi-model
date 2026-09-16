"""Real hidden iframe -> reveal -> native SVG download extent regressions.

C4_REAL_PACKAGE supplies read-only canonical input. Fresh HTML and downloads go
only to temporary files (C4_HIDDEN_EVIDENCE optionally retains the evidence).
"""
from pathlib import Path
import html
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parents[1]
CHROME = os.environ.get('C4_BROWSER') or shutil.which('chromium') or '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
STATE = """() => {
  const map=document.querySelector('#map'), vp=document.querySelector('#vp'), b=vp.getBBox();
  return {ready:repoFlowmap.ready(),width:+map.dataset.contentWidth,height:+map.dataset.contentHeight,
    bbox:{x:b.x,y:b.y,width:b.width,height:b.height},
    paths:[...vp.querySelectorAll('path.c4-edge')].map(p=>[p.dataset.relation,p.getAttribute('d')]),
    nodes:[...vp.querySelectorAll('[data-canonical-id]')].map(n=>[n.dataset.canonicalId,n.dataset.type,n.getAttribute('transform'),n.innerHTML]),
    rows:[...vp.querySelectorAll('.c4-relation-row')].map(n=>n.dataset.relation)};
}"""


@unittest.skipUnless(sync_playwright and Path(CHROME).is_file() and os.environ.get('C4_REAL_PACKAGE'),
                     'actual Chrome, Playwright and C4_REAL_PACKAGE required')
class HiddenNativeExtentTests(unittest.TestCase):
    def test_hidden_reveal_remeasures_extent_without_rerouting(self):
        self.check_hidden_download(observer=True)

    def test_export_remeasures_when_optional_resize_observer_is_unavailable(self):
        self.check_hidden_download(observer=False)

    def check_hidden_download(self, observer):
        source = Path(os.environ['C4_REAL_PACKAGE']) / 'diagrams/deployment.flowmap.json'
        data = json.loads(source.read_text())
        expected = data['c4']['view']['relationshipIds']
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
            work = Path(tmp)
            if os.environ.get('C4_HIDDEN_EVIDENCE'):
                work = Path(os.environ['C4_HIDDEN_EVIDENCE']) / ('observer' if observer else 'export')
                work.mkdir(parents=True, exist_ok=True)
            native = work / 'deployment.html'
            build = subprocess.run(['node', str(ROOT / 'assets/repo-flowmap/scripts/build_flowmap.mjs'),
                                    str(source), str(ROOT / 'assets/repo-flowmap/template.html'), str(native)],
                                   capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            # Deliberately independent of the report template: the native renderer
            # must survive a normal sandboxed tab lifecycle in any host document.
            host = work / 'host.html'
            native_html = native.read_text()
            if not observer:
                # Disable the optional capability before native scripts execute.
                native_html = native_html.replace('<head>', '<head><script>window.ResizeObserver=undefined;</script>', 1)
            host.write_text('<!doctype html><meta charset="utf-8"><style>body{margin:0}iframe{width:100%;height:850px;border:0}</style>'
                            '<button onclick="panel.hidden=!panel.hidden">Toggle tab</button>'
                            '<section id="panel" hidden><iframe sandbox="allow-scripts allow-downloads" srcdoc="'
                            + html.escape(native_html, quote=True) + '"></iframe></section>')
            browser = pw.chromium.launch(executable_path=CHROME, headless=True)
            try:
                for width in (1440, 360):
                    with self.subTest(width=width, observer=observer):
                        page = browser.new_page(viewport={'width': width, 'height': 1000}, offline=True)
                        errors = []
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
                        page.goto(host.as_uri())
                        frame = page.locator('iframe').element_handle().content_frame()
                        frame.wait_for_function('window.repoFlowmap && repoFlowmap.ready()')
                        frame.evaluate('document.fonts.ready')
                        if not observer:
                            self.assertEqual(frame.evaluate('typeof ResizeObserver'), 'undefined')
                        hidden = frame.evaluate(STATE)
                        self.assertEqual(hidden['bbox']['width'], 0, 'must genuinely initialize without layout')
                        self.assertGreater(hidden['width'], 0, 'zero bbox must not erase base dimensions')
                        self.assertEqual(len(hidden['paths']), len(expected))
                        page.get_by_role('button', name='Toggle tab').click()
                        frame.locator('#download-svg').wait_for(state='visible')
                        # Let actual observer/layout events run; never click Theme or
                        # rerender, which would conceal the stale extent defect.
                        frame.evaluate('() => new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                        visible = frame.evaluate(STATE)
                        self.assertGreater(visible['bbox']['width'], 0)
                        for key in ('paths', 'nodes', 'rows'):
                            self.assertEqual(visible[key], hidden[key], key + ' changed on reveal')
                        target = work / f'deployment-{width}.svg'
                        with page.expect_download() as download:
                            frame.locator('#download-svg').click()
                        download.value.save_as(target)
                        root = ET.parse(target).getroot()
                        self.assertEqual(root.tag, '{http://www.w3.org/2000/svg}svg')
                        paths = [[e.attrib['data-relation'], e.attrib['d']] for e in root.iter()
                                 if 'c4-edge' in e.attrib.get('class', '').split()]
                        self.assertEqual(paths, hidden['paths'], 'export must not reroute or drop relationships')
                        self.assertEqual(sorted(r for r, _ in paths), sorted(expected))
                        rows = [e.attrib['data-relation'] for e in root.iter()
                                if 'c4-relation-row' in e.attrib.get('class', '').split()]
                        self.assertEqual(sorted(rows), sorted(expected))
                        exported = browser.new_page(offline=True)
                        exported.goto(target.as_uri())
                        exported.evaluate('document.fonts.ready')
                        bounds = exported.evaluate('''() => {
                          const svg=document.documentElement,v=svg.viewBox.baseVal,b=svg.querySelector('#vp').getBBox();
                          return {x:b.x,y:b.y,right:b.x+b.width,bottom:b.y+b.height,width:v.width,height:v.height};
                        }''')
                        exported.close()
                        after = frame.evaluate(STATE)
                        page.get_by_role('button', name='Toggle tab').click()
                        page.get_by_role('button', name='Toggle tab').click()
                        frame.evaluate('() => new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                        repeated = frame.evaluate(STATE)
                        evidence = {'hidden': hidden, 'visible': visible, 'afterExport': after,
                                    'repeated': repeated, 'exportBounds': bounds, 'errors': errors}
                        (work / f'states-{width}.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
                        page.close()
                        self.assertGreaterEqual(bounds['x'], 0)
                        self.assertGreaterEqual(bounds['y'], 0)
                        self.assertLessEqual(bounds['right'], bounds['width'], bounds)
                        self.assertLessEqual(bounds['bottom'], bounds['height'], bounds)
                        if observer:
                            self.assertLessEqual(visible['bbox']['x'] + visible['bbox']['width'], visible['width'], visible)
                        self.assertEqual((after['width'], after['height']), (repeated['width'], repeated['height']),
                                         'repeat reveal must not grow extents indefinitely')
                        self.assertEqual(repeated['paths'], hidden['paths'])
                        self.assertFalse(errors, errors)
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main()
