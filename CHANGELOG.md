# Changelog

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
