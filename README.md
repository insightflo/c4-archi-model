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
- **그림과 함께 단계별 읽기**: 단계 선택·원본 그림·근거 설명을 한 화면에 둔다. 원본 SVG의 View·단계·관계 식별자와 실제 도형 위치를 대조해 해당 메시지만 강조한다. 반복 관계도 단계별로 구별하며, 선택 부분/전체 그림·확대·읽기 크기·방향키 탐색을 지원한다. 의미 식별자가 없거나 모호하면 강조하지 않고 원본과 한계를 표시한다. 원본 파일은 수정하지 않는다.
- **책임·미확인 비교**: 구성요소별 역할·기록된 장애 영향을 같은 표에서 비교하고 선택 요소를 원본 그림에서 강조한다. 관계는 해당 그림의 받음/보냄, 배치 유형·배치 View, 나머지 범위로 구분해 모두 보존한다. 모바일에서는 선택 설명을 그림 바로 아래에 두고 비교표로 초점을 돌려준다. 미확인은 내용 → 영향 분류 → 다음 확인에 더해 원장에 연결된 View·요소로 이동할 수 있으며, 관계만으로 특정 단계의 결함을 추정하지 않는다.
- **주장에서 원장까지**: 단계·책임·미확인·추적성 표의 주장 버튼으로 정확한 Claim 원장과 출처, locator, 인용문, 충돌 근거를 연다. DOC_ONLY 등 확인 수준을 보존하며 근거 열람을 운영 검증으로 취급하지 않는다. 인쇄에는 전체 원본 그림(SVG·제공된 PNG 등), 모든 단계와 책임표 관계 본문을 표시하고 인쇄 후 펼침 상태를 복원한다.
- **기록 시점 구분**: 개요의 ‘현재/최신’ 표현과 과거 분석 범위·이해도 QA는 당시 기록으로 표시한다. 원문의 결과·시각·대상·한계를 보존하며 이번 HTML 빌드 검사나 새 브라우저 검사로 바꾸어 해석하지 않는다. 시각이나 대상이 없으면 없다고 표시한다.

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
# 환경 진단 — 선택될 렌더 경로 표시 (archify / 번들 repo-flowmap / 폴백)
python3 scripts/doctor.py

# 스킬 패키지 자체 검증
python3 scripts/validate_skill_package.py --root .

# 산출물 전체 검증
python3 scripts/validate_all.py \
  --root <output-root> \
  --data <output-root>/html/report-data.json

# 회귀 테스트
python3 scripts/run_regression_tests.py
python3 -m unittest discover -s tests -v
```

실제 화면 회귀 검사는 로컬 Chrome/Chromium과 Python `playwright`를 사용한다. PDF 텍스트 검사에는 `pypdf`도 필요하다. 브라우저 경로는 `C4_BROWSER`로 지정할 수 있다. `C4_REAL_PACKAGE=/absolute/package/path`를 설정하면 실제 패키지를 **읽기 전용**으로 임시 HTML에 빌드하고 원본 파일 해시가 그대로인지 확인한다. 브라우저 미설치나 실제 패키지 미지정으로 건너뛴 검사는 통과로 세지 않는다.

```bash
C4_REAL_PACKAGE=/absolute/package/path python3 -B -m unittest discover -s tests -v
python3 -B -m unittest discover -s tests -p test_report_external_review.py -v
```

문자열 회귀는 `<!-- <script>`, 닫는 script 태그, 한국어와 HTML 원문을 넣어 **실제 초기화와 내용 복원**을 함께 확인한다. 인쇄는 PDF 본문·책임표 구조·펼침 복원, 모바일은 선택 설명과 초점 위치, 동작 줄이기는 실제 버튼 클릭 후 이동 좌표로 확인한다. 콘솔 오류가 없거나 미디어 규칙이 존재한다는 사실만으로 통과시키지 않는다.

---

## 렌더링 영수증 재생성

구 영수증에 해시만 덧붙이지 말고 실제 렌더링을 다시 실행한다. 번들 repo-flowmap은
다음 명령이 검증·빌드와 입력/출력 SHA-256(파일 변경 확인값) 기록을 함께 수행한다:

```bash
python3 scripts/build_repo_flowmap.py --root <output-root> \
  --input diagrams/<view>.flowmap.json --output diagrams/<view>.flowmap.html
```

Archify는 native `validate`/`deliver --json` 결과를 보존하고
`extract_archify_svg.py --json`으로 다시 추출한다. 추출 영수증의 `sourceSha256`도 필수다.
화면·인쇄 자산은 같은 View의 검증된 파일이어야 하며 바이트 수만 기록한 영수증은 거부한다.
실행 예제: [receipt-flowmap](examples/receipt-flowmap/README.md).
상세 계약: [Archify](references/archify-adapter.md), [repo-flowmap](references/repo-flowmap-adapter.md).

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


## Repo-flowmap 보기 종류 확장 (명시적 포크)

Archify 우선 / 번들 repo-flowmap 폴백은 유지한다. 새 엔진으로 교체하지 않고,
기존 `assets/repo-flowmap/template.html` 안에 구조/클래스/시퀀스/배치를 확장했다.
출처와 라이선스 제한은 [포크 기록](assets/repo-flowmap/VENDORED.md),
지원 범위·schema·실행·NOT_RUN 계약은 [어댑터](references/repo-flowmap-adapter.md)를 따른다.

```bash
python3 scripts/generate_repo_flowmap_demo.py --output /tmp/new-flowmap-demo
python3 scripts/build_repo_flowmap.py --root /tmp/new-flowmap-demo \
  --model model/architecture-model.json --view ordering-sequence
python3 -B -m unittest discover -s tests -v
python3 scripts/run_regression_tests.py
python3 scripts/validate_skill_package.py --root .
```

데모는 가상 사실이다. 실제 코드 분석 결과로 인용하지 않는다. 브라우저용 선택 도구는
`export_repo_flowmap_svg.py`, `check_repo_flowmap_browser.py`이며 둘 다 기본은 file://다.
Node HTML 생성 성공은 브라우저 표시/상호작용 성공을 의미하지 않는다.
