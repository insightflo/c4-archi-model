# 분석 Profile

작성 모드는 설명 방식이고 Profile은 조사 범위와 종료 조건이다. 두 축을 섞지 않는다.

## guided

목적: 처음 보는 사람이 전체 구조를 빠르게 이해하도록 한다.

기본 범위:

- 대상 시스템의 System Context
- 대상 시스템의 Container View
- 가장 중요한 정상 Dynamic 시나리오 1개
- 현재 질문에 직접 관련된 미확인과 다음 확대 후보

종료 기준:

- 대상 시스템의 바깥 경계와 주요 실행 단위를 설명할 수 있다.
- 핵심 흐름 하나를 시작부터 끝까지 따라갈 수 있다.
- 현재 설명이 답하지 않는 질문이 명시되어 있다.

## focus

목적: 특정 Container, Component 영역, Dynamic 시나리오 또는 배포 환경을 집중 분석한다.

필수:

- `targetIds` 또는 사람이 모호하지 않게 식별할 수 있는 대상
- 집중 질문과 기대 결과
- 포함 범위와 제외 범위

예:

```text
Order API 내부 Component
주문 저장 후 이벤트 발행 실패 경로
Production Deployment
인증과 권한 확인 흐름
```

focus라고 해서 Context를 완전히 생략하지 않는다. 집중 영역을 이해하는 데 필요한 상위 Context와 Container 요약은 유지한다.

## full

목적: 입력 자료에서 확인 가능한 전체 구조와 주요 시나리오를 조사한다.

가능한 범위:

- System Landscape
- 주요 System Context
- 전체 Container와 주요 Component
- 정상·실패·비동기 Dynamic 시나리오
- 환경별 Deployment
- intended / implemented / deployed 차이
- 전체 Evidence, Coverage, 충돌과 위험

full은 무한 조사를 뜻하지 않는다. Session의 자료 Snapshot, 범위, stopCondition으로 끝을 정의한다.

## 선택 규칙

```text
특정 대상 지정 → focus
전체·전부·full 명시 → full
그 외 → guided
```

독자 모드와 조합할 수 있다.

```text
beginner + full
expert + guided
both + focus
```

초보자용이라는 이유로 Evidence나 C4 semantic 검증을 생략하지 않는다. 달라지는 것은 설명 순서와 표현이다.
