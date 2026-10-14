# Changelog

## Unreleased — 예제 재구성: 수제 SVG를 실제 렌더러 산출물로 교체

- **배경**: 예제 report-data의 다이어그램 2개(ordering-context·ordering-container)가
  수제 SVG(`examples/ordering-system-{context,container}.svg`)를 assetPath로 써서
  `validate_all`이 RCP-007 2건으로 실패했다(HEAD부터 선재). 예제 HTML도 옛 템플릿
  시점이라 strict 빌드가 이 검증에 막혀 재생성하지 못했다.
- **변경**: 두 뷰를 실제 파이프라인으로 다시 만들었다 — 어댑터 투영(`build_repo_flowmap.py
  --model --view` — 모델 데이터는 그대로 투영, 가상 메타데이터 덮어쓰기 없음) → 렌더러
  HTML `diagrams/<view>.flowmap.html`(화면 원본, iframe srcdoc 임베드) → Chromium
  `exportSvg()` 추출 `diagrams/<view>.flowmap.svg`(printAssetPath) → 실행 시점 영수증
  `qa/repo-flowmap-{validate,build,svg}-<view>.json`. 예제 report-data의 diagrams 2개
  항목(mimeType `text/html`, dataUri는 빌더가 임베드)과 expectedFiles를 새 산출물로
  갈아끼웠다. presentation(안내 문구·nextViewIds·caption·alt)은 기존 내용 유지.
- **수제 SVG 삭제**: 참조가 manifest에만 남아 있어 `examples/ordering-system-context.svg`·
  `ordering-system-container.svg`를 삭제했다.
- **strict 빌드 재생성**: `examples/html-report-example.html`을 `--lenient` 없이 다시
  만들었다(검증 보고서 `qa/html-build-validation.json`). 비교 섹션·비유 대응 표·장치별
  안내·프로필이 포함되고 외부 의존·플레이스홀더 잔류 없다(오프라인 단일 HTML 유지).
- **결과**: `validate_all --root . --data examples/html-report-data.example.json` 전체
  PASS, RCP-007 0건. 재생성 절차는 README '예제 보고서 재생성' 참고. 예제 모델은
  계속 가상 데이터다(mini-example.md 관례 유지).

## Unreleased — W5 D10: 변경 전후 아키텍처 비교 보기

- **비교 산출물**: `scripts/compare_architecture_models.py`가 canonical model 두 개(--before
  --after)를 입력받아 변경 비교 JSON을 별도 산출물로 남긴다(예: `qa/architecture-comparison.json`,
  예시 패키지에서는 `<system>.architecture-comparison.json`). 분류는 요소 추가·삭제·이동
  (parentId 변경)·속성 변경(이름·기술·설명 등 표시 영향 필드), 관계 추가·삭제·방향 변경
  (출발·도착 교체=반전, 한쪽 교체=재연결)이고 모두 ID 일치 기준이다. 원본 모델은 수정하지
  않고, 비교 필드에 claimIds가 없으므로 입력 모델의 근거 연결(MOD-006/011)은 경고로만
  남긴다(과거 스냅샷의 원래 근거장은 비교 범위 밖). 구조·시맨틱 오류는 여전히 차단한다.
- **미확정 대응**: 같은 ID가 서로 다른 대상을 가리킬 가능성이 큰 변화는 미확정으로 표시하고
  확정 분류하지 않는다 — 같은 ID의 type 불일치(요소), 출발·도착이 모두 교체된 관계, 그리고
  이동·재연결 대상의 이전/이후 상위·끝점이 미확정 요소인 경우(사유 전파). 판정 기준은
  스크립트 문서문자열과 SKILL.md에 문서화했다.
- **스키마·검증기**: `references/architecture-model-comparison.schema.json`을 추가하고
  `validate_model_comparison`(CMP-001~008: 통계·스냅샷 존재 규칙·미확정 사유·subtype·
  changedFields·after 측 ID·뷰 포함 대조)를 `c4_validation.py`에 연결했다.
  `build.comparisonPath`를 번들 로드·검증에 포함하고(선택 — 없으면 무변경), 빌더가 비교
  산출물을 하이드레이션에서 그대로 전달한다(새 사실을 만들지 않는다).
- **보고서 보기**: 보고서 템플릿에 '변경 전후 아키텍처 비교' 섹션(장점·비용·위험과 확인 필요
  사이)을 추가했다. 전·후 시점 요약 카드, 통계 문장, 색+기호+한글 라벨 범례(색상만으로
  구분 금지 원칙 유지), 요소·관계 변경 표, 미확정 안내 콜아웃. 표가 완전 목록이고 그림은
  보조다 — 어느 뷰에도 속하지 않은 변경은 '그림 밖'으로 표시되고 표에서 사라지지 않는다.
  기존 뷰 그림을 다시 그리지 않는다(새 렌더러 종류 없음). 비교 데이터가 없는 보고서는
  섹션이 숨겨져 현재와 무변경. 모바일(375px 무변경 확인)·인쇄(행 분할 방지)에서 기존 표
  패턴을 재사용했다.
- **예시**: `examples/ordering-system.architecture-model.previous.json`(개정 0 가상
  스냅샷 — 가상임을 명시)과 이 스크립트로 실제 생성한
  `examples/ordering-system.architecture-comparison.json`을 추가하고 예시 report-data에
  `comparisonPath`·expectedFiles·원본 파일 항목으로 연결했다. 비교 예시는 요소 3추가·2삭제·
  1이동·1변경, 관계 2추가·2삭제·1재연결·1미확정(그림 밖 삭제 요소 포함)을 담는다.
- 문서: SKILL.md Step 10 '변경 전후 비교(선택)' 절과 실행 스크립트 목록,
  `references/html-output-guide.md`(정보 구조·build 경로), `references/validation-checklist.md`
  G 섹션 확인 문구.
