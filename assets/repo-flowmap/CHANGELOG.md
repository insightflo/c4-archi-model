# 로컬 포크 변경 — 2026-10-15 (W5-b: 스테이지 리사이즈가 확대 배율을 리셋하지 않는다)

- 창 크기·설명 패널 접기 등으로 스테이지 크기가 바뀔 때마다 ResizeObserver가
  c4ReadingView()를 다시 호출해 사용자가 직접 올린 확대를 최대 100%인 읽기 배율로
  되돌리던 것을 고쳤다. 이제 C4 뷰의 ResizeObserver 콜백은 측정(c4MeasureExtent)만
  다시 한다. 사용자가 설정한 배율은 자동으로 바꾸지 않는다(자동 재개 금지와 같은
  원칙) — 창이 바뀌어도 배율을 유지하고 잘린 부분은 드래그로 탐색한다. C4가 아닌
  분기(fitFlow/fitAll 재맞춤)는 원본 동작을 그대로 둔다.
- c4ReadingView의 초기 읽기 배율 상한을 1 → 1.2로 완화해 전체 맞춤(fitAll, maxK 1.2)과
  정렬했다. 자연 크기보다 화면이 넓은 작은 그림은 최대 120%로 읽기 시작한다. 이
  호출은 이제 초기 로드·fonts.ready 시점에만 발생한다. 하한 0.72, 폭<600 k=1,
  '1:1'·'전체' 버튼은 무변경이다.
- 검증: tests/test_repo_flowmap_real_browser.py StageResizeZoomTests — 확대 3회 후
  뷰포트 축소로 스테이지 리사이즈를 유발해도 camera.k 유지(수정 전 실측 2.197 →
  0.898 리셋, 수정 후 2.636 유지), 폭 넉넉한 화면에서 초기 k=1.2(수정 전 1). 포크
  계약에 따라 RENDERER_RULES.md 조작 문단을 함께 갱신했다.

---

# 로컬 포크 변경 — 2026-10-14 (W5-a: 애니메이션 이동의 카메라 상태 알림)

- moveTo의 animate 분기(CSS 전환에 맡기고 바로 return하던 경로)가 이제 상태 알림을
  예약한다(scheduleStatePush). 줌 100% 버튼·핏·흐름 맞춤·더블클릭 핏처럼 애니메이션으로
  카메라를 바꿀 때도 뷰 값은 호출 시점에 이미 확정되므로, 부모 문서(보고서)가 해당
  카메라를 `repo-flowmap-state`로 받아 내부 펼치기 저장·복원에 반영한다. 기존에는 이
  경로만 알림이 없어 줌 버튼으로 바꾼 카메라가 부모에 전파되지 않았다.
- 즉시 push 경로(비애니메이션 moveTo)와 같은 180ms 디바운스로 묶이므로 두 경로가
  겹쳐도 중복 알림이 무해하다. 단독 실행(window.parent===window)에서는 pushState가
  아무 것도 보내지 않는다(기존 동작 유지).
- 검증: tests/test_report_view_navigation.py의 two_level 카메라 복원 테스트가 줌 버튼
  경로에서 부모 기록(camera.k 증가) 도착을 기다린 뒤 복원 카메라를 비교한다 —
  전체 파일 3회 통과. 포크 계약에 따라 RENDERER_RULES.md 상태 알림 문단을 함께 갱신했다.

---

# 로컬 포크 변경 — 2026-10-14 (W4-d: 공유 시각 프로필 메시지)

- 부모 문서(보고서)와 색·글꼴·간격 역할 값을 공유한다(D5). 부모의
  `repo-flowmap-profile`(roles:{light:{역할:값},dark:{…}}) 메시지를 받아 현재 테마의 역할 값을
  html 요소 인라인 CSS 변수로 덮어쓴다. 역할 ID는 이 템플릿의 기존 CSS 변수명 그대로고,
  이 문서에 정의되지 않은 역할은 무시한다(미래 호환). 값은 실제 색·글꼴·간격 값만 허용한다.
