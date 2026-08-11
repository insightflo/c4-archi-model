# C4 모델 분류 가이드

이 문서는 설계 문장의 명사를 박스로 바꾸기 전에, 각 대상을 어떤 C4 요소와 View로
분류할지 판단하기 위한 기준이다.

## 1. C4가 무엇을 표현하는가

C4 모델은 소프트웨어 구조를 다음 확대 수준으로 나눠 설명한다.

```text
Software System
  └─ Container
       └─ Component
            └─ Code Element
```

사람이나 역할인 Person은 Software System을 사용한다.
핵심 정적 View는 System Context, Container, Component, Code이며,
System Landscape, Dynamic, Deployment가 이를 보완한다.

C4는 특정 도형, 색상, 렌더러를 강제하지 않는다. 대신 추상화 수준, 범위, 이름,
책임, 관계 설명을 일관되게 유지하는 것이 중요하다.

---

## 2. 요소 판정

### Person

사람, 역할, 페르소나, 조직 내 행위자 또는 소프트웨어가 아닌 외부 주체.

좋은 이름:

```text
고객
업무 담당자
시스템 관리자
외부 개발자
```

나쁜 이름:

```text
김철수              # 특정 개인이 중요하다는 근거가 없을 때
User                # 실제 역할을 구분할 수 있는데 지나치게 일반적
```

특정 개인이 시스템 권한·소유권상 실제 행위자라면 이름을 사용할 수 있다.

### Software System

사용자 또는 다른 시스템에 독립적인 가치를 제공하는 소프트웨어 경계.
주로 소유권, 책임, 팀 경계, 제품 경계와 함께 판단한다.

판정 질문:

1. 사용자가 이 대상을 하나의 제품·서비스처럼 인식하는가?
2. 다른 시스템과 구분되는 책임과 소유권이 있는가?
3. 내부 구현을 감추고 외부에 독립적인 기능을 제공하는가?

도메인 이름, 팀 이름, 조직 이름을 자동으로 Software System으로 만들지 않는다.

### Container

C4에서 Container는 **실행되는 애플리케이션 또는 데이터 저장소**다.
Docker Container만을 뜻하지 않는다.

대표 예:

```text
브라우저에서 실행되는 SPA
모바일 앱
서버 측 API 애플리케이션
백그라운드 Worker
배치 애플리케이션
서버리스 함수
데이터베이스 또는 논리 스키마
파일 저장소
객체 저장소
Queue 또는 Topic을 논리 저장·전달 경계로 모델링한 요소
```

판정 질문:

1. 별도 실행 공간 또는 프로세스로 동작하는가?
2. 독립적으로 배포·시작·중지되는 애플리케이션인가?
3. 데이터를 지속적으로 저장하는 책임이 있는가?
4. 상위 Software System 안에 포함되는가?

### Component

한 Container 내부에서 관련 기능을 묶고, 잘 정의된 인터페이스 뒤에 캡슐화한 단위.
C4의 Component는 별도 배포 단위가 아니다. 같은 Container 안의 Component는 보통 같은
프로세스 공간에서 실행된다.

판정 질문:

1. 어느 Container 안에 있는지 명확한가?
2. 사용자나 다른 Component에 설명할 수 있는 책임이 있는가?
3. 인터페이스나 진입점 뒤에 구현이 묶여 있는가?
4. 독립 배포되지 않는가?

폴더·패키지 구조를 그대로 Component로 복사하지 않는다.
`utils`, `common`, `misc`는 책임을 설명하지 못하므로 재검토 대상이다.

### Code Element

클래스, 인터페이스, 함수, 객체, 테이블, 파일 등 구현 수준 요소.
Code Diagram은 변경이 잦으므로 중요하거나 복잡한 영역에만 사용하고,
가능하면 코드 분석 도구로 자동 생성한다.

### Deployment Node

Software System 또는 Container 인스턴스가 실행되는 위치.

예:

```text
물리 서버
가상 머신
Docker Container
Kubernetes Cluster / Node / Pod
PaaS 실행 환경
브라우저 또는 모바일 기기
데이터베이스 서버
```

Container는 논리 실행·저장 단위이고 Deployment Node는 그 인스턴스가 놓이는 위치다.

### Infrastructure Node

배포 환경에서 시스템 실행을 지원하지만 C4 Container로 보지 않는 인프라 요소.

