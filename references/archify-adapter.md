# Archify 어댑터 — 다이어그램 저작·렌더링 기본 경로

archify는 typed JSON IR을 결정적으로 검증해 자가완결 인터랙티브 HTML로 컴파일하는
Node.js 렌더러·검증기다. 이 스킬의 다이어그램 저작·렌더링 기본 경로다.
canonical model은 여전히 유일한 진실의 원본이고, archify JSON IR은
View별 파생 source diagram이다 (`.puml`/`.dsl`과 같은 지위).

```text
architecture-model.json (canonical)
  → View별 archify JSON IR (파생 source)
    → validate (기계 영수증)
    → deliver (인터랙티브 HTML 아티팩트 + SHA-256)
    → extract_archify_svg.py (보고서 임베딩용 정적 SVG)
```

---

## 1. 요구 조건과 가용성 판정

요구 조건:

- Node.js 18 이상
- archify 패키지 루트 (`bin/archify.mjs`가 있는 디렉터리)
- 그 외 의존성 설치 불필요 — `validate`와 `deliver`는 로컬에서 결정적으로 동작한다
  (2026-09-02 실측: clone 직후 `node_modules` 없이 validate/deliver 모두 exit 0)

가용성 판정 순서:

```text
1. 사용자가 지정한 경로
2. 이 스킬과 같은 skills 디렉터리의 archify 스킬 (예: ../archify)
3. 일반 스킬 설치 경로 (사용 중인 에이전트의 skills/archify)
4. 찾지 못하면 archify 미가용로 판정
```

판정 명령:

```bash
node <archify-root>/bin/archify.mjs doctor
```

`doctor`가 전 항목 `[ok]`면 사용 가능하다. Node 버전 미달이나 패키지 손상이면
archify 미가용로 판정하고 폴백 경로(Structurizr → Mermaid/PlantUML → ASCII)로 내려간다.

금지:

- 가용성을 확인하지 않고 archify 명령을 문서에 적는 것
- 사용자 동의 없이 임의로 설치(`npx skills add` 등)하는 것
- archify 부재를 작업 실패로 취급하는 것 — 폴백은 정상 경로다

## 2. C4 View → archify 타입 매핑

| C4 View | archify 타입 | 비고 |
|---|---|---|
| System Context | `architecture` | Person은 external 타입 노드 + 라벨로 유형 표기 |
| System Landscape | `architecture` | View가 과밀하면 여러 장으로 분리 |
| Container | `architecture` | 경계 그룹으로 Software System 표현 |
| Component | `architecture` | 대상 Container 하나의 확대 |
| Dynamic | `sequence` 또는 `workflow` | 요청·응답 흐름은 `sequence`, 승인·분기·다단계 절차는 `workflow` |
| Deployment | `architecture` | 소유권·리전 사실이 근거로 있을 때만 `deployment-ownership` 프로파일 |
| Code | 요청 시만 | 일반적으로 archify로 만들지 않는다 |

타입이 모호하면 안내 명령의 판정을 참고한다:

```bash
node <archify-root>/bin/archify.mjs guide "<시나리오 설명>" --json
```

## 3. 요소 → archify 컴포넌트 타입 매핑

archify는 역할별 고정 색상 체계를 쓴다 (Cocoon-AI/architecture-diagram-generator에서
계승). 색은 타입 선택의 결과일 뿐이고, 타입은 canonical 분류에서 온다.

| canonical 요소 성격 | archify `type` | 변형 |
|---|---|---|
| Web SPA, 모바일 앱, 데스크톱 UI | `frontend` | 기본 |
| API 서버, 백엔드 서비스, 워커 | `backend` | 핵심 경로면 `emphasis` |
| RDBMS, 캐시, 객체 저장소 | `database` | 기본 |
| 클라우드 인프라, CDN, 로드밸런서 | `cloud` | 기본 |
| 방화벽, 인증, 게이트웨이 보안 통제 | `security` | `security` 변형 |
| 메시지 브로커, 이벤트 버스, 큐 | `messagebus` | 기본 |
| 외부 SaaS, 제3자 시스템, Person | `external` | 기본 |

규칙:

- Person을 `frontend`로 만들지 않는다. `external` + 라벨에 `[Person]` 표기.
- 미확인 기술을 타입 근거로 추측하지 않는다. 저장 책임이 확인된 것만 `database`.
- 브랜드 표시는 실제 제품명을 지칭할 때만 canonical 내장 ID를 `brand`에 넣는다.
  흔한 역할명("database")으로 브랜드를 추론하지 않는다.

