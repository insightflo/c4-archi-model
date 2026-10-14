"""D5: 보고서와 그림이 공유하는 시각 프로필.

프로필 = 색·글꼴·간격 역할(두 템플릿의 기존 CSS 변수명) 값의 묶음이다.
(a) 템플릿 정의 파싱 — 기본 프로필은 빈 덮어쓰기(기존 값 무변경),
(b) 프로필 역할이 실제 템플릿에 존재(모르는 역할 무시·빠진 역할 기본 보충),
(c) 고대비 프로필이 verify_visual_contrast --profile로 63역할 모두 통과,
(d) 브라우저에서 보고서·임베드 렌더더·전체 화면 동시 반영, 테마 전환과의 직교,
기본 복귀, 모르는 역할 무시를 실제 Chromium에서 확인한다(산출물은 전부 임시 파일).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.dont_write_bytecode = True

from verify_visual_contrast import (  # noqa: E402
    RENDERER,
    REPORT,
    merge_profile,
    parse_css_variables,
    parse_visual_profiles,
    profile_overrides,
)
from c4_validation import ValidationReport  # noqa: E402

CHROME = os.environ.get('C4_BROWSER') or shutil.which('chromium') or '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

BROWSER_NEEDED = bool(sync_playwright and Path(CHROME).is_file() and shutil.which('node'))
CHECKER = ROOT / 'scripts' / 'verify_visual_contrast.py'

# 기대 기준색(템플릿 원문 값 — 프로필 미적용 상태)
REPORT_INK_DEFAULT = 'rgb(26, 26, 26)'      # --ink #1a1a1a
REPORT_INK_HIGH_CONTRAST = 'rgb(0, 0, 0)'   # --ink #000000
RENDERER_INK_DEFAULT = 'rgb(24, 32, 29)'    # --color-ink #18201d
RENDERER_INK_HC_LIGHT = 'rgb(0, 0, 0)'      # 고대비 밝음 --color-ink #000000
RENDERER_INK_HC_DARK = 'rgb(255, 255, 255)'  # 고대비 어두움 --color-ink #ffffff


def element(eid: str, etype: str, name: str, parent: str | None = None) -> dict[str, Any]:
    return {"id": eid, "type": etype, "name": name, "description": f"{name}의 canonical 설명",
            "technology": None, "parentId": parent, "environment": None, "tags": [],
            "derivation": "explicit", "confidence": "DOC_ONLY", "rationale": None,
            "claimIds": ["claim-d5"], "instanceOfId": None}


def relation(rid: str, src: str, dst: str, desc: str) -> dict[str, Any]:
    return {"id": rid, "sourceId": src, "destinationId": dst, "description": desc,
            "technology": None, "kind": "association", "derivation": "explicit",
            "confidence": "DOC_ONLY", "rationale": None, "claimIds": ["claim-d5"], "tags": [],
            "environment": None, "interactionId": None}


def make_model() -> dict[str, Any]:
    elements = [
        element("customer", "person", "고객"),
        element("ordering-system", "softwareSystem", "주문 시스템"),
        element("web-app", "container", "웹 앱", "ordering-system"),
    ]
    relationships = [relation("r-use", "customer", "web-app", "화면에서 주문한다")]
    views = [{"id": "containers", "type": "container", "title": "주문 시스템 내부",
              "scopeId": "ordering-system", "environment": None, "description": "구조 설명",
              "question": "무엇을 보는가?", "notShown": [],
              "elementIds": ["customer", "web-app"], "relationshipIds": ["r-use"],
              "steps": [], "nextViewIds": [], "claimIds": []}]
    return {"schemaVersion": "1.0.0",
            "metadata": {"title": "프로필 샘플", "modelRevision": "d5-profile",
                         "description": "D5 공유 시각 프로필 검증용 canonical 모델"},
            "elements": elements, "relationships": relationships, "views": views}


def typed_projection(model: dict[str, Any], view_id: str) -> dict[str, Any]:
    from repo_flowmap_adapter import project
    raw = json.dumps(model, ensure_ascii=False)
    return project(model, 'model/architecture-model.json',
                   hashlib.sha256(raw.encode()).hexdigest(), view_id)


def build_view_html(data: dict[str, Any], target: Path) -> Path:
    source = target.with_suffix('.json')
    source.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    result = subprocess.run(
        ['node', str(ROOT / 'assets/repo-flowmap/scripts/build_flowmap.mjs'),
         str(source), str(ROOT / 'assets/repo-flowmap/template.html'), str(target)],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return target


def make_report_data(model: dict[str, Any], base: Path) -> dict[str, Any]:
    html = build_view_html(typed_projection(model, 'containers'), base / 'containers.html').read_text(encoding='utf-8')
    uri = 'data:text/html;base64,' + base64.b64encode(html.encode()).decode()
    return {"analysis": {}, "flows": [],
            "diagrams": [{"id": "d-containers", "viewId": "containers",
                          "mimeType": "text/html", "dataUri": uri}],
            "elementGroups": [{"id": "scope", "title": "주문 구성요소",
                               "scopeModelId": "ordering-system",
                               "elements": [{"modelId": "ordering-system"}, {"modelId": "web-app"}]}]}


class ProfileDefinitionTests(unittest.TestCase):
    """템플릿의 프로필 정의 — 기본 무변경·역할 실재(단위, 브라우저 불필요)."""

    @classmethod
    def setUpClass(cls):
        cls.report_text = (ROOT / REPORT).read_text(encoding='utf-8')
        cls.profiles = parse_visual_profiles(cls.report_text)
        cls.renderer_scopes = parse_css_variables((ROOT / RENDERER).read_text(encoding='utf-8'))
        cls.report_scopes = parse_css_variables(cls.report_text)

    def test_default_profile_is_empty_overrides(self):
        # 기본 프로필 = 현재 템플릿 값 그대로(빈 덮어쓰기). 새로운 시각을 만들지 않는다.
        default = self.profiles['default']
        self.assertEqual(default['report'], {})
        self.assertEqual(default['renderer'], {'light': {}, 'dark': {}})
        self.assertTrue(self.profiles['high-contrast']['report'])
        self.assertTrue(self.profiles['high-contrast']['renderer']['light'])

    def test_profile_roles_exist_in_both_templates(self):
        # 역할 ID는 두 템플릿의 기존 CSS 변수명이다. 모르는 역할은 어느 쪽에도 없다.
        hc = self.profiles['high-contrast']
        for theme in ('light', 'dark'):
            for key in hc['renderer'][theme]:
                self.assertIn(key, self.renderer_scopes['light'], f'{key}이 렌더더 밝음 정의에 없음')
                self.assertIn(key, self.renderer_scopes['dark'], f'{key}이 렌더더 어두움 정의에 없음')
        for key in hc['report']:
            self.assertIn(key, self.report_scopes['light'], f'{key}이 보고서 정의에 없음')

    def test_high_contrast_keeps_missing_roles_default(self):
        # 프로필은 부분 정의다 — 지정하지 않은 역할(빠진 역할)은 기본값 그대로 보충된다.
        hc = self.profiles['high-contrast']
        merged = merge_profile(
            {t: dict(self.renderer_scopes[t]) for t in ('light', 'dark')},
            profile_overrides(hc, RENDERER), RENDERER, ValidationReport('test'))
        self.assertNotIn('--color-accent', hc['renderer']['light'])  # 빠진 역할
        self.assertEqual(merged['light']['--color-accent'], self.renderer_scopes['light']['--color-accent'])
        self.assertEqual(merged['light']['--color-ink'], hc['renderer']['light']['--color-ink'])
        self.assertEqual(merged['dark']['--color-edge'], hc['renderer']['dark']['--color-edge'])

    def test_report_template_wires_profile_ui_and_frames(self):
        # 보고서: 선택 UI·프로필 적용·임베드/전체 화면 프레임 전달 배선이 템플릿에 있다.
        text = self.report_text
        self.assertIn('id="visual-profile"', text)
        self.assertIn("type:'repo-flowmap-profile'", text)
        self.assertIn('sendProfileToFrame(img)', text)          # 임베드 iframe 로드 시 전달
        self.assertIn('sendProfileToFrame(dialogEmbed)', text)  # 전체 화면(srcdoc 재사용) 전달
        self.assertIn('visualProfiles[profileSelect.value]', text)

    def test_renderer_template_applies_profile_and_ignores_unknown(self):
        # 렌더더: 프로필 메시지 처리·테마 전환 시 재적용·모르는 역할 무시 배선이 있다.
        text = (ROOT / RENDERER).read_text(encoding='utf-8')
        self.assertIn("e.data.type==='repo-flowmap-profile'", text)
        self.assertIn('applyProfileRoles(); // 프로필은 테마와 직교', text)
        self.assertIn('이 렌더더가 모르는 역할은 무시', text)
        # 내보내기(SVG)도 활성 프로필 역할을 싣는다(기본이면 바이트 무변경).
        self.assertIn('profileApplied[pi]', text)


class ProfileVerifierTests(unittest.TestCase):
    """검사기 --profile 진입점 — 고대비 전체 통과·오류 분기·기본 동작 무변경."""

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        return subprocess.run([sys.executable, '-B', str(CHECKER), *args],
                              capture_output=True, text=True, env=env)

    def test_high_contrast_profile_passes_all_roles(self):
        # 고대비 프로필: 63역할 모두 PASS — 한계(LIMIT) 기록도 없다(기본 팔레트의 3건 한계 해소).
        result = self._run('--profile', 'high-contrast')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Result: PASS', result.stdout)
        self.assertEqual(result.stdout.count('[PASS]'), 63)
        self.assertNotIn('[LIMIT]', result.stdout)
        self.assertNotIn('[FAIL]', result.stdout)
        self.assertIn('Warnings: 0', result.stdout)

    def test_high_contrast_json_rows_marked_with_profile(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'hc.json'
            result = self._run('--profile', 'high-contrast', '--output-json', str(out), '--quiet')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            rows = json.loads(out.read_text())['rows']
            self.assertEqual(len(rows), 94)
            self.assertTrue(all(r.get('profile') == 'high-contrast' for r in rows))
            self.assertTrue(all(r['result'] in ('PASS', 'DECOR') for r in rows))

    def test_unknown_profile_name_is_an_error(self):
        result = self._run('--profile', 'nope')
        self.assertEqual(result.returncode, 1)
        self.assertIn('CNT-PROFILE', result.stdout)

    def test_baseline_run_without_profile_is_unchanged(self):
        # 인자 없으면 기존 동작 그대로 — 기본 팔레트의 한계 3건은 경고로 남는다.
        result = self._run('--quiet')
        self.assertEqual(result.returncode, 0)
        self.assertIn('Result: WARN', result.stdout)
        self.assertIn('Warnings: 3', result.stdout)

    def test_merge_profile_warns_on_unknown_role_and_keeps_default(self):
        # 오래된/불완전 프로필: 템플릿에 없는 역할은 경고하고 무시, 나머지는 그대로.
        report = ValidationReport('test')
        scopes = {'light': {'--color-ink': '#18201d', '--color-accent': '#17624b'}}
        merged = merge_profile(scopes, {'light': {'--color-ink': '#000000', '--ghost-role': '#fff'}},
                               RENDERER, report)
        self.assertEqual(merged['light']['--color-ink'], '#000000')
        self.assertEqual(merged['light']['--color-accent'], '#17624b')
        self.assertNotIn('--ghost-role', merged['light'])
        self.assertEqual(len(report.warnings), 1)
        self.assertEqual(report.warnings[0].code, 'CNT-PROFILE-ROLE')


@unittest.skipUnless(BROWSER_NEEDED, 'actual Chrome, Playwright and Node required')
class VisualProfileBrowserTests(unittest.TestCase):
    """D5: 프로필이 보고서·임베드 그림·전체 화면에 함께 적용되고 테마와 직교한다."""

    @classmethod
    def setUpClass(cls):
        from build_html_report import hydrate_report, inject
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        model = make_model()
        data = make_report_data(model, base)
        hydrated = hydrate_report(data, {"session": {}, "understanding": None, "model": model,
                                         "ledger": {"sources": [], "claims": []},
                                         "coverage": {"completion": {"result": "NOT_RUN",
                                                                     "reason": "D5 profile fixture"}}},
                                  ValidationReport('test'))
        template = (ROOT / 'assets/html-report-template.html').read_text(encoding='utf-8')
        cls.report = base / 'report.html'
        cls.report.write_text(inject(template, hydrated), encoding='utf-8')
        cls.standalone = build_view_html(typed_projection(model, 'containers'), base / 'standalone.html')
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=CHROME, headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.tmp.cleanup()

    def setUp(self):
        self.page = self.browser.new_page(viewport={'width': 1440, 'height': 1000}, offline=True)
        self.errors: list[str] = []
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))

    def tearDown(self):
        self.page.close()
        self.assertEqual(self.errors, [])

    def renderer_frame(self, page):
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            try:
                if frame.evaluate('window.repoFlowmap ? window.repoFlowmap.state().viewId : null') == 'containers':
                    return frame
            except Exception:
                continue
        raise AssertionError('임베드 렌더더 프레임을 찾지 못했다')

    def body_color(self, frame) -> str:
        return frame.evaluate('getComputedStyle(document.body).color')

    def wait_dialog_body_color(self, expected: str, tries: int = 60) -> str:
        # 다이어그랬로그 iframe은 로드 이벤트(스크립트 실행 완료) 뒤 프로필 메시지를 받는다.
        locator = self.page.frame_locator('#dialog-embed').locator('body')
        for _ in range(tries):
            try:
                if locator.evaluate('el=>getComputedStyle(el).color') == expected:
                    return expected
            except Exception:
                pass
            self.page.wait_for_timeout(100)
        raise AssertionError(f'다이어그랬로그 iframe 본문 색이 {expected}가 되지 않았다')

    def test_profile_applies_to_report_embed_and_dialog_then_reverts(self):
        page = self.page
        page.goto(self.report.as_uri())
        page.wait_for_function(
            "()=>!!document.querySelector('#diagram-panels iframe[data-native-camera=\"1\"]')")
        frame = self.renderer_frame(page)
        # 기본 프로필: 보고서·렌더더 모두 템플릿 원문 색.
        self.assertEqual(page.evaluate("getComputedStyle(document.querySelector('.hero h1')).color"),
                         REPORT_INK_DEFAULT)
        self.assertEqual(self.body_color(frame), RENDERER_INK_DEFAULT)

        # 고대비 선택 → 보고서 색 변수와 임베드 렌더더 계산 스타일이 함께 바뀐다.
        page.select_option('#visual-profile', 'high-contrast')
        page.wait_for_function(
            "()=>getComputedStyle(document.querySelector('.hero h1')).color==='rgb(0, 0, 0)'")
        frame.wait_for_function("()=>getComputedStyle(document.body).color==='rgb(0, 0, 0)'")
        self.assertEqual(frame.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--color-ink').trim()"),
                         '#000000')

        # 전체 화면 다이어그랬로그(srcdoc 재사용)도 같은 전달을 받는다.
        # 샌드박스 임베드는 불투명 오리진이라 프레임 안에서 직접 계산 스타일을 읽는다.
        page.locator('#diagram-panel-d-containers [data-full]').click()
        page.wait_for_function("!document.getElementById('dialog-embed').hidden")
        embed_color = self.wait_dialog_body_color('rgb(0, 0, 0)')
        self.assertEqual(embed_color, 'rgb(0, 0, 0)')
        page.locator('#dialog-close').click()

        # 기본 복귀 → 보고서·렌더더 원문 값으로 돌아오고 인라인 덮어쓰기가 해제된다.
        page.select_option('#visual-profile', 'default')
        page.wait_for_function(
            "()=>getComputedStyle(document.querySelector('.hero h1')).color==='%s'" % REPORT_INK_DEFAULT)
        frame.wait_for_function(
            "()=>getComputedStyle(document.body).color==='%s'" % RENDERER_INK_DEFAULT)
        self.assertEqual(frame.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--color-ink').trim()"),
                         '#18201d')

    def test_profile_is_orthogonal_to_renderer_theme_toggle(self):
        page = self.page
        page.goto(self.report.as_uri())
        page.wait_for_function(
            "()=>!!document.querySelector('#diagram-panels iframe[data-native-camera=\"1\"]')")
        frame = self.renderer_frame(page)
        page.select_option('#visual-profile', 'high-contrast')
        frame.wait_for_function("()=>getComputedStyle(document.body).color==='rgb(0, 0, 0)'")

        # 렌더더 테마 전환(기존 기능) — 프로필은 유지된 채 새 테마의 프로필 값이 적용된다.
        frame.locator('#theme').click()
        frame.wait_for_function("()=>getComputedStyle(document.body).color==='rgb(255, 255, 255)'")
        self.assertEqual(frame.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--color-ink').trim()"),
                         '#ffffff')
        # 보고서(밝은 테마만)는 렌더더 테마와 무관하게 고대비를 유지한다 — 직교.
        self.assertEqual(page.evaluate("getComputedStyle(document.querySelector('.hero h1')).color"),
                         REPORT_INK_HIGH_CONTRAST)
        # 다시 밝음으로 — 프로필 여부와 무관하게 테마 전환은 계속 작동한다.
        frame.locator('#theme').click()
        frame.wait_for_function("()=>getComputedStyle(document.body).color==='rgb(0, 0, 0)'")

    def test_renderer_ignores_unknown_roles_and_clears_on_empty_map(self):
        page = self.page
        # 단독 실행 렌더더(window.parent===window): 프로필 메시지를 직접 받는다.
        page.goto(self.standalone.as_uri())
        page.wait_for_function('()=>!!window.repoFlowmap')
        # 모르는 역할(--color-not-a-role)은 무시하고, 아는 역할만 적용한다(부분 정의 보충).
        page.evaluate("window.postMessage({type:'repo-flowmap-profile',"
                      "roles:{light:{'--color-ink':'#123456','--color-not-a-role':'#ff0000'}}},'*')")
        page.wait_for_function("()=>getComputedStyle(document.body).color==='rgb(18, 52, 86)'")
        unknown = page.evaluate(
            "getComputedStyle(document.documentElement).getPropertyValue('--color-not-a-role').trim()")
        self.assertEqual(unknown, '')
        self.assertNotIn('--color-not-a-role',
                         page.evaluate("document.documentElement.getAttribute('style')||''"))
        # 빈 맵 = 기본 복귀: 덮어쓰기가 전부 해제된다.
        page.evaluate("window.postMessage({type:'repo-flowmap-profile',roles:{light:{},dark:{}}},'*')")
        page.wait_for_function("()=>getComputedStyle(document.body).color==='%s'" % RENDERER_INK_DEFAULT)


if __name__ == '__main__':
    unittest.main()
