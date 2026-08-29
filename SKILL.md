---
name: c4-archi-model
description: |
  설계 문서, 소스 코드, API 명세, 배포 설정과 런타임 자료에서 검증 가능한 근거를 추출해
  C4 기반의 canonical architecture model, 다이어그램, 설명, 근거·Coverage·QA 산출물을 만들고,
  마지막에는 브라우저에서 바로 열 수 있는 단일 HTML 보고서로 조립하는 에이전트 독립 스킬.

  작업 시작 전에 사용자가 이미 명시하지 않았다면 반드시 "초보자용 / 전문가용" 작성 모드를 묻는다.
  작성 모드와 별도로 guided / focus / full 분석 Profile을 관리하며, 같은 아키텍처 사실을
  독자 수준에 맞는 서로 다른 설명 경로로 제공한다.

  사용 트리거:
  - 설계 문서를 C4로 그려 달라는 요청
  - 시스템 구조를 Context / Container / Component / Dynamic / Deployment로 설명하는 요청
  - 코드와 설계 문서를 비교해 아키텍처 문서를 만드는 요청
  - C4 산출물을 HTML로 보기 쉽게 정리하는 요청
  - 초보자용 또는 전문가용 소프트웨어 아키텍처 설명·검토 요청

  특정 LLM, 코딩 에이전트, 운영체제 경로, 전용 메모리, 플러그인 또는 전용 도구 호출 문법에
  종속되지 않는다. 사용할 수 없는 기능은 명시하고, 검증 가능한 텍스트 산출물로 낮춰서 제공한다.
---

# C4 Architecture Model

글로 흩어진 설계 의도와 실제 구현·배포 증거를 **근거가 추적되는 하나의 아키텍처 모델**로 바꾸고,
그 모델에서 C4 View와 독자 수준별 설명을 생성한 뒤 단일 HTML 보고서로 전달한다.

목표는 박스와 화살표를 늘리는 것이 아니다. 다음 질문에 검증 가능한 답을 주는 것이 목표다.

```text
무엇이 시스템 안과 밖에 있는가?
각 실행 단위는 무엇을 책임지는가?
누가 누구에게 어떤 목적으로 요청하거나 이벤트를 전달하는가?
중요한 흐름은 어떤 순서로 진행되는가?
이 설명은 어느 자료에서 확인되었는가?
무엇은 아직 확인하지 못했는가?
독자는 이 구조를 실제로 이해할 수 있는가?
```

---

## 1. 실행 계약

다음 규칙은 선택 사항이 아니다.

1. **독자 모드가 먼저다.** 사용자가 이미 명시하지 않았다면 분석 전에 `초보자용 / 전문가용`을 묻는다.
2. **분석 깊이는 별도 축이다.** 독자 모드와 `guided / focus / full` Profile을 혼동하지 않는다.
3. **Session이 먼저다.** 질문, 목적, 범위, 제외 범위, 종료 조건과 출력 형식을
   `architecture-session.json`에 기록한다.
4. **근거가 모델보다 먼저다.** 읽은 자료를 Source Snapshot으로 고정하고 Claim을 추출한다.
5. **Canonical model이 그림보다 먼저다.** 그림과 설명은 모델의 파생 출력이다.
6. **아키텍처 사실과 표현을 분리한다.** 독자 모드, 비유, 카드 순서는 canonical model에 넣지 않는다.
7. **근거 없는 빈칸을 채우지 않는다.** 문서에 없는 Kubernetes, Cloud, 복제 수, 재시도,
   멱등성, 보안 통제, 팀 소유권을 현재 시스템의 사실로 만들지 않는다.
8. **추상화 수준을 섞지 않는다.** System, Container, Component, Code, Deployment Node를
   한 View에 무분별하게 섞지 않는다.