예:

```text
DNS
Load Balancer
Firewall
CDN
Service Mesh Gateway
```

---

## 3. View 선택 규칙

### System Context Diagram

- 범위: 하나의 Software System
- 주요 요소: 대상 시스템, 이를 사용하는 Person, 직접 연결된 외부 Software System
- 질문: "이 시스템은 누구를 위해 존재하고 외부와 어떻게 연결되는가?"
- 권장 독자: 기술·비기술 이해관계자
- 넣지 않는 것: 내부 데이터베이스, 내부 Worker, 클래스, Pod

### Container Diagram

- 범위: 하나의 Software System
- 주요 요소: 내부 Container
- 보조 요소: 직접 연결된 Person과 외부 Software System
- 질문: "내부 애플리케이션과 데이터 저장소는 무엇이며 어떻게 통신하는가?"
- 기술·프로토콜: 확인되는 범위에서 표시
- 넣지 않는 것: Pod 수, Load Balancer, 클래스, 내부 Component

### Component Diagram

- 범위: 하나의 Container
- 주요 요소: 그 Container 내부 Component
- 보조 요소: Component와 직접 연결된 Container, Person, Software System
- 질문: "이 Container의 주요 책임은 어떤 기능 단위로 나뉘는가?"
- 여러 Container 내부 Component를 한 View에 동시에 펼치지 않는다.

### Code Diagram

- 범위: 하나의 Component
- 주요 요소: 클래스, 함수, 인터페이스, 테이블 등
- 질문: "이 Component는 코드에서 어떻게 구현되는가?"
- 장기 문서에는 선택적으로만 사용한다.

### System Landscape Diagram

- 범위: 조직·부서·제품군 등 여러 Software System
- 질문: "선택한 범위의 시스템 전체는 어떻게 연결되는가?"
- 특정 시스템 하나에 초점을 맞추지 않는 Context 지도와 비슷하다.

### Dynamic Diagram

- 범위: 하나의 시나리오 또는 유스케이스
- 질문: "이 기능이 실행될 때 어떤 요소가 어떤 순서로 상호작용하는가?"
- 정적 연결과 실행 순서를 구분한다.
- 단계 번호와 구체적인 동사를 사용한다.

### Deployment Diagram

- 범위: 하나의 배포 환경. 예: Production, Staging, Development
- 질문: "논리 Container 인스턴스가 실제 인프라 어디에서 실행되는가?"
- Deployment/Infrastructure Node와 Container 인스턴스를 표현한다.
- 서로 다른 환경은 별도 View로 나누는 것이 기본이다.

---

## 4. 관계 작성 규칙

모든 화살표에는 **관계의 의도**가 있어야 한다.

```text
주어 → 목적어 : 구체적인 동작 [확인된 기술/프로토콜]
```

예:

```text
Customer → Web App : 주문을 생성하고 상태를 조회한다
Web App → Order API : 주문 생성 요청을 전송한다 [HTTPS/JSON]
Order API → Order Database : 주문과 결제 상태를 읽고 저장한다 [SQL]
Order API → order-created topic : 주문 생성 이벤트를 발행한다 [Kafka]
Fulfilment Worker → order-created topic : 주문 생성 이벤트를 소비한다 [Kafka]
```

피해야 할 관계 라벨:

```text
uses
data
API
calls
message
connection
```

영어를 쓰는 것 자체가 문제가 아니라, 목적을 설명하지 못하는 것이 문제다.

양방향 통신을 한 화살표로 뭉개지 않는다. 읽기와 쓰기, 요청과 콜백처럼 의미가 다르면
두 관계 또는 Dynamic View로 나눈다.

---

## 5. 자주 헷갈리는 표현

### API

- 별도 프로세스로 실행되는 API 애플리케이션 → Container 후보
- 같은 애플리케이션 내부의 기능 경계 → Component 또는 Interface 후보
- `POST /orders` 같은 개별 endpoint → 보통 C4 독립 요소가 아님

### Database

- 논리 데이터베이스·스키마·저장소 → Container
- 실제 DB 서버·관리형 인스턴스 → Deployment Node
- 둘 다 필요하면 논리 모델과 배포 모델에서 각각 표현

### Server