## 4. IR 저작 규칙

읽기 예산 — archify 패키지 안에서 다음만 읽는다:

```text
schemas/common.schema.json
선택한 타입의 schemas/<type>.schema.json 1종
examples/의 대응 예시 1종
```

renderer·validator 소스, 테스트, 벤치마크는 진단에 실패한 뒤에만 연다.

저작 계약:

1. **canonical ID 대응**: 노드·참가자 ID는 canonical element ID와 대응시키고
   대응표를 IR `meta` 또는 세션 기록에 남긴다.
2. **노드 예산**: 주요 노드 최대 12개. 초과하면 View를 나눈다
   (`references/visual-budgets.md` 경고선과 같은 방향).
3. **관계 라벨은 의미 데이터**: canonical 관계 설명("주문 생성 요청을 전송한다 [HTTPS/JSON]")을
   라벨로 옮긴다. 라벨이 겹치면 위치·경로·간격을 먼저 조정하고, 양 끝점이 이미 의미를
   완전히 함의할 때만 생략한다.
4. **`meta.quality_profile: "showcase"`** 를 기본으로 한다. 사용자가 밀도 높은
   전체 지도를 요청한 경우에만 `standard`.
5. **좌표를 산문으로 계획하지 않는다**: 자동 레이아웃으로 시작하고,
   `via`/`channelX`/`channelY`/`labelAt`은 진단이 요구할 때 한 번에 하나만 추가한다.
6. **한국어 저작**: 본문·라벨은 한국어로 쓴다. 단 `meta.locale`은 `en`/`zh-CN`만 지원하므로
   생략하고, 뷰어 UI(버튼·메뉴)가 영문으로 표시됨을 결과 보고에 밝힌다.
7. **기존 다이어그램 원본은 기계 변환 금지**: 입력에 PlantUML/Mermaid 원본이 있어도
   archify IR로 통역하지 말고 canonical model에서 새로 저작한다. 위상만 참고한다.
8. **`meta.visual_preset` 기본 생략** (기본 `classic`). `meta.subtitle`도 기본 생략.
9. **애니메이션은 요청 시만**: `meta.animation: "trace"`는 사용자가 데모·발표를
   요청할 때만 켠다.

## 5. 검증·납품 사이클

각 View 후보마다:

```bash
# 1) 저작 직후와 수정마다
node <archify-root>/bin/archify.mjs validate <type> <candidate.json> \
  --quality showcase --json

# 2) 통과하면 최종 납품 (인터랙티브 HTML 확정)
node <archify-root>/bin/archify.mjs deliver <type> <candidate.json> \
  <output.html> --quality showcase --json
```

규칙:

- `validate` 영수증은 9개 artifact check가 모두 보고되고 오류·경고가 0이어야
  showcase 통과다. 4개 기본 검사만 있는 영수증은 통과가 아니다.
- 검증 실패 시 진단의 `subject`만 보고, `evidence`를 확인하고, `supportedFixes`에서
  하나를 골라 수정한다. 연속 2회 개선이 없으면 사실대로 미해결로 보고한다.
- `deliver` exit code가 0이 아니면 성공이라고 말하지 않는다. 실패한 deliver는
  이전 산출물을 보존하므로 그 경로에 visual-check를 하지 않는다 (낡은 파일 검사가 됨).
- 통과한 최종 후보는 동결한다. 이후 편집 금지. 수정이 필요하면 새 후보 사이클을 돌린다.
- 사용자가 즉시 미리보기를 원할 때만 `preview`를 쓴다.
- `visual-check`는 선택적 브라우저 증거 수집이다. 이것이 지각 품질 승인이 아님을
  구분해 보고한다.

영수증 보관:

```text
qa/archify-validate-<nn>-<view>.json
qa/archify-deliver-<nn>-<view>.json
qa/archify-svg-<nn>-<view>.json   (아래 §7 추출 영수증)
```

## 6. 출력 파일 계약

archify 경로의 `diagrams/`:

```text
diagrams/
├─ 01-system-context.architecture.json   archify IR (View source)
├─ 01-system-context.html                인터랙티브 아티팩트 (deliver 산출물)
├─ 01-system-context.svg                 보고서 임베딩용 정적 추출
├─ 02-container.architecture.json
├─ 02-container.html
├─ 02-container.svg
├─ 03-dynamic-<scenario>.sequence.json
├─ 03-dynamic-<scenario>.html
├─ 03-dynamic-<scenario>.svg
├─ 04-component-<container>.architecture.json
├─ 05-deployment-<environment>.architecture.json
```

- IR JSON과 deliver HTML은 필수, 추출 SVG는 보고서에 임베딩할 때 필수다.
- 폴백 경로(archify 미가용)는 기존대로 `.puml`/`.mmd`/`.dsl`을 같은 위치에 둔다.
- output package manifest는 이 파일들을 일반 파일로 포함한다 (SHA-256 자동 기록).

## 7. 보고서 임베딩용 정적 SVG 추출

archify 산출물의 다이어그램 SVG는 페이지 CSS에 의존하고, 테마 변수는
`<html data-theme>`에 정의된다. 보고서에 넣기 전에 반드시 추출 스크립트를 거친다:

```bash
python3 <skill>/scripts/extract_archify_svg.py \
  --html diagrams/01-system-context.html \
  --output diagrams/01-system-context.svg \
  --scope-id archify-svg-01-system-context \
  --json qa/archify-svg-01-system-context.json
```

스크립트가 보장하는 것 (2026-09-02 실측):

- 산출물에 `<svg>` 블록이 정확히 1개인지 확인
- `<script>`, `foreignObject`, 외부 `http(s)` 참조 존재 시 FAIL (exit 1)
- SVG가 사용하는 클래스만 남기고, `html`/`body`/`:root`/뷰어 UI 셀렉터는 제거
- 살린 규칙 전부를 고유 루트 id(`#archify-svg-...`)로 스코핑해 보고서 문서에
  스타일이 새어나가지 않게 함 (`@media` 내부 포함)
- 테마 속성(`data-theme`)을 SVG 루트로 옮겨 색상 변수가 유지되게 함
- `@keyframes`/`animation` 제거 (정적 임베딩)

직접 `<svg>`를 복사해 넣지 않는다. 추출 SVG는 파생 정적 뷰이고,
인터랙티브 원본은 deliver HTML이며 보고서에서 링크로 연다.

보고서의 View 카드에는 두 진입점을 모두 제공한다:

```text
정적 SVG (임베딩 — 오프라인 단일 파일 계약 유지)
인터랙티브 아티팩트 링크 (diagrams/<view>.html — 탐색·검색·내보내기)
```

## 8. Deployment View 특례

`engineering_profile: "deployment-ownership"`은 fail-closed다:

- 소유자, 리전 배치, private database 범위, 경계 통과가 근거로 확인된 경우에만 활성화
- 누락되면 검증이 실패하며, 프로파일을 제거해 통과시키지 않는다
- 활성화 후 근거가 부족해지면 사실을 진단대로 보고한다

이 동작은 이 스킬의 "근거 없는 빈칸을 채우지 않는다" 원칙과 같은 방향이다.

## 9. 경계 — archify가 아닌 것

- **정보 그림(인포그래픽)**: 목록 나열, 절차 단계, 양측 비교 같은 정보 구조 꾸미기는
  C4 View가 아니다. archify 5타입으로 밀어 넣지 않는다. 이런 표현이 필요하면
  정보 그림 엔진(예: AntV Infographic)이나 보고서 마크다운/HTML 표로 처리하고,
  그 산출물을 C4 다이어그램이나 근거로 취급하지 않는다.
- **실시간 대시보드가 아니다**: 산출물은 정적 HTML/SVG다. 지표·트래픽 갱신은 없다.
- **편집형 캔버스가 아니다**: 수동 편집 결과를 canonical로 역반영하지 않는다.

## 10. 검증 보고

`validation-report.md`의 다이어그램 항목에 archify 결과를 추가 기록한다:

```text
Archify availability (doctor): available / unavailable (사유)
Archify IR authored per view: <View 목록>
Archify validate receipt: pass/fail per view (check 수, 오류, 경고)
Archify deliver: exit 0 per view / 실패 사유
Archify SVG extraction: pass/fail per view (스코핑 id, 규칙 수)
Interactive artifact link in report: yes/no
```

`not run`은 실패가 아니다. 실행하지 않은 검사를 통과했다고 쓰지 않는다.
