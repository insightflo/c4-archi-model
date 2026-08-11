# {{ARCHITECTURE_TITLE}}

> 독자 모드: {{BEGINNER | EXPERT | BOTH}}  
> 분석 Profile: {{GUIDED | FOCUS | FULL}}  
> 질문: {{SESSION_QUESTION}}  
> Canonical model revision: {{MODEL_REVISION}}  
> 검증 상태: {{PASS | PASS_BOUNDED | REQUEST_CHANGES | NOT_RUN}}

## 먼저 알아둘 범위

- 포함 범위: {{IN_SCOPE}}
- 제외 범위: {{OUT_OF_SCOPE}}
- 종료 조건: {{STOP_CONDITION}}
- 자료 Snapshot: {{SOURCE_SNAPSHOT_ID_AND_SCOPE}}
- 남은 경계: {{COVERAGE_COMPLETION_REASON}}

`PASS_BOUNDED`는 현재 질문과 범위 안에서 설명이 충분하다는 뜻이며,
전체 시스템·배포·운영 특성까지 모두 검증됐다는 뜻이 아니다.

## 한 문장 아키텍처 요약

{{근거가 등록된 claim만 사용해 시스템의 목적과 구조를 한 문장으로 설명}}

## 자료와 확인 수준

- [확인됨] {{VERIFIED CLAIMS}}
- [문서에서만 확인됨] {{DOC_ONLY CLAIMS}}
- [일부 확인됨] {{PARTIAL CLAIMS}}
- [확인 필요] {{UNVERIFIED OR UNKNOWN_RELEVANT}}
- [충돌] {{CONFLICT CLAIMS, 없으면 없음}}

---

## 0. 이 시스템은 어떤 문제를 해결하는가?

{{BEGINNER: 사용자 관점에서 문제, 대상 시스템 경계, 결과를 쉬운 말로 설명}}
{{EXPERT: business boundary, system boundary, ownership와 책임 범위를 설명}}

근거 Claim: {{CLAIM_IDS}}

## 1. System Context

![System Context]({{DIAGRAM_PATH_OR_REFERENCE}})

### 이 View가 답하는 질문

{{누가 대상 시스템을 사용하고 어떤 외부 시스템과 연결되는가}}

### 이 View가 의도적으로 답하지 않는 질문

{{내부 Container, Component, Deployment 등}}

### 다음 확대

{{CONTAINER_VIEW_REFERENCE}}

## 2. Container 구조

![Container Diagram]({{DIAGRAM_PATH_OR_REFERENCE}})

{{각 Container의 책임, 확인된 기술, 상태 소유권, 관계 설명}}

### 이 View가 의도적으로 답하지 않는 질문

{{Container 내부 구현 또는 근거 없는 운영 토폴로지}}

### 다음 확대 후보

{{COMPONENT_OR_DYNAMIC_EXPANSION_POINTS}}

## 3. 핵심 시나리오

각 시나리오는 Canonical Dynamic View와 relationship을 참조한다.
단일 정상 흐름만 있다고 가정하지 않는다.

### {{SCENARIO_1_NAME}} — {{HAPPY_PATH | FAILURE_PATH | ASYNC | RECOVERY}}

![Dynamic Diagram]({{DIAGRAM_PATH_OR_REFERENCE}})

1. {{STEP 1 — DYNAMIC_STEP_ID / RELATIONSHIP_ID / CLAIM_ID}}
2. {{STEP 2 — DYNAMIC_STEP_ID / RELATIONSHIP_ID / CLAIM_ID}}
3. {{STEP 3 — DYNAMIC_STEP_ID / RELATIONSHIP_ID / CLAIM_ID}}

{{추가 시나리오가 있으면 같은 형식으로 반복}}

## 4. Component 상세 — {{CONTAINER_NAME}}

{{자료와 현재 질문에 필요한 경우에만 포함}}

- 책임: {{RESPONSIBILITIES}}
- 입력·출력 인터페이스: {{INTERFACES}}
- 상위 Container: {{PARENT_CONTAINER_ID}}
- 확인된 근거: {{CLAIM_IDS}}
- 확인되지 않은 항목: {{RELATED_COVERAGE_IDS}}

## 5. Deployment와 운영 구조

{{근거가 있을 때만 설명한다. 자료가 없으면 다음과 같이 명시한다.}}

> 현재 Source Snapshot에서는 실행 노드, 복제 수, 네트워크 경계,
> 장애 조치와 운영 환경을 확인할 수 없다. 따라서 Deployment View를 생성하지 않았다.

## 6. 설계상 장점, 비용과 위험

각 항목은 자유로운 감상문이 아니라 다음 구조로 쓴다.

```text
관찰된 구조
→ 기대 효과
→ 효과가 성립하는 전제
→ 비용 또는 위험
→ Claim / Source / 미확인 Coverage
```