- 검증: tests/test_model_comparison.py 19건(분류·미확정 전파·통계·그림 밖·스키마·원본 무변경
  CLI·CMP 검증기 7건·하이드레이션 2건·브라우저 2건: 범례 색+기호·완전 목록 표·모바일 무변경·
  비교 없는 보고서 섹션 숨김). verify_visual_contrast 기본 3한계·고대비 63 PASS 유지(새 칩은
  기존 토큰 쌍 재사용, 본문 텍스트 대비 4.84~5.59). validate_all 예시 RCP-007 2건 기준선 유지.

## Unreleased — W4-d D5: 보고서와 그림이 공유하는 시각 프로필

- **공유 시각 프로필**: 색·글꼴·간격 역할 값(역할 ID = 두 템플릿의 기존 CSS 변수명 그대로)을
  하나의 프로필로 묶어 메인 보고서와 임베드된 그림에 함께 적용한다. 개별 그림의
  light/dark 테마 전환은 새로 만들지 않고 그대로 둔다 — 프로필은 테마별 덮어쓰기로
  테마와 직교한다(렌더더가 테마를 바꾸면 새 테마의 프로필 값을 다시 적용).
- **이름 있는 프로필**: 보고서 상단 바에서 '기본'·'고대비'를 선택한다. 기본 프로필은 빈
  덮어쓰기(현재 값 무변경). 고대비는 D4 검사기 기준을 63역할 모두 통과하도록 맞춘 값
  (기본 팔레트의 한계 3건도 해소). 프로필은 부분 정의다 — 빠진 역할은 템플릿 기본값으로
  보충되고 저장된 원본 프로필을 덮어쓰지 않는다. 사용자 값 편집·임의 저장 UI는 이번
  범위 밖이며, 상태는 세션 메모리만 쓴다(오프라인 단일 HTML·file:// — 새로고침이면 기본).
- **전달**: 보고서가 임베드 렌더더 iframe(srcdoc, 불투명 오리진)에 역할 ID→값 맵을
  postMessage(`repo-flowmap-profile`, roles:{light,dark})로 보내고 렌더더가 자기 CSS 변수에
  반영한다. 임베드·전체 화면 다이어그랬로그(iframe load 때마다 재전송)에 모두 전달된다.
  렌더더는 자신에게 정의된 변수만 받고 모르는 역할은 무시한다(미래 호환). 활성 프로필은
  SVG 내보내기에도 실린다(기본이면 바이트 무변경). 프로필 전환은 재생·카메라·선택·안내
  상태를 건드리지 않는다.
- **한계**: 미리 렌더링된 인쇄 이미지(printDataUri)는 빌드 시점 산출물이라 프로필 반영이
  안 된다 — 프로필을 바꾼 화면과 인쇄물이 다를 수 있다(visual-budgets.md 한계 목록 기록).
- **검사기 연계**: `verify_visual_contrast.py --profile <이름>` 진입점 — 프로필 역할 값을
  템플릿 기본값 위에 덮어쓴 상태로 같은 63역할을 검사한다(빠진 역할 기본 보충, 템플릿에
  없는 역할은 경고 후 무시). 인자 없으면 기존 동작 무변경.
- 문서: `assets/repo-flowmap/references/RENDERER_RULES.md`(프로필 프로토콜),
  `references/visual-budgets.md`(프로필 검사·한계), `references/validation-checklist.md`
  H 섹션 확인 문구, `assets/repo-flowmap/CHANGELOG.md`(포크 기록).
- 검증: tests/test_visual_profile.py 13건(정의 파싱·기본 무변경·역할 실재·부분 보충·고대비
  63 PASS·오류 분기·브라우저 3건: 보고서+임베드+전체 화면 동시 반영·기본 복귀, 테마 전환과
  직교, 모르는 역할 무시·빈 맵 복귀). 기존 안내 재생 연대기 검사 1건은 시각 값만 전달하는
  profile 메시지를 '단계·재생 지시 없음' 조건에서 제외했다(의도와 일치). 전체 unittest
  339 OK(+13) 5 skip, 회귀 15/15, validate_all 예제 RCP-007 2건 기준선 유지.

## Unreleased — W4-c A5: 상위 경계를 유지하는 내부 펼치기

- **안내 정지 사유 귀속 수정(검증 중 발견)**: 전체 화면 다이어그림 로그를 열면 Chrome이 배경을
  교차 없음으로 보아 IntersectionObserver가 '화면 밖' 사유로 안내를 멈추고, 카드 클릭 경로의
  '사용자 조작' 사유를 덮어썼다(네이티브 카메라 iframe이 없는 카드는 클릭 정지가 스킵되기도
  했다). 이제 [data-zoom]/[data-full] 클릭은 그림 종류·뷰와 무관하게 진행 중인 모든 안내를
  '사용자 조작'으로 멈추고, 대화상자가 열려 있는 동안 배경 IO 업데이트는 '화면 밖' 사유로
  처리하지 않는다.

- **연결된 뷰 탐색**: 보고서의 레벨별 보기 전환이 실제 탐색으로 이어진다. 요소 카드와
  그림(대화형 임베드)에서 선택한 요소를 그 요소를 경계로 펼친 더 깊은 구조 뷰로
  들어간다. 대상은 canonical ID와 뷰 포함 목록·parentId 체인(빌더가 뷰마다
  `scopeId`·`scopeChain`을 하이드레이션)으로만 식별한다 — systemContext → container →
  component → code 확대 순서에서 더 깊은 뷰만 후보가 되고, 같은 깊이면 문서 순서,
  더 얕은 확대 단계가 있으면 그것을 먼저 준다. 펼친 뷰가 이 보고서에 없는 요소는
  비활성 단추와 '펼친 View 기록 없음' 안내로 진입 불가를 표시한다(없는 뷰를 지어내지
  않는다). 뷰 안내의 '다음으로 확대할 View'도 같은 체계의 링크가 되고, 이 보고서에
  그림이 없는 다음 뷰는 기존처럼 안내 문구로만 남는다.
- **부모 경로와 복원**: 확대로 떠날 때 그 뷰의 선택 요소(canonical ID)와 카메라를 내부
  스택(브라우저 히스토리와 무관)에 남기고, 그림 탭 위 부모 경로(breadcrumb)에 확대
  경로를 표시한다. 경로 조상을 누르면 한 번에 되돌아가고 렌더러에 선택·카메라를
  정확히 되돌린다. 직접 탭 선택은 스택을 정리한다(경로에 있으면 그 아래만, 없으면
  전체). 탐색 이동은 안내 재생을 정지한다(기존 stopGuides 'tab' 경로 재사용, 자동 재개
  없음). 인쇄에서는 탐색 UI가 나오지 않는다.
- **렌더러 프로토콜 확장**: 렌더러가 선택 변화마다·카메라 확정 뒤(180ms 묶음)
  `repo-flowmap-state`(viewId·selectedId·camera)를 부모에게 알리고, 부모의
  `repo-flowmap-focus`(viewId·canonicalId·camera)가 선택·카메라를 되돌린다.
  canonicalId가 null이면 '선택 없음'으로 되돌리고 등록된 노드 ID만 선택한다 — 없는
  ID로 선택을 지어내지 않는다. 카메라는 기존 메시지와 같은 정확한 변환(moveTo) 경로.
  repoFlowmap.state()에 node가 추가됐다(기존 필드 무변경).
- 문서: `assets/repo-flowmap/references/RENDERER_RULES.md` 프로토콜 문단,
  `assets/repo-flowmap/CHANGELOG.md`(포크 기록), `references/validation-checklist.md`
  G·H 섹션에 탐색·복원 확인 문구.
- 검증: tests/test_report_view_navigation.py(7건 — scopeChain 하이드레이션·부모
  순환 안전, 요소 카드 진입/불가 표시, 2단계 진입 → 한 번에 최상위 복귀 시 선택·카메라
  복원, 다음 뷰 링크 탐색·안내 정지, 직접 탭 스택 정리, focus 프로토콜의 등록 ID만
  선택). 전체 unittest 326 OK(+7) 5 skip, 회귀 15/15, validate_all 예제 RCP-007 2건
  기준선 유지.
## Unreleased — W4-b A1·A8: 구성요소별 비유 대응표, 입력 장치에 맞는 조작 안내

- **A1 비유 대응**: 보고서 데이터 스키마(0.4.0, 선택 필드 추가로 버전 무변경)의
  비유 문장(`analogy`) 옆에 선택적 `mappings`(항목: `{term, modelId, kind, note?}`
  — kind는 element·relationship)과 `limits`(비유가 맞지 않는 범위)를 추가했다.
  단계 설명·요소 설명·용어집 세 표면 모두에서 쓸 수 있고, mappings가 없으면
  기존 데이터·렌더링이 그대로다(스키마·검증기·브라우저 테스트로 증명). 검증기는
  HTML-DATA-023으로 modelId가 kind에 맞는 canonical 등록 ID인지 확인한다
  (미등록 ID·kind 불일치 거부). 빌더는 canonical model에서 이름을 해석해 채운다
  — 관계 대응은 `출발 → 도착` 이름으로 — 비유가 모델 사실을 재정의하지 않게
  한다. 보고서 템플릿은 비유 콜아웃 아래에 최소 대응 표(비유 개념 ↔ 실제
  구성요소 이름+modelId, note, '비유가 맞지 않는 범위' 문장)를 렌더링한다.
  SKILL.md Step 7·10에 작성 규칙(모델 ID로만, 한계 숨기지 않음)을 추가했다.
- **A8 장치별 안내**: 렌더러 하단 캔버스 조작 안내를 주 포인터에 따라 분기한다
  — 기본(마우스+키보드: 드래그·휠·키보드 단축키) / 터치(pointer coarse·hover none:
  한 손가락 드래그·두 손가락 확대) / 키보드 포커스(터치 기기에서 실제 키보드
  입력이 들어오면 키보드 안내 복귀). typed(C4) 모드이 init에서 다시 쓰는 범례도
  같이 분기한다. matchMedia 리스너로 장치 전환(에뮬레이션 포함)마다 문구를
  갱신하고, 단축키가 붙은 줌 버튼 title도 장치에 맞게 바뀐다. 보고서 쪽 그림
  도구는 CSS 미디어쿼리(hover/pointer)로 키보드 전용 안내 문구를 감추고
  원본 그림 프레임의 aria-label도 생성 시점에 장치에 맞게 분기한다.
  **조작 기능 자체는 전 장치에서 불변** — 팬·핀치·휠·탭 선택·키보드 이동·재생
  컨트롤 모두 그대로다(터치 컨텍스트 브라우저 테스트로 확인). reduced-motion·
  print·mobile 기존 처리 및 W3-1 안내 재생 버튼은 무변경이다.
- 문서: `assets/repo-flowmap/references/RENDERER_RULES.md` 조작·편집 규칙,
  `assets/repo-flowmap/CHANGELOG.md`(포크 기록).
- 검증: tests/test_report_analogy_mappings.py(7건 — 스키마 무변경 통과·kind별
  modelId 해석/거부·세 표면 이름 해석·브라우저 렌더링·기존 출력 무변경·예제
  엄격 빌드 치환·자리표시자 부재), tests/test_input_guides.py(7건 — 데스크톱/
  터치 문구 분기·matchMedia 동적 전환·터치 팬/줌/탭 기능 불변·typed 뷰 분기·
  보고서 키보드 문구·프레임 라벨 분기).

## Unreleased — W4-a D2·D6: 모델 범위와 화면 상세도 분리, 표현 축약 내역

- **D2 표시 상세도**: 작성 세션 스키마(`architecture-session.schema.json` 0.4.0, 선택 필드
  추가·버전 무변경 — codeDetails 관례와 동일)에 `presentationDetail`(full/labels/minimal,
  기본 full·생략 가능)을 추가했다. 값은 스키마 enum이 검증하고 `validate_session`이
  SES-005 PASS로 기록한다(없으면 기존 동작 무변경). `repo_flowmap_adapter.project()`가
  `presentation_detail` 인자로 해석한다: labels는 노드 설명(desc)을 종류·기술 요약으로
  바꾸고 단계 부기(note)를 생략, minimal은 desc를 비우고 note·기술(data)도 생략한다.
  라벨(label·call)과 canonical 복제(element·relationship·canonicalStep·view)은 모든 수준에서
  원문 그대로며, 뷰 포함 목록(elementIds·relationshipIds·steps)의 요소·관계·단계는 하나도
  삭제·병합되지 않는다. 빌드 CLI에 `--presentation-detail`이 추가되었고(기본 full,
  legacy --input과 별도 사용 거부), typed 재검증(build legacy 경로·DIA-008 모두)은 스탬프된
  상세도로 재투영해 대조한다. 기본(설정 없음) 출력은 기존과 바이트 수준으로 동일하다
  (HEAD 어댑터 전 뷰 대조로 확인).
- **D6 축약 내역**: 상세도를 낮추면 어댑터가 모든 화면 변경을 flowmap의
  `c4.presentationLog`(detail·counts{elements, relationships, steps{canonical, displayed}}·
  entries[{kind, id, original, displayed, reason}])로 남긴다. id는 canonical 요소·관계·step
  ID라서 독자가 원본 모델로 되짚을 수 있고, 원본 수·표시 수 일치가 미삭제의 기계 증거다.
  kind는 description-shortened/description-omitted/note-omitted/annotation-omitted/
  view-split-proposal이다 — 마지막 것은 visual-budgets.md 경고선(Context ≈10,
  Container ≈14, Component ≈15요소, Dynamic 15단계)을 넘은 뷰에 대한 분리 권고이며 자동
  분리가 아니다. 이름변경(rename)은 이 투영이 만들지 않는다(label === element.name 강제).
  기록 위치를 영수증이 아닌 flowmap JSON로 한 이유: 그림과 함께 배포되어 독자가 바로 읽고,
  DIA-008 재투영 대조에 포함되어 위조되면 실패하며, 영수증의 같은 실행 기록 계약을 유지할
  수 있기 때문이다. 빌드 영수증에는 같은 실행에서 계산된 요약(`presentation`: detail·counts·
  logEntries)만 추가한다(full 빌드 영수증 무변경). Node 검증기(포크)도 상세도별 규칙과
  log 형식·counts를 검사한다.
- 문서: `repo-flowmap-adapter.md` 4장(신규, 이후 장 재번호), `assets/repo-flowmap/SCHEMA.md`,
  `validation-checklist.md` A(SES-005)·C(canonical 재정의 금지)·D(축약 내역 되짚기·뷰 분리
  명시), `visual-budgets.md` 상호 참조, `assets/repo-flowmap/CHANGELOG.md`(포크 기록).
- 검증: tests/test_repo_flowmap_presentation_detail.py(13건) — 기본 바이트 동일·전 뷰 포함
  목록 보존·상세도별 표현·로그 정확성(원본↔표시·이유)·위조 스탬프/표시/counts 거부(Node)·
  세션 스키마 유효/무효/생략·CLI 스탬프·영수증 요약·legacy 재검증·플래그 가드.
  run_regression_tests.py에 presentation-stamp-mismatch(위조 상세도 스탬프 → DIA-008) 추가 —
  전체 unittest 305 OK(+13) 5 skip(3회 연속 안정), 회귀 15/15(+1), validate_all 예제
  기준선(RCP-007 2건) 유지.

## Unreleased — W3-1 A3·A4·A6: 보고서 안내 재생, C4 관계선 진행 표시, 시각 표시·낭독 알림 분리

- **A3 보고서 안내 재생**: 실행 흐름 패널에 '안내 재생' 컨트롤을 추가했다. 개별 그림의 기존
  재생(렌더러 ▶ togglePlay)을 다시 만들지 않고, 보고서가 단계 설명·진행 표시를 갱신하고 같은
  View의 원본 그림(임베드 iframe, 다이어그랬로그 제외)에 새 postMessage `repo-flowmap-step`
  {viewId, stepIndex, requestId}를 보낸다. 렌더러는 setStep 적용 후 `repo-flowmap-step-ack`
  {viewId, requestId, stepIndex, ready, step}로 반영을 알리고, 보고서는 확인 뒤 다음 단계로
  넘어간다(ack 상한 1.5초·준비 재시도 8회·무응답 그림이 있어도 안내가 멈추지 않게 한다).
  시작 전 렌더러 자체 재생과 겹치지 않게 먼저 `repo-flowmap-playback` stop을 보낸다. 단계
  간격은 2800ms — 렌더어 재생 간격(1500ms)은 그림만 볼 때의 값이고, 안내는 단계 설명을 함께
  읽으므로 넉넉히 잡았다. 마지막 단계 후 종료하고, 단계 수동 선택·이전/다음·탭 전환·확대/전체
  화면 조작·인쇄·스크롤로 화면 밖(IntersectionObserver)에 즉시 멈춘다. 다시 시작은 안내 재생
  버튼뿐이다(자동 재개 금지). 전체 화면 다이어그랬로그는 기존 렌더러 재생이 이미 있으므로
  안내 대상에서 제외했다(범위 최소화). steps가 없는 흐름에는 컨트롤을 내놓지 않고, 1단계뿐인
  흐름에도 두지 않는다.
- **A4 C4 관계선 진행 표시**: 번들 렌더러의 구조계 뷰(path.c4-edge)에서 선택 단계 관계선 위에
  작은 진행 표시(g.c4-flow-mark — 같은 경로의 오버레이 조각이 출발 → 도착으로 흐름 + 정적 방향
  화살촉)를 얹었다. 원본 선 색·굵기·의존/실현 점선 보존, CSS 애니메이션 기반(reduced-motion에서
  대표 위치 고정), 상태색은 flowmap 스키마의 steps[].state 기록 시에만(failover/blocked=빨강,
  cond=호박색, blocked는 기존 62% 절단 비유), export SVG에서는 표시 제거·기존 선만 유지.
  시퀀스 뷰는 기존 번호·활선 강조를 그대로 둔다. 세부 기록은
  assets/repo-flowmap/CHANGELOG.md, 프로토콜·표시 규칙은 references/RENDERER_RULES.md.
- **A6 시각 표시·낭독 알림 분리**: 진행 숫자 readout('3 / 7 단계')은 시각 전용(aria-hidden)으로
  두고, 별도 낭독 알림 영역(role=status, aria-live=polite, 시각적으로 숨김)이 단계 제목이 바뀌는
  의미 있는 변화에서만 문장을 교체한다. 숫자만 바뀌는 갱신으로 연속 낭독을 유발하지 않는다.
  수동 단계 선택도 같은 영역이 단계 제목으로 알린다(기존 알림 기능 유지·내용 강화). 안내
  시작/종료/중단 사유도 이 영역에만 알리고, 렌더어 stopnote(role=status)와 이중 낭독이 없게
  안내 경로에서는 렌더러 재생을 조용히 정지한다.
- 검증: tests/test_report_guided_playback.py(9건, 실제 Chrome) — 진행 표시 방향·export 제외·
  reduced-motion 고정·기록 상태 재색·시퀀스 무표시, 안내 재생의 단계·그림(iframe 2곳) 동기·
  종료, 수동 조작·탭 전환·확대 정지, 무응답 그림 무경유 진행, 재개 금지, A6 알림/숫자 readout
  분리(MutationObserver), 1단계 흐름 컨트롤 없음, 인쇄 시 컨트롤 숨김.

## Unreleased — W2 A10·D8: 연결처럼 보이는 근접선 검사, 그리는 순서 기반 라벨 가림 검사

- 브라우저 검수 스크립트의 기하 검사(GEOMETRY evaluate)에 A10·D8 두 검사를 같은 공유 기하
  기반(모델 근거 관계 끝점·점/사각형 거리·문서순서)으로 추가했다. 렌더러(template.html)와
  기존 경로·관계 ID·좌표는 바꾸지 않았다 — 순수 검사 추가다.
- A10 `nearConnectionMimics`: 관계선(c4-edge/c4-message-line)의 표본점과 관계 라벨이 실제
  연결 대상이 아닌 노드(.c4-body)에 2.5px 이내로 닿아 연결처럼 보이는 곳을 보고한다.
  모델 근거 예외만 허용한다: 실제 양끝 노드(flow-data step의 from/to, 없을 때만 경로 끝점
  스냅), 같은 노드 쌍 관계의 겹치는 공유 복도(2px), 배지 점유 지점(13px), 라이프라인은
  애초에 검사 대상이 아니고 노드 rect는 실제 .c4-body만 본다(component mark 삐져나옴
  제외).
- D8 `labelOcclusions`: 라벨 배경(rect.c4-label-bg)·라벨 글자(c4-message-label)가 문서
  순서에서 나중에 그려진 노드와 기하적으로 겹치면 가림 후보로 보고한다. 배경 경계
  겹침(soft-border)·노드 표식 겹침(mark)·실제 가림(hard-text — 라벨 면적 30% 이상이
  불투명 노드 안)을 구분하고, 화면 DOM과 내보내기 SVG(exportSvg)에서 같은 로직으로
  확인한다(내보내기가 순서를 바꾸면 structure-mismatch로 실패).
- 검사 결과는 check_repo_flowmap_browser.py의 새 레코드 `near-connection-mimics`·
  `label-occlusion`로 FAIL을 낸다. 임계값·예외 근거는 GEOMETRY 안 주석·상수로 문서화했다.
- 검증: tests/test_repo_flowmap_geometry_checks.py — 조립 SVG 단위 검사(각 위반·각 예외
  개별 확인), 데모 6뷰×2폭 기준 오탐 0, 렌더링 후 노드 이동 변이 감지(A10)·라벨 덮기 변이
  감지(D8 hard-text 화면+내보내기). 검사기 전체 실행: 6개 데모 뷰 × 1440/360에서 두 검사
  전부 PASS(빈 결과).

## Unreleased — D1·D3·D4·D9·A7: 출력 용도 규격, 글자 굵기 일치, 밝기 대비, SVG 접근성, 보이지 않을 때 재생 정지

- `references/visual-budgets.md`에 출력 용도별 규격(문서용 HTML 보고서·발표용 슬라이드·인쇄용 A4의
  권장 캔버스·글자 단계·글자 하한 11px·안전 여백·인쇄 최소 글자 5pt 공식)과 “슬라이드로 옮길 때
  글자 축소 금지 — View 분리 또는 확대 경로 제공” 이식 원칙을 추가했다. 수치는 렌더러 실측에서
  온 권장선이며 외부 픽셀값을 강제하지 않는다.
- 번들 repo-flowmap 템플릿의 C4 텍스트 굵기를 단일 맵(`C4_TEXT_WEIGHT`)으로 통일해 캔버스 측정과
  화면 표시가 같은 굵기를 쓰게 했다. c4-kind는 측정을 700으로, c4-target·c4-uncertain은 표시를
  700으로 맞췄다(강조 가치). 정적·실제 Chrome 검사를 tests/test_repo_flowmap_text_weight.py에
  추가했다. 세부 기록은 assets/repo-flowmap/CHANGELOG.md.
- export 안전 여백은 6개 표준 뷰 실측(좌 40–48 · 상 약 17 · 우 40–49 · 하 50–62px)에서 이미
  충분해 코드 변경 없이 근거를 visual-budgets.md에 남겼다. macOS 한국어 폴백 폰트는 한글 전진
  폭이 굵기와 무관(400=700)하고 라틴·숫자만 넓어지는 것을 확인해 혼합 문자열 넘침 위험의
  실제 경로를 기록했다.
- 역할·실제 배경별 밝기 대비 검사기를 scripts/verify_visual_contrast.py로 추가했다. 렌더더
  밝음·어두움 테마와 보고서 밝은 테마의 CSS 변수를 파싱해 WCAG 상대 휘도로 계산하며,
  반투명 색은 배경 합성 후 계산하고 기준 미달 시 실패한다(63 역할 검사).
  미달 해소 최소 수정: 렌더더 미확정 색 #b16616 하드코딩 → --color-uncertain 변수
  (패널 위 4.06/3.90 → 6.17/6.86), 관계선 기본색 --color-edge 1.71/2.29 → 3.51/3.49,
  STALE 라벨 #8a6d3b → --warn-tx. 보고서는 --soft #7f8998→#626e7d, --accent
  #e63946→#c1121f(전 사용처가 글자), warn 라벨 #a07020→--gold, 내비 그룹 라벨
  #a0a8b5→--soft. 이중 표시로 유지되는 경계적 표시 3종(선택 테두리·조건 분기 선·
  유령 관계선)은 visual-budgets.md에 한계로 기록했다. 기준·결과표·한계는
  references/visual-budgets.md “밝기 대비 기준”, 검사 항목은 validation-checklist.md H.
  단위·실행 테스트는 tests/test_visual_contrast.py.
