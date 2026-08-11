# C4 Visual Budgets

시각 예산은 절대 제한이 아니라 첫 화면이 인간의 작업 기억을 짓밟기 시작하는 경고선이다.
초과하면 같은 추상화 수준의 View를 나누거나 확대 경로를 제공한다.

| View | 기본 경고선 | 대응 |
|---|---:|---|
| System Context | 대상 시스템 포함 약 10개 요소 | 외부 그룹 분리 또는 Landscape 추가 |
| Container | 약 14개 요소 | 도메인·흐름별 Container View 분리 |
| Component | 한 Container, Component 약 15개 | 책임 영역별 Component View 분리 |
| Dynamic | 2~15 step, 핵심 읽기는 5~12 권장 | 정상·실패·재처리 흐름 분리 |
| Deployment | 환경별 View, 중첩 Node 3단계 권장 | Production/Staging 분리 |

## Progressive disclosure

```text
System Landscape
→ System Context
→ Container
→ 선택한 Component
→ 핵심 Code 또는 Deployment
```

각 View에 다음을 표시한다.

```text
이 View가 답하는 질문
의도적으로 보여주지 않는 것
다음으로 확대할 View
```

## 금지

- 과밀도를 해결하려고 글자를 읽을 수 없게 줄이기
- 서로 다른 추상화 수준을 한 장에 넣기
- 화살표를 생략해 관계 의미를 감추기
- 모든 기능을 첫 화면에 배치하기
- 색상만으로 확인됨·미확인·충돌 상태를 구분하기

## 접근성

- 색상 외에 텍스트·아이콘·선 스타일을 함께 사용한다.
- 다이어그램에 대체 텍스트와 caption을 둔다.
- 브라우저 확대와 키보드 탭 이동을 지원한다.
- 한글이 들어간 SVG는 실제 브라우저에서 깨짐과 잘림을 확인한다.
