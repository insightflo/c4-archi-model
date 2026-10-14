"""D4 밝기 대비 검사기(verify_visual_contrast) 회귀.

(a) WCAG 상대 휘도·대비 공식의 기지 값, (b) rgba/fill-opacity 합성,
(c) CSS 변수 해석(재귀 var(), 어두움 오버라이드, 대체값, 순환)을 단위 검증하고
(d) 실제 두 템플릿에 대해 검사기를 실행해 미달(FAIL) 없음을 확인한다.
한계 기록(LIMIT)은 visual-budgets.md의 한계 목록과 대응되므로 경고로만 남는다.
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from verify_visual_contrast import (  # noqa: E402
    RENDERER,
    REPORT,
    ColorError,
    Role,
    composite,
    contrast,
    evaluate_role,
    opaque,
    parse_color,
    parse_css_variables,
    relative_luminance,
    resolve_var,
)
from c4_validation import ValidationReport  # noqa: E402

CHECKER = ROOT / 'scripts' / 'verify_visual_contrast.py'


class ContrastFormulaTests(unittest.TestCase):
    """WCAG 2.x 상대 휘도·대비 공식의 기지 값."""

    def test_black_white(self):
        self.assertAlmostEqual(contrast((0, 0, 0), (255, 255, 255)), 21.0, places=6)

    def test_known_gray_on_white(self):
        # WCAG 사례값: #767676 은 흰색 위 4.54:1 (4.5 통과 직전 값)
        gray = parse_color('#767676')[0]
        self.assertAlmostEqual(contrast(gray, (255, 255, 255)), 4.54, places=2)

    def test_symmetry_and_identity(self):
        self.assertAlmostEqual(contrast((222, 12, 44), (240, 240, 230)),
                               contrast((240, 240, 230), (222, 12, 44)), places=9)
        self.assertAlmostEqual(contrast((90, 130, 110), (90, 130, 110)), 1.0, places=9)

    def test_luminance_bounds(self):
        self.assertAlmostEqual(relative_luminance((255, 255, 255)), 1.0, places=9)
        self.assertAlmostEqual(relative_luminance((0, 0, 0)), 0.0, places=9)


class CompositeTests(unittest.TestCase):
    """반투명 색은 배경과 합성한 뒤 계산한다."""

    def test_half_red_on_white(self):
        merged = composite((255, 0, 0), 0.5, (255, 255, 255))
        self.assertEqual(merged, (255, 127.5, 127.5))

    def test_alpha_extremes(self):
        bg = (10, 20, 30)
        self.assertEqual(composite((200, 200, 200), 0.0, bg), bg)
        self.assertEqual(composite((200, 200, 200), 1.0, bg), (200, 200, 200))

    def test_over_spec_multiplies_fill_opacity(self):
        scope = {'--fill': 'rgba(0,0,0,.5)', '--bg': '#ffffff'}
        rgb, alpha = opaque(('over', ('var', '--fill'), ('var', '--bg'), 0.5), scope)
        self.assertEqual(alpha, 1.0)
        # rgba 알파 .5 × fill-opacity .5 = .25 → 흰색 배경 위 (191.25, 191.25, 191.25)
        self.assertEqual(rgb, (255 * 0.75 + 0, 255 * 0.75 + 0, 255 * 0.75 + 0))

    def test_transparent_color_keeps_alpha_until_over(self):
        scope = {'--t': 'rgba(0,0,0,.5)'}
        rgb, alpha = opaque(('var', '--t'), scope)
        self.assertEqual(alpha, 0.5)  # over 사양 없이는 합성하지 않고 알파를 돌려준다(검사 단계에서 거부)


class VariableResolutionTests(unittest.TestCase):
    """CSS 변수 파싱·재귀 해석·어두움 오버라이드."""

    CSS = """
    :root{--ink:#111111;--paper:#ffffff;--text:var(--ink);--chain:var(--text)}
    @media (prefers-color-scheme: dark){
      :root:not([data-theme="light"]){--ink:#eeeeee}
    }
    :root[data-theme="dark"]{--ink:#eeeeee}
    """

    def test_themes_and_recursion(self):
        scopes = parse_css_variables(self.CSS)
        self.assertEqual(set(scopes), {'light', 'dark'})
        self.assertEqual(resolve_var('--chain', scopes['light']), '#111111')
        self.assertEqual(resolve_var('--chain', scopes['dark']), '#eeeeee')

    def test_fallback_and_errors(self):
        scope = {'--a': 'var(--missing, #abc)', '--b': 'var(--missing)'}
        self.assertEqual(resolve_var('--a', scope), '#abc')
        with self.assertRaises(ColorError):
            resolve_var('--b', scope)
        with self.assertRaises(ColorError):
            resolve_var('--undefined', scope)
        cycle = {'--a': 'var(--b)', '--b': 'var(--a)'}
        with self.assertRaises(ColorError):
            resolve_var('--a', cycle)

    def test_dark_block_drift_is_rejected(self):
        drifted = self.CSS.replace(':root[data-theme="dark"]{--ink:#eeeeee}',
                                   ':root[data-theme="dark"]{--ink:#dddddd}')
        with self.assertRaises(ColorError):
            parse_css_variables(drifted)

    def test_real_templates_resolve(self):
        for path, expect_dark in ((ROOT / RENDERER, True), (ROOT / REPORT, False)):
            scopes = parse_css_variables(path.read_text())
            self.assertIn('light', scopes)
            self.assertEqual('dark' in scopes, expect_dark)
            for theme in scopes:
                resolve_var('--color-uncertain' if 'repo-flowmap' in str(path) else '--accent', scopes[theme])


class GateLogicTests(unittest.TestCase):
    """미달 판정·한계 기록 분기."""

    def _run_role(self, role: Role, scope: dict) -> ValidationReport:
        report = ValidationReport('test')
        evaluate_role(role, {'light': scope}, 'test.html', report)
        return report

    def test_below_bar_without_note_fails(self):
        scope = {'--fg': '#999999', '--bg': '#ffffff'}
        report = self._run_role(Role('T-1', '테스트', ('var', '--fg'), ('var', '--bg'), 'text', ('light',)), scope)
        self.assertEqual(report.result, 'FAIL')
        self.assertTrue(any(f.code == 'CNT-LOW' for f in report.errors))

    def test_below_bar_with_note_is_limit_not_fail(self):
        scope = {'--fg': '#999999', '--bg': '#ffffff'}
        role = Role('T-2', '테스트', ('var', '--fg'), ('var', '--bg'), 'nontext', ('light',), note='이중 표시 근거')
        report = self._run_role(role, scope)
        self.assertEqual(len(report.errors), 0)
        self.assertTrue(any(f.code == 'CNT-LIMIT' for f in report.warnings))
        self.assertEqual(report.checks[0].result, 'LIMIT')

    def test_decorative_has_no_minimum(self):
        scope = {'--fg': '#f0f0f0', '--bg': '#ffffff'}
        role = Role('T-3', '장식', ('var', '--fg'), ('var', '--bg'), 'decorative', ('light',))
        report = self._run_role(role, scope)
        self.assertEqual(report.result, 'PASS')
        self.assertEqual(report.checks[0].result, 'PASS')

    def test_unresolvable_role_is_error(self):
        report = self._run_role(Role('T-4', '깨진 참조', ('var', '--nope'), ('lit', '#fff'), 'text', ('light',)), {'--other': '#000'})
        self.assertEqual(report.result, 'FAIL')
        self.assertTrue(any(f.code == 'CNT-PARSE' for f in report.errors))


class RealTemplateRunTests(unittest.TestCase):
    """실제 두 템플릿에 대한 검사기 실행(전체 PASS/한계 기록 확인)."""

    def test_checker_passes_on_real_templates(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        result = subprocess.run([sys.executable, '-B', str(CHECKER)], capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Result:', result.stdout)
        self.assertNotIn('[FAIL]', result.stdout)
        self.assertNotIn('CNT-LOW', result.stdout)
        self.assertIn('Result: WARN', result.stdout)  # 한계 기록 3건은 경고로 남는다
        # 렌더더 31 역할(밝음·어두움) + 보고서 32 역할 = 63 검사
        self.assertEqual(result.stdout.count('[PASS]') + result.stdout.count('[LIMIT]'), 63)

    def test_json_output_rows_cover_both_themes(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'vc.json'
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
            result = subprocess.run(
                [sys.executable, '-B', str(CHECKER), '--output-json', str(out), '--quiet'],
                capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(out.read_text())
            rows = payload['rows']
            self.assertEqual(len(rows), 94)  # 렌더더 31×2 + 보고서 32
            self.assertEqual({r['theme'] for r in rows}, {'light', 'dark'})
            self.assertTrue(all(r['result'] in ('PASS', 'LIMIT', 'DECOR') for r in rows))


if __name__ == '__main__':
    unittest.main()
