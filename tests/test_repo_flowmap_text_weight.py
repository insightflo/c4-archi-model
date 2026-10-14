"""D3 글자 굵기 일치(측정=표시)와 D1 export 안전 여백 회귀.

측정(c4Lines 캔버스 font)과 표시(c4Text 인라인 font-weight, .c4-view CSS)가
C4_TEXT_WEIGHT 하나에서 굵기를 얻는지를 소스 정적 검사와 실제 Chrome 렌더링
양쪽에서 검증한다. c4-kind/c4-target/c4-uncertain 과거 불일치(표시 700/측정 400,
측정 700/표시 400)의 재발을 막는다.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
TEMPLATE = ROOT / 'assets/repo-flowmap/template.html'
CHROME = os.environ.get('C4_BROWSER') or shutil.which('chromium') or '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

# 맵에 없는 클래스는 측정·표시 모두 기본 400이어야 한다(아래 정적 검사가 확인).
UNMAPPED_CLASSES = {'c4-id', 'c4-tech', 'c4-desc', 'c4-member', 'c4-message-label'}


def weight_map(source: str) -> dict[str, int]:
    m = re.search(r"var C4_TEXT_WEIGHT=\{([^}]*)\}", source)
    assert m, 'C4_TEXT_WEIGHT map missing in template'
    return {k: int(v) for k, v in re.findall(r"'(c4-[a-z-]+)'\s*:\s*(\d+)", m.group(1))}


def css_text_weights(source: str) -> dict[str, int]:
    """`.c4-view text.<cls>{...}` 규칙에서 font-weight 값을 모은다(없으면 수집 안 함)."""
    out = {}
    for cls, body in re.findall(r"\.c4-view text\.(c4-[a-z-]+)\{([^}]*)\}", source):
        w = re.search(r"font-weight:\s*(\d+)", body)
        if w:
            out[cls] = int(w.group(1))
    return out


def split_args(inner: str) -> list[str]:
    """문자열·괄호 깊이를 존중해 최상위 콤마로 인자를 나눈다."""
    args, depth, cur, quote = [], 0, [], None
    i = 0
    while i < len(inner):
        c = inner[i]
        if quote:
            if c == '\\':
                cur.append(inner[i:i + 2]); i += 2; continue
            if c == quote:
                quote = None
            cur.append(c)
        elif c in ('"', "'"):
            quote = c; cur.append(c)
        elif c in '([{':
            depth += 1; cur.append(c)
        elif c in ')]}':
            depth -= 1; cur.append(c)
        elif c == ',' and depth == 0:
            args.append(''.join(cur)); cur = []
        else:
            cur.append(c)
        i += 1
    args.append(''.join(cur))
    return [a.strip() for a in args]


def call_sites(source: str, name: str) -> list[list[str]]:
    """정의부를 제외한 모든 name(...) 호출의 인자 목록(소스 순)."""
    sites, idx = [], 0
    while True:
        i = source.find(name + '(', idx)
        if i < 0:
            return sites
        if source[max(0, i - 9):i] == 'function ':
            idx = i + len(name) + 1
            continue
        depth, j = 0, i + len(name)
        while j < len(source):
            if source[j] == '(':
                depth += 1
            elif source[j] == ')':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        sites.append(split_args(source[i + len(name) + 1:j]))
        idx = j


class TextWeightSourceTests(unittest.TestCase):
    """측정·표시 굵기의 단일 원천(C4_TEXT_WEIGHT) 정적 일치 검사."""

    @classmethod
    def setUpClass(cls):
        cls.source = TEMPLATE.read_text()
        cls.map = weight_map(cls.source)

    def test_weight_map_matches_css(self):
        css = css_text_weights(self.source)
        base = re.search(r"\.c4-view text\.c4-text\{[^}]*font-weight:\s*(\d+)", self.source)
        self.assertTrue(base and int(base.group(1)) == 400, 'base .c4-text weight must stay 400')
        for cls, weight in self.map.items():
            self.assertEqual(css.get(cls), weight, f'.c4-view text.{cls} CSS weight drifted from C4_TEXT_WEIGHT')
        for cls, weight in css.items():
            if cls != 'c4-text' and cls not in self.map:
                self.assertEqual(weight, 400, f'{cls} has CSS weight {weight} but is not in C4_TEXT_WEIGHT')

    def test_measurement_and_display_share_one_source(self):
        self.assertIn("c4MeasureContext.font=c4Weight(cls)+' '+size+'px system-ui'", self.source)
        self.assertIn("style=\"font-size:'+size+'px;font-weight:'+weight+'\"", self.source)
        self.assertIn('var weight=c4Weight(cls);', self.source)
        # 측정 전용 굵기 분기(과거 불일치의 원인)가 다시 생기지 않게 한다.
        self.assertNotIn("(bold?'700 ':'400 ')", self.source)

    def test_all_call_sites_use_class_signature(self):
        # 측정·표시 헬퍼 정의 자체(내부 호출은 변수 인자)를 제외하고 호출처만 검사한다.
        source = self.source
        scan = source[:source.index('function c4Lines(')] + source[source.index('function c4LeafMetric('):]
        for args in call_sites(scan, 'c4Block') + call_sites(scan, 'c4Lines'):
            self.assertEqual(len(args), 4, 'c4Block/c4Lines must be (text, width, size, cls): ' + str(args))
            m = re.fullmatch(r"'(c4-[a-z-]*)'|''", args[3])
            self.assertTrue(m, 'cls argument must be a literal: ' + str(args))
            cls = m.group(1) or ''
            self.assertIn(cls, set(self.map) | UNMAPPED_CLASSES | {''}, f'unknown text class {cls!r}')
        for args in call_sites(scan, 'c4Text'):
            self.assertEqual(len(args), 5, 'c4Text must be (lines, x, y, size, cls): ' + str(args))

    def test_c4lines_wraps_without_truncation(self):
        body = self.source.split('function c4Lines(', 1)[1].split('\n  function ', 1)[0]
        for banned in ('.slice(', '.substring(', '.substr(', '.truncate'):
            self.assertNotIn(banned, body, f'c4Lines must wrap, never truncate ({banned})')
        self.assertIn("lines.push(line || ' ')", body)


@unittest.skipUnless(sync_playwright and Path(CHROME).is_file(), 'actual Chrome and Playwright required')
class ChromeTextWeightAndMarginTests(unittest.TestCase):
    def test_deployment_view_weight_match_and_export_margin(self):
        from generate_repo_flowmap_demo import make_model
        from repo_flowmap_adapter import project
        model = make_model()
        # 인스턴스 리프 하나를 미확정으로 바꿔 c4-uncertain 텍스트 행을 만든다.
        api = next(e for e in model['elements'] if e['id'] == 'api-instance')
        api['derivation'] = 'unresolved'
        api['confidence'] = 'UNVERIFIED'
        data = project(model, 'model/architecture-model.json', 'a' * 64, 'ordering-deployment')
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
            source = Path(tmp) / 'input.json'; source.write_text(json.dumps(data, ensure_ascii=False))
            output = Path(tmp) / 'view.html'
            result = subprocess.run(['node', str(ROOT / 'assets/repo-flowmap/scripts/build_flowmap.mjs'),
                str(source), str(ROOT / 'assets/repo-flowmap/template.html'), str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            browser = pw.chromium.launch(executable_path=CHROME, headless=True)
            page = browser.new_page(offline=True)
            errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(output.as_uri()); page.evaluate('document.fonts.ready')
            page.wait_for_function('document.querySelector("#map").dataset.renderStatus')
            self.assertTrue(page.evaluate('window.repoFlowmap.ready()'))
            script = '''() => {
              const map = %s;
              const canvas = document.createElement('canvas').getContext('2d');
              const out = [];
              document.querySelectorAll('#vp text.c4-text').forEach(t => {
                const cls = [...t.classList].find(c => c.startsWith('c4-') && c !== 'c4-text') || '';
                const size = parseFloat(t.style.fontSize) || parseFloat(getComputedStyle(t).fontSize);
                const text = t.textContent;
                const at = w => { canvas.font = w + ' ' + size + 'px system-ui'; return canvas.measureText(text).width; };
                const want = map[cls] || 400;
                out.push({cls, shown: getComputedStyle(t).fontWeight, want,
                          len: t.getComputedTextLength(), same: at(String(want)), size, text});
              });
              // 랩 판정 전제 확인: 캔버스 측정이 굵기를 반영하는지. 라틴·숫자로 검사한다
              // (macOS 한국어 폴백 폰트는 한글 전진 폭이 굵기와 무관하다).
              const probe = 'Order Processing System 123';
              const sizes = [...new Set(out.map(r => r.size).concat([11, 22]))];
              const probeDiff = sizes.map(size => {
                canvas.font = '400 ' + size + 'px system-ui'; const a = canvas.measureText(probe).width;
                canvas.font = '700 ' + size + 'px system-ui'; const b = canvas.measureText(probe).width;
                return {size, diff: b - a};
              });
              return {rows: out, probeDiff};
            }''' % json.dumps(weight_map(TEMPLATE.read_text()))
            result = page.evaluate(script)
            rows, probe_diff = result['rows'], result['probeDiff']
            for probe in probe_diff:
                self.assertGreater(probe['diff'], 2, f"system-ui does not discriminate weight at {probe['size']}px")
            seen = set()
            for row in rows:
                seen.add(row['cls'])
                with self.subTest(cls=row['cls'], text=row['text'][:40]):
                    # 표시 굵기 == 측정에 쓰인 굵기(맵).
                    self.assertEqual(int(row['shown']), row['want'])
                    # 같은 굵기·같은 글꼴의 캔버스 측정과 렌더 길이가 일치(측정=표시의 실행 증거).
                    # SVG·캔버스 셰이핑 차이를 감안해 3%+3px 허용오차를 둔다.
                    self.assertLessEqual(abs(row['len'] - row['same']), max(3, 0.03 * row['same']),
                                         f"rendered {row['len']:.1f} vs measured {row['same']:.1f}")
            # 이번 수정의 대상 클래스가 실제로 그려졌는지 확인.
            self.assertTrue({'c4-kind', 'c4-target', 'c4-uncertain', 'c4-title', 'c4-id'} <= seen, sorted(seen))
            # D1: 내보낸 SVG의 viewBox가 콘텐츠 전체를 안전 여백과 함께 담는다.
            svg = page.evaluate('window.repoFlowmap.exportSvg()')
            margin = page.evaluate('''() => { const b = document.querySelector('#map #vp').getBBox();
                return {x: b.x, y: b.y, right: b.x + b.width, bottom: b.y + b.height,
                        w: +document.querySelector('#map').dataset.contentWidth,
                        h: +document.querySelector('#map').dataset.contentHeight}; }''')
            vw, vh = (float(v) for v in re.search(r'viewBox="([^"]+)"', svg).group(1).split()[2:])
            self.assertGreaterEqual(vw, margin['right'] + 24, 'right safe margin')
            self.assertGreaterEqual(vh, margin['bottom'] + 24, 'bottom safe margin')
            self.assertGreaterEqual(margin['x'], 12, 'left safe margin')
            self.assertGreaterEqual(margin['y'], 12, 'top safe margin')
            self.assertFalse(errors)
            browser.close()


if __name__ == '__main__':
    unittest.main()
