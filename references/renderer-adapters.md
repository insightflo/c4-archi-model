# 렌더러 어댑터 가이드

C4는 특정 표기법과 도구에 종속되지 않는다. 이 스킬은 canonical JSON model을 중심으로 두고,
현재 환경과 사용자 요청에 맞춰 다이어그램 출력 형식을 선택한다.

---

## 1. 출력 계층

### 필수 원본

```text
architecture-model.json
```

렌더러가 바뀌어도 유지되는 요소, 관계, View, 근거를 저장한다.

### 기본 다이어그램 소스·렌더러 (archify 가용 시)

```text
<view>.<type>.json    archify JSON IR (View별 파생 source)
<view>.html           인터랙티브 아티팩트 (deliver 확정)
<view>.svg            보고서 임베딩용 정적 추출
```

자세한 계약은 `references/archify-adapter.md`를 따른다.

### 폴백 model-as-code

```text
workspace.dsl
```

Structurizr DSL은 C4 모델의 계층과 View를 표현하고 여러 다이어그램을 한 모델에서 생성하기에 적합하다.
다만 실행 도구 설치를 스킬의 필수 조건으로 만들지 않는다.

### diagrams-as-code 어댑터

```text
Mermaid
PlantUML / C4-PlantUML
D2 또는 Graphviz, 사용자가 지정한 경우
```

이 형식들은 렌더링과 문서 삽입에는 편리하지만, 자체적으로 C4 계층 규칙을 검증하지 못할 수 있다.
따라서 canonical model과 QA 검증을 생략하지 않는다.

### 편집형 출력

```text
Excalidraw
Draw.io
기타 사용자가 지정한 편집형 형식
```

발표와 수동 편집에는 유용하지만 canonical source로 사용하지 않는다.
수동 편집 후 모델과 달라질 수 있으므로 `generated from model` 여부를 표시한다.

---

## 2. 선택 규칙

```text
사용자가 형식을 지정함
→ 해당 형식 + canonical JSON

archify 패키지와 Node 18+가 가용함 (doctor 통과)
→ archify JSON IR 저작·검증·deliver (기본 경로)

C4-aware 렌더러와 검증기가 사용 가능함
→ model-as-code 생성·검증 후 렌더링

일반 다이어그램 렌더러만 사용 가능함
→ canonical JSON에서 source diagram 생성 후 렌더링

렌더러가 없음
→ canonical JSON + source diagram + ASCII 미리보기
```

도구가 없을 때 설치 명령을 자동으로 강요하지 않는다.
사용자가 설치를 요청한 경우에만 현재 운영체제와 환경을 확인한 뒤 안내한다.

archify의 5가지 타입(architecture/workflow/sequence/dataflow/lifecycle)은
시스템 구조·흐름 표현용이다. 목록·절차·비교 같은 정보 그림(인포그래픽)은
C4 View가 아니므로 archify로 강제하지 않는다 (`references/archify-adapter.md` §9).

---

## 3. Archify 어댑터 (기본 경로)

전체 계약은 `references/archify-adapter.md`를 따른다. 요약:

```text
C4 View → archify 타입 매핑
  Context/Landscape/Container/Component/Deployment → architecture
  Dynamic(요청·응답) → sequence, Dynamic(승인·분기·다단계) → workflow

저작: schemas/common.schema.json + 타입 schema 1종 + 예시 1종만 읽는다.
      주요 노드 ≤ 12, quality_profile "showcase",
      관계 라벨은 canonical 관계 설명에서 옮긴다.
      기존 PUML/Mermaid는 통역하지 않고 canonical에서 재저작한다.

검증: validate → 진단(supportedFixes)만 수정 → deliver (exit 0 확인).
      영수증은 qa/archify-*.json 에 보관. 통과 후보는 동결.

추출: scripts/extract_archify_svg.py로 보고서 임베딩용 정적 SVG 생성
      (id 스코핑 + script/foreignObject/외부 URL 검사 + 테마 보존).
```

---

## 4. Structurizr DSL 어댑터

`assets/workspace-template.dsl`을 시작 골격으로 사용할 수 있다.

규칙:

- `model`에 요소와 관계를 한 번 정의한다.
- `views`에는 모델의 일부를 선택한다.
- identifier는 canonical JSON ID와 대응표를 유지한다.
- Container는 Software System 안에, Component는 Container 안에 정의한다.
- View key는 안정적인 영문 ID를 사용한다.
- `autoLayout` 방향은 주요 흐름과 맞춘다.
- 미확인 기술을 임의의 제품명으로 채우지 않는다.
- 렌더링 또는 parser가 있으면 문법 검증 후 전달한다.
- 검증 수단이 없으면 `문법 미검증`이라고 QA 문서에 적는다.

Structurizr는 C4 모델 저자가 만든 reference implementation이지만,
이 사실이 다른 렌더러 사용을 금지한다는 뜻은 아니다.

---

## 5. Mermaid 어댑터

Mermaid의 지원 문법은 실행 환경과 버전에 따라 다를 수 있다.

안전 규칙:

- 현재 환경에서 지원되는 문법을 확인할 수 없으면 일반 flowchart로 C4 타입을 라벨에 명시한다.
- 실험적이거나 특정 renderer 전용 C4 문법을 검증 없이 사용하지 않는다.
- subgraph를 Software System 또는 Container 경계로 사용하되 계층을 섞지 않는다.
- 관계 라벨을 생략하지 않는다.
- 요소 ID는 canonical model ID와 매핑한다.

일반 flowchart fallback 예:

