# C4 Architecture Validation Checklist

이 체크리스트는 사람이 읽는 요약이다. 실제 최종 판정은 `scripts/validate_all.py`와 개별 validator가 수행한다.
체크박스만 채우고 실행 결과 없이 PASS라고 쓰지 않는다.

## A. Session

- [ ] SES-001 inScope와 outOfScope가 충돌하지 않는다.
- [ ] SES-002 focus Profile에는 target이 있다.
- [ ] SES-003 target ID가 canonical model에서 해석된다.
- [ ] SES-004 HTML이 사람이 여는 기본 출력에 포함된다.
- [ ] 독자 모드와 분석 Profile이 서로 다른 축으로 기록되어 있다.
- [ ] 질문, 기대 결과와 stopCondition이 검증 가능하게 적혀 있다.

## B. Source Snapshot와 Evidence

- [ ] EVD-001 Session과 Ledger의 sessionId가 같다.
- [ ] Source와 Claim ID가 중복되지 않는다.
- [ ] Snapshot sourceIds와 Evidence Ledger의 등록 Source 목록이 정확히 일치한다.
- [ ] Session, Model, Ledger의 Snapshot ID가 같다.
- [ ] mutable technical source에는 immutableRef 또는 contentHash가 있다. 없으면 경고다.
- [ ] 모든 support·contradiction source ID가 등록되어 있다.
- [ ] VERIFIED Claim에는 support가 있다.
- [ ] CONFLICT Claim에는 contradiction이 있다.
- [ ] 모든 targetId와 usedBy가 실제 canonical ID를 가리킨다.
- [ ] canonical model이 참조하는 모든 Claim이 Ledger에 있다.

## C. Canonical Model과 C4 Semantic

- [ ] MOD-001 element, relationship, view, dynamic step ID가 전역에서 고유하다.
- [ ] targetSystemId가 Software System을 가리킨다.
- [ ] Container parent는 Software System이다.
- [ ] Component parent는 Container이다.
- [ ] Code Element parent는 Component이다.
- [ ] Deployment parent와 instanceOfId가 유효하다.
- [ ] unresolved 항목을 VERIFIED로 표시하지 않았다.
- [ ] 모든 element와 relationship에 Claim이 있다.
- [ ] relationship endpoint가 존재한다.
- [ ] 화살표 설명은 방향·동사·목적을 가진다.

## D. View

- [ ] 모든 elementId, relationshipId, nextViewId가 존재한다.
- [ ] View의 relationship endpoint가 모두 elementIds 안에 있다.
- [ ] Context에 내부 Container·Component가 섞이지 않았다.
- [ ] Component View는 하나의 Container만 확대한다.
- [ ] Dynamic View에는 step이 있고 order가 1..N 연속이다.
- [ ] Dynamic step relationship이 같은 View의 relationshipIds에 있다.
- [ ] 비-Dynamic View에는 step이 없다.
- [ ] 각 View는 답하는 질문과 의도적으로 보여주지 않는 것을 설명한다.
- [ ] 시각 예산 초과 경고를 확인하고 분리 여부를 결정했다.

## E. Coverage

- [ ] Coverage ID가 고유하다.
- [ ] affected model/view, source, claim 참조가 유효하다.
- [ ] blocker가 completion.blockingIds에 포함된다.
- [ ] PASS에는 blocker가 없고 questionAnswered와 stopConditionMet이 true다.
- [ ] PASS_BOUNDED에는 명시적 경계가 있고 blocker는 없다.
- [ ] REQUEST_CHANGES에는 blocker가 있다.
- [ ] NOT_RUN이 완료를 주장하지 않는다.

## F. Human Understanding