- 번들 repo-flowmap 렌더러의 화면 지도·내보낸 SVG에 접근성 이름 구조(role="img"·고유
  `<title id>`/`<desc id>`·`aria-labelledby`)를 추가했다. ID는 viewId(legacy는 동작 ID) 기준
  접두사로 만들어 여러 그림을 한 문서에 합쳐도 충돌하지 않으며, 원본 viewId(점 포함)는
  보존하고 ID로 쓸 때만 sanitize한다. 포스터·인쇄·개별 저장 SVG는 같은 구조를 그대로 가지고,
  `export_repo_flowmap_svg.py`가 이 구조를 검사한다(`validate_svg_accessibility` — 기존
  `validate_svg`와 수제 예제 SVG에는 소급 적용되지 않는다). 세부 기록은
  assets/repo-flowmap/CHANGELOG.md.
- 재생(▶ 순서대로 보기)이 화면 밖·숨김·제거 상태에서 계속 도는 것을 막았다. 탭/임베드
  숨김(`visibilitychange`), 그림 화면 밖(`IntersectionObserver` 선택 API), iframe 제거
  (`pagehide`), 보고서 다이어그랬로그 닫힘(`repo-flowmap-playback: stop` postMessage)에서
  정지하고 정지 사유를 패널에 안내한다. 자동 재개는 어떤 경로에도 없다 — 사용자가 재생
  버튼으로 다시 시작한다. 움직임 줄이기 설정에서는 자동 진행 대신 수동 단계 이동 안내를
  준다. 검증은 tests/test_repo_flowmap_a11y_playback.py(실제 Chrome).

