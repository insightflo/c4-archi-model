# 단일 HTML 출력 가이드

최종 사용자가 먼저 여는 파일은 `index.html`이다. JSON, PUML, DSL과 Markdown은 수정·검증용 원본으로 보존하되 첫 진입점으로 강요하지 않는다.

## 1. 데이터 흐름

```text
Session + Canonical Model + Evidence Ledger + Coverage + Understanding Gate
→ strict validation
→ html/report-data.json의 presentation mapping
→ canonical 사실 hydrate
→ SVG/PNG와 원본 파일 내장
→ 단일 index.html
→ static·browser·package QA
```

HTML은 canonical model을 대체하지 않는다. report data는 canonical 이름·유형·기술·책임을 복제하지 않는다.

## 2. 권장 정보 구조

```text
이해하기
  문제와 한 문장 요약
  Context / Container / Dynamic / 필요한 Component
  요소 책임과 용어

설계 검토
  경계·상태·계약·실패·배포·트레이드오프
  Coverage와 다음 결정

근거·QA
  Source Snapshot
  Claim과 traceability
  Coverage 완료 판정
  Human Understanding Gate
  validator 결과

원본 파일
  Session, Model, Ledger, Coverage, PUML/DSL/Markdown
```

초보자 첫 화면에는 내부 UUID, locator와 raw JSON을 전면 배치하지 않는다. 필요할 때 펼쳐 보게 한다.

## 3. View 표시

각 다이어그램 탭은 canonical View ID를 참조한다.

필수 표시:

```text
View title과 type
답하는 질문
scope
설명
reading tips
의도적으로 보여주지 않는 것
다음 확대 View
대체 텍스트
```

이미지의 text가 작아도 읽을 수 있도록 확대·축소·100% 복원·전체 화면을 제공한다.

## 4. Dynamic flows[]

시나리오마다 flow 하나를 만든다.

```text
happy-path
failure-path
retry-path
administrative-path
other
```

각 step presentation은 canonical `stepId`를 참조한다. 순서, relationship, endpoint와 기술은 canonical model에서 가져온다.

```json
{
  "stepId": "step-web-api",
  "explanation": "Web App이 Order API에 주문 생성 요청을 보낸다.",
  "attention": "화면은 데이터베이스에 직접 접근하지 않는다.",
  "analogy": "접수 창구에 주문서를 전달하는 단계"
}
```

## 5. Element presentation

허용:

```json
{
  "modelId": "order-api",
  "shortId": "C2",
  "presentation": {
    "whyItMatters": "주문 처리 책임을 한 경계에 모은다.",
    "withoutIt": "책임이 화면과 저장 코드에 흩어질 수 있다.",
    "analogy": "주문 접수 창구",
    "notes": []
  }
}
```

금지:

```json
{
  "modelId": "order-api",
  "name": "Payment API",
  "type": "externalSystem",
  "technology": "Rust + Cassandra"
}
```

Schema가 금지 필드를 거부해야 한다.

## 6. report-data build paths

```json
{
  "build": {
    "sessionPath": "model/architecture-session.json",
    "canonicalModelPath": "model/architecture-model.json",
    "evidenceLedgerPath": "qa/evidence-ledger.json",
    "coveragePath": "qa/coverage.json",
    "understandingPath": "qa/human-understanding.json",
    "expectedFiles": []
  }
}
```

required file은 실제로 존재해야 한다. 선택 파일은 누락 시 경고로 남긴다.

## 7. 빌드

```bash
python3 <skill>/scripts/build_html_report.py   --root <output-root>   --data html/report-data.json   --template <skill>/assets/html-report-template.html   --output <output-root>/index.html   --validation-output <output-root>/qa/html-build-validation.json
```

strict mode는 artifact bundle 오류가 있으면 종료 코드 1로 중단한다.
`--lenient`는 진단용 FAIL HTML을 만들고 종료 코드 2를 반환한다. 최종 배포에 사용하지 않는다.

## 8. 오프라인과 보안

금지:

- 원격 script와 stylesheet
- 외부 웹폰트
- 원격 image·PlantUML server
- `javascript:` URL
- 검증하지 않은 `innerHTML`
- SVG script, foreignObject, 외부 URL

허용:

- 내장 CSS와 JavaScript
- data URI 이미지
- escape된 text content
- 사용자가 명시적으로 누르는 로컬 다운로드 기능

## 9. 접근성과 반응형

- `<meta charset="utf-8">`와 viewport를 둔다.
- tab과 control은 키보드로 이동할 수 있어야 한다.
- 선택 상태는 색상 외에 ARIA·text·border로 표시한다.
- 다이어그램은 alt와 caption을 가진다.
- 375~390px에서 전체 페이지가 의도치 않게 가로 overflow하지 않는다.
- 다이어그램 자체의 내부 scroll은 허용하되 page layout을 깨지 않는다.
- 인쇄 모드에서 핵심 섹션과 그림이 사라지지 않는다.

## 10. Clean rebuild

HTML template에 임시 CSS·JS patch가 누적되어 다음이 발생하면 깨끗한 template에서 재생성한다.

```text
중복 selector와 event listener
삭제된 section을 참조하는 코드
깨진 tab ID
서로 다른 report-data 계약 혼용
외부 dependency 잔존
```

canonical model과 report data를 유지하고 HTML만 clean rebuild한다.

## 11. QA

정적:

```bash
python3 <skill>/scripts/validate_html_assets.py index.html --svg diagrams/example.svg
```

브라우저:

```text
Desktop·Mobile
콘솔 오류
외부 network request
탭·확대·전체 화면·검색
한글 깨짐·text clipping
인쇄 미리보기
```

브라우저 자동화 또는 수동 검토를 실행하지 못했으면 `NOT RUN`으로 기록한다.

## 12. 패키지

HTML 생성 후 Handoff와 output manifest를 만든다.

```bash
python3 <skill>/scripts/build_output_manifest.py --root <output-root>
python3 <skill>/scripts/validate_package.py --root <output-root> --update-manifest
```

manifest hash가 검증된 뒤 파일을 수정하면 다시 생성·검증한다.
