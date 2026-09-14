---
name: repo-flowmap
description: 레포의 패키지·모듈·컴포넌트 사이 동작을 근거 코드에서 추출해 JSON 기반 인터랙티브 단일 HTML 흐름도로 생성하거나 git diff 기준으로 갱신한다. 최초 생성(init), 사용자 확인형 증분 갱신(update), 삭제 없는 자동 갱신(auto), 흐름도 규칙·연결점·SVG 출력이 필요한 저장소 문서화 작업에 사용한다.
---

# Repo Flowmap

레포의 실제 호출 관계를 `docs/flowmap/flowmap.json` 하나로 관리하고 고정 렌더러로
`docs/flowmap/flowmap.html`을 만든다. 추측한 관계를 추가하지 않는다.

작업 전에 반드시 [`SCHEMA.md`](SCHEMA.md)를 읽는다. 렌더러 동작을 판단해야 할 때만
[`references/RENDERER_RULES.md`](references/RENDERER_RULES.md)를 읽는다.

## 고정 계약

- 상태의 단일 진실 공급원은 `flowmap.json`이다.
- `template.html`은 사용자가 렌더러 수정을 요청한 경우 외에는 수정하지 않는다.
- JSON은 `template.html`의 `/* FLOWMAP_JSON */` 한 곳에 인라인 주입한다.
- `fetch`로 바꾸지 않는다. 결과는 `file://`에서도 동작해야 한다.
- 노드·플로우 ID는 한번 공개되면 불변이다.
- 플로우 ID는 `^[A-Za-z0-9_-]+$` 슬러그만 쓴다. URL `#flow=<id>` 복원 계약이며
  점·공백·한글 ID는 하위 호환 없이 검증에서 거부된다.
- 코드 근거가 불명확한 단계는 만들지 말고 후보 또는 stale로 보고한다.
- 브랜드·외부 링크·로고·마스코트·개인 이름·이메일·이전 레포 예시를 넣지 않는다.
  근거 파일은 저장소 상대 경로만 쓰고, 로컬 절대경로·원격 자산·추적 코드를 추가하지 않는다.

## 모드 결정

1. `docs/flowmap/flowmap.json`이 없으면 **init**
2. 파일이 있으면 **update**
3. 사용자가 자동·무확인 실행을 요청하거나 스케줄 실행이면 **auto**

## init

1. 진입점(UI 액션, API 라우트, CLI, 이벤트, 작업 스크립트)을 찾는다.
2. 각 진입점에서 실제 호출·데이터 전달을 따라 노드와 플로우 후보를 만든다.
3. 패키지/모듈 목록, 플로우 목록, 제외 사유를 사용자에게 확인받는다.
4. 승인 후 스키마에 맞춰 `flowmap.json`을 만들고 현재 HEAD를
   `meta.last_analyzed_commit`에 기록한다.
5. 검증하고 HTML을 생성한다.

```bash
node <skill>/scripts/validate_flowmap.mjs docs/flowmap/flowmap.json
node <skill>/scripts/build_flowmap.mjs docs/flowmap/flowmap.json \
  <skill>/template.html docs/flowmap/flowmap.html
```

6. 가능하면 브라우저에서 목록, 두 보기 모드, 단계 선택, 이동·확대, SVG 다운로드,
   콘솔 오류를 확인한다. 브라우저를 쓸 수 없으면 검증 통과와 마커 소거를 확인한다.

## update

1. `git diff <meta.last_analyzed_commit>..HEAD --stat`으로 변경 범위를 고정한다.
2. 변경 파일이 관여하는 기존 플로우만 다시 추적하고 새 진입점만 추가 탐색한다.
3. 추가·수정·삭제 후보를 diff 형태로 보여주고 승인받는다.
4. 승인된 JSON 변경만 적용한다. 렌더러는 수정하지 않는다.
5. `meta.last_analyzed_commit`을 현재 HEAD로 바꾸고 검증·빌드한다.
6. JSON diff가 승인 내용과 1:1인지 확인한다.

## auto

update 절차를 따르되 확인을 생략하고 다음 제한을 지킨다.

- 추가·수정만 적용한다.
- 삭제 후보는 삭제하지 않고 `status: "stale"`과 `stale_reason`만 기록한다.
- 기존 노드·플로우 ID를 변경하지 않는다.
- `docs/flowmap/auto-report.md`에 날짜, 커밋 범위, 적용 내용, stale 후보를 덧붙인다.

stale 삭제는 이후 수동 update에서만 수행한다.

## 데이터 표현 규칙

- `from !== to`: 모듈 사이 외부 연결
- `from === to`: 기본적으로 카드 내부 처리 행
- 실제 재귀·자기호출만 `kind: "self"` 또는 `recursive: true`
- `fromSide`/`toSide`는 코드나 도메인상 방향이 중요한 경우에만 지정
- 반환·콜백은 별도 방향 필드 없이 배치 순서로 자동 분류
- 단계의 `data`에는 “무엇이 넘어가는지”를 구체적으로 쓴다.

## 완료 보고

다음만 간결하게 보고한다.

- 모드(init/update/auto)와 분석 커밋 범위
- 노드·플로우·단계 수
- 추가·수정·stale·삭제 수
- 검증 및 브라우저 확인 결과
- 생성된 `flowmap.json`, `flowmap.html`의 절대 경로