### 장점

{{BENEFITS}}

### Trade-off

{{TRADEOFFS}}

### 위험

{{RISKS}}

## 7. 확인 필요, 충돌과 다음 조사

### 현재 질문에 중요한 미확인

{{coverage.unknownRelevant}}

### 의도적으로 제외한 미확인

{{coverage.unknownOutOfScope}}

### 다음 확대 후보

{{coverage.expansionPoints}}

### 경계

{{coverage.boundaries}}

### 자료 간 충돌

{{evidence-ledger claims with confidence=CONFLICT}}

## 8. 독자별 설명

### 초보자용

각 핵심 요소를 다음 순서로 설명한다.

```text
무엇인가
→ 왜 필요한가
→ 누구와 연결되는가
→ 없거나 실패하면 어떤 영향이 있는가
→ 비유와 실제 구조가 다른 지점
```

{{BEGINNER_CONTENT}}

### 전문가용

다음 항목 중 근거가 있는 것과 미확인을 구분한다.

```text
system / ownership boundary
responsibility와 state ownership
inbound / outbound interface
sync / async interaction
failure propagation과 recovery
security / trust boundary
deployment / scaling / observability
trade-off와 open decision
```

{{EXPERT_CONTENT}}

`BOTH`가 아니면 선택하지 않은 설명 절은 HTML에서 숨기되,
두 설명이 사용하는 Canonical 요소·관계·기술 사실은 달라지지 않아야 한다.

## 9. Human Understanding Gate

- 방법: {{HUMAN_REVIEW | PERSONA_SIMULATION | NOT_RUN}}
- 실제 사용자 검토 여부: {{SIMULATED_FALSE_TRUE}}
- 결과: {{PASS | PASS_BOUNDED | REQUEST_CHANGES | NOT_RUN}}
- 실패 또는 제한: {{LIMITATIONS}}

{{BEGINNER: B-01 ~ B-05 결과}}
{{EXPERT: E-01 ~ E-06 결과}}

Persona simulation을 실제 사용자 테스트라고 표현하지 않는다.

## 10. 용어 또는 결정 요약

{{BEGINNER: 용어집과 일상 비유}}
{{EXPERT: architecture decision, open decision, 근거 수준}}

---

## 근거 추적

### Source Snapshot

{{snapshot id, immutable revision/hash, 읽은 파일·페이지·줄 범위, 접근 실패 범위}}

### Evidence Ledger

| Claim ID | 주장 | Derivation | Confidence | 근거 | 사용 View·설명 |
|---|---|---|---|---|---|
| {{CL-001}} | {{STATEMENT}} | {{explicit / normalized / inferred / unresolved}} | {{VERIFIED / PARTIAL / DOC_ONLY / UNVERIFIED / CONFLICT}} | {{SOURCE + LOCATOR}} | {{usedBy}} |

### Coverage Completion

{{coverage.completion.result와 reason}}

---

## HTML 최종 보고서 매핑

이 Markdown은 설명 초안이며, Canonical 사실의 원본이 아니다.
`assets/html-report-data.template.json`으로 `html/report-data.json`을 만든 뒤
최종 `index.html`을 다음 순서로 조립한다.

```text
질문·Profile·범위·검증 상태
→ 문제와 한 문장 요약
→ C4 View 탭
→ 여러 핵심 Dynamic 흐름
→ 주요 요소 책임 카드
→ 초보자용 또는 전문가용 설명
→ 장점·비용·위험
→ Coverage·충돌·다음 조사
→ Human Understanding Gate
→ Source Snapshot·Evidence Ledger
→ QA·패키지 무결성
→ 접을 수 있는 원본 모델·다이어그램 source·설명 Markdown
```

HTML 표시 데이터는 다음 사실을 다시 정의하지 않는다.

```text
요소 이름
C4 유형
기술
책임
관계 방향과 설명
View 구성
```

이 값은 `architecture-model.json`에서 가져온다. HTML 데이터에는 `modelId`와
설명용 presentation만 둔다. Session ID, model revision, View ID, relationship ID,
Claim ID, Source ID와 Coverage ID는 각 원본과 일치해야 한다.

## 최종 산출물과 전달

- 사람이 먼저 여는 파일: `index.html`
- 분석 계약: `model/architecture-session.json`
- Canonical 사실: `model/architecture-model.json`
- 근거: `qa/evidence-ledger.json`
- 범위와 미확인: `qa/coverage.json`
- 이해도 검사: `qa/human-understanding.json`
- HTML 표시 데이터: `html/report-data.json`
- 검증 결과: `qa/*.json`
- 패키지 목록과 hash: `manifest.json`
- 인수인계: `HANDOFF.md`