## 0.10.0 — repo-flowmap typed-view fork (적용 후보, 2026-09-15)

- 0e2aef4 기준. Archify 우선/repo-flowmap 폴백 및 기존 native CLI/legacy 기능을 유지한다.
- 번들 repo-flowmap template 자체에 구조/클래스/시퀀스/배치를 추가한다. 별도 엔진은 추가하지 않는다.
- 선택 codeDetails/codeRelation 및 Claim 검증, authoritative projection DIA-008,
  native 구현 해시 RCP-010을 추가하고 기존 provenance/strict 게이트를 유지한다.
- 생산자/보고서/SVG 추출의 입력·출력·영수증 충돌을 첫 쓰기 전에 거부한다.
- 마지막 참가자의 긴 자기호출을 실제 glyph bbox와 native SVG export 범위에 포함한다.
- iframe native 카메라 bridge, 좁은 화면, 선택 브라우저 추출 및 재현 검사 명령을 추가한다.
- 가상 샘플 generator와 실행 로그를 남기는 테스트를 추가한다. 모든 환경의 가독성/file://
  또는 인쇄 완전성을 보장하지 않는다. 각 실행 PASS/FAIL/NOT_RUN을 별도 보고한다.
- 포크 범위/원출처/라이선스 미확인 제한/3-way update 정책을 VENDORED.md에 명시한다.
- 화살표 연결점을 drawio 원칙을 참고해 독립 구현: C4 고유 슬롯·양끝 방향·카드 회피 검사·자기 연결·경로 실패 경고. 세부 기록은 assets/repo-flowmap/CHANGELOG.md와 assets/repo-flowmap/references/RENDERER_RULES.md.
- 보고서 템플릿 다이어그램 iframe sandbox를 3곳(패널·의미 강조 폴백·전체화면 다이얼로그)에서
  `allow-scripts allow-downloads`로 확장했다. 같은 원점 허용(allow-same-origin)은 넣지 않아
  부모 문서 접근 차단은 그대로고, 실제 격리 검증에서 parent 접근이 계속 SecurityError로 거부됐다.
  이 다운로드 결함은 이번 통합 검증에서 독립적으로 발견해 수정했다.