9. **Coverage를 숨기지 않는다.** 확인한 영역, 관련 미확인, 범위 밖 미확인과 다음 확인 지점을 기록한다.
10. **검증 규칙은 실제로 실행한다.** 체크리스트만 작성하고 `PASS`라고 부르지 않는다.
11. **사람이 여는 최종 진입점은 HTML이다.** 파일 작성이 가능하면 오프라인 단일 `index.html`을 만든다.
12. **오류가 있으면 strict build를 중단한다.** 잘못된 모델을 예쁜 HTML로 포장하지 않는다.
13. **실제 사용자 테스트와 simulation을 구분한다.** persona simulation을 사람 검토라고 표현하지 않는다.
14. **렌더링 실패를 숨기지 않는다.** source diagram만 만들었으면 그림을 완성했다고 말하지 않는다.
15. **특정 에이전트에 종속되지 않는다.** 일반적인 읽기·검색·파일 작성·렌더링·검증 능력만 전제로 한다.

---

## 2. Step 0 — 작성 모드와 분석 Profile 결정

### 2.1 필수 작성 모드 질문

같은 요청 안에 `초보자용`, `전문가용`, `둘 다`가 없다면 다른 본문 분석보다 먼저 다음을 묻는다.

```text
작성 모드를 선택해 주세요.

1. 초보자용 — 용어 풀이, 일상 비유, 단계별 흐름 중심
2. 전문가용 — 경계, 책임, 계약, 품질 속성, 트레이드오프와 위험 중심
```

규칙:

- 이미 모드를 명시했다면 다시 묻지 않는다.
- 사용자의 직업이나 문서 난이도를 보고 모드를 추측하지 않는다.
- `둘 다`면 canonical model과 다이어그램은 하나만 만들고 설명만 두 버전으로 만든다.
- 모드가 확정되기 전에는 파일 목록·경로 확인처럼 가역적인 준비만 한다.

### 2.2 분석 Profile

작성 모드는 **설명 방식**, Profile은 **조사 범위와 종료 조건**이다.

| Profile | 목적 | 기본 산출물 |
|---|---|---|
| `guided` | 전체 구조를 빠르게 이해 | Context, Container, 핵심 Dynamic 1개, 관련 미확인 |
| `focus` | 특정 Container·흐름·배포 환경 집중 | 선택 영역의 Component/Dynamic/Deployment와 근거 |
| `full` | 확인 가능한 전체 범위 조사 | Landscape, 주요 Context·Container·Component·Dynamic·Deployment, 전체 QA |

선택 규칙:

- 사용자가 `전체`, `전부`, `full`을 명시하면 `full`.
- 특정 Container·도메인·흐름만 지정하면 `focus`.
- 별도 지시가 없으면 `guided`.
- 모드를 묻는 상황에서는 Profile도 함께 보여 줄 수 있지만, Profile 미선택만으로 작업을 멈추지 않는다.
- `focus`는 target ID 또는 사람이 이해할 수 있는 명시적 대상이 필요하다.

자세한 기준은 `references/analysis-profiles.md`를 따른다.

---

## 3. 데이터 계약과 진실의 원본

각 파일은 서로 다른 책임을 가진다. 같은 사실을 여러 파일에서 제멋대로 다시 정의하지 않는다.

| 파일 | 책임 | 포함하지 않는 것 |
|---|---|---|
| `architecture-session.json` | 질문, 독자 모드, Profile, 범위, 종료 조건 | 아키텍처 요소·관계 |
| `evidence-ledger.json` | Source Snapshot, Claim, locator, 충돌, confidence | C4 View 레이아웃 |
| `architecture-model.json` | 요소, 관계, View, Dynamic step | 비유, 독자용 문장, Source Register 복제 |
| `coverage.json` | 확인 범위, 미확인, 다음 확인, 완료 판정 | 근거 없는 해결책 |
| `human-understanding.json` | 독자 이해도 Gate 결과 | 실제로 하지 않은 사용자 테스트 |
| `html/report-data.json` | canonical ID에 연결된 표현·탐색 데이터 | 이름·유형·기술·책임 재정의 |
| `manifest.json` | 출력 파일 목록, 역할, SHA-256, 크기 | 아키텍처 주장 |

### Derivation과 Confidence

두 축을 분리한다.

```text
Derivation: explicit / normalized / inferred / unresolved
Confidence: VERIFIED / PARTIAL / DOC_ONLY / UNVERIFIED / CONFLICT
```

예:

```text
설계 문서에 직접 명시됐지만 코드·배포 검증은 없음
→ explicit + DOC_ONLY

코드와 IaC에서 같은 실행 경계를 확인함
→ normalized + VERIFIED

두 자료가 서로 다른 DB 또는 프로토콜을 주장함
→ explicit + CONFLICT
```

