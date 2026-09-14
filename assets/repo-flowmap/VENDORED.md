# Vendored: repo-flowmap

이 디렉터리는 c4-archi-model의 **번들 폴백 다이어그램 렌더러**다. archify가 미가용일 때
Node 18+만으로 다이어그램을 검증·렌더링하기 위해 포함했다. 사용 계약은
`references/repo-flowmap-adapter.md`를 따른다.

- 원본: `/Users/kwak/Projects/ref/knowledge/skills/repo-flowmap`
- 포함 시점: 2026-09-14 (원본 파일 기준 2026-08-31 스냅샷)
- 라이선스: 원본 저장소에 LICENSE 파일이 없다. c4-archi-model(MIT)과 같은 소유자의
  사내·개인 자산이므로 여기에 포함한다. 원본을 외부에 배포할 계획이 생기면 라이선스를 먼저 정리한다.

## 포함 파일

| 파일 | 용도 |
|---|---|
| `SKILL.md` | repo-flowmap 원본 사용 계약 (모드·고정 규칙) |
| `SCHEMA.md` | flowmap.json 스키마 |
| `template.html` | 고정 렌더러 (수정 금지) |
| `references/RENDERER_RULES.md` | 렌더러 동작 규칙 |
| `scripts/validate_flowmap.mjs` | JSON 검증기 |
| `scripts/build_flowmap.mjs` | HTML 빌더 (JSON 마커 주입) |
| `CHANGELOG.md` | 원본 변경 이력 |

## 제외 파일

- `agents/openai.yaml` — 특정 에이전트 하네스 전용 설정. c4-archi-model의
  에이전트 독립성 원칙에 맞지 않아 제외.

## 수정 정책

- 기능 파일(SKILL.md, SCHEMA.md, template.html, scripts, references)은 원본과 동일하게
  유지한다. 기능 파일을 바꿨다면 이 문서에 "로컬 변경" 절을 추가하고 내용을 적는다.
- 현재 로컬 변경: **없음** (2026-09-14).
- 원본을 갱신할 때는 이 디렉터리에 다시 복사하고, c4-archi-model의
  `python3 scripts/generate_manifest.py --root .`를 재실행한다.
