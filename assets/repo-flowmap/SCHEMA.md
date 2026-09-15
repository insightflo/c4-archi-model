## 선택적 typed-view 확장 (extension v1)

원래 meta/layers/nodes/flows 계약은 그대로다. 새 `c4` 객체가 있으면 native validator는
extensionVersion=1, mode(structure/class/sequence/deployment), modelPath/modelSha256,
exact viewId, canonical view/boundaries/targets를 요구한다. 각 native node의 `element`,
각 step의 `relationship`/`canonicalStep`은 canonical 원문 복제이며 ID/label/call/order와
일치해야 한다. 더 강한 authoritative model·SHA·전체 projection 검사는 프로젝트 DIA-008이 한다.
외부 어댑터는 이 데이터만 매핑하며, 좌표/SVG를 주입하지 않는다. class codeDetails 및
codeRelation의 필드·근거 규칙은 프로젝트 adapter와 모델 스키마를 따른다.
Native typed 단계는 return/async/alt/par를 지원하는 것처럼 조용히 표시하지 않는다.
`interaction.condition`은 원문 그대로 `조건: <condition>\n<note>` 표시용 note에 붙인다
(원문 note가 없으면 줄바꿈 없음). canonicalStep은 변경하지 않으며 Node가 둘을 대조한다.
decision/failure/recovery 단계는 지원하지 않는다.

Deployment의 `c4.deploymentPresentation`:
- `physical-instances` (생략 시 기본): deploymentNode/infrastructureNode만 허용한다.
- `logical-placement`: softwareSystem/container가 하나 이상 있어야 하며 그 논리 요소에
  instanceOfId를 넣을 수 없다. 허용 타입은 위 물리 타입과 softwareSystem/container뿐이다.
  parentId와 관계를 그대로 유지한다. 펼친 경계 끝점은 해당 머리글에 연결하며,
  실제 인스턴스 배치가 아님을 화면·SVG에 명시한다. 물리 호스트 안으로 논리 요소를 옮기지 않는다.
- 다른 mode의 deploymentPresentation 또는 알 수 없는 값은 오류다.

이 필드는 표시 계약이며 canonical 스키마/모델 변경이 아니다. 물리 인스턴스를 추론하지 않는다.
아래는 기존 legacy schema다.

---

# flowmap.json 스키마

`flowmap.json`은 상태의 단일 진실 공급원이다. 빌드 스크립트가 JSON을
`template.html`의 `/* FLOWMAP_JSON */` 마커에 인라인 주입한다.

## 최상위

```jsonc
{
  "meta": { ... },
  "layers": [ ... ],
  "nodes": [ ... ],
  "flows": [ ... ]
}
```

## meta

| 필드 | 필수 | 설명 |
|---|---:|---|
| `project` | 예 | 레포 식별자 (문자열) |
| `title` | 아니오 | 탭·헤더 제목. 생략 시 템플릿 기본 문구 |
| `subtitle` | 아니오 | 헤더 부제. 생략 시 템플릿 기본 문구 |
| `last_analyzed_commit` | 예 | 다음 update의 diff 시작 커밋 |
| `basis` | 아니오 | 분석 기준 |
| `note` | 아니오 | 푸터 주석 |

## layers[]

| 필드 | 필수 | 설명 |
|---|---:|---|
| `id` | 예 | 유일한 레이어 ID |
| `label` | 예 | 컬럼 제목 |
| `color` | 아니오 | CSS 색상. `#hex`, 색상 이름, `rgb()`/`hsl()`, `var(--l-ui)` 형태만 허용(validator 검사) |

배열 순서는 왼쪽에서 오른쪽으로 배치되는 순서다.

## nodes[]

| 필드 | 필수 | 설명 |
|---|---:|---|
| `id` | 예 | 유일·불변 ID |
| `label` | 예 | 카드 제목 |
| `desc` | 아니오 | 카드 부제 |
| `layer` | 예 | `layers[].id` |
| `file` | 아니오 | 근거 파일 또는 식별자 |

같은 레이어 안에서는 배열 순서대로 위에서 아래로 배치한다.

## flows[]

| 필드 | 필수 | 설명 |
|---|---:|---|
| `id` | 예 | 유일·불변 ID. URL `#flow=<id>`에 사용하므로 영숫자·`_`·`-`만 허용 |
| `group` | 아니오 | 사이드바 그룹명 |
| `title` | 예 | 동작 이름 |
| `summary` | 아니오 | 한 줄 설명 |
| `status` | 아니오 | `"stale"`만 허용. 목록에 STALE 배지 + 흐림, 상세 패널에 경고 표시 |
| `stale_reason` | 아니오 | stale 근거 커밋·사유 |
| `steps` | 예 | 단계 배열 |

