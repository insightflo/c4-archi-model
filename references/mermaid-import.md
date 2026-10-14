# 기존 Mermaid 다이어그램 가져오기 (mermaid-import)

이미 존재하는 Mermaid 다이어그램(`.mmd`)을 읽어 근거 원장에 "출처가 그림인 주장"으로
등록하는 최소 변환 경로다. `scripts/convert_mermaid_input.py`가 담당한다.

## 불변 계약

1. **정규 모델만 의미 진실이다.** 변환 결과는 근거 원장의 claim일 뿐이며,
   canonical model의 검증된 사실이 아니다. 사람이 주장을 검토한 뒤 기존 작성
   모드(`references/writing-modes.md`)대로 모델을 만든다. 변환기는 모델 뷰를
   자동 생성하지 않고 요소·관계 후보 목록(candidates)까지만 제공한다.
2. **실행 금지.** `.mmd` 텍스트를 렌더러나 자바스크립트로 실행하지 않는다.
   정규식 텍스트 파싱만 하고, 원본 줄은 claim의 `excerpt`에 그대로 보존한다(비실행 보존).
3. **스냅샷 등록.** 입력 `.mmd`는 원장 source로 등록한다 — `kind: "existing-diagram"`,
   `evidenceClass: "diagram"`, `immutableRef`·`contentHash`는 원본 bytes의 SHA-256.
4. **VERIFIED 불가.** 그림에서 읽은 주장의 `confidence`는 절대 `VERIFIED`가 될 수 없다.
   검증기 규칙 EVD-019가 강제한다(그림 근거만으로 VERIFIED인 claim 거부).
5. **읽지 못한 항목 보존.** 파싱 실패·무시된 줄은 결과 JSON의 `warnings`에 줄 번호와
   이유로 남기고 조용히 버리지 않는다.
6. **방향·ID 보존.** `TD/TB/BT/LR/RL` 방향 표기와 노드·참가자 ID를 원문 그대로 보존한다.

## 지원 범위와 지연 항목

지원하는 Mermaid 하위집합:

- `flowchart`/`graph`: 방향 선언, 노드(라벨·모양), 엣지(`-->`, `---`, `-.->`, `-.-`,
  `==>`, `===`, `--o`, `--x`, `<-->`, 파이프 라벨 `-->|라벨|`, 텍스트 라벨
  `-- 라벨 -->`), `&` 다중 끝점, `subgraph`(멤버십 기록).
- `sequenceDiagram`: `participant`/`actor`, 메시지(`->>`, `-->>`, `->`, `-->`, `-x`,
  `--x`), `Note over/left of/right of`, `alt/opt/loop/par/critical/break/rect` 블록,
  `autonumber`.

명시적으로 지연(이번에 지원하지 않음):

- **draw.io(`.drawio`), Excalidraw(`.excalidraw`) 변환** — XML/JSON 파싱 설계가
  별도로 필요하다. 필요해지면 이 문서와 변환기를 확장한다.
- 그 외 Mermaid 유형(`classDiagram`, `erDiagram`, `stateDiagram`, `gantt`, `pie`,
  `mindmap` 등) — 경고로 기록하고 주장을 만들지 않는다.
- 스타일·인터랙션 지시문(`style`, `classDef`, `click`, `linkStyle` 등)은 의미 정보가
  없어 무시하며 경고로 남긴다. 주석(`%%`)은 주석으로 인식해 경고 대상이 아니다.

## 사용법

```bash
# 1) 변환: 파싱 결과 + 원장 조각(source 1개 + claims) + 경고를 JSON으로 출력
python3 <skill>/scripts/convert_mermaid_input.py \
  --input legacy-flow.mmd \
  --output mermaid-conversion.json \
  --captured-at 2026-10-14T00:00:00Z

# 2) 기존 근거 원장에 병합(선택) — 원본 원장은 그대로 두고 병합본을 따로 쓴다
python3 <skill>/scripts/convert_mermaid_input.py \
  --input legacy-flow.mmd --output mermaid-conversion.json \
  --ledger architecture-evidence-ledger.json \
  --ledger-output architecture-evidence-ledger.merged.json \
  --claim-prefix CL-LEGACY
```

- `--source-id`(기본 `S-DIAG-<hash8>`), `--claim-prefix`(기본 `CL-DIAG`)로 ID 충돌을
  피한다. 병합 시 ID 충돌이 있으면 오류로 종료한다.
- 병합은 `snapshot.sourceIds`에 새 source를 추가해 EVD-004(스냅셋·source 일치)를
  유지하고, snapshot note에 변환 경로를 기록한다.

## 출력 구조

변환 결과 JSON(`--output`)의 최상위 키:

```text
parsed          — diagramType, flowchart{direction,nodes,edges,subgraphs} 또는
                  sequence{participants,messages,notes,blocks}, comments
candidates      — elements/relationships 후보(제안 ID, 이름, 근거 claim ID)
ledgerFragment  — 원장에 넣을 source(existing-diagram) + claims 배열
warnings        — 파싱 실패·무시된 줄(줄 번호·원문·이유)
stats           — 개수 요약
contract        — textOnlyParsing/renderOrExecutesMermaid=false 등 계약 고지
```

## derivation·confidence 매핑

| 그림 내용 | derivation | confidence | 이유 |
| --- | --- | --- | --- |
| 노드·참가자·엣지·메시지·라벨·화살표 표기 | `explicit` | `DOC_ONLY` | 그림에 명시되었고, 문서로만 존재(코드 미검증) |
| 배치 방향(TD/LR 등) 해석 | `inferred` | `UNVERIFIED` | 레이아웃 해석일 뿐 구조·의존 방향을 확정하지 않는다 |
| 화살표 종류의 동기·비동기 의미 해석 | (변환기가 만들지 않음) | — | 표기만 사실로 남기고 해석은 사람이 추가 근거와 함께 판단 |

`VERIFIED`는 어떤 경우에도 변환기가 생성하지 않는다. 이후 코드 근거가 붙어
`VERIFIED`로 승격하려면 `supports`에 코드 근거를 함께 두어야 한다(EVD-019는
그림 근거만 있는 VERIFIED를 거부한다).

## 후보 → 모델 워크플로

1. 변환 결과의 `warnings`를 먼저 읽는다(무시된 줄이 있는지).
2. `ledgerFragment.claims`를 검토하고 오독·누락을 사람이 판단한다.
   `targetIds`는 그림 ID에서 제안한 임시 ID다 — canonical model을 만든 뒤 실제
   요소·관계 ID로 다시 연결한다(`--model` 검증은 그 전까지 targetIds 오류를 낸다).
3. `candidates`를 참고해 기존 작성 모드대로 canonical model을 만들고, claim의
   `usedBy`를 채운다.
4. `validate_evidence_ledger.py`(EVD-019 포함)와 `validate_architecture_model.py`로
   검증한다.

예시: `examples/mermaid-import/legacy-order-flow.mmd`와 변환 결과
`examples/mermaid-import/legacy-order-flow.conversion.json`.