확률 숫자는 산정 방법이 없으면 사용하지 않는다.

---

## 4. 전체 워크플로

### Step 1 — Architecture Session 작성

`assets/architecture-session.template.json`을 기반으로 다음을 기록한다.

```text
질문과 목적
작성 모드
분석 Profile
대상 ID 또는 대상 설명
기대 결과
포함 범위와 제외 범위
종료 조건
위험 Trigger
Source Snapshot ID
출력 폴더와 요청 형식
```

입력이 부족해도 아키텍처 사실을 추측하지 않는다. 현재 목적에 영향을 주는 누락은 Coverage에 남긴다.

### Step 2 — 자료 목록과 Source Snapshot 고정

지원 입력:

- Markdown, 텍스트, HTML, PDF, DOCX, Wiki export
- 소스 저장소 또는 일부 디렉터리
- OpenAPI, AsyncAPI, GraphQL schema
- Docker Compose, Kubernetes, Terraform, CloudFormation
- DDL, migration, ERD 설명
- 런북, 로그, trace, 장애 보고서
- 기존 C4, PlantUML, Mermaid, Structurizr, 이미지 다이어그램

각 Source에는 가능한 범위에서 다음을 기록한다.

```text
source ID
자료 이름·위치·종류
버전·날짜·commit SHA 또는 content hash
실제로 읽은 파일·섹션·줄·페이지
확인 가능한 내용
확인할 수 없는 내용
capture 시각
```

변경 가능한 원격 자료나 코드에는 immutable commit 또는 content hash를 우선 사용한다.
`main 브랜치`나 URL만 기록하고 재현 가능하다고 주장하지 않는다.
자세한 규칙은 `references/source-snapshot.md`를 따른다.

### Step 3 — Evidence Claim 추출

원문에서 바로 박스를 만들지 않는다. 먼저 다음 형태의 Claim을 만든다.

```json
{
  "id": "CL-001",
  "statement": "Order API는 PostgreSQL에 주문을 저장한다.",
  "targetIds": ["order-api", "order-database", "api-to-db"],
  "derivation": "explicit",
  "confidence": "DOC_ONLY",
  "supports": [
    {
      "sourceId": "S1",
      "locator": "architecture.md > Persistence",
      "excerpt": null
    }
  ],
  "contradictions": [],
  "usedBy": [
    {"kind": "relationship", "id": "api-to-db"}
  ],
  "notes": []
}
```

- locator는 파일·제목·페이지·줄·심볼 중 실제로 확인 가능한 가장 구체적인 위치를 사용한다.
- 긴 원문을 복제하지 않는다.
- 자료 충돌은 조용히 하나로 합치지 않고 `CONFLICT`와 contradiction으로 남긴다.
- intended, implemented, deployed, observed 구조가 다르면 View 또는 설명에서 분리한다.

### Step 4 — Canonical Architecture Model 생성

`assets/architecture-model.template.json`과 `references/c4-model-guide.md`를 사용한다.

분류 기준:

```text
사람·역할                         → Person
독립적인 사용자 가치를 제공하는 경계 → Software System
실행 애플리케이션·데이터 저장소       → Container
한 Container 내부의 책임 묶음         → Component
클래스·함수·인터페이스·테이블          → Code Element
실행 위치·서버·VM·Cluster·Pod          → Deployment Node
DNS·방화벽·Load Balancer 등            → Infrastructure Node
```

부모 규칙:

```text
Container.parentId       → Software System
Component.parentId       → Container
Code Element.parentId    → Component
Deployment Node.parentId → Deployment Node 또는 null
```

모호한 `service`, `API`, `server`, `engine`, `module`, `platform`, `database`는
이름만 보고 확정하지 않는다. 실행 경계, 저장 책임, 독립 배포, 소유 범위와 상위 경계를 확인한다.

모든 요소와 관계는 최소 한 개의 Claim ID를 가진다. 관계는 다음처럼 작성한다.

```text
나쁨: Web App → API : Uses
좋음: Web App → Order API : 주문 생성 요청을 전송한다 [HTTPS/JSON]
```

### Step 5 — 필요한 C4 View 선택