- [ ] 방법이 human-review / persona-simulation / not-run 중 하나다.
- [ ] simulation 여부가 method와 일치한다.
- [ ] beginner에는 B-01..B-05가 있다.
- [ ] expert에는 E-01..E-06이 있다.
- [ ] both에는 두 세트가 모두 있다.
- [ ] 실행한 질문에는 answer가 있다.
- [ ] PASS_BOUNDED에는 limitation이 있다.
- [ ] 질문의 model/view/evidence 참조가 유효하다.
- [ ] persona simulation을 실제 사용자 테스트라고 표현하지 않는다.

## G. HTML Report Data

- [ ] JSON Schema에 맞는다.
- [ ] diagram viewId가 canonical View를 가리킨다.
- [ ] flow viewId가 Dynamic View이고 stepId가 실제 canonical step이다.
- [ ] element card는 modelId와 presentation만 사용한다.
- [ ] name, type, technology, description을 표시 데이터가 재정의하지 않는다.
- [ ] factual section에는 Claim, model 또는 Coverage issue 연결이 있다.
- [ ] 모든 Claim과 issue ID가 등록되어 있다.
- [ ] required expected file이 실제로 존재한다.

## H. SVG와 HTML

- [ ] SVG가 parseable하다.
- [ ] SVG에 script, javascript URL, foreignObject, 외부 asset URL이 없다.
- [ ] archify 경로를 썼다면: deliver exit 0 영수증이 qa/에 있고, 통과 후보를 재편집하지
      않았고, 임베딩 SVG는 extract_archify_svg.py 추출 영수증과 함께 있다.
- [ ] archify 산출물에서 추출한 SVG의 스타일이 고유 id로 스코핑되어 있다.
- [ ] HTML에 외부 script, CSS, font, image runtime 의존성이 없다.
- [ ] `__REPORT_DATA_JSON__`, `{{PLACEHOLDER}}`, 미치환 token이 없다.
- [ ] 기본 HTML 문서 marker와 charset이 있다.
- [ ] 다이어그램 title, caption, alt가 있다.
- [ ] 키보드 탐색, 확대·축소, 전체 화면, 검색, 인쇄 기능을 확인했다.
- [ ] Desktop·Mobile·한글 렌더링 검사를 실행했거나 NOT RUN으로 기록했다.

## I. Output Package

- [ ] index.html, HANDOFF.md와 manifest.json이 있다.
- [ ] manifest의 모든 파일 SHA-256과 byte 크기가 실제 파일과 같다.
- [ ] unlisted 또는 missing 파일이 없다.
- [ ] entryPoint와 paths가 실제 파일을 가리킨다.
- [ ] `.git`, `.DS_Store`, cache, bytecode, database, backup 파일이 없다.
- [ ] symlink나 package root 밖 경로가 없다.
- [ ] QA report를 생성하고 manifest validation 결과를 갱신했다.

## J. 실행 순서

```bash
python3 <skill>/scripts/validate_all.py   --root <output-root>   --data html/report-data.json   --output-json qa/content-validation.json

python3 <skill>/scripts/build_html_report.py   --root <output-root>   --data html/report-data.json   --template <skill>/assets/html-report-template.html   --output <output-root>/index.html   --validation-output <output-root>/qa/html-build-validation.json

python3 <skill>/scripts/validate_html_assets.py   <output-root>/index.html   --output-json <output-root>/qa/html-static-validation.json

python3 <skill>/scripts/build_output_manifest.py --root <output-root>
python3 <skill>/scripts/validate_package.py   --root <output-root>   --manifest manifest.json   --output-json <output-root>/qa/package-validation.json   --update-manifest
```

## K. 최종 판정

```text
PASS             현재 질문과 종료 조건 충족, blocker 없음
PASS_BOUNDED     질문은 답했으나 명시적 경계가 남음
REQUEST_CHANGES  핵심 판단을 막는 미확인 또는 오해가 남음
NOT_RUN          검사를 실행하지 않음
FAIL             Schema·semantic·asset·package 오류
```

검사하지 않은 것을 PASS로 바꾸지 않는다. validation JSON과 Handoff에 실제 결과를 남긴다.