- 전체화면 다이얼로그를 `showModal()` 후에 `srcdoc`을 넣는 순서로 바꿔, 열기→닫기→다른 View의
  반복·연속 열기에서도 iframe 기하가 0×0으로 남지 않는다.
- native 렌더러가 숨은 상태에서 초기화돼 bbox가 0×0 또는 이전 값이어도 초기 렌더·ResizeObserver·
  내보내기 직전에 실제 도형 bbox를 다시 측정해(c4MeasureExtent) 기존 범위에서 확장만 적용한다.
  세부 기록은 assets/repo-flowmap/CHANGELOG.md.
- 통합 검증(2026-09-16): 단위 232건 전부 통과(0 skip), 회귀 14/14, 실제 file:// Chromium
  48케이스 중 44건의 실제 다운로드 성공(1440/360 두 폭). 전체 증거는 /tmp/c4-integrated-final.

## 0.9.0 — 2026-09-14

### 외부 리뷰(ChatGPT) 반영 — 검증 강제화와 인쇄 무결성

문서·설계 감사만 수행한 외부 리뷰의 지적을 코드 대조로 검증해 반영/반박했다.

반영 (P0-1, P0-2, P0-3, P2):

- **다이어그램 입력 교차검증**: `scripts/validate_diagram_inputs.py` 신설. archify IR·flowmap의
  노드·관계·Dynamic step 순서를 canonical model과 이름 기준 대조 (DIA-001~007). 렌더러 로컬 ID
  변환과 무관하게 검사한다. 지금까지는 에이전트 규율에만 의존했다.