모든 View를 의무적으로 만들지 않는다. Session 질문에 답하는 View만 만든다.

| 질문 | View |
|---|---|
| 누가 시스템을 쓰고 어떤 외부 시스템과 연결되는가 | System Context |
| 조직 전체 시스템 지도가 필요한가 | System Landscape |
| 시스템 안 실행 단위와 저장소는 무엇인가 | Container |
| 특정 Container 내부 책임은 어떻게 나뉘는가 | Component |
| 요청·이벤트가 어떤 순서로 흐르는가 | Dynamic |
| 실제 환경 어디에서 실행되는가 | Deployment |
| 중요한 구현 세부가 필요한가 | Code, 요청 시만 |

각 View에는 다음을 기록한다.

```text
이 View가 답하는 질문
범위
포함 요소와 관계
의도적으로 보여주지 않는 것
다음 확대 View
근거 Claim
```

Dynamic View의 step ID와 order는 canonical model에 두며, order는 `1..N` 연속이어야 한다.
여러 시나리오는 `flows[]`로 각각 표현한다.

### Step 6 — Coverage 기록

`coverage.json`에 다음을 분리한다.

```text
explored            확인한 영역
unknownRelevant     현재 질문과 관련된 미확인
unknownOutOfScope   현재 범위 밖의 미확인
expansionPoints     다음 확대 후보
boundaries          자료·시간·도구·범위 경계
```

완료 결과:

- `PASS`: 현재 질문과 종료 조건을 충족했고 blocker가 없음.
- `PASS_BOUNDED`: 현재 질문은 답했지만 명시적인 경계가 남음. blocker는 없어야 함.
- `REQUEST_CHANGES`: 핵심 질문 또는 변경 판단을 막는 미확인이 남음.
- `NOT_RUN`: Coverage 검사를 수행하지 않음.

`PASS_BOUNDED`를 전체 아키텍처 검증 완료라고 표현하지 않는다.

### Step 7 — 독자 수준별 설명 작성

자세한 규칙은 `references/writing-modes.md`를 따른다.

#### 초보자용

- 시스템이 해결하는 문제부터 설명한다.
- Context → Container → 핵심 흐름 → 필요한 Component 순으로 확대한다.
- 전문 용어 첫 등장 시 영어 원문, 한국어 뜻, 구체적 예 또는 비유를 함께 준다.
- 각 요소를 `무엇인지 / 왜 필요한지 / 누구와 대화하는지 / 없거나 실패하면 어떤 영향인지`로 설명한다.
- 실제 요청 하나를 번호 순서로 따라간다.
- 쉬운 설명을 위해 사실을 삭제하거나 바꾸지 않는다.
- 설명 구조는 장면 프레임형 독자 경험(한눈 요약, 독자 계약, 장면 목차·점프, 근거 인용 병렬,
  증거 체인 종합, 상황별 시나리오)을 기본으로 제안한다.
  최소 계약은 `references/scene-frame-reporting.md`를 따른다.

#### 전문가용

- 경계, ownership, 책임, public/consumed interface, 상태 소유권을 설명한다.
- 동기·비동기, 계약, 실패 전파, transaction boundary, security/trust boundary,
  scaling unit, observability, deployment evidence를 자료 범위 안에서 분석한다.
- 장점만 쓰지 않고 전제, 비용, 결합도와 risk를 함께 적는다.
- 근거 없는 timeout, retry, idempotency, consistency 보장을 채우지 않는다.

### Step 8 — 다이어그램 Source와 렌더링

`references/renderer-adapters.md`를 따른다.

우선순위:

1. 사용자가 지정한 형식
2. C4-aware model-as-code
3. 현재 환경에서 검증 가능한 diagrams-as-code
4. 렌더러가 없으면 source diagram + 텍스트 미리보기

필수 보존:

- canonical JSON
- View source diagram
- 사람이 읽는 설명
- 렌더링 성공 여부

SVG를 HTML에 넣기 전 script, `foreignObject`, 외부 URL과 위험한 참조를 검사한다.

### Step 9 — Human Understanding Gate

`references/human-understanding-gates.md`를 따른다.

초보자용 기본 질문:

```text
B-01 누가 시스템을 사용하는가?
B-02 시스템은 어떤 문제를 해결하는가?
B-03 주요 실행 단위는 무엇인가?
B-04 핵심 요청은 어디서 시작해 어디서 끝나는가?
B-05 아직 확인되지 않은 것은 무엇인가?
```

전문가용 기본 질문:

```text
E-01 시스템·팀 소유 경계는 어디인가?
E-02 각 Container는 어떤 상태와 책임을 소유하는가?
E-03 동기·비동기 및 계약 경계는 어디인가?
E-04 실패 전파·격리·복구 근거는 무엇인가?
E-05 보안·신뢰·배포·관측성 근거는 무엇인가?
E-06 주요 trade-off와 다음 결정은 무엇인가?
```

실제 사람에게 검토받지 못하면 `persona-simulation`으로 표시한다.
수행하지 못하면 `NOT_RUN`으로 남긴다. 그럴듯한 답을 만들어 `PASS`로 바꾸지 않는다.

### Step 10 — HTML 표시 데이터 작성

`assets/html-report-data.template.json`을 사용한다.

`html/report-data.json`은 다음만 가진다.

```text
canonical model/view/step ID 참조
읽기 순서와 설명 카드
비유와 why-it-matters
View asset 경로
Claim·Coverage issue 연결
원본 파일 목록
```

다음 canonical 사실을 복제하지 않는다.

```text
name
type
technology
description
relationship endpoint
```

HTML 빌더가 canonical model에서 위 사실을 읽어 화면에 채운다.
이 구조가 이름만 같은 가짜 `Payment API`를 슬쩍 끼워 넣는 사소하고도 인간적인 재앙을 막는다.

### Step 11 — Strict validation 실행

HTML 생성 전에 다음 순서로 검사한다.

```text
Session Schema·scope
→ Canonical Schema·C4 semantic
→ Evidence Schema·snapshot·claim
→ Coverage Schema·completion
→ Human Understanding Gate
→ HTML Report Data Schema·canonical reference
→ SVG와 asset
```

권장 명령:

```bash
python3 <skill>/scripts/validate_all.py \
  --root <output-root> \
  --data html/report-data.json \
  --output-json qa/content-validation.json
```

오류가 하나라도 있으면 strict build를 중단한다.
`--lenient`는 진단용 FAIL HTML에만 사용하며 최종 납품으로 취급하지 않는다.

### Step 12 — 단일 HTML 보고서 생성

```bash
python3 <skill>/scripts/build_html_report.py \
  --root <output-root> \
  --data html/report-data.json \
  --template <skill>/assets/html-report-template.html \
  --output <output-root>/index.html \
  --validation-output <output-root>/qa/html-build-validation.json
```

HTML 요구사항:

- 로컬에서 직접 열리는 단일 파일
- 외부 CDN, 웹폰트, 원격 JavaScript, 원격 PlantUML 서버에 의존하지 않음
- SVG/PNG와 텍스트 원본을 내장
- Context / Container / Dynamic / Component / Deployment를 단계별 탐색
- 확대·축소·100% 복원·전체 화면·검색·인쇄 기능
- `이해하기 / 설계 검토 / 근거·QA / 원본 파일` 영역 분리
- 초보자 첫 화면에 내부 ID와 locator를 과도하게 노출하지 않음
- 첫 화면에 한눈 요약(30초 요약)과 독자 계약(표기 읽는 법)을 제공하고,
  장면 목차가 각 프레임·섹션으로 이동함
- 설명 카드에 근거 인용(locator 포함)을 함께 노출하고, 소스 → 결론 증거 체인 종합 표를 제공함
- 검증 로그(View 수·step 순서·참조 무결성·validator 결과)를 본문에서 열람 가능함
- 상황별 "그래서 무엇을 해야 하는가" 시나리오 섹션을 제공함 (초보자용 기본)
- 확인 필요, `PASS_BOUNDED`, `NOT_RUN`, conflict를 숨기지 않음
- 대체 텍스트와 키보드 탐색 제공

기존 HTML에 CSS·JS patch가 누적되어 구조가 불명확해지면 깨끗한 template에서 다시 빌드한다.

### Step 13 — Technical QA와 브라우저 QA

정적 검사:

```bash
python3 <skill>/scripts/validate_html_assets.py \
  <output-root>/index.html \
  --svg <rendered-svg> \
  --output-json <output-root>/qa/html-static-validation.json
```

가능하면 실제 브라우저에서 확인한다.

```text
Desktop 1366~1440px
Mobile 375~390px
한글 깨짐과 글자 잘림
의도치 않은 전체 가로 overflow
다이어그램 탭·확대·전체 화면·검색
인쇄 미리보기
콘솔 오류와 외부 네트워크 요청
```

브라우저를 실행하지 못했으면 `NOT RUN`으로 명시한다.
정적 검사를 브라우저 상호작용 검사라고 부르지 않는다.

### Step 14 — Handoff와 Output Package Manifest

최종 출력 구조:

```text
c4-architecture/
├─ index.html
├─ HANDOFF.md
├─ manifest.json
├─ 00-overview.md
├─ model/
│  ├─ architecture-session.json
│  └─ architecture-model.json
├─ html/
│  └─ report-data.json
├─ diagrams/
│  ├─ 01-system-context.svg
│  ├─ 01-system-context.puml
│  ├─ 02-container.svg
│  ├─ 02-container.puml
│  ├─ 03-dynamic-<scenario>.*
│  ├─ 04-component-<container>.*
│  └─ 05-deployment-<environment>.*
├─ explanation/
│  ├─ beginner.md
│  └─ expert.md
└─ qa/
   ├─ evidence-ledger.json
   ├─ coverage.json
   ├─ human-understanding.json
   ├─ content-validation.json
   ├─ html-build-validation.json
   ├─ html-static-validation.json
   └─ package-validation.json
```

`HANDOFF.md`에는 사람이 먼저 열 파일, 질문, 범위, 결과, 남은 경계와 재검증 명령을 적는다.

```bash
python3 <skill>/scripts/build_output_manifest.py --root <output-root>
python3 <skill>/scripts/validate_package.py \
  --root <output-root> \
  --manifest manifest.json \
  --output-json <output-root>/qa/package-validation.json \
  --update-manifest
```

manifest는 파일 역할, SHA-256과 byte 크기를 기록한다.
Overview에 적힌 파일과 실제 패키지가 다르면 수정한 뒤 다시 생성한다.

---

## 5. C4 핵심 규칙

### 계층

```text
Person
  └─ uses Software System
       └─ contains Container
            └─ contains Component
                 └─ implemented by Code Elements
```

- C4 Container는 Docker 전용 용어가 아니다.
- Component는 보통 독립 배포 단위가 아니다. 독립 배포된다면 Container 후보다.
- Docker, VM, Pod, Cluster는 Deployment View의 실행 위치에 가깝다.
- Component View는 Container 하나를 확대한다.
- Code View는 변경이 잦으므로 가치가 분명한 영역에만 만든다.

### View별 금지 혼합

```text
System Context → Person, Software System
Container      → 대상 System의 Container와 필요한 외부 Person/System
Component      → 선택한 Container의 Component
Deployment     → Container instance, Deployment/Infrastructure Node
```

View가 과밀하면 다른 추상화 수준을 섞지 말고 같은 수준의 여러 View로 나눈다.
`references/visual-budgets.md`의 기준을 경고선으로 사용한다.

### 사실 표기

```text
[확인됨]       explicit 또는 검증된 Claim
[분류됨]       확인된 사실을 C4 개념으로 normalized
[제한적 추론]  근거와 rationale이 있는 inferred
[확인 필요]    unresolved 또는 UNVERIFIED
[충돌]         CONFLICT
```

---

## 6. Validation failure 규칙

다음은 최종 `PASS`를 막는다.

