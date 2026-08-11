# Evidence Ledger와 Canonical Architecture Model

근거, C4 사실, 분석 범위와 화면 설명은 서로 다른 책임이다. 한 JSON에 모두 넣으면 같은 ID가 다른 사실을 말하는 사태가 생긴다.

## 1. 네 가지 분리

```text
architecture-session.json  질문·독자·Profile·범위
Evidence Ledger            Source Snapshot과 Claim
Canonical Model             C4 요소·관계·View·Dynamic step
HTML Report Data            설명 순서·비유·카드·asset 참조
```

Canonical Model은 Source Register를 복제하지 않는다. 모든 사실은 `claimIds`로 Evidence Ledger에 연결한다.

## 2. Source Register와 Snapshot

Source는 다음을 기록한다.

```text
ID
이름과 위치
kind
version
readScope
limitations
immutableRef 또는 contentHash
capturedAt
```

자료의 날짜·버전·commit을 확인할 수 없으면 만들지 말고 null로 둔다.
상세 규칙은 `source-snapshot.md`를 따른다.

## 3. Claim

Claim은 "이 아키텍처 사실을 왜 믿는가"를 표현한다.

```json
{
  "id": "CL-011",
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
    {"kind": "relationship", "id": "api-to-db"},
    {"kind": "view", "id": "ordering-container"}
  ],
  "notes": []
}
```

### Derivation

- `explicit`: 자료에 직접 명시됨.
- `normalized`: 확인된 사실을 C4 유형·상위 관계로 정규화함.
- `inferred`: 제한적인 추론. rationale과 근거가 필요함.
- `unresolved`: 둘 이상의 해석 또는 근거 부족.

### Confidence

- `VERIFIED`: 독립적 근거나 구현·배포·런타임으로 확인됨.
- `PARTIAL`: 일부만 확인됨.
- `DOC_ONLY`: 문서에는 있으나 구현·배포 검증은 없음.
- `UNVERIFIED`: 확인하지 못함.
- `CONFLICT`: 자료가 충돌함.

`unresolved + VERIFIED`는 허용하지 않는다. `CONFLICT`는 contradiction이 있어야 한다.

## 4. Locator

```text
문서: 파일 > 제목 > 하위 제목 > 페이지 또는 줄
코드: repository/path:심볼 또는 줄
API: 파일 > operationId/channel
IaC: 파일 > resource/module
기존 그림: 파일 > 다이어그램 제목 > 요소
Runtime: trace/log/run ID와 시간 범위
```

존재하지 않는 줄 번호를 만들지 않는다. 인용문은 필요한 최소 범위만 보존한다.

## 5. Canonical Element

```json
{
  "id": "order-api",
  "type": "container",
  "name": "Order API",
  "description": "주문 요청을 받고 저장과 이벤트 발행을 조정한다.",
  "technology": null,
  "parentId": "ordering-system",
  "environment": null,
  "tags": [],
  "derivation": "normalized",
  "confidence": "DOC_ONLY",
  "rationale": null,
  "claimIds": ["CL-004"],
  "instanceOfId": null
}
```

규칙:

- ID는 안정적으로 유지한다.
- description은 책임을 동사로 설명한다.
- technology는 확인된 경우만 쓴다.
- 모든 요소는 Claim을 가진다.
- parent 계층은 C4 semantic validator가 검사한다.
- Deployment instance는 `instanceOfId`로 논리 Container를 참조할 수 있다.

## 6. Canonical Relationship

```json
{
  "id": "web-to-api",
  "sourceId": "web-app",
  "destinationId": "order-api",
  "description": "주문 생성 요청을 전송한다.",
  "technology": "HTTPS/JSON",
  "interactionStyle": "synchronous",
  "derivation": "explicit",
  "confidence": "DOC_ONLY",
  "rationale": null,
  "claimIds": ["CL-010"]
}
```

- source와 destination은 실제 element여야 한다.
- 설명은 화살표 방향과 맞는 구체적인 동사와 목적을 사용한다.
- 기술과 interactionStyle은 근거가 있을 때만 쓴다.
- 양방향 의미는 별도 관계로 나눈다.

## 7. View와 Dynamic step

```json
{
  "id": "ordering-create-order",
  "type": "dynamic",
  "title": "주문 생성 흐름",
  "scopeId": "ordering-system",
  "environment": null,
  "description": "주문 입력부터 배송 준비 시작까지의 정상 흐름",
  "question": "주문 한 건은 어떤 순서로 이동하는가?",
  "notShown": ["재시도", "실패 복구"],
  "elementIds": ["customer", "web-app", "order-api", "order-database"],
  "relationshipIds": ["customer-to-web", "web-to-api", "api-to-db"],
  "steps": [
    {
      "id": "step-web-api",
      "order": 1,
      "relationshipId": "web-to-api",
      "kind": "request",
      "condition": null,
      "note": null,
      "claimIds": ["CL-010"]
    }
  ],
  "nextViewIds": [],
  "claimIds": ["CL-016"]
}
```

- Dynamic order는 1..N 연속이다.
- step relationship은 같은 View의 relationshipIds에도 있어야 한다.
- Component View는 Container 하나를 확대한다.
- View의 요소·관계는 canonical ID만 참조한다.

## 8. 자료 충돌

자동 우선순위를 만들지 않는다.

```text
[CONFLICT C-01]
S1 설계 문서: API가 Payment System을 직접 호출
S2 코드: payment-requested topic에 이벤트 발행
영향: 동기/비동기 실패 의미와 consistency 설명이 달라짐
처리: intended와 implemented View 분리 또는 사용자 결정 필요
```

## 9. 자료 종류별 한계

- 문서만 있음: intended architecture는 설명 가능. 구현·배포 일치 여부는 미확인.
- 코드만 있음: 구현 의존성은 설명 가능. 비즈니스 목적과 ownership은 제한적.
- IaC만 있음: 배포 경계는 설명 가능. 비즈니스 책임은 이름만으로 확정 불가.
- Runtime만 있음: 관찰 기간 호출은 설명 가능. 호출이 없다고 관계 부재를 단정 불가.

## 10. HTML 사실 분리

`html-report-data.json`의 element card는 다음처럼 canonical ID와 표현만 가진다.

```json
{
  "modelId": "order-api",
  "shortId": "C2",
  "presentation": {
    "whyItMatters": "주문 저장과 후속 이벤트 발행 조정을 한 경계에 모은다.",
    "withoutIt": "주문 처리 책임이 여러 곳에 흩어질 수 있다.",
    "analogy": "주문 접수 창구",
    "notes": []
  }
}
```

name, type, technology, description은 HTML builder가 canonical model에서 읽는다.
표시 데이터가 이 필드를 다시 쓰면 Schema 위반이다.