- **렌더러 영수증 강제**: `scripts/validate_render_receipts.py` 신설. 렌더 경로별 영수증 존재,
  성공 기록, 산출물 해시/크기 일치를 강제 (RCP-000~008). 미지 렌더러 계열 에셋(RCP-007)은 0.7.0의
  수제 렌더러 금지 규칙의 기계 검사다. 두 검증기 모두 `validate_all.py`에 연결되고 회귀 픽스처
  3케이스(변조→탐지)가 추가됐다 (총 14/14 PASS).
- **인쇄·PDF 무결성**: repo-flowmap iframe은 인쇄에서 캔버스가 잘리는 결함을 실측으로 확인.
  `diagrams[].printAssetPath`(정적 SVG)를 신설해 화면은 iframe, 인쇄는 SVG로 분리 출력. 저작
  시점 SVG 추출 절차(headless 브라우저 `getBBox` 직렬화 또는 UI 내보내기)를 어댑터 문서에 추가.
  단일 파일 이동·file:// 렌더링은 실측 PASS로 유지된다.
- **환경 진단**: `scripts/doctor.py` 신설 — Python/Node/archify 가용성·번들 repo-flowmap 상태와
  이 환경에서 선택될 렌더 경로를 요약한다 (`--json` 지원).

반박/연기 (P1 — 대표 픽스처 기반 시각 QA 코퍼스):

