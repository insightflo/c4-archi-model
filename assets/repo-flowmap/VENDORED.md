# Repo-flowmap — 명시적 유지보수 포크 (typed views extension v1)

이 디렉터리는 **repo-flowmap 자체의 번들 포크**다. 별도 렌더러나 외부 SVG 엔진으로
대체하지 않는다. 기존 `scripts/build_repo_flowmap.py → scripts/build_flowmap.mjs →
template.html` 경로, 지도 DOM, 라우팅, 상태, 목록·패널, 카메라, 드래그, SVG 내보내기를 사용한다.
**Archify 우선 / repo-flowmap 번들 폴백 정책은 변경하지 않는다.** 사용자가 repo-flowmap을
명시적으로 선택하면 기존 정책에 따라 이 경로를 사용한다.

## 원 출처·라이선스

- 기준: c4-archi-model `0e2aef45ed9c01a329b6af2f71039c11e19f482c`의 번들.
- 기준 번들의 출처 기록: `/Users/kwak/Projects/ref/knowledge/skills/repo-flowmap`.
- 원래 포함일: 2026-09-14; 원본 파일 기준 2026-08-31 스냅샷.
- 기준 문서에는 upstream LICENSE가 없고, 동일 소유자의 사내·개인 자산으로 포함했다고
  적혀 있다. 이번 변경에서 확인하지 않은 원격 저장소 URL이나 upstream 라이선스를
  만들어 붙이지 않는다. 프로젝트 루트 MIT가 모든 upstream 권리를 확정한다는 주장은 하지 않는다.
- 기존 template의 Freesentation subset/OFL 고지 및 내장 데이터는 보존했다.
  별도 폰트 파일을 추가하거나 배포하지 않는다.
- 외부 배포 전 upstream 라이선스 정리가 필요하다는 기존 제한은 그대로 남는다.

## 이번에 명시적으로 바꾼 번들 파일

| 파일 | 변경 |
|---|---|
| `template.html` | 같은 renderMap에서 structure/class/sequence/deployment 분기, 기존 직각 라우팅 재사용, 타입·경계·UML marker·lifeline, 실제 SVG bbox 기반 export, 좁은 화면 및 iframe 카메라 메시지 |
| `scripts/validate_flowmap.mjs` | 선택적인 `c4` typed 확장 검증; legacy 검증 유지 |
| `scripts/build_flowmap.mjs` | 기존 JSON 마커 주입 유지, 쓰기 전 입력/템플릿/출력 충돌 차단 |
| `SKILL.md`, `SCHEMA.md` | 포크와 typed 계약을 명시; 아래 upstream legacy 규칙의 적용 범위 분리 |
| `references/RENDERER_RULES.md` | typed 규칙·지원 범위·기존 카메라 재사용 기록 |
| `CHANGELOG.md` | 이번 포크 변경을 과거 이력과 분리해 추가 |
| `UPSTREAM-HASHES.json` (신규) | 0e2aef4 번들 8개 원본 파일의 SHA-256. 원본 백업이 아닌 비교 기준 |

## 수정·유지보수·업데이트 정책

이 변경은 사용자가 **repo-flowmap renderer 수정**을 명시적으로 요구한 결과다.
기존의 ‘매 산출물마다 template을 임의 수정하지 않는다’ 원칙은 유지하되,
‘upstream과 무조건 byte-identical’ 계약은 이 문서로 **명시적 포크 유지** 계약으로 갱신한다.
분석 에이전트는 그림 하나를 만들 때 template을 고치지 않고 모델/입력만 바꾼다.
렌더러 수정은 이 소스에 코드·테스트·변경 기록을 함께 적용하는 유지보수 작업이다.

upstream을 갱신할 때 덮어쓰지 않는다. `UPSTREAM-HASHES.json`과 원본 0e2aef4를 기준으로
3-way diff를 만들고, upstream 변경과 로컬 typed 분기를 검토·병합한다. Legacy unit/회귀,
새 canonical/receipt/충돌 테스트와 browser 시각·상호작용 검사를 실행하고 결과 및
NOT_RUN을 기록한다. native 코드 변경 후 기존 typed 영수증은 다시 렌더링해 갱신한다.
마지막으로 프로젝트 manifest를 다시 생성한다. 원본의 라이선스가 추가되면 별도로 검토·기록한다.
