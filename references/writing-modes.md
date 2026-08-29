# 작성 모드 가이드

같은 canonical architecture model을 사용하되 독자가 이해하는 경로를 다르게 설계한다.
초보자용과 전문가용 사이에서 요소 이름·관계·기술·근거가 달라지면 안 된다.

작성 모드는 설명 방식이고 `guided / focus / full`은 분석 범위다.
`초보자용 + full`, `전문가용 + guided`처럼 독립적으로 조합할 수 있다.
설명 후에는 `human-understanding-gates.md`의 해당 질문으로 이해 경로를 점검한다.

---

## 공통 원칙

1. **문제부터 설명한다.** 기술 목록보다 시스템이 해결하려는 문제와 경계를 먼저 제시한다.
2. **정적 구조와 실행 흐름을 분리한다.** "연결되어 있다"와 "이 순서로 호출한다"를 혼동하지 않는다.
3. **확인 수준을 숨기지 않는다.** 확인됨, 분류됨, 확인 필요, 충돌을 구분한다.
4. **이름보다 책임을 설명한다.** `Order Service`라는 명사만 적지 말고 무엇을 소유하고 무엇을 하지 않는지 쓴다.
5. **장점만 쓰지 않는다.** 선택의 비용, 결합도, 운영 부담, 장애 전파 가능성을 함께 적는다.
6. **개인화된 억지 사례를 넣지 않는다.** 입력에 없는 사용자 회사·프로젝트·과거 대화를 본문으로 끌어들이지 않는다.
7. **출처를 짧고 정확하게 남긴다.** 파일명·문서 제목·섹션·페이지·코드 경로·심볼을 사용한다.

---

# 1. 초보자용 모드

## 독자 가정

- 웹, 앱, 데이터베이스 같은 단어는 들어봤지만 시스템 설계 경험은 적을 수 있다.
- C4, Container, Component, 동기/비동기, event-driven 같은 용어를 처음 접할 수 있다.
- 그림의 화살표가 왜 필요한지부터 설명해야 한다.

## 톤

- 친근하지만 군더더기 없는 존댓말
- 한 문장을 지나치게 길게 만들지 않음
- 전문 용어를 숨기지 않고 처음 한 번 제대로 풀이
- "그냥 그렇다"보다 "왜 나누는가"를 먼저 설명
- 압축보다 풀어쓰기. 단, 같은 설명을 표현만 바꿔 반복하지 않음

## 핵심 설명 패턴

중요한 전문 용어는 첫 등장 시 다음 세 가지를 함께 제공한다.

```text
영어 원문 또는 약자
한국어 뜻
일상 비유 또는 구체적인 예
```

예:

```text
Container(컨테이너): C4에서는 실행되는 애플리케이션이나 데이터 저장소를 뜻합니다.
택배 상자가 아니라, 식당의 홀·주방·창고처럼 서로 다른 책임을 가진 운영 공간에 가깝습니다.
Docker Container와는 같은 말이 아닙니다.
```

비유는 이해를 돕는 보조 장치다. 비유가 실제 구조와 다른 지점도 짧게 알려준다.

## 권장 문서 구조

```text
제목
이 문서에서 보는 범위
한눈 요약 — 30초 만에 이해하기
증거를 읽는 법 — 이 문서의 표기 약속([확인됨] 등을 어떻게 읽는지)
장면 목차 — 클릭하면 해당 프레임·섹션으로 이동

0. 먼저, 이 시스템은 무슨 문제를 해결하나?
1. 한 장으로 보는 바깥 관계 — System Context
2. 시스템 안에는 무엇이 있나? — Container
3. 실제 요청 하나를 따라가 보기 — Dynamic
4. 필요한 내부 영역만 더 확대 — Component
5. 실제 어디서 실행되나? — Deployment, 근거가 있을 때
6. 자주 헷갈리는 용어
7. 주의할 점과 아직 확인되지 않은 것
그래서 무엇을 해야 할까 — 내 상황에서의 다음 행동
마지막. 그림을 읽는 순서 요약
```

