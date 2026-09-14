# Repo-flowmap 어댑터 — 번들 폴백 다이어그램 경로

repo-flowmap은 flowmap JSON을 결정적으로 검증해 자가완결 인터랙티브 HTML로 빌드하는
Node.js 기반 렌더러다. **archify가 미가용일 때의 기본 경로**이며, 스킬에
`assets/repo-flowmap/`으로 번들되어 별도 설치가 필요 없다.
canonical model은 여전히 유일한 진실의 원본이고, flowmap.json은 View별 파생
source diagram이다 (archify IR, `.puml`, `.dsl`과 같은 지위).

```text
architecture-model.json (canonical)
  → View별 flowmap.json (파생 source)
    → build_repo_flowmap.py (번들 validate + build 실행, 해시 영수증)
    → 인터랙티브 HTML 아티팩트
    → 보고서 embed (data URI iframe, 기본 템플릿 지원)
```

---

## 1. 요구 조건과 가용성

요구 조건:

- Node.js 18 이상 — `validate_flowmap.mjs`와 `build_flowmap.mjs`는 표준 라이브러리만 쓴다
- Python 3 — 스킬의 영수증 생성 래퍼 실행 (표준 라이브러리만 사용)
- 그 외 의존성·설치 불필요 — 번들 자체로 완결이다

가용성 판정:

```text
1. assets/repo-flowmap/scripts/ 가 존재하고 node가 실행되면 사용 가능
2. Node가 없거나 스크립트가 손상되면 Structurizr → Mermaid/PlantUML → ASCII 체인으로 내려간다
```

`archify가 가용하면 repo-flowmap을 쓰지 않는다` — repo-flowmap은 폴백이다. 사용자가
명시적으로 repo-flowmap을 지정하면 그것을 따른다.

금지:

- 번들 `template.html`을 수정하는 것 (repo-flowmap 고정 계약)
- 가용성 확인 없이 빌드 명령을 문서에 적는 것
- validate를 통과하지 않은 JSON을 빌드하는 것

## 2. C4 View → flowmap 매핑

flowmap은 `layers`(열) + `nodes`(카드) + `flows`(동작·단계) 모델이다.

| C4 View | 매핑 |
|---|---|
| System Context / Landscape | layers = 요소 유형(Person / 시스템 경계), nodes = View 요소, flows = View 관계 (1 관계 = 1 flow, steps 1개) |
| Container | layers = Software System 경계 또는 실행 계층, nodes = Container, flows = View 관계 |
| Component | 대상 Container 하나의 확대. layers = 역할 그룹, nodes = Component |
| Dynamic | flow 1개, steps = order 순서 그대로. `call` = 관계 technology, `data` = 전달 내용, `note` = canonical step note |
| Deployment | layers = 배치 경계 후보, nodes = 배치 대상. 소유권·리전 사실이 없으면 "후보"로 라벨링 |

저작 규칙:

- 노드 `label`은 canonical 요소 name, `desc`는 유형·기술 요약. canonical에 없는
  노드·플로우·단계를 발명하지 않는다.
- flow `steps`의 `state`(`failover`/`blocked`/`cond`)는 canonical 관계·step에 그 사실이
  근거로 있을 때만 쓴다. 근거 없는 분기·차단 표현을 장식으로 넣지 않는다.
- `meta.title`에 View title을 쓰고, `meta.basis`에 "derived from architecture-model.json
  (modelRevision)"을 쓴다.
- `meta.last_analyzed_commit`은 스키마 필수 필드다. 코드 리포지토리 분석이 아니면
  실제 커밋 대신 근거 지시자(예: `sources-<sha256 앞 8자>`)를 쓴다.
- canonical ID가 `^[A-Za-z0-9_-]+$`이면 그대로 쓰고, 아니면 슬러그로 변환해
  `file` 필드 또는 flow `summary`에 원본 canonical ID를 보존한다.

## 3. 검증·빌드 명령

```bash
python3 <skill-root>/scripts/build_repo_flowmap.py \
  --root <output-root> \
  --input diagrams/<view>.flowmap.json \
  --output diagrams/<view>.flowmap.html
```

래퍼는 번들 검증기와 빌더를 순서대로 실행한다. 경로는 `--root` 기준이며,
입출력은 같은 View stem을 가진 `diagrams/` 파일이어야 한다. 성공하려면 두 실행 모두
exit 0이어야 한다. 영수증은 자동으로 qa/에 저장한다:

```text
qa/repo-flowmap-validate-<view>.json   ok/exitCode + stdout/stderr
qa/repo-flowmap-build-<view>.json      ok/exitCode + input/specification.sha256 + output/artifact.sha256
```