- 밀도 예산(`references/visual-budgets.md`), archify 내장 게이트(label-route-clearance,
  desktop-readability ≥6px, corridor 충돌), flowmap anti-slop 검사가 이미 각 렌더 단계에서
  측정값으로 동작한다. 한글 장문·복잡 연결 코퍼스는 렌더러 자체 품질 영역으로, 스킬 과제로
  별도 로드맵 항목으로 보류한다.

## 0.8.0 — 2026-09-14

### 번들 폴백 렌더러 repo-flowmap (archify 미가용 시 기본)

- repo-flowmap(JSON 검증기 + 고정 렌더러 + 인터랙티브 단일 HTML 빌더)을 `assets/repo-flowmap/`
  으로 포함했다. Node 18+ 표준 라이브러리만 사용, 별도 설치 불필요. 출처·동기화 규칙은
  `assets/repo-flowmap/VENDORED.md`.
- Step 8 우선순위 체인을 6단으로 확장: archify → **repo-flowmap(번들)** → Structurizr →
  Mermaid/PlantUML/D2 → source+텍스트. archify 설치 동의가 없거나 불가능하면 번들 repo-flowmap,
  Node 자체가 없을 때만 Structurizr 체인으로 하락.
- `references/repo-flowmap-adapter.md` 신설: C4 View → flowmap 매핑, ID 대응·meta 규칙,
  validate/build 명령과 영수증(qa/repo-flowmap-*.json), 보고서 embed 계약, 한계(정적 SVG 없음,
  임베드 드래그 제한).
- 보고서 템플릿이 text/html 다이어그램을 `sandbox="allow-scripts"` iframe으로 렌더링하도록 확장
  (다이어그램 카드 + 전체화면 다이얼로그 + 인쇄 CSS). 빌더는 기존 data URI 경로를 그대로 사용
  (mimetypes가 .html → text/html 해석). SVG 위생 검사는 SVG에만 스코핑 유지.
- renderer-adapters: 출력 계층·선택 규칙·내장 규칙·렌더링 보고 항목에 repo-flowmap 추가.
  즉석 커스텀 렌더러 금지는 유지되며 repo-flowmap은 규정된 렌더러로 명시.

## 0.7.0 — 2026-09-14

### 수제 렌더러 허점 봉합 (2026-09-14 papercompany 산출물 회귀 방지)

- 증상: archify가 설치되지 않은 환경에서 실행 에이전트가 폴백 체인도 아닌 즉석 작성
  커스텀 SVG 렌더러(`custom-deterministic-svg/1`)를 만들어 써서 1200×2641px 기형
  lane 레이아웃 다이어그램을 산출했다.
- Step 8: archify 미가용 시 사용자에게 설치를 제안하고, 동의를 받으면 에이전트 skills
  디렉터리에 설치 후 `doctor` 재판정으로 기본 경로를 쓰도록 변경. 동의가 없을 때만
  폴백 체인(3~5)으로 하락.
- 즉석 작성 커스텀 SVG·이미지 렌더러 사용을 Validation failure로 명시 (Step 8 + §6).
- `references/archify-adapter.md`: 미가용 시 설치 제안·표준 설치 위치 절차 추가,
  금지 목록에 수제 렌더러 대체 명시.

## 0.6.0 — 2026-09-02

### Archify 기본 다이어그램 경로 (참고: tt-a1i/archify 2.17, Cocoon-AI/architecture-diagram-generator, antvis/Infographic)

- 다이어그램 저작·렌더링 기본 경로를 archify(JSON IR → 결정적 검증 → 자가완결 인터랙티브 HTML)로
  지정했다. `references/archify-adapter.md`에 C4 View → archify 타입 매핑, canonical 요소 →
  컴포넌트 타입(역할별 고정 색상 계승) 매핑, IR 저작 계약, validate/deliver 사이클과 영수증
  보관 규칙을 정의했다.
- Node 18+와 archify 패키지(`bin/archify.mjs`)가 가용할 때만 기본 경로를 쓰고, 미가용 시
  기존 폴백 체인(Structurizr → Mermaid/PlantUML → ASCII)을 그대로 유지한다. 임의 설치 금지,
  에이전트 독립성 유지.
- `scripts/extract_archify_svg.py`를 추가했다. deliver 산출물에서 보고서 임베딩용 정적 SVG를
  추출하며, 고유 루트 id로 CSS를 스코핑해 보고서 문서로 스타일이 새어나가지 않게 하고,
  테마 변수를 SVG 루트로 옮기며, script/foreignObject/외부 URL 위생 검사와 @keyframes 제거를
  수행한다. 실제 archify 2.17 산출물로 동작 검증(923 CSS 규칙 중 SVG 관련 153규칙 스코핑 보존,
  클래스 100% 커버, XML 유효).