- `API Server`가 애플리케이션을 뜻함 → Container 후보
- VM 또는 물리 장비를 뜻함 → Deployment Node
- 이름만으로 판정하지 않는다.

### Service

- 독립 Software System, Container, Component, 비즈니스 기능 중 무엇이든 될 수 있다.
- 소유권, 실행 경계, 배포 방식, 상위 시스템을 확인한다.

### Microservice

마이크로서비스를 무조건 Container 하나로 처리하지 않는다.

- 하나의 Software System 안에서 같은 팀이 소유하는 독립 실행 서비스 → Container 또는 Container 그룹 후보
- 별도 팀이 독립적으로 소유·운영하고 외부 계약을 제공 → Software System 후보
- 한 마이크로서비스가 API와 전용 데이터 저장소 등 여러 실행 단위로 구성 → 여러 Container를 하나의 그룹으로 표현 가능

결론은 이름이 아니라 실제 책임과 소유 경계로 정한다.

### Queue와 Topic

메시지 브로커 전체만 박스로 그리면 실제 결합 관계가 가려질 수 있다.
자료가 충분하면 개별 Queue/Topic을 논리 Container로 표현하거나 관계 기술에
`via <queue/topic>`을 명시한다. 물리 브로커 배치는 Deployment View로 분리한다.

### Module

코드 모듈, 패키지, Component, 플러그인, 별도 프로세스일 수 있다.
실행·배포 경계와 책임을 확인한다.

---

## 6. C4에 억지로 넣지 말아야 하는 내용

| 설명하려는 내용 | 더 적합한 표현 |
|---|---|
| 업무 승인 절차·비즈니스 프로세스 | BPMN 또는 Flowchart |
| 객체 상태 전이 | State Machine |
| 상세 데이터 모델 | ERD |
| 도메인 개념과 불변식 | Domain Model |
| 상세 API 계약 | OpenAPI/AsyncAPI/GraphQL schema |
| 위협과 신뢰 경계 | Threat Model/Data Flow Diagram |
| 네트워크 라우팅 상세 | Network Diagram |

C4 Dynamic은 소프트웨어 요소 간 실행 순서에는 적합하지만,
복잡한 인간 업무 승인 절차 전체를 대체하려고 사용하지 않는다.

---

## 7. 표기와 가독성

C4는 notation independent다. 어떤 도형·색을 쓰든 다음은 필요하다.

- 다이어그램 제목
- 다이어그램 유형
- 범위
- 범례
- 모든 요소의 이름과 유형
- 요소의 한 줄 책임 설명
- 적용 가능한 기술 정보
- 모든 관계의 방향과 목적
- 약어 설명

가독성 휴리스틱이며 C4 공식 규칙은 아닌 권장값:

- 한 View에 핵심 요소가 약 5~12개면 읽기 쉽다.
- 15개를 크게 넘기면 같은 수준의 여러 View로 분리할지 검토한다.
- 선 교차를 줄이고 주요 흐름은 왼쪽→오른쪽 또는 위→아래 중 하나로 통일한다.
- 색상은 유형이나 상태처럼 명확한 의미가 있을 때만 사용하고 범례에 설명한다.

---

## 8. 공식 출처

아래는 이 가이드가 근거로 삼은 공식 문서다. 내용은 요약·재구성했으며,
예제 이미지나 문장을 복제하지 않는다.

- C4 model home: https://c4model.com/
- Introduction: https://c4model.com/introduction
- Abstractions: https://c4model.com/abstractions
- Diagrams overview: https://c4model.com/diagrams
- System Context: https://c4model.com/diagrams/system-context
- Container: https://c4model.com/diagrams/container
- Component: https://c4model.com/diagrams/component
- Code: https://c4model.com/diagrams/code
- System Landscape: https://c4model.com/diagrams/system-landscape
- Dynamic: https://c4model.com/diagrams/dynamic
- Deployment: https://c4model.com/diagrams/deployment
- Notation: https://c4model.com/diagrams/notation
- Review checklist: https://c4model.com/diagrams/checklist
- Structurizr DSL: https://docs.structurizr.com/dsl

C4 공식 사이트와 예제 다이어그램은 CC BY 4.0으로 제공된다.
이 스킬이 공식 예제 이미지나 수정본을 포함하도록 확장될 경우 출처 표시와 라이선스 조건을 확인한다.
