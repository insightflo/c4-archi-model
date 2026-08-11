# C4 Architecture Model

검증 가능한 근거를 추적하는 C4 아키텍처 모델 스킬. 설계 문서, 소스 코드, API 명세, 배포 설정에서 증거를 추출해 **canonical architecture model**을 만들고, 단일 오프라인 HTML 보고서로 조립한다.

Agent-independent: 특정 LLM, 코딩 에이전트, 운영체제, 플러그인에 종속되지 않는다. Python 표준 라이브러리만으로 검증 스크립트가 동작한다.

---

## What it does

```
Design docs · Code · API specs · Deploy configs · Runtime data
  ↓ Source Snapshot + Evidence Claim
Canonical Architecture Model (JSON)
  ↓ C4 Views + Beginner/Expert explanation
Single offline HTML report
```

- **근거 추적**: 모든 아키텍처 요소·관계는 출처(Claim)가 연결된다. 문서에 없는 사실을 채우지 않는다.
- **독자 수준별 설명**: 초보자용(용어 풀이·비유·단계별 흐름) / 전문가용(경계·책임·계약·트레이드오프)
- **분석 Profile**: `guided`(빠른 전체 구조) / `focus`(특정 영역 심층) / `full`(전체 범위)
- **검증 파이프라인**: Schema → C4 semantic → Evidence → Coverage → Human Understanding Gate → HTML
- **단일 HTML 보고서**: 외부 CDN·웹폰트 없이 로컬에서 바로 열리는 오프라인 파일

---

## Quick install

### Hermes Agent

```bash
# skill 디렉토리에 복사
cp -r c4-archi-model ~/.hermes/skills/software-development/

# manifest 재생성 (SKILL.md 수정 시)
cd ~/.hermes/skills/software-development/c4-archi-model
python3 scripts/generate_manifest.py --root .
```

### Claude / 기타 agent

skill 디렉토리에 `SKILL.md`가 있으면 자동으로 인식하는 에이전트는 복사만 하면 된다. 그 외에는 `SKILL.md`를 시스템 프롬프트나 context로 제공한다.

---

## Usage

스킬이 로드된 상태에서 자연어로 요청하면 된다.

```
이 설계 문서를 C4로 그려줘
코드베이스 구조를 Context / Container / Component로 설명해줘
초보자용으로 시스템 아키텍처 설명해줘
배포 환경까지 포함해서 전체 아키텍처 문서를 만들어줘
```

상세한 워크플로와 규칙은 `SKILL.md`를 참고한다.

---

## Validate (self-check)

```bash
# 스킬 패키지 자체 검증
python3 scripts/validate_skill_package.py --root .

# 산출물 전체 검증
python3 scripts/validate_all.py \
  --root <output-root> \
  --data <output-root>/html/report-data.json

# 회귀 테스트
python3 scripts/run_regression_tests.py
```

---

## Output structure

```
c4-architecture/
├─ index.html              ← 사람이 열 최종 보고서
├─ HANDOFF.md
├─ manifest.json
├─ model/
│  ├─ architecture-session.json
│  └─ architecture-model.json
├─ html/
│  └─ report-data.json
├─ diagrams/
│  ├─ *.svg
│  └─ *.puml
├─ explanation/
│  ├─ beginner.md
│  └─ expert.md
└─ qa/
   ├─ evidence-ledger.json
   ├─ coverage.json
   ├─ human-understanding.json
   └─ *-validation.json
```

---

## Requirements

- Python 3.9+ (표준 라이브러리만 사용, 외부 패키지 불필요)
- 파일 읽기·쓰기가 가능한 에이전트 환경

---

## License

[MIT](LICENSE) · © 2026 inflo
