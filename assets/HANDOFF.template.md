# C4 Architecture Package Handoff

Status: `PASS | PASS_BOUNDED | REQUEST_CHANGES | NOT_RUN`

## 사람이 먼저 열 파일

- `index.html`

## 분석 계약

- 작성 모드: `<beginner | expert | both>`
- 분석 Profile: `<guided | focus | full>`
- 질문: `<architecture-session.json의 question>`
- 범위: `<inScope 요약>`
- 제외 범위: `<outOfScope 요약>`
- 종료 조건: `<stopCondition>`

## 원본과 파생 산출물

- 분석 세션: `model/architecture-session.json`
- Canonical model: `model/architecture-model.json`
- Evidence ledger: `qa/evidence-ledger.json`
- Coverage: `qa/coverage.json`
- 이해도 Gate: `qa/human-understanding.json`
- HTML 표시 데이터: `html/report-data.json`
- 패키지 Manifest: `manifest.json`

## 검증 명령

```bash
python3 <skill>/scripts/validate_all.py \
  --root . \
  --data html/report-data.json \
  --output-json qa/content-validation.json

python3 <skill>/scripts/validate_html_assets.py \
  index.html \
  --output-json qa/html-static-validation.json

python3 <skill>/scripts/validate_package.py \
  --root . \
  --manifest manifest.json \
  --output-json qa/package-validation.json
```

## 주장하면 안 되는 것

- 근거가 없는 배포 구조, 장애 대응, 재시도, 멱등성, 보안 통제를 확인된 사실처럼 말하지 않는다.
- `PASS_BOUNDED`를 전체 아키텍처 검증 완료로 바꾸어 말하지 않는다.
- Persona simulation을 실제 사용자 테스트라고 말하지 않는다.
- 렌더링되지 않은 source diagram을 완성된 그림이라고 말하지 않는다.

## 남은 경계와 다음 확인

`qa/coverage.json`의 `unknownRelevant`, `unknownOutOfScope`, `expansionPoints`를 따른다.
