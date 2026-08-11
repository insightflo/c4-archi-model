# Human Understanding Gates

다이어그램이 렌더링됐다는 사실과 독자가 이해했다는 사실은 다르다. 문명은 이 둘을 놀라울 정도로 자주 혼동한다.

## 방법

- `human-review`: 실제 대상 독자가 검토함. `simulated=false`.
- `persona-simulation`: 정의한 독자 persona로 점검함. `simulated=true`.
- `not-run`: 실행하지 않음. 결과는 `NOT_RUN`.

persona simulation을 실제 사용자 테스트라고 표현하지 않는다.

## 초보자용 30초 Gate

필수 ID:

```text
B-01 누가 시스템을 사용하는가?
B-02 시스템은 어떤 문제를 해결하는가?
B-03 주요 실행 단위는 무엇이며 왜 나뉘는가?
B-04 핵심 요청 또는 이벤트는 어디서 시작해 어디서 끝나는가?
B-05 아직 확인되지 않았거나 이 문서가 답하지 않는 것은 무엇인가?
```

답변은 canonical model/view/claim/source 또는 Coverage issue를 참조해야 한다.

## 전문가용 5분 Gate

필수 ID:

```text
E-01 시스템과 ownership 경계는 어디인가?
E-02 각 Container는 어떤 책임·상태·인터페이스를 소유하는가?
E-03 동기·비동기와 계약 경계는 어디인가?
E-04 실패 전파·격리·복구 방식은 무엇이 확인되었는가?
E-05 보안·신뢰·배포·관측성 근거와 미확인은 무엇인가?
E-06 핵심 trade-off, risk, 다음 결정은 무엇인가?
```

## 결과

- `PASS`: 모든 필수 질문을 답했고 중대한 이해 장애가 없음.
- `PASS_BOUNDED`: 핵심은 이해되지만 명시된 limitation이 있음.
- `REQUEST_CHANGES`: 한 개 이상의 필수 질문을 답하지 못하거나 설명이 오해를 유발함.
- `NOT_RUN`: Gate를 수행하지 않음.

## 실패 예

```text
그림에는 박스가 있지만 어떤 문제를 해결하는지 설명할 수 없음
화살표 방향은 보이지만 요청과 이벤트의 차이를 알 수 없음
초보자 화면 첫 장에 내부 UUID와 Source locator만 가득함
전문가 설명에서 상태 소유권과 실패 경계가 누락됨
PASS_BOUNDED인데 남은 경계가 표시되지 않음
```

## 수정 Loop

```text
Gate 질문 실행
→ 실패 질문과 영향을 기록
→ 설명·View·reading order 수정
→ canonical 사실 변경 여부 검사
→ validator 재실행
→ Gate 재실행
```

설명을 고치다가 canonical 사실을 바꾸면 새 근거 Claim과 Model revision이 필요하다.