- 기존 light/dark 테마 전환(#theme 버튼·prefers-color-scheme)은 그대로 작동한다 — 테마를
  바꾸면 새 테마의 프로필 값을 다시 적용한다(프로필과 테마는 직교). 빈 맵은 기본 복귀
  (덮어쓰기 전부 해제)다. 이 메시지는 재생·카메라·선택 상태를 건드리지 않는다.
- SVG 내보내기(serializeCurrentSvg)에 활성 프로필의 역할 값을 실은다 — 스타일시트 복사만으로는
  html 요소 인라인 덮어쓰기가 전달되지 않기 때문이다. 기본 프로필(빈 덮어쓰기)이면 아무 것도
  추가하지 않아 내보내기 바이트가 무변경이다.
- 검증: tests/test_visual_profile.py — 브라우저 3건(보고서+임베드 동시 반영·기본 복귀, 테마
  전환과 직교, 모르는 역할 무시·빈 맵 복귀). 기존 재생·정지·내보내기·reduced-motion·print·
  mobile 동작 무변경(전체 unittest 339 OK 5 skip). 포크 계약에 따라 본 변경기록과
  RENDERER_RULES.md 프로토콜 문단을 함께 갱신했다.

---

# 로컬 포크 변경 — 2026-10-14 (W4-c: 내부 펼치기 상태 교환 메시지)

- 상위 경계를 유지하는 내부 펼치기(A5)를 위해 부모 문서(보고서)와 선택·카메라 상태를
  주고받는다. 렌더러는 노드 선택이 바뀔 때마다, 카메라가 확정된 뒤(드래그·줌·핏 등
  moveTo 호출은 180ms로 묶어서) `repo-flowmap-state`(viewId·selectedId·camera{k,tx,ty})
  를 부모에게 postMessage로 알린다. 단독 실행(window.parent===window)에서는 아무
  메시지도 보내지 않는다.
- 부모의 `repo-flowmap-focus`(viewId·canonicalId·camera) 지시를 처리한다: canonicalId가
  null이면 선택 없음으로 되돌리고, 등록된 노드 ID만 선택하며(NODE에 없는 ID로 선택을
  지어내지 않는다), 유한수 카메라는 기존 moveTo 정확한 변환으로 적용한다. 이 지시는
  재생을 시작하지 않는다. 초기 렌더 뒤에도 현재 상태를 한 번 알려 부모가 초기 선택·
  카메라를 알 수 있게 했다.
- `window.repoFlowmap.state()`에 `node`(현재 선택 canonical ID 또는 null)를 추가했다.
  기존 필드는 무변경이고 legacy(비-typed) 입력도 같은 경로를 쓴다(viewId는 null).
- 검증: tests/test_report_view_navigation.py — 선택 푸시·복귀 시 선택/카메라 복원,
  등록되지 않은 canonicalId 무시, 보고서 탐색 전체. 기존 재생·정지·내보내기·
  reduced-motion·print·mobile 동작 무변경(전체 unittest 326 OK 5 skip). 포크 계약에
  따라 본 변경기록과 RENDERER_RULES.md 프로토콜 문단을 함께 갱신했다.

---

# 로컬 포크 변경 — 2026-10-14 (W4-b: 입력 장치별 조작 안내 문구)

- 캔버스 조작 안내를 주 포인터에 따라 분기했다(A8). 조작 기능(드래그 팬·휠 줌·
  핀치·탭 선택·키보드 이동·재생 컨트롤)은 전 장치에서 그대로 두고 문구만 바꾼다.
  측정은 `matchMedia('(pointer: coarse)')` 또는 `('(hover: none)')` — 주 포인터가
  coarse면 터치 문구(한 손가락 드래그 · 두 손가락 이동 / 두 손가락 벌리기·오므리기
  확대)만 보여주고 마우스/휠·hover·키보드 전용 문구(`드래그로 이동`·`휠 확대/축소`·
  `0/F/1`·`← → 단계 이동`)는 감춘다. 실제 키보드 입력이 들어오면
  (`data-keyboard-active`) 터치 모드에서도 키보드 안내를 다시 보여준다.
- 범례 행은 `data-guide`(mouse/touch/key) 속성으로 표시하고 `html[data-input-guide]`
  로 가시성을 제어한다. typed(C4) 모드이 init에서 다시 쓰는 범례도 같은 속성으로
  분기한다. 상단 힌트 문구도 같은 기준으로 재작성되고, 단축키가 붙은 줌 버튼
  title(`전체 맞춤 (0)` 등)도 터치에서는 단축키 없는 문구로 바뀐다.
- matchMedia 리스너로 장치 전환(데스크톱↔터치 에뮬레이션)마다 문구를 갱신한다.
  reduced-motion·print·mobile 기존 처리 및 안내 재생 버튼 체계는 무변경이다.
- 검증: tests/test_input_guides.py — 데스크톱/터치 문구 분기, 터치에서 마우스·
  키보드 전용 문구 부재, matchMedia 동적 전환(CDP 터치 에뮬레이션 토글),
  터치 컨텍스트에서 팬·줌·탭 기능 불변, typed 뷰 분기. 포크 계약에 따라 본
  변경기록과 RENDERER_RULES.md 조작·편집 규칙을 함께 갱신했다.

---

# 로컬 포크 변경 — 2026-10-14 (W4-a: 표시 상세도 검증, 축약 내역 검증)

- typed-view 검증기(`scripts/validate_flowmap.mjs`)에 표시 상세도 `c4.presentationDetail`
  (full 기본·생략 / labels / minimal) 검사를 추가했다. Python 어댑터의 표시용 투영 규칙을
  그대로 반영한다: full은 노드 `desc`가 canonical 설명 그대로, labels는 종류·기술 요약
  (`종류: <유형>[ · 기술: <기술>]` — 같은 TYPE_LABELS·기술 결합 규칙을 JS로 미러링),
  minimal은 빈 문자열이어야 한다. labels/minimal에서 단계 `note`는 null, minimal에서는
  `data`도 null이어야 한다(시퀀스 조건 prefix 규칙은 full에서만 적용).
- 축약 내역 `c4.presentationLog` 형식을 검사한다: reduced 상세도에서는 필수이고 detail이
  스탬프와 일치해야 하며, counts.elements의 canonical/displayed가 실제 노드 수와 같아야
  하고(미삭제 증거), counts.relationships는 양쪽이 같아야 하며, counts.steps.displayed가
  표시 단계 수와 같아야 한다. 각 entry는 알려진 kind(description-shortened·
  description-omitted·note-omitted·annotation-omitted·view-split-proposal)·canonical id·
  이유 문구를 갖는다. full 입력에 presentationLog가 있으면 거부한다(기본 무변경).
- 렌더러(template.html)는 바꾸지 않았다 — desc/note/data 생략은 기존 선택 필드 경로로
  이미 안전하다. legacy(비-typed) 입력 검증은 무변경이다.
- 검증: tests/test_repo_flowmap_presentation_detail.py — 전 데모 뷰(7종) labels/minimal
  통과, 상세도 위조(desc 되돌리기·note 잔존·log 삭제·full+log·counts 축소) 거부,
  minimal data 잔존 거부. 기본(full) projection 바이트 동일성은 HEAD 어댑터 대조로 확인.

---

# 로컬 포크 변경 — 2026-10-14 (W3-1: 관계선 진행 표시, 단계 지시 메시지)

- 구조계 뷰(class·structure·deployment, `path.c4-edge`)의 선택 단계 관계선 위에 진행 표시
  (`g.c4-flow-mark`)를 얹었다. 같은 경로를 그리는 오버레이 조각(`.c4-flow-dash`, pathLength=100,
  dasharray `7 93`)이 출발 → 도착 방향으로 흐르고(c4-flow-dash 키네임, dashoffset −7→−93),
  대표 위치(58%)에 접선 방향 화살촉(`.c4-flow-head`)을 남겨 움직임을 끈 화면에서도 방향을 읽는다.
  원본 선의 색·굵기·의존/실현 점선(marker·dasharray)은 그대로 둔다.
- 상태색은 flowmap 입력 스키마가 정의하는 `steps[].state`가 기록되었을 때만 바뀐다:
  failover·blocked=빨강(--stop), cond=호박색(--warn-bd). blocked는 기존 62% 절단 비유
  (BLOCK_CUT)와 같은 비율까지만 흐른다(c4-flow-dash-blocked, −7→−62). 표준 projection은
  구조계 뷰에 이 필드를 만들지 않으므로 기본 accent색이 보통이다. 범례에 상태줄은 실제
  기록된 상태만 나온다. 시퀀스 뷰(이미 번호·활선 강조 있음)에는 표시를 두지 않는다.
- `prefers-reduced-motion` 두 블록 모두에 진행 표시 고정 규칙을 추가했다(조각 58%·차단 45%
  고정, 애니메이션 none). 기존 "대표 프레임 한 장" 원칙과 같은 방식이고, 기본 규칙을 첫
  reduced-motion 블록보다 앞에 두어 문서 순서로 재정의가 이기는 기존 패턴을 유지했다.
- 부모 문서 프로토콜에 `repo-flowmap-step`(viewId·stepIndex·requestId)를 추가했다. 받으면
  렌더러 자체 재생을 조용히 정지하고(안내 문구 없음 — 안내 상태는 부모가 알린다) setStep을
  적용한 뒤 `repo-flowmap-step-ack`(viewId·requestId·stepIndex·ready·step)로 응답한다.
  임베드가 아닐 때(window.parent===window)는 ack를 보내지 않는다. 이 메시지로 재생이 시작되지
  않는다(자동 재개 금지 유지).
- 내보내기(serializeCurrentSvg)에서 `g.c4-flow-mark`를 클론에서 제거해 정적 저장에는 기존
  관계선만 남긴다. 단계 강조(hot)는 한 장으로 읽히는 정적 스타일이므로 기존 동작을 유지했다.
- 검증: tests/test_report_guided_playback.py — 활성 선만 표시·정방향 흐름(dashoffset 단조 감소)·
  화살촉 위치/각도, export에서 표시 제거·의존/실현 점선 보존, reduced-motion 고정(−58px),
  기록 상태 재색·blocked 62%·범례, 시퀀스 무표시, 보고서 안내 재생(단계·그림 동기, ack, 수동
  조작·탭 전환·무응답 그림, 재개 금지, 1단계 흐름 컨트롤 없음).

---

# 로컬 포크 변경 — 2026-10-14 (저장 SVG 접근성 이름·설명, 보이지 않을 때 재생 정지)

- 화면 지도와 내보낸 SVG가 같은 접근성 이름 구조를 공유한다. `renderMap`이 뷰·동작 전환 때마다
  SVG 첫 자식 `<title id>`/`<desc id>`를 갱신하고 루트에 `aria-labelledby`로 이름을 연결한다.
  ID는 `rfm-<sanitize(viewId|flowId|all)>-title/-desc`로 만들어 서로 다른 그림을 한 문서에
  합쳐도 이름 참조가 충돌하지 않는다. 원본 viewId(점 포함)는 데이터로 보존하고 ID로 쓸 때만
  sanitize한다. desc 문장은 View의 question·description(legacy는 summary)을 잇고 없으면
  기본 문구로 떨어진다. 화면 role은 기존 조작 모드 관리(`applyMapFocusModel`)가 맡고,
  `serializeCurrentSvg`는 클론에 `role="img"`을 고정해 포스터·인쇄·개별 저장 어디서든
  이름·설명이 유지되게 했다(전체화면 다이어그랬로그는 iframe DOM을 그대로 쓰므로 자동 해결).
- `export_repo_flowmap_svg.py`가 추출 SVG의 접근성 구조(role="img", title/desc id,
  aria-labelledby 연결·ID 고유성)를 `c4_validation.validate_svg_accessibility`로 검사한다.
  기존 `validate_svg` 동작과 수제 예제 SVG에는 소급 적용되지 않는다.
- 재생 제어 확장: 재생 중 화면이 숨겨지면(`visibilitychange`) 정지하고, `IntersectionObserver`
  (선택 API)로 그림이 화면 밖이거나 임베드가 숨겨지면 정지하고, `pagehide`/`beforeunload`에서
  타이머를 정리한다. 보고서 다이어그랬로그가 닫힐 때 `repo-flowmap-playback: stop` postMessage로
  정지한다('start'는 없다 — 자동 재개 금지). 다시 보이거나 다시 열어도 재생은 사용자 버튼으로만
  시작되고, 정지 사유가 패널 안내(`.stopnote`)로 남는다.
- 움직임 줄이기(`prefers-reduced-motion`) 사용자가 재생을 누르면 자동 진행 대신 수동 단계
  이동 안내를 보여주고, 재생 중 설정이 켜지면 즉시 정지한다. 기존 reduced-motion CSS
  (대표 프레임 고정)과 어긋나지 않게 표시 전환은 여전히 CSS가 처리한다.
- 검증: tests/test_repo_flowmap_a11y_playback.py — exportSvg XML 구조·ID 비충돌(점 포함 viewId),
  legacy 동작 전환 갱신, 실제 export 실행의 게이트 통과/위반 감지(mutated template),
  visibilitychange·IntersectionObserver·postMessage stop 정지와 재개 금지, reduced-motion
  에뮬레이션, 보고서 다이어그랬로그 닫힘→임베드 정지·재오픈 유지.

---

# 로컬 포크 변경 — 2026-10-14 (역할별 밝기 대비 기준)

- 미확정(unresolved) 표시색을 테마 무관 하드코딩 `#b16616`에서 `--color-uncertain` 변수로
  옮겼다(밝음 `#8a4d0f` · 어두움 `#d9964a`). c4-uncertain 텍스트(12px 굵게)가 패널 배경에서
  4.06/3.90 → 6.17/6.86, 미확정 경계선은 캔버스에서 3.62/4.20 → 5.49/7.39. 주황 계열 경고
  성격과 굵기 700(D3 맵)은 유지했다.
- 관계선 기본색 `--color-edge`를 `#aeb6b0`/`#46534c` → `#737d77`/`#616f66`으로 최소 조정했다
  (캔버스 위 1.71/2.29 → 3.51/3.49, 비텍스트 기준 3.0 충족). 화살촉 폴백·범례에도 쓰이는 색이라
  기본색 자체를 맞췄고, 유령선의 45% 불투명도 렌더링은 이중 표시 근거와 함께 한계로 기록했다.
  구분선(장식)·정방향 관계선과의 위계는 유지된다.
- STALE 라벨 `.fstale b` `#8a6d3b` → `var(--warn-tx)`(틴트 합성 배경 위 3.97/3.28 → 6.75/9.86).
  STALE 배지(흰색 on #8a6d3b, 4.85)와 테두리는 그대로다.
- 검사기·기준·테스트는 스킬 루트에 있다: scripts/verify_visual_contrast.py,
  references/visual-budgets.md “밝기 대비 기준”, tests/test_visual_contrast.py.

---

# 로컬 포크 변경 — 2026-10-13 (측정·표시 글자 굵기 일치)

- 텍스트 굵기의 단일 원천으로 `C4_TEXT_WEIGHT` 맵을 두고, 캔버스 측정(`c4Lines`)과 화면 표시(`c4Text` 인라인 font-weight)가 모두 이 맵에서 굵기를 얻게 했다. `c4Block`/`c4Lines`의 bold 불리언 인자를 cls 기반 시그니처로 바꿔 측정과 표시가 어긋날 여지를 구조적으로 제거했다.
- 과거 불일치 3종을 맞췄다. `c4-kind`는 표시 700 유지·측정 400→700, `c4-target`·`c4-uncertain`은 측정 700 유지·표시 400→700(CSS 클래스 정의 추가). c4-title 700/700, c4-id·c4-tech·c4-desc·c4-member 400/400 등 기존 일치 쌍은 그대로다. class 모드 속성·메서드 머리글(`c4-kind`)도 함께 일치된다.
- 긴 이름은 기존처럼 줄바꿈·상자 확대 우선이며 자르는 경로는 없다(정적 검사로 유지).
- 검증: 맵↔CSS↔전 호출처 시그니처 정적 검사와 실제 Chrome 검사(계산 font-weight=맵, 같은 굵기 캔버스 측정과 렌더 길이 일치, 내보낸 viewBox 안전 여백)를 tests/test_repo_flowmap_text_weight.py에 추가했다.
- 확인된 폰트 사실: macOS 한국어 폴백(Apple SD Gothic Neo)은 한글 전진 폭이 굵기와 무관하고(400=700) 라틴·숫자만 약 6% 넓어진다. 때문에 불일치의 실제 넘침 위험은 ID·기술명 등 혼합 문자열에서 발생했다. 굵기 통일이 이 경로를 닫는다.

---

# 로컬 포크 변경 — 2026-09-16 (화살표 연결점 보완)

- drawio의 면 연결점·양끝 방향 원칙을 참고해 독립 구현했다. 외부 소스나 라우터를 복사한 이식은 아니다.
- C4 단일 연결에는 중점 투영, 여러 연결에는 면 전체의 고유 슬롯을 적용했다. 비-C4 비율 슬롯과 경로는 유지한다.
- 경로 탐색에 중간 좌표를 추가하고, 가까운 카드의 간격에 맞춰 여유 공간과 끝 구간을 조정한다. 자기 연결도 직각 경로 탐색을 사용한다.
- 선 분산이 끝 방향이나 카드 회피를 깨면 검증된 원래 경로를 유지한다. 양끝 방향을 무시하는 Z자 대체 경로를 제거했다.
- 안전한 경로를 찾지 못하면 관계 ID를 포함한 한국어 경고를 화면과 내보낸 SVG에 표시한다. 관계 설명표는 보존한다.
- 번호를 선 위에 안전하게 놓지 못하면 번호와 관계 식별 정보를 설명 목록으로 옮기고 사유를 표시한다. 좁은 배치 화면이나 자기 연결에서 그림 전체가 사라지던 문제를 수정했다.
- 검증 항목: 네 면의 고유 슬롯, 16가지 면 조합, 가까운 카드, 다중·왕복·자기 연결, 기존 비-C4 경로 보존, 실제 Chrome 경고·SVG 영역·관계 수 검사. 선 두께·화살촉 전체 충돌과 모든 배치의 무겹침을 보장하지는 않는다.
- C4 경로 탐색에서 캔버스 밖의 음수 좌표 격자점을 후보에서 제외하고, 분산 후 안전성 검사를 통과하지 못하면 분산 전 경로로 되돌린다. 그래도 못 그리면 카드를 관통하는 대체 경로를 만들지 않고 해당 선을 비우고 관계 ID 경고를 남긴다.
- 숨은 iframe에서 초기화되면 bbox가 0×0 또는 이전 값(1416px)으로 읽힌다. 초기 렌더·ResizeObserver·SVG 내보내기 직전에 c4MeasureExtent로 실제 도형 bbox를 다시 측정해 기존 범위에서 확장만 하고, 경로를 다시 계산하거나 관찰 대상 stage 크기를 바꾸지 않는다. 숨은 패널 내보내기와 새 다이얼로그 내보내기가 바이트 단위로 같았다(공개 후 폭 1450, 내보내기 오른쪽 끝 1418).
- 통합 검증(2026-09-16): 밀집 양방향 행렬은 두 폭(1440/360)에서 요구된 모든 경로(7/8/8)를 그려야 하며 6/6 통과, 경고 행은 전체 관계 ID를 표시하고 다운로드 SVG는 viewBox 안에 있다. 전체 증거는 /tmp/c4-integrated-final.

---

# 로컬 포크 변경 — 2026-09-15 (extension v1)

- 기존 template renderMap에 structure/class/sequence/deployment를 추가했다.
- deployment의 logical-placement 표시 계약: 원래 경계·논리 요소·관계 유지, 경계 머리글 라우팅, 실제 인스턴스 배치가 아님을 화면/SVG에 명시한다. 물리 모드 제한은 유지한다.
- interaction 조건을 원문 보존 note 접두어로 표시하고 Node에서도 검증한다. decision/failure/recovery는 계속 거부한다.
- 카메라/지도/직각 라우팅/flow 목록/상세 패널/legacy 편집/테마/SVG를 유지한다.
- 입력/출력 별칭 사전 차단과 typed native 검증, 긴 한국어 bbox 및 iframe 지원을 추가했다.
- 출처·라이선스 제한·정식 포크 유지보수 규칙은 VENDORED.md, 원본 파일 지문은 UPSTREAM-HASHES.json.

---

## 아래는 보존한 upstream 변경 이력

# 변경 기록

## 렌더러 — 선 읽기 개선

다이어그램 기법 모음집의 검증된 카드 5종을 렌더러에 반영했다. 스키마 변경은 `state` 계열 하나뿐이고
나머지는 기존 `flowmap.json` 그대로 동작한다.

### 화살촉 (context-stroke)
- 색깔별 마커 3벌(`ar` / `ar-back` / `ar-self`)을 **1벌로 합쳤다.** 촉이 `fill:context-stroke`로
  자기를 부른 선의 색을 따라간다(SVG 2). 선 종류를 늘릴 때 마커를 같이 늘릴 필요가 없어졌다.
- `currentColor`는 대안이 아니다 — 마커는 자기 트리의 색을 보므로 선 색이 전달되지 않는다.
- `fill:var(--edge); fill:context-stroke;` 두 줄로 쓴다. 뒤 선언을 모르는 엔진은 그 줄만 버리고
  앞 값을 쓰므로, 미지원 환경에서 촉이 **검게** 칠해지는 대신 선 색 근사치로 남는다.
  내보낸 SVG를 어디서 열지 알 수 없으므로 이 이중 선언이 필수다.

### 교차 홉
- 레인 분리로도 남는 교차에서 **덜 중요한 선만 반원(r=9)으로 넘어간다.** 기준선은 진행(정방향)
  경로이며 반환·자기호출만 그 위를 넘는다.
- 끝점을 공유하는 접합부는 교차로 세지 않는다. **교차는 홉, 연결은 점**이라 T자에서 오독이 없다.
- 부푸는 방향을 화면 기준으로 고정했다(가로선은 위, 세로선은 오른쪽). 진행 방향에 따라 반원이
  뒤집히면 한 그림 안에서 홉이 위아래로 섞여 읽힌다.

### 평행 가닥
- 같은 직선을 26px 이상 함께 지나는 선들을 6px씩 어긋난 평행 가닥으로 분리한다.
  겹쳐 그리면 세 개가 들어가도 맨 위 한 줄만 보인다.
- 복도 안에서 순서를 바꾸지 않는다 — 들어온 쪽·나갈 쪽의 위치로 한 번 정하고 끝까지 유지한다.
- 포트에 물린 첫·끝 구간과 사용자가 직접 지정한 연결(`manual`)은 밀지 않는다.
  현재 라우터는 대개 스스로 벌려 놓으므로 이 단계는 남는 겹침만 받아 내는 안전망이다.

### 선의 상태 — `steps[].state`
- `failover`(장애) · `blocked`(차단) · `cond`(조건 분기) 3종과 짧은 `stateLabel`을 추가했다.
  화면 규칙은 [`references/RENDERER_RULES.md`](references/RENDERER_RULES.md), 값의 뜻은
  [`SCHEMA.md`](SCHEMA.md)에 있다.
- 죽은 길을 지우지 않는다. `blocked`는 62%에서 끊고 남은 구간을 옅은 점선으로 남겨
  "원래 가려던 곳"을 보여준다.
- validator가 값·내부 처리 단계 금지·`stateLabel` 12자·`state` 없는 단독 라벨을 거부한다.
- 상태를 쓴 동작에서만 캔버스 범례에 줄이 붙고, 내보낸 SVG가 그 범례를 들고 나간다.
- 단계 번호는 X·분기 라벨을 피해 앉는다(배지 배치 후보에 상태 표시를 먼저 넣는다).
- 상태 표시도 카드 자리를 피한다 — 기준 지점(장애 50% · 분기 34%)에서 조금씩 벌려 빈자리를 찾는다.
  차단의 X 만은 끊긴 자리를 가리키는 표시라 옮기지 않는다.

### 움직임 최소화
- `prefers-reduced-motion`에서 **그 자리에서 멈추지 않는다.** 멈춘 자리는 사용자마다 다르다.
  `stroke-dashoffset:0`으로 대표 프레임을 못 박아 누가 열어도 같은 한 장이 나온다.
- 멈출 때 무엇이 남는지를 따로 정했다 — 움직임이 말하던 건 "지금 이 단계"이므로 현재 단계를
  실선으로 굳힌다. 나머지 점선은 종류를 뜻하므로 두고, 차단·장애의 대시는 표시 자체라 예외다.

## 배포 정리

### 보안
- `layers[].color`가 SVG 속성 문자열에 이스케이프 없이 들어가 DOM 스크립트 주입이
  가능하던 문제 수정. 렌더러 4곳에 `esc()` 적용 + validator 색상 화이트리스트 추가(이중 방어).
  등급: Medium(공개 배포 전 수정 필수). 산출 HTML 내부 XSS이며 OS 수준 실행은 아니다.

### 검증
- validator가 `null` 항목·비배열 입력에서 TypeError를 내던 문제 수정(`isPlainObject` 가드).
- `layers[].label` 필수 검사 추가. 누락 시 렌더링이 조용히 실패하던 문제 차단.
- `meta.project` / `meta.last_analyzed_commit` 문자열 타입 검사 추가.
- `flows[].id`를 `^[A-Za-z0-9_-]+$`로 제한.
  **하위 호환 없음** — 점·공백·한글이 포함된 기존 ID는 검증에서 거부된다.
  URL 인코딩 대신 제한을 택한 이유: ID는 불변 슬러그 계약이고, 렌더러 2곳 수정 없이
  발생 지점에서 차단되기 때문.

### 렌더러
- `meta.title` / `meta.subtitle` 반영. 미지정 시 기존 문구 유지(기존 산출물 영향 없음).
- `meta.note` / `meta.basis` 생략 시 푸터에 `undefined`가 찍히던 문제 수정.
- `status: "stale"` 표시 추가 — 목록 STALE 배지 + 흐림(opacity .62), 상세 패널에 `stale_reason` 출력.

### 빌드
- `import.meta.dirname` → `fileURLToPath(import.meta.url)` 로 교체(Node 20.11 미만 호환).

### 패키징
- ZIP 경로 구분자를 `\` → `/` 로 정상화. 이전 패키지는 Linux/macOS에서 구조가 깨졌다.
- 프리뷰 HTML은 패키지에 포함하지 않는다. 특정 레포 산출물이라 범용 스킬의 계약이 아니다.

### 배포 중립화
- 브랜드 링크·로고, 내장 개인 이미지 2건, 생성기 주석, 특정 프로젝트 기본 제목 제거.
- 내장 폰트는 **유지**. OFL 1.1 저작권 고지는 재배포 조건이므로 함께 유지하며,
  레이아웃 상수(범례 폭 등)가 이 폰트 메트릭에 맞춰져 있어 제거 시 텍스트가 약 25% 넓어진다.
- 산출물(`flowmap.json` / `flowmap.html`)에는 `meta.project`,
  `meta.last_analyzed_commit`, `nodes[].file`이 남는다. 익명 공유 시 별도 제거 필요.