래퍼는 읽은 입력 바이트를 임시 파일로 동결하고 동일한 파일을 검증·빌드한다.
새 임시 HTML이 생성되고 원본 입력이 바뀌지 않았을 때만 최종 HTML과 성공 영수증을 확정한다.
실패하면 이전 HTML은 보존하되 해당 실행의 실패 영수증으로 덮어써 낡은 산출물 재사용을 막는다.
직접 `build_flowmap.mjs`를 실행한 stdout이나 `outputBytes`만으로는 납품 영수증이 되지 않는다.
**기존 HTML에 현재 해시를 사후 보충하지 않는다.** 구 영수증은 이 명령으로 실제 재빌드한다.
해시는 파일 변경 탐지용이며, 편집 가능한 로컬 영수증이 실행 진위를 암호학적으로 증명하지는 않는다.

## 4. 보고서 임베딩

`html/report-data.json`의 `diagrams[]`에 다음처럼 지정한다:

```json
{
  "id": "diagram-01-context",
  "viewId": "01-context",
  "assetPath": "diagrams/01-context.flowmap.html",
  "mimeType": "text/html",
  "required": true,
  "presentation": { "...": "기존 계약과 동일" }
}
```

- 빌더가 파일을 `data:text/html;base64` data URI로 내장하고, 기본 템플릿은
  `mimeType === 'text/html'` 다이어그램을 `<iframe sandbox="allow-scripts">`로 렌더링한다.
- assetPath를 SVG에서 flowmap HTML로 바꿀 때는 `presentation.caption`·`alt`도 새 렌더러에
  맞게 갱신한다. 이전 렌더러 문구가 남으면 사실 왜곡 소지가 있다.
- 임베드 확인은 산출 HTML에서 `data:text/html;base64` 발생 수로 센다. `<iframe` 리터럴은
  런타임 생성이라 정적 HTML에 나타나지 않는다.
- 빌더의 `--data` 인자는 `--root` 기준 상대경로로 해석된다 (2026-09-14 실측).
- iframe은 불투명 origin에서 동작한다. repo-flowmap의 localStorage 접근은 try/catch로
  감싸져 있어 연결점 저장이 비활성될 뿐 렌더링은 정상이다.
- **인쇄 폴백(정적 SVG)**: iframe은 인쇄·PDF에서 신뢰할 수 없다(2026-09-14 실측: 캔버스 잘림).
  따라서 저작 시점에 View별 정적 SVG를 추출해 report-data의 `diagrams[].printAssetPath`로 지정한다.
  빌더가 `printDataUri`로 내장하고, 기본 템플릿은 화면에서는 숨기고 인쇄 시에만 iframe 대신 표시한다.
  추출은 브라우저에서 실행되는 별도 작업이다. 이 스킬의 빌드 래퍼는 정적 SVG를 만들지 않는다.
  브라우저 추출기를 사용하는 경우 **그 추출 실행 안에서** 원본 HTML 바이트 해시를 잡고,
  해당 HTML을 로드해 `#map`을 직렬화하고, 원본이 변하지 않았음을 확인한 뒤
  `qa/repo-flowmap-svg-<view>.json`을 남겨야 한다. 필수 필드는 `ok:true`,
  `source`(빌드 HTML 경로), `sourceSha256`, `output`(SVG 경로), `svgSha256`이다.
  수동 「SVG 다운로드」 파일만 있거나 사후 작성한 해시 영수증이면 인쇄 자산으로 연결하지 않는다.
  추출기·유효 영수증이 없으면 `printAssetPath`를 생략하고 인쇄 시 그림이 빠진다는 한계를
  HANDOFF에 명시한다. `extract_archify_svg.py`는 동적 flowmap HTML용 추출기가 아니다.
- 임베드 안에서는 마우스 드래그 이동이 iframe 영역에서 막힌다(브라우저 한계).
  확대·축소 버튼과 전체 화면은 동작한다.

## 5. 위생 검사

- archify SVG와 달리 flowmap HTML은 `<script>`를 포함하는 것이 정상이다.
  HTML-STATIC 검사의 외부 의존성·placeholder·`javascript:` 규칙은 그대로 적용된다.
- flowmap JSON·HTML에 외부 URL, 원격 자산, 추적 코드를 넣지 않는다 (repo-flowmap
  원본 계약과 동일).
- 추출 없이 내장되므로 `extract_archify_svg.py`는 이 경로에서 실행하지 않는다.

## 6. 렌더링 보고 항목

```text
Repo-flowmap availability: bundled-ok / node-missing / broken (사유)
Repo-flowmap IR authored per view: <View 목록>
Repo-flowmap validate: pass/fail per view (오류 수)
Repo-flowmap build: exit 0 per view / 실패 사유
Repo-flowmap report embed: embedded/missing per view
```

`not run`은 실패가 아니다. 실행하지 않은 검사를 통과했다고 쓰지 않는다.