단계 배열 순서가 화면 단계 번호다.

## steps[]

| 필드 | 필수 | 설명 |
|---|---:|---|
| `from` / `to` | 예 | `nodes[].id` |
| `call` | 아니오 | 실제 함수·이벤트·쿼리 이름 |
| `data` | 아니오 | 이 구간에서 전달되는 값 |
| `note` | 아니오 | 함정·주의점 |
| `fromSide` / `toSide` | 아니오 | `top/right/bottom/left` 또는 `n/e/s/w` |
| `internalLabel` | 아니오 | 카드 내부 처리 행의 짧은 이름 |
| `kind` | 아니오 | 실제 자기호출일 때만 `"self"` |
| `recursive` | 아니오 | 실제 재귀일 때만 `true` |
| `state` | 아니오 | `"failover"` \| `"blocked"` \| `"cond"` — 아래 "선의 상태" |
| `stateLabel` | 아니오 | 분기 이름 등 12자 이하 짧은 라벨. `state` 없이 쓸 수 없음 |

### 선의 상태

평소에는 쓰지 않는다. 그 구간에서 **사건이 일어난다는 사실 자체가 이 동작의 요점일 때만** 붙인다.

| 값 | 뜻 | 화면 |
|---|---|---|
| `failover` | 이 길은 죽었고 다른 단계가 대신 간다 | 빨간 점선 + 가운데 X. **선을 지우지 않는다** — 무엇이 죽었는지가 같이 보여야 장애도가 읽힌다 |
| `blocked` | 목적지에 닿지 못하고 경계에서 끝난다(권한 거부·rate limit·정책 차단) | 62% 지점에서 끊기고 X, 남은 구간은 "원래 가려던 곳"을 옅은 점선으로 |
| `cond` | 조건에 따라 갈리는 갈래. 죽은 게 아니라 **둘 다 정상 경로** | 호박색 선 + `stateLabel` 칩(`HIT`/`MISS` 등) |

```jsonc
{ "from": "api", "to": "cache", "call": "get(key)", "state": "cond", "stateLabel": "HIT" },
{ "from": "api", "to": "db",    "call": "query()",  "state": "cond", "stateLabel": "MISS" },
{ "from": "req", "to": "web",   "call": "GET /",    "state": "blocked", "stateLabel": "429" }
```

`failover`로 죽은 길을 표시했으면 **대체 경로를 다음 단계로 반드시 함께 적는다.** 죽은 길만 있고
살아 있는 길이 없으면 그림이 "여기서 끝난다"고 말하게 되는데, 그건 `blocked`의 뜻이다.

### 같은 노드 단계

```jsonc
// 일반 내부 처리: 외부 선 없이 카드 안에 행으로 표시
{ "from": "validator", "to": "validator", "call": "normalize()" }

// 실제 자기호출/재귀: 카드 외부 순환 화살표
{ "from": "walker", "to": "walker", "call": "visit(child)", "recursive": true }
```

`from === to`라는 이유만으로 `kind: "self"`를 쓰지 않는다.

### 방향

기본 방향은 렌더러가 상대 위치와 장애물로 결정한다. 방향 자체가 도메인 의미를
가지거나 자동 결과가 불명확할 때만 `fromSide`/`toSide`를 쓴다.
사용자가 화면에서 편집한 연결점은 브라우저 로컬 저장값이 JSON보다 우선한다.

## 무결성 규칙

쓰기 전 `scripts/validate_flowmap.mjs`를 통과해야 한다.

- `meta.project`, `meta.last_analyzed_commit` 존재
- `layers`, `nodes`, `flows` 배열 존재
- 레이어·노드·플로우 ID 중복 금지
- 모든 `nodes[].layer`가 존재
- 모든 `steps[].from/to`가 존재
- 허용되지 않은 연결점·status·kind 값 금지
- `recursive: true` 또는 `kind: "self"`는 `from === to`에서만 허용
- `steps[].state`는 `failover`·`blocked`·`cond`만 허용하며 모듈 내부 처리 단계에는 금지
- `steps[].stateLabel`은 12자 이하이며 `state` 없이 단독 사용 금지
- `layers[].label` 필수, `layers[].color`는 허용 색상 형식만
- `flows[].id`는 `^[A-Za-z0-9_-]+$`
- 각 배열 항목은 객체여야 하며 `null` 항목 금지

렌더러는 일부 잘못된 엣지를 조용히 생략할 수 있으므로 눈으로만 검증하지 않는다.