앞의 한눈 요약·증거 읽는 법·장면 목차는 장면 프레임형 독자 경험 요소다.
각 요소의 최소 계약은 `references/scene-frame-reporting.md`를 따른다.
섹션 수는 자료에 맞춘다. 자료가 짧은데 번호를 채우기 위해 내용을 늘리지 않는다.

## 각 요소 설명 템플릿

각 주요 박스는 다음 질문에 답한다.

```text
무엇인가?
왜 필요한가?
무엇을 책임지는가?
누구와 어떤 목적으로 대화하는가?
이 요소가 없거나 실패하면 사용자에게 어떤 영향이 있는가?
근거는 어디에 있는가?
```

예:

```text
Order API는 주문 요청을 받는 서버 애플리케이션입니다.
사용자 화면이 데이터베이스에 직접 접근하지 않도록 주문 규칙과 저장 절차를 한곳에서 맡습니다.
Web App에서 주문 생성 요청을 받고, 확인된 설계에 따르면 Order Database에 주문을 저장합니다.
이 API가 멈추면 새 주문 접수와 주문 조회가 실패할 수 있습니다.
```

장애 영향은 자료에 근거가 없으면 일반론으로 단정하지 말고
`구조상 예상되는 영향`이라고 표시하거나 생략한다.

## 시나리오 따라가기

최소 하나의 핵심 사용 흐름을 번호로 설명한다.

```text
1. 사용자가 Web App에서 주문 버튼을 누릅니다.
2. Web App이 Order API에 주문 생성 요청을 보냅니다.
3. Order API가 주문 규칙을 확인합니다.
4. Order API가 Order Database에 주문을 저장합니다.
5. 응답이 Web App으로 돌아오고 사용자는 주문 번호를 확인합니다.
```

각 단계에서 새로운 기술 용어가 나오면 그 자리에서 짧게 풀이한다.

## 강조 블록

출력 형식이 Markdown callout이나 카드 스타일을 지원하면 다음 의미로 사용한다.
지원하지 않으면 동일한 제목의 일반 단락으로 쓴다.

```text
용어       — 첫 등장 전문 용어
비유       — 추상 개념을 일상 사례로 설명
주의       — 흔한 오해나 잘못 읽는 방법
권장       — 올바른 해석·설계 원칙
확인 필요  — 자료로 확정할 수 없는 내용
핵심       — 섹션의 가장 중요한 한 문장
```

본문이 모두 박스가 되지 않도록 일반 설명을 중심으로 두고 강조 블록은 필요할 때만 사용한다.

## 숫자와 예시

- 실제 숫자가 자료에 있으면 계산 방식과 단위를 표시한다.
- 실제 숫자가 없으면 설명용 가상 예시임을 명시한다.
- 처리량, 지연시간, 복제 수를 근거 없이 예시 숫자로 채워 설계 사실처럼 보이게 하지 않는다.

## 피해야 할 문장

```text
"쉽게 말해 그냥 서버입니다."            # 무엇이 쉬운지 설명하지 않음
"Kafka가 알아서 처리합니다."             # 책임과 실패를 숨김
"이 구조는 확장성이 좋습니다."            # 조건과 근거가 없음
"초보자는 여기까지 몰라도 됩니다."        # 이해 경로를 끊음
```

대신:

```text
"설계 문서에는 이벤트가 Queue에 저장된다고 적혀 있습니다. 이 구조는 송신자와 처리자가
같은 순간에 실행되지 않아도 된다는 장점이 있지만, 중복 처리와 재시도 규칙은 별도로 확인해야 합니다."
```

---

# 2. 전문가용 모드

## 독자 가정

- 소프트웨어 설계, API, 데이터베이스, 배포, 분산 시스템의 기본 용어를 이해한다.
- 무엇이 있는지보다 경계와 선택의 이유, 운영 결과를 알고 싶어 한다.
- 설계 검토와 의사결정에 사용할 수 있는 정확한 정보가 필요하다.

