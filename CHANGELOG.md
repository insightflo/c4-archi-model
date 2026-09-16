# Changelog

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
