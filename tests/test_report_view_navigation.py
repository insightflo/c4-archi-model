"""A5: 상위 경계를 유지하는 내부 펼치기 — 연결된 탐색·부모 경로·상태 복원.

브라우저 케이스는 실제 Chromium에서 file:// URL로 같은 native 렌더러·같은 보고서
템플릿을 돌린다(모킹 없음, 산출물은 전부 임시 파일). 탐색 연결은 canonical ID와
뷰 포함 목록·parentId 체인뿐이다 — 이름 매칭으로 뷰를 지어내지 않는지가 검증 대상이다.
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
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / 'tests'))

CHROME = os.environ.get('C4_BROWSER') or shutil.which('chromium') or '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

BROWSER_NEEDED = bool(sync_playwright and Path(CHROME).is_file() and shutil.which('node'))


def element(eid: str, etype: str, name: str, parent: str | None = None) -> dict[str, Any]:
    return {"id": eid, "type": etype, "name": name, "description": f"{name}의 canonical 설명",
            "technology": None, "parentId": parent, "environment": None, "tags": [],
            "derivation": "explicit", "confidence": "DOC_ONLY", "rationale": None,
            "claimIds": ["claim-a5"], "instanceOfId": None}


def relation(rid: str, src: str, dst: str, desc: str) -> dict[str, Any]:
    return {"id": rid, "sourceId": src, "destinationId": dst, "description": desc,
            "technology": None, "kind": "association", "derivation": "explicit",
            "confidence": "DOC_ONLY", "rationale": None, "claimIds": ["claim-a5"], "tags": [],
            "environment": None, "interactionId": None}


def make_model() -> dict[str, Any]:
    """3단계 확대 체인(맥락 → 컨테이너 → 컴포넌트)과 안내 재생용 dynamic 뷰.

    구조 뷰의 관계는 확장 경계(deployment가 아닌 structure의 경계 요소)를 끝점으로
    쓰지 않는다 — 어댑터의 실제 제약 그대로다.
    """
    elements = [
        element("customer", "person", "고객"),
        element("ordering-system", "softwareSystem", "주문 시스템"),
        element("web-app", "container", "웹 앱", "ordering-system"),
        element("order-api", "container", "주문 API", "ordering-system"),
        element("order-controller", "component", "주문 컨트롤러", "web-app"),
        element("order-store", "component", "주문 저장소", "web-app"),
    ]
    relationships = [
        relation("r-context", "customer", "ordering-system", "주문을 넣는다"),
        relation("r-use", "customer", "web-app", "화면에서 주문한다"),
        relation("r-call", "web-app", "order-api", "주문 API를 호출한다"),
        relation("r-store", "order-controller", "order-store", "저장을 위임한다"),
    ]

    def view(vid: str, vtype: str, title: str, scope: str, eids: list[str], rids: list[str],
             next_ids: list[str], steps: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return {"id": vid, "type": vtype, "title": title, "scopeId": scope, "environment": None,
                "description": f"{title} 설명", "question": f"{title}에서 무엇을 보는가?",
                "notShown": [], "elementIds": eids, "relationshipIds": rids,
                "steps": steps or [], "nextViewIds": next_ids, "claimIds": []}

    views = [
        view("ctx", "systemContext", "주문 시스템 맥락", "ordering-system",
             ["customer", "ordering-system"], ["r-context"], ["containers"]),
        view("containers", "container", "주문 시스템 내부", "ordering-system",
             ["customer", "web-app", "order-api"], ["r-use", "r-call"], ["web-internal"]),
        view("web-internal", "component", "웹 앱 내부", "web-app",
             ["order-controller", "order-store"], ["r-store"], []),
        view("create-order", "dynamic", "주문 만들기 흐름", "ordering-system",
             ["customer", "web-app", "order-api"], ["r-use", "r-call"], [],
             [{"id": "s1", "order": 1, "relationshipId": "r-use", "kind": "interaction",
               "note": "첫 번째 단계", "condition": None},
              {"id": "s2", "order": 2, "relationshipId": "r-call", "kind": "interaction",
               "note": "두 번째 단계", "condition": None}]),
    ]
    return {"schemaVersion": "1.0.0",
            "metadata": {"title": "주문 샘플", "modelRevision": "a5-nav", "description": "A5 탐색 검증용 canonical 모델"},
            "elements": elements, "relationships": relationships, "views": views}

def typed_projection(model: dict[str, Any], view_id: str) -> dict[str, Any]:
    from repo_flowmap_adapter import project
    raw = json.dumps(model, ensure_ascii=False)
    return project(model, 'model/architecture-model.json', hashlib.sha256(raw.encode()).hexdigest(), view_id)


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
    uris = {}
    for vid in ("ctx", "containers", "web-internal"):
        html = build_view_html(typed_projection(model, vid), base / f'{vid}.html').read_text(encoding='utf-8')
        uris[vid] = 'data:text/html;base64,' + base64.b64encode(html.encode()).decode()
    return {
        "analysis": {},
        "flows": [{"id": "create", "viewId": "create-order", "kind": "normal"}],
        "diagrams": [
            {"id": "d-ctx", "viewId": "ctx", "mimeType": "text/html", "dataUri": uris["ctx"]},
            {"id": "d-containers", "viewId": "containers", "mimeType": "text/html", "dataUri": uris["containers"]},
            {"id": "d-web", "viewId": "web-internal", "mimeType": "text/html", "dataUri": uris["web-internal"]},
        ],
        "elementGroups": [{"id": "scope", "title": "주문 구성요소", "scopeModelId": "ordering-system",
                           "elements": [{"modelId": "ordering-system"}, {"modelId": "web-app"},
                                        {"modelId": "order-controller"}]}],
    }


def make_bundle(model: dict[str, Any]) -> dict[str, Any]:
    return {"session": {}, "understanding": None, "model": model,
            "ledger": {"sources": [], "claims": []},
            "coverage": {"completion": {"result": "NOT_RUN", "reason": "A5 navigation fixture"}}}


class ScopeChainHydrationTests(unittest.TestCase):
    """빌더가 뷰 경계 체인을 canonical ID로만 만드는지(단위, 브라우저 불필요)."""

    def test_scope_id_and_parent_chain_hydrate_without_invention(self) -> None:
        from build_html_report import hydrate_report
        from c4_validation import ValidationReport
        model = make_model()
        result = hydrate_report(_data_for(model), make_bundle(model), ValidationReport("test"))
        by_view = {d["viewId"]: d for d in result["diagrams"]}
        self.assertEqual(by_view["ctx"]["scopeId"], "ordering-system")
        self.assertEqual(by_view["ctx"]["scopeChain"], ["ordering-system"])
        self.assertEqual(by_view["web-internal"]["scopeId"], "web-app")
        # parentId 포함 관계: 웹 앱 내부 뷰는 웹 앱 안이고, 그 위 주문 시스템 경계 안에 있다.
        self.assertEqual(by_view["web-internal"]["scopeChain"], ["web-app", "ordering-system"])
        # 구성요소 동일성: 상위 뷰 요소 ID와 하위 뷰 경계 ID가 같은 canonical 문자열이다.
        self.assertIn("web-app", by_view["containers"]["elementIds"])
        self.assertEqual(by_view["web-internal"]["scopeChain"][0], "web-app")
        # dynamic 뷰의 안내 링크도 canonical viewId를 그대로 전달한다.
        self.assertEqual(by_view["containers"]["nextViewIds"], ["web-internal"])

    def test_scope_chain_stops_on_parent_cycle_without_error(self) -> None:
        from build_html_report import scope_chain
        elements = {"a": {"id": "a", "parentId": "b"}, "b": {"id": "b", "parentId": "a"}}
        self.assertEqual(scope_chain("a", elements), ["a", "b"])
        self.assertEqual(scope_chain(None, elements), [])
        self.assertEqual(scope_chain("missing", elements), [])


def _data_for(model: dict[str, Any]) -> dict[str, Any]:
    """단위 테스트용(data URI 없이) — hydrate는 자산 없이도 뷰 정보를 채운다."""
    return {
        "analysis": {},
        "flows": [],
        "diagrams": [
            {"id": "d-ctx", "viewId": "ctx", "mimeType": None, "dataUri": None},
            {"id": "d-containers", "viewId": "containers", "mimeType": None, "dataUri": None},
            {"id": "d-web", "viewId": "web-internal", "mimeType": None, "dataUri": None},
        ],
        "elementGroups": [{"id": "scope", "title": "주문 구성요소", "scopeModelId": "ordering-system",
                           "elements": [{"modelId": "ordering-system"}, {"modelId": "web-app"},
                                        {"modelId": "order-controller"}]}],
    }


@unittest.skipUnless(BROWSER_NEEDED, 'actual Chrome, Playwright and Node required')
class ViewNavigationBrowserTests(unittest.TestCase):
    """A5: 확대 진입·부모 경로·선택/카메라 복원·안내 정지가 실제 브라우저에서 돌아가는지."""

    @classmethod
    def setUpClass(cls):
        from build_html_report import hydrate_report, inject
        from c4_validation import ValidationReport
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        cls.model = make_model()
        data = make_report_data(cls.model, base)
        hydrated = hydrate_report(data, make_bundle(cls.model), ValidationReport('test'))
        template = (ROOT / 'assets/html-report-template.html').read_text(encoding='utf-8')
        cls.report = base / 'report.html'
        cls.report.write_text(inject(template, hydrated), encoding='utf-8')
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=CHROME, headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.tmp.cleanup()

    def load(self):
        page = self.browser.new_page(viewport={'width': 1440, 'height': 1000}, offline=True)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.add_init_script(
            "window.__rfmStates=[];"
            "window.addEventListener('message',e=>{"
            "if(e.data&&e.data.type==='repo-flowmap-state')window.__rfmStates.push(e.data);});")
        page.goto(self.report.as_uri())
        page.wait_for_function(
            "()=>document.querySelectorAll('#diagram-tabs [role=\"tab\"]').length===3")
        return page, errors

    def frame_state(self, page, view_id: str):
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            try:
                if frame.evaluate('window.repoFlowmap ? window.repoFlowmap.state().viewId : null') == view_id:
                    return frame.evaluate('window.repoFlowmap.state()')
            except Exception:
                continue
        return None

    def states_for(self, page, view_id: str):
        return [s for s in page.evaluate('window.__rfmStates') if s['viewId'] == view_id]

    def active_tab(self, page) -> str:
        return page.evaluate(
            "()=>{const t=[...document.querySelectorAll('#diagram-tabs [role=\"tab\"]')]"
            ".find(b=>b.getAttribute('aria-selected')==='true');return t?t.textContent.trim():null;}")

    def click_and_wait(self, page, locator, predicate, arg=None, timeout: int = 12000,
                       via_keyboard: bool = False) -> None:
        """클릭→목표 상태를 긍정형 predicate로 기다린다. 부하가 높은 전체 실행에서
        드물게 클릭 이벤트가 애플리케이션에 닿지 않는 경우(LESSONS.md) 멱등 재클릭
        1회로만 흡수한다 — 탭·확대·경로 이동 재클릭은 같은 뷰를 다시 선택할 뿐이다.

        via_keyboard: 마우스 클릭의 자동 스크롤이 흐름 패널을 화면 밖으로 밀어내면
        제품의 IntersectionObserver '화면 밖' 정지가 탭 전환 정지('다른 탭' 사유)보다
        먼저 발생한다(실측: 안내 영역이 화면 밖...). 'tab' 사유는 2500ms user 보정
        대상이 아니므로 기다리는 안내 문구가 영원히 오지 않는다. focus(+Enter)는
        스크롤 없이 동일한 click 이벤트 경로(문서 수준 정지 청취자)를 건드린다."""
        def activate() -> None:
            if via_keyboard:
                locator.focus()
                page.keyboard.press('Enter')
            else:
                locator.click()
        activate()
        try:
            page.wait_for_function(predicate, arg=arg, timeout=8000)
        except Exception:
            activate()
            page.wait_for_function(predicate, arg=arg, timeout=timeout)

    ACTIVE_TAB_JS = (
        "()=>{const t=[...document.querySelectorAll('#diagram-tabs [role=\"tab\"]')]"
        ".find(b=>b.getAttribute('aria-selected')==='true');return t?t.textContent.trim():null;}")

    def test_element_card_zoom_enters_internal_view_and_reports_absence(self):
        page, errors = self.load()
        page.locator('#elements').scroll_into_view_if_needed()
        details = page.locator('#group-panel-scope details.responsibility-details')
        details.locator('summary').click()
        # 진입 불가 표시: 펼친 뷰가 없는 요소는 비활성 + 안내 문구(지어내지 않는다).
        leaf = page.locator('button[data-element-zoom="order-controller"]')
        self.assertTrue(leaf.is_disabled())
        note = page.locator('button[data-element-zoom="order-controller"] ~ .element-zoom-note')
        self.assertEqual(note.inner_text(), '펼친 View 기록 없음')
        # 시스템 요소는 그 내부(컨테이너 뷰)로, 컨테이너 요소는 컴포넌트 뷰로 들어간다.
        # 클릭 직후 곧바로 읽지 않고 목표 상태(활성 탭)를 긍정형으로 기다린다.
        self.click_and_wait(page, page.locator('button[data-element-zoom="ordering-system"]'),
                            self.ACTIVE_TAB_JS, arg='주문 시스템 내부')
        self.assertEqual(self.active_tab(page), '주문 시스템 내부')
        crumbs = page.locator('#view-breadcrumb button')
        self.assertEqual(crumbs.count(), 1)
        self.assertEqual(crumbs.first.get_attribute('data-crumb-view'), 'ctx')
        self.assertEqual(page.locator('#view-breadcrumb .crumb-current').inner_text(), '주문 시스템 내부')
        self.click_and_wait(page, page.locator('button[data-element-zoom="web-app"]'),
                            self.ACTIVE_TAB_JS, arg='웹 앱 내부')
        self.assertEqual(self.active_tab(page), '웹 앱 내부')
        self.assertEqual(page.locator('#view-breadcrumb button').count(), 2)
        page.close()
        self.assertEqual(errors, [])

    def test_two_level_breadcrumb_return_restores_selection_and_camera(self):
        page, errors = self.load()
        page.locator('#diagrams').scroll_into_view_if_needed()
        ctx_frame = page.frame_locator('#diagram-panels iframe[data-view-id="ctx"]')
        # 그림 노드 선택(동일성: canonical ID로 노드를 찾는다) → 보고서가 상태를 안다.
        ctx_frame.locator('g.node[data-canonical-id="ordering-system"]').click()
        expand = page.locator('#diagram-panel-d-ctx [data-expand]')
        page.wait_for_function(
            "sel=>!document.querySelector(sel).disabled", arg='#diagram-panel-d-ctx [data-expand]')
        # 떠나기 전 카메라를 바꿔 둔다(기존 카메라 메시지 경로). 줌 버튼 경로는
        # 애니메이션 이동(moveTo animate=true)이라 상태 알림을 쏘지 않으므로, 부모
        # 기록 수 증가가 아니라 렌더러 카메라(k)가 실제로 커졌음을 목표 상태로 기다린다
        # (고정 sleep은 부하에서 클릭 반영 전에 지나갈 수 있다).
        ctx_renderer = page.locator('#diagram-panels iframe[data-view-id="ctx"]').element_handle().content_frame()
        k_before = ctx_renderer.evaluate('window.repoFlowmap.state().camera.k')
        page.locator('#diagram-panel-d-ctx [data-zoom="in"]').click()
        ctx_renderer.wait_for_function(
            "(k)=>window.repoFlowmap&&window.repoFlowmap.state().camera.k>k+1e-9", arg=k_before, timeout=12000)
        saved = self.states_for(page, 'ctx')[-1]
        self.assertEqual(saved['selectedId'], 'ordering-system')
        self.click_and_wait(page, page.locator('#diagram-panel-d-ctx [data-expand]'),
                            self.ACTIVE_TAB_JS, arg='주문 시스템 내부')
        self.assertEqual(self.active_tab(page), '주문 시스템 내부')
        # 두 번째 단계 확대: 컨테이너 뷰에서 웹 앱 노드 선택 → 컴포넌트 뷰로.
        containers = page.frame_locator('#diagram-panels iframe[data-view-id="containers"]')
        containers.locator('g.node[data-canonical-id="web-app"]').click()
        page.wait_for_function(
            "sel=>!document.querySelector(sel).disabled", arg='#diagram-panel-d-containers [data-expand]')
        # 같은 줌 대기 근거: 렌더러 카메라가 실제로 커졌음을 긍정형으로 기다린다.
        containers_renderer = page.locator(
            '#diagram-panels iframe[data-view-id="containers"]').element_handle().content_frame()
        k_before = containers_renderer.evaluate('window.repoFlowmap.state().camera.k')
        page.locator('#diagram-panel-d-containers [data-zoom="in"]').click()
        containers_renderer.wait_for_function(
            "(k)=>window.repoFlowmap&&window.repoFlowmap.state().camera.k>k+1e-9", arg=k_before, timeout=12000)
        self.click_and_wait(page, page.locator('#diagram-panel-d-containers [data-expand]'),
                            self.ACTIVE_TAB_JS, arg='웹 앱 내부')
        self.assertEqual(self.active_tab(page), '웹 앱 내부')
        crumbs = page.locator('#view-breadcrumb button')
        self.assertEqual(crumbs.count(), 2)
        # 한 번에 최상위 복귀 → 원래 뷰의 선택 요소·카메라가 그대로 돌아온다.
        # 복귀 지시(repo-flowmap-focus)를 받은 렌더러는 처리 뒤 즉시 상태를 알려오므로,
        # 그 기록이 도착한 뒤 프레임 상태를 읽는다(정지 프레임 없이 곧바로 읽으면
        # 복원 적용 전 카메라를 읽을 수 있다).
        before = len(self.states_for(page, 'ctx'))
        self.click_and_wait(page, page.locator('#view-breadcrumb button[data-crumb-view="ctx"]'),
                            self.ACTIVE_TAB_JS, arg='주문 시스템 맥락')
        self.assertEqual(self.active_tab(page), '주문 시스템 맥락')
        self.assertTrue(page.locator('#view-breadcrumb').is_hidden())
        page.wait_for_function(
            "(n)=>window.__rfmStates.filter(s=>s.viewId==='ctx').length>n", arg=before, timeout=12000)
        state = self.frame_state(page, 'ctx')
        self.assertIsNotNone(state)
        self.assertEqual(state['node'], 'ordering-system')
        for key in ('k', 'tx', 'ty'):
            self.assertAlmostEqual(state['camera'][key], saved['camera'][key], places=4,
                                   msg=f'camera {key} restored')
        page.close()
        self.assertEqual(errors, [])

    def test_guide_next_view_link_navigates_and_stops_guidance(self):
        page, errors = self.load()
        page.locator('#flows').scroll_into_view_if_needed()
        page.evaluate('''() => {
          window.__announce = [];
          const region = document.querySelector('#flow-panel-create .flow-step-announce');
          new MutationObserver(records => records.forEach(() => window.__announce.push(region.textContent)))
            .observe(region, {childList: true, characterData: true, subtree: true});
        }''')
        page.locator('#flow-panel-create .flow-guide-btn').click()
        # 시작 대기는 안내 문구만이 아니라 버튼의 aria-pressed='true'까지 목표 상태로 본다.
        page.wait_for_function(
            "()=>window.__announce.some(t=>t.includes('안내 재생을 시작합니다'))"
            "&&document.querySelector('#flow-panel-create .flow-guide-btn').getAttribute('aria-pressed')==='true'",
            timeout=12000)
        # 뷰 안내의 다음 뷰 링크도 같은 탐색 체계다 — 이동은 안내를 정지한다(자동 재개 없음).
        link = page.locator('#diagram-panel-d-ctx .guide-next-view')
        self.assertEqual(link.get_attribute('data-next-view'), 'containers')
        self.click_and_wait(page, link, self.ACTIVE_TAB_JS, arg='주문 시스템 내부', via_keyboard=True)
        self.assertEqual(self.active_tab(page), '주문 시스템 내부')
        page.wait_for_function(
            "()=>window.__announce.some(t=>t.includes('다른 탭을 선택해 안내 재생을 멈추었습니다'))"
            "&&document.querySelector('#flow-panel-create .flow-guide-btn').getAttribute('aria-pressed')==='false'",
            timeout=12000)
        pressed = page.locator('#flow-panel-create .flow-guide-btn').get_attribute('aria-pressed')
        self.assertEqual(pressed, 'false')
        self.assertEqual(page.locator('#view-breadcrumb .crumb-current').inner_text(), '주문 시스템 내부')
        page.close()
        self.assertEqual(errors, [])

    def test_manual_tab_switch_reconciles_stack(self):
        page, errors = self.load()
        page.locator('#diagrams').scroll_into_view_if_needed()
        # 확대 두 단계 진입 후 직접 탭 선택은 스택을 정리한다(있는 뷰는 잘라내고, 없으면 비운다).
        ctx_frame = page.frame_locator('#diagram-panels iframe[data-view-id="ctx"]')
        ctx_frame.locator('g.node[data-canonical-id="ordering-system"]').click()
        page.wait_for_function("sel=>!document.querySelector(sel).disabled", arg='#diagram-panel-d-ctx [data-expand]')
        self.click_and_wait(page, page.locator('#diagram-panel-d-ctx [data-expand]'),
                            self.ACTIVE_TAB_JS, arg='주문 시스템 내부')
        containers = page.frame_locator('#diagram-panels iframe[data-view-id="containers"]')
        containers.locator('g.node[data-canonical-id="web-app"]').click()
        page.wait_for_function("sel=>!document.querySelector(sel).disabled", arg='#diagram-panel-d-containers [data-expand]')
        self.click_and_wait(page, page.locator('#diagram-panel-d-containers [data-expand]'),
                            self.ACTIVE_TAB_JS, arg='웹 앱 내부')
        self.assertEqual(self.active_tab(page), '웹 앱 내부')
        # 클릭 직후 곧바로 읽지 않고, 스택 정리 결과(경로 1단계만 남음)를 기다린다.
        self.click_and_wait(
            page, page.locator('#diagram-tabs [role="tab"]', has_text='주문 시스템 내부'),
            "()=>{const b=document.querySelectorAll('#view-breadcrumb button');"
            "return b.length===1&&b[0].dataset.crumbView==='ctx';}")
        crumbs = page.locator('#view-breadcrumb button')
        self.assertEqual(crumbs.count(), 1)
        self.assertEqual(crumbs.first.get_attribute('data-crumb-view'), 'ctx')
        # 경로에 없는 뷰로 직접 이동하면 스택이 사라진다(경로가 아니었으므로).
        self.click_and_wait(
            page, page.locator('#diagram-tabs [role="tab"]', has_text='웹 앱 내부'),
            "()=>{const h=document.querySelector('#view-breadcrumb');return !!h&&h.hidden;}")
        self.assertTrue(page.locator('#view-breadcrumb').is_hidden())
        page.close()
        self.assertEqual(errors, [])

    def test_focus_command_restores_only_known_canonical_ids(self):
        page, errors = self.load()
        page.locator('#diagrams').scroll_into_view_if_needed()
        page.wait_for_function(
            "()=>!!document.querySelector('#diagram-panels iframe[data-view-id=\"containers\"]')")
        # 등록된 canonical ID + 카메라 → 정확히 되돌린다.
        page.evaluate('''() => {
          document.querySelector('#diagram-panels iframe[data-view-id="containers"]').contentWindow.postMessage(
            {type:'repo-flowmap-focus',viewId:'containers',canonicalId:'web-app',
             camera:{k:1,tx:120,ty:80}},'*');
        }''')
        # focus 처리가 끝나면 렌더러가 repo-flowmap-state를 알려온다 — 그 목표
        # 상태(선택+카메라 반영)가 기록되었음을 긍정형으로 기다린 뒤 읽는다.
        page.wait_for_function(
            "()=>window.__rfmStates.some(s=>s.viewId==='containers'&&s.selectedId==='web-app'"
            "&&s.camera&&Math.abs(s.camera.tx-120)<0.001)", timeout=12000)
        state = self.frame_state(page, 'containers')
        self.assertEqual(state['node'], 'web-app')
        self.assertAlmostEqual(state['camera']['tx'], 120, places=3)
        # 등록되지 않은 ID로 선택을 지어내지 않는다(null 선택 상태를 유지한다).
        # focus 처리는 항상 상태 알림으로 마치므로, 알림 도착(처리 완료)을 기다린 뒤
        # '변하지 않음'을 읽는다 — 고정 sleep으로는 처리 전 상태를 읽을 수 있다.
        before = len(self.states_for(page, 'containers'))
        page.evaluate('''() => {
          document.querySelector('#diagram-panels iframe[data-view-id="containers"]').contentWindow.postMessage(
            {type:'repo-flowmap-focus',viewId:'containers',canonicalId:'not-in-model'},'*');
        }''')
        page.wait_for_function(
            "(n)=>window.__rfmStates.filter(s=>s.viewId==='containers').length>n", arg=before, timeout=12000)
        state = self.frame_state(page, 'containers')
        self.assertEqual(state['node'], 'web-app')
        page.close()
        self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()