## 톤

- 간결하고 직접적이되, 명사와 약어만 나열하지 않음
- 책임, 소유권, 계약, 실패 의미를 문장으로 명시
- 근거가 없는 장점 표현 금지
- 기술적 불확실성을 숨기지 않음
- 비유는 복잡한 경계 문제를 설명할 때만 제한적으로 사용

## 권장 문서 구조

```text
Executive architecture summary
Scope, sources, and verification status
1. System boundary and external dependencies
2. Container decomposition and ownership
3. Interfaces, protocols, and data ownership
4. Critical dynamic scenarios
5. Component decomposition for selected containers
6. Deployment topology and environment differences
7. Quality attributes and operational characteristics
8. Security and trust boundaries
9. Trade-offs, risks, and architecture smells
10. Contradictions, unknowns, and decisions required
Appendix: traceability and terminology
```

자료가 지원하지 않는 섹션은 `확인할 수 없음`으로 표시하거나 생략한다.

## 요소 설명 템플릿

```text
Responsibility
Boundary and owner
Public/consumed interfaces
State ownership
Inbound/outbound dependencies
Execution model
Failure semantics
Scaling unit
Deployment evidence
Observability evidence
Security/trust assumptions
Source evidence
```

모든 항목을 형식적으로 채우지 않는다. 근거가 있는 항목만 쓰고 누락은 별도로 모은다.

## 관계 설명

관계마다 가능한 범위에서 다음을 기록한다.

```text
source → destination
intent
sync/async
protocol or mechanism
payload or contract reference
authentication/authorization
timeout/retry/idempotency
failure propagation
evidence
```

문서에 없는 timeout, retry, idempotency를 관행으로 추정하지 않는다.
없다는 뜻이 아니라 확인되지 않았다는 뜻으로 기록한다.

## 품질 속성 분석

다음 항목은 자료가 말하는 범위에서만 평가한다.

- Availability
- Reliability and failure containment
- Performance and latency sensitivity
- Scalability and scaling unit
- Data consistency and transaction boundaries
- Security and privacy
- Modifiability and coupling
- Deployability
- Observability and operability
- Cost drivers

평가 문장 구조:

```text
관찰된 구조 → 기대되는 효과 → 전제 조건 → 비용 또는 위험 → 확인 근거
```

예:

```text
Order API와 Fulfilment Worker가 Queue를 통해 분리되어 있어 처리 시간의 결합은 낮아진다.
다만 이 이점은 durable delivery, 재시도, 중복 처리 제어가 구성되어 있다는 전제가 필요하다.
현재 자료에서는 해당 정책을 확인할 수 없다.
```

## 트레이드오프 표현

나쁜 예:

```text
Microservice 구조라 확장성과 유지보수성이 좋다.
```

좋은 예:

```text
결제와 주문이 별도 배포 단위로 분리되어 각기 확장할 수 있다.
대신 API 계약 변경, 분산 추적, 장애 전파 제어, 데이터 일관성 정책이 운영 책임으로 추가된다.
현재 입력에서는 계약 버전 정책과 분산 추적 구성을 확인할 수 없다.
```

## Architecture smell 후보

확정적 결함으로 단정하지 말고 근거와 함께 `검토 후보`로 제시한다.

```text
단일 장애점 후보
순환 의존
공유 데이터베이스에 의한 강한 결합
비동기 처리의 소유자 불명확
중복 책임
외부 시스템에 대한 직접 결합
관측성 공백
배포 단위와 팀 경계 불일치
신뢰 경계 불명확
```

---

# 3. 둘 다 모드

`둘 다`를 선택한 경우:

1. Evidence Ledger와 canonical model은 한 번만 만든다.
2. 다이어그램도 가능한 한 같은 파일을 공유한다.
3. 설명 문서만 `beginner.md`, `expert.md`로 분리한다.
4. 초보자용에서 생략한 전문 분석이 전문가용에 추가될 수는 있지만,
   두 문서의 요소·관계·기술·확인 상태는 일치해야 한다.
5. 서로 다른 주장으로 보이면 validation 오류로 처리한다.


---

# 4. HTML에서 모드 차이를 표현하는 방법

HTML은 같은 canonical model과 같은 C4 View를 사용한다. 모드가 달라졌다고 박스·화살표·기술·근거를
다르게 만들면 안 된다. 달라지는 것은 첫 화면의 안내, 다이어그램 옆 설명, 요소 카드의 보조 필드,
분석 섹션의 깊이다.

## 초보자용 HTML

첫 화면과 View 옆에서 다음을 우선한다.

```text
이 시스템이 해결하는 문제
왜 구조가 여러 부분으로 나뉘었는가
그림에서 어디부터 보면 되는가
각 박스가 무엇이고 왜 필요한가
핵심 요청이 어떤 순서로 움직이는가
처음 나온 용어의 뜻과 비유
```

Container와 Component 카드에는 가능한 범위에서 다음 필드를 사용한다.

```text
무엇인가
왜 필요한가
주요 연결
없거나 실패하면 어떤 영향이 있는가
근거
```

다이어그램 확대 기능이 있다고 설명을 생략하지 않는다. 확대는 작은 글자를 보는 기능이지,
초보자가 화살표의 의미를 자동으로 깨닫게 하는 신비한 장치가 아니다.

## 전문가용 HTML

첫 화면과 View 옆에서 다음을 우선한다.

```text
Scope와 system boundary
Ownership와 state boundary
Inbound/outbound interface
동기·비동기 상호작용
Protocol과 contract
Failure semantics와 propagation
Scaling/deployment evidence
Trust boundary, observability, operational responsibility
Architecture decision과 open decision
```

요소 카드에는 근거가 있는 경우 `경계·소유`, `운영 관점` 필드를 추가한다.
설계 검토 영역은 장점, 전제, 비용, 위험을 분리한다.

## 둘 다 HTML

- 하나의 `index.html` 안에서 공통 다이어그램과 근거를 공유한다.
- `audienceSections`에 beginner/expert 구분을 넣어 두 설명을 모두 표시한다.
- 같은 요소에 서로 충돌하는 설명이 있으면 HTML 문제가 아니라 모델·설명 일관성 FAIL이다.
- 두 개의 별도 HTML을 요청받지 않았다면 한 파일을 기본으로 한다.

## 공통 HTML 금지 규칙

- 초보자용에서 원본 근거와 QA를 제거하지 않는다. 뒤쪽으로 배치할 수는 있다.
- 전문가용에서 명사와 약어만 늘어놓지 않는다.
- HTML 카드에 canonical model에 없는 기술·책임·소유권을 추가하지 않는다.
- `확인 필요`와 `NOT RUN`을 접어 숨긴 채 PASS처럼 보이게 만들지 않는다.
- 디자인을 위해 같은 요소 이름을 짧게 바꾸고 canonical ID 매핑을 잃지 않는다.

---

# 5. 최종 톤 검사

## 초보자용

- 용어가 첫 등장 때 풀렸는가?
- 설명이 "무엇"뿐 아니라 "왜"를 포함하는가?
- 비유가 실제 구조를 왜곡하지 않는가?
- 핵심 시나리오가 번호 순서로 설명되었는가?
- 짧게 줄이느라 중요한 관계를 삭제하지 않았는가?

## 전문가용

- 시스템과 Container의 경계 및 책임이 명확한가?
- 프로토콜·데이터 소유권·실패 의미가 근거 범위에서 적혔는가?
- 장점과 비용이 함께 적혔는가?
- 미확인 운영 정책을 관행으로 가정하지 않았는가?
- 전문 용어가 설명을 대신하고 있지 않은가?