- Step 8 우선순위, Step 14 출력 트리(IR + HTML + SVG, qa/ 영수증), 검증 실패 규칙(deliver
  exit≠0, 동결 후보 재편집, 추출 SVG 위생), 렌더링 보고 항목을 archify 계약에 맞게 갱신했다.
- 기존 PlantUML/Mermaid 원본은 archify IR로 통역하지 않고 canonical model에서 재저작하는
  규칙과, 목록·절차·비교 같은 정보 그림(인포그래픽)은 archify로 강제하지 않는 경계 규칙을
  추가했다 (archify 원조 프로젝트 Cocoon-AI/architecture-diagram-generator와 정보 그림 엔진
  antvis/Infographic의 용도 구분 참고).

## 0.5.0 — 2026-09-01

### Scene-frame reader experience (참고: 2026-08-28 온보딩 「아키텍처 그림, 문서 쉽게 만들기 — C4 · ADR · arc42」 장면 프레임 리포트)

- `references/scene-frame-reporting.md`를 추가해 검증된 장면 프레임형 독자 경험(한눈 요약,
  독자 계약, 장면 목차·점프, 근거 인용 병렬, 증거 체인 종합, 상황별 시나리오, 검증 로그 공개,
  한계와 불확실성)을 C4 보고서 규범으로 일반화했다.
- `validate_html_text`가 로컬 상대 참조(src/href/poster)의 파일 존재와 문서 내 앵커 대상을
  검사한다(HTML-STATIC-005/006). 참조가 전혀 없는 문서는 통과이며, 참조하는데 대상이
  없으면 strict build를 중단한다. 2026-09-01 manual-onboarding 사고(배포본 HTML이 없는
  frames/*.jpg를 참조해 장면 이미지 7장 전부 404, 기존 QA 통과)의 재발 방지.
- `validate_html_assets.py`와 `build_html_report.py`, 패키지 entryPoint 검사에 base_dir을
  전달해 발행 직전과 패키지 검증에서 동일한 참조 무결성 검사를 수행한다.
- 초보자용 권장 문서 구조와 HTML 권장 정보 구조에 한눈 요약·독자 계약·장면 목차·
  상황별 시나리오·증거 체인 종합 슬롯을 추가했다.

## 0.4.0 — 2026-08-10

### Correctness and traceability

- `architecture-session.json`을 추가해 독자 모드와 분석 범위 Profile을 아키텍처 사실에서 분리했다.
- `evidence-ledger.json`을 추가해 Source Snapshot, Claim, 근거 locator, 충돌, 사용 위치를 독립 관리한다.
- `coverage.json`을 추가해 확인한 영역, 현재 질문과 관련된 미확인, 범위 밖 미확인,
  다음 확대 후보와 종료 판정을 `PASS / PASS_BOUNDED / REQUEST_CHANGES / NOT_RUN`으로 기록한다.
- Canonical model에서 `writingMode`와 Source Register를 제거하고, 아키텍처 사실과 표현 설정을 분리했다.
- HTML 표시 데이터가 canonical 이름·유형·기술·책임을 재정의하지 못하도록 ID 참조형 계약으로 변경했다.
- Dynamic View를 여러 개 지원하도록 `flows[]`와 canonical dynamic step ID 매핑을 추가했다.

### Executable validation

- JSON Schema 검사뿐 아니라 C4 부모 계층, 관계 endpoint, View scope, Dynamic 순서,
  근거 Claim, Source Snapshot, Coverage 완료 판정, 이해도 Gate와 HTML 참조를 실제 코드로 검사한다.
- 빌더는 strict validation을 먼저 실행하며 오류가 있으면 HTML 생성을 중단한다.
- 잘못된 부모, 없는 endpoint/View 참조, 비연속 Dynamic 순서, 미등록 Source,
  HTML 사실 재정의, 위험한 SVG가 반드시 거부되는 회귀 테스트를 추가했다.
- 스킬 패키지 자체의 파일 목록, SHA-256, 버전, frontmatter, 금지 파일을 검사하는
  `validate_skill_package.py`를 추가했다.
- 검증 스크립트 실행 자체가 `__pycache__`를 패키지에 남기지 않도록 bytecode 생성을 억제했다.

### Comprehension and delivery

- 초보자용 30초 Gate와 전문가용 5분 Gate를 독립 `human-understanding.json`으로 기록한다.
- 실제 사용자 검토와 persona simulation을 구분하고, simulation을 사용자 테스트로 표현하지 못하게 했다.
- Source Snapshot, 시각 예산, 분석 Profile, 이해도 Gate 가이드를 추가했다.
- 최종 패키지에 `HANDOFF.md`, hash-locked output manifest와 브라우저용 단일 HTML을 포함하는 절차를 정리했다.
- `.git`, 캐시, 데이터베이스, 백업 파일 등 런타임 퇴적물이 스킬 패키지에 들어가지 않도록 검사한다.

## 0.3.0 — 2026-08-10

- 최종 기본 진입점을 외부 런타임 의존성 없는 단일 `index.html`로 정의했다.
- 초보자용/전문가용 모드에 맞춘 HTML 읽기 순서와 설명 카드 규칙을 추가했다.
- C4 View 탭, 확대·축소·전체 화면, Dynamic 단계, 요소 책임 카드, 근거 검색,
  QA, 원본 JSON·PUML·DSL·Markdown 열람을 포함한 HTML 템플릿을 추가했다.
- `html-report-data.json` 템플릿과 JSON Schema를 추가했다.
- canonical model, source register, evidence, View ID, element ID, 예상 파일 목록을
  교차검사하고 SVG/PNG 및 텍스트 원본을 내장하는 표준 라이브러리 기반 빌더를 추가했다.
- Desktop·Mobile·인쇄·오프라인·패키지 무결성 검증 절차를 스킬 워크플로에 통합했다.
- 실행 가능한 Ordering System 예제 모델, 다이어그램, report data, 완성 HTML을 추가했다.

## 0.1.0 — 2026-08-10

- `c4-archi-model` 초기 버전.
- 작업 전 초보자용/전문가용 모드 확인, 근거 추적, canonical model 우선 생성,
  C4 View 분리, 특정 LLM·에이전트 비종속 규칙을 정의했다.