- Container의 parent가 Software System이 아님
- Component가 여러 Container에 걸쳐 있거나 잘못된 parent를 가짐
- 존재하지 않는 relationship endpoint 또는 View 참조
- Dynamic order가 `1..N` 연속이 아니거나 step relationship이 View에 없음
- canonical element/relationship에 Claim이 없음
- Claim이 미등록 Source를 참조함
- Source Snapshot ID가 Session·Model·Ledger에서 다름
- HTML data가 존재하지 않는 model/view/step/claim/issue ID를 참조함
- HTML data가 canonical 이름·유형·기술·책임을 재정의함
- blocker가 있는데 Coverage가 PASS 또는 PASS_BOUNDED임
- 이해도 Gate 질문이 빠졌거나 실제 수행 없이 PASS임
- 필수 파일 누락, manifest hash 불일치, 금지 파일 포함
- SVG에 script, `foreignObject`, 외부 URL이 포함됨
- HTML에 외부 runtime 의존성 또는 미치환 token이 남음
- HTML이 참조하는 로컬 파일이 존재하지 않거나 문서 내 앵커 대상이 없음
  (HTML-STATIC-005 / HTML-STATIC-006)

경고는 숨기지 않는다. 시각 예산 초과, mutable source hash 누락, 브라우저 QA 미실행은
결과와 Handoff에 남긴다.

---

## 7. 에이전트·도구 독립 규칙

해야 하는 것:

- 기능을 자료 읽기, 검색, 파일 작성, 렌더링, 검증 같은 일반 능력으로 표현한다.
- 경로는 사용자 입력 또는 작업 디렉터리 상대 경로를 사용한다.
- 렌더러가 없으면 source diagram과 텍스트 설명으로 낮춘다.
- Python validator는 표준 라이브러리만으로도 동작해야 한다.
- 사용자가 지정한 언어와 출력 형식을 우선한다.

하지 말아야 하는 것:

- 특정 LLM·코딩 에이전트 이름이나 함수 호출을 필수 절차로 넣기
- 특정 OS의 절대 경로를 기본값으로 강제하기
- 이전 대화나 개인 기억을 Source로 취급하기
- 플러그인이나 MCP가 없다는 이유로 전체 작업을 중단하기
- 편집용 그림을 canonical source로 취급하기
- JSON·PUML만 전달하고 사람이 읽을 최종 산출물을 만들었다고 주장하기
- `.git`, cache, database, `__pycache__`, backup 파일을 스킬 또는 출력 패키지에 포함하기

---

## 8. 자료 위치

### 시작 템플릿

- `assets/architecture-session.template.json`
- `assets/architecture-model.template.json`
- `assets/evidence-ledger.template.json`
- `assets/coverage.template.json`
- `assets/human-understanding.template.json`
- `assets/html-report-data.template.json`
- `assets/html-report-template.html`
- `assets/output-manifest.template.json`
- `assets/HANDOFF.template.md`

### 규칙과 Schema

- `references/analysis-profiles.md`
- `references/scene-frame-reporting.md`
- `references/c4-model-guide.md`
- `references/evidence-and-model.md`
- `references/source-snapshot.md`
- `references/writing-modes.md`
- `references/human-understanding-gates.md`
- `references/visual-budgets.md`
- `references/renderer-adapters.md`
- `references/html-output-guide.md`
- `references/validation-checklist.md`
- `references/*.schema.json`

### 실행 스크립트

- `scripts/validate_all.py`
- `scripts/validate_architecture_session.py`
- `scripts/validate_architecture_model.py`
- `scripts/validate_evidence_ledger.py`
- `scripts/validate_coverage.py`
- `scripts/validate_human_understanding.py`
- `scripts/validate_html_report_data.py`
- `scripts/validate_html_assets.py`
- `scripts/build_html_report.py`
- `scripts/build_output_manifest.py`
- `scripts/validate_package.py`
- `scripts/run_regression_tests.py`
- `scripts/generate_manifest.py`
- `scripts/validate_skill_package.py`

### 실행 예시

- `examples/ordering-system.*`
- `examples/html-report-data.example.json`
- `examples/html-report-example.html`
- `examples/mini-example.md`
- `examples/invalid-fixtures/README.md`

---

## 9. 최종 전달 규칙

최종 답변 또는 Handoff에는 다음을 명확히 적는다.

```text
사람이 먼저 열 파일
작성 모드와 분석 Profile
Coverage 결과와 경계
이해도 Gate 방식과 결과
실행한 validator와 결과
브라우저 QA 실행 여부
렌더링되지 않은 형식
남은 관련 미확인
```

검사하지 않은 항목을 `PASS`로 쓰지 않는다. 확인할 수 없는 것은 `확인할 수 없음` 또는 `NOT RUN`으로 남긴다.