```mermaid
flowchart LR
  customer["Customer<br/>[Person]"]
  subgraph ordering["Ordering System [Software System]"]
    web["Web App<br/>[Container]"]
    api["Order API<br/>[Container]"]
    db[("Order Database<br/>[Container]")]
  end
  customer -->|주문을 생성하고 조회한다| web
  web -->|주문 요청을 전송한다 [HTTPS/JSON]| api
  api -->|주문을 읽고 저장한다 [SQL]| db
```

이 예시는 형식 설명용이며 실제 시스템 사실로 재사용하지 않는다.

---

## 6. PlantUML/C4-PlantUML 어댑터

- 라이브러리 include 경로와 버전을 사용 환경에서 확인한다.
- 외부 include를 사용할 수 없는 환경이면 로컬 의존성을 요구하지 말고 일반 PlantUML로 대체한다.
- canonical model의 element type, name, description, technology를 유지한다.
- 동적 View는 번호가 보이는 Sequence 또는 C4 Dynamic 표현을 사용한다.
- 실제 렌더링 테스트가 없으면 문법 검증 여부를 밝힌다.

---

## 7. SVG/PNG 렌더링

이미지를 생성할 수 있을 때:

- 제목, 유형, 범위, 범례를 이미지 안에 포함한다.
- 한글 글꼴이 실제 렌더링 환경에 있는지 확인한다.
- 글자 깨짐, 잘림, 선 겹침, 범례 누락을 시각 검토한다.
- SVG를 우선하면 텍스트 선명도와 확대가 유리하다.
- PNG가 필요하면 충분한 해상도로 내보낸다.
- 이미지 생성 후 source diagram과 model 파일도 함께 제공한다.

이미지를 직접 확인하지 못했다면 `시각 검토 완료`라고 쓰지 않는다.

---

## 8. HTML 보고서 어댑터

HTML은 canonical source가 아니라 사람이 읽는 최종 진입점이다.
`references/html-output-guide.md`를 따르고, 기본 템플릿은 `assets/html-report-template.html`을 사용한다.

### 필수 출력

```text
index.html
html/report-data.json
```

`report-data.json`은 canonical model의 ID와 View, Evidence Ledger의 Claim·Source ID를 HTML 표시 구조에 매핑한다.
검증 기준은 `references/html-report-data.schema.json`이다.

### 내장 규칙

- 렌더링된 SVG를 우선해 data URI로 내장한다.
- PNG만 있으면 충분한 해상도의 PNG를 내장한다.
- JSON, PUML, DSL, Markdown 같은 텍스트 원본을 접을 수 있는 영역에 내장한다.
- 외부 CDN, 외부 JavaScript, 외부 CSS, 외부 폰트, 원격 PlantUML 서버를 요구하지 않는다.
- 출처 URL은 사용자가 클릭하는 링크로 표시할 수 있지만 페이지 렌더링 자체가 그 URL에 의존해서는 안 된다.
- raw source에서 가져온 HTML을 검증 없이 실행 가능한 DOM으로 삽입하지 않는다.

### 기능

```text
C4 View 탭
확대 / 축소 / 100% / 전체 화면
번호형 Dynamic 흐름
Container·Component 책임 카드
초보자용 용어집 또는 전문가용 리뷰 카드
Evidence Source·Claim Traceability 검색
QA와 package integrity 표시
원본 복사·파일 저장
인쇄 / PDF
```

### 선택적 빌더

`scripts/build_html_report.py`는 Python 표준 라이브러리만 사용한다.
특정 에이전트나 운영체제 경로를 요구하지 않으며, package root와 파일 경로를 인자로 받는다.
빌더를 사용할 수 없는 환경에서는 동일한 template/data 계약으로 다른 파일 작성 수단을 사용한다.

### 실패 처리

- 필수 다이어그램이 없으면 성공 HTML로 위장하지 않는다.
- Evidence Ledger와 HTML의 Source·Claim 참조가 다르면 먼저 수정한다.
- source ID, element ID, View ID가 canonical model에 없으면 FAIL이다.
- 브라우저를 열지 못했으면 시각·상호작용 검사는 `NOT RUN`이다.

---

## 9. 편집형 캔버스

편집형 파일을 생성할 때:

- 각 요소에 canonical model ID를 metadata 또는 링크로 보존한다.
- System Context → Container → Component/Dynamic/Deployment로 이동할 수 있는 링크를 권장한다.
- 자동 생성 영역과 수동 편집 영역을 구분한다.
- 수동 변경을 다시 model에 반영하지 않았다면 drift 가능성을 경고한다.
- 아이콘은 의미를 보조할 뿐 타입과 책임 설명을 대체하지 않는다.

---

## 10. 렌더링 보고

`validation-report.md`에 다음을 기록한다.

```text
Archify availability (doctor): available/unavailable
Archify IR authored: view 목록
Archify validate receipt: pass/fail/not run per view
Archify deliver: exit 0/fail per view
Archify SVG extraction: pass/fail per view
Canonical model schema validation: pass/fail/not run
Structurizr DSL parse: pass/fail/not run
Diagram source syntax check: pass/fail/not run
Image render: pass/fail/not run
Visual inspection: pass/fail/not run
Editable export: created/not requested/not available
HTML report data validation: pass/fail/not run
HTML build: pass/fail/not run
HTML local open: pass/fail/not run
HTML desktop visual inspection: pass/fail/not run
HTML mobile visual inspection: pass/fail/not run
HTML interaction check: pass/fail/not run
Package integrity: pass/fail/not run
```

`not run`은 실패가 아니다. 다만 실행하지 않은 검사를 통과했다고 표현하면 안 된다.
