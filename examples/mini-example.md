# 최소 예시 — 같은 사실, 다른 설명 깊이

이 예시는 스킬 동작 방식을 보여주기 위한 가상 자료다. 실제 시스템에 재사용하지 않는다.

## 입력 문장

```text
고객은 웹 화면에서 주문을 생성한다.
Web App은 Order API에 HTTPS/JSON으로 요청한다.
Order API는 주문을 PostgreSQL에 저장하고 order-created topic에 이벤트를 발행한다.
Fulfilment Worker는 해당 이벤트를 소비해 배송 준비를 시작한다.
```

## 추출된 C4 요소

```text
Customer                 Person
Ordering System          Software System, 범위 이름은 작업자가 명시해야 함
Web App                  Container
Order API                Container
Order Database           Container [PostgreSQL]
order-created topic      Container 후보
Fulfilment Worker        Container
```

`Ordering System`이라는 상위 경계는 입력 문장에 직접 명시되지 않았으므로,
실제 작업에서는 대상 시스템 범위를 사용자 입력이나 주변 문서에서 확인해야 한다.
이 예시에서는 설명을 위해 가상의 범위를 사용한다.

## v0.4.0 분석 계약 예시

이 예시는 설명 모드와 분석 깊이를 분리한다.

```text
독자 모드: beginner
분석 Profile: guided
질문: 주문 생성 구조와 핵심 흐름은 무엇인가?
포함 범위: 주문 생성, 저장, order-created 이벤트 발행과 소비
제외 범위: 결제, 반품, 실제 Production 배포
종료 조건: Context, Container, 주문 생성 Dynamic 흐름과 중요한 미확인을 설명하면 종료
```

Canonical model은 위 계약과 무관하게 동일한 아키텍처 사실만 보유한다.
설명 모드와 Profile은 `architecture-session.json`, 독자별 표현은
`html/report-data.json`에 기록한다.

## 근거와 Coverage 예시

```text
CL-001  Web App이 Order API에 주문 요청을 보낸다.
        derivation=explicit, confidence=DOC_ONLY

CL-002  Order API가 PostgreSQL에 주문을 저장한다.
        derivation=explicit, confidence=DOC_ONLY

U-001   DB commit과 이벤트 발행의 원자성은 확인할 수 없다.
        unknownRelevant, 다음 확인=트랜잭션·이벤트 발행 구현

U-002   Production 복제 수와 네트워크 구조는 현재 질문의 범위 밖이다.
        unknownOutOfScope
```

따라서 결과는 모든 운영 특성을 검증했다는 `PASS`가 아니라, 현재 질문에 대해서는
충분하지만 경계가 남았다는 `PASS_BOUNDED`가 될 수 있다.

## 초보자용 설명 예시

Order API는 주문을 접수하는 서버 애플리케이션입니다. 사용자의 Web App이 데이터베이스에
직접 주문을 쓰지 않도록, 주문 저장과 다음 작업 시작을 한곳에서 맡습니다.

`topic(토픽)`은 여러 프로그램이 받을 수 있도록 메시지를 올려두는 논리 채널입니다.
식당 주문서를 주방 게시대에 꽂아 두면, 홀 직원은 다음 일을 계속하고 주방은 자기 순서에 맞춰
주문서를 가져가는 것과 비슷합니다. 다만 실제 시스템에서는 메시지 보존, 중복 처리,
재시도 정책이 따로 필요할 수 있으며 이 입력만으로는 그 정책을 확인할 수 없습니다.

```text
1. 고객이 Web App에서 주문합니다.
2. Web App이 Order API에 HTTPS/JSON 요청을 보냅니다.
3. Order API가 PostgreSQL에 주문을 저장합니다.
4. Order API가 order-created topic에 이벤트를 발행합니다.
5. Fulfilment Worker가 이벤트를 받아 배송 준비를 시작합니다.
```

## 전문가용 설명 예시

Order API가 주문 상태의 write boundary이며 PostgreSQL을 소유 저장소로 사용하는 구조로 보인다.
주문 생성 후 `order-created` topic을 통해 Fulfilment Worker와 비동기 결합한다.
이 분리는 주문 접수 지연과 fulfilment 처리 시간을 분리할 수 있지만, durable delivery,
consumer retry, idempotency, ordering, schema evolution 정책은 입력에서 확인되지 않는다.

현재 문장만으로는 다음을 확정할 수 없다.

- PostgreSQL이 Order API 전용 데이터 저장소인지 공유 DB인지
- event publish와 DB commit 사이의 원자성 보장 방식
- topic의 broker 기술과 retention 정책
- Fulfilment Worker의 scaling unit과 failure recovery 방식

## 공통 사실 검증

두 설명은 어휘와 분석 깊이는 다르지만 다음 사실은 같아야 한다.

```text
Web App → Order API       주문 요청 [HTTPS/JSON]
Order API → PostgreSQL    주문 저장
Order API → topic         주문 생성 이벤트 발행
Worker → topic            주문 생성 이벤트 소비
```

---

## HTML 최종 산출물 예시

이 예시를 HTML로 조립할 때는 `examples/html-report-data.example.json`처럼 표시 데이터를 만들고,
`assets/html-report-template.html`에 삽입한다.

HTML에서의 권장 읽기 순서:

```text
주문 시스템이 해결하는 문제
→ System Context
→ Container View
→ 주문 생성 5단계 흐름
→ Web App, Order API, Order Database, Topic, Worker 책임 카드
→ 아직 확인되지 않은 이벤트 전달·중복 처리 정책
→ 근거와 QA
→ canonical JSON과 PUML 원본
```

초보자용에서는 `topic`과 C4 `Container`를 용어집에서 풀고,
전문가용에서는 transaction boundary, publish atomicity, retry/idempotency 미확인을 검토 항목으로 둔다.
두 HTML 설명이 가리키는 박스와 화살표는 같아야 한다.
