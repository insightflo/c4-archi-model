# C4 Architecture Validation Checklist

이 체크리스트는 사람이 읽는 요약이다. 실제 최종 판정은 `scripts/validate_all.py`와 개별 validator가 수행한다.
체크박스만 채우고 실행 결과 없이 PASS라고 쓰지 않는다.

## A. Session

- [ ] SES-001 inScope와 outOfScope가 충돌하지 않는다.
- [ ] SES-002 focus Profile에는 target이 있다.
- [ ] SES-003 target ID가 canonical model에서 해석된다.
- [ ] SES-004 HTML이 사람이 여는 기본 출력에 포함된다.
- [ ] SES-005 presentationDetail(선택)이 모델 범위와 별개 축으로 기록되어 있다. 세션의 값을
      build_repo_flowmap.py `--presentation-detail`에 그대로 전달했다.
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
- [ ] 그림(existing-diagram) 근거만 있는 Claim은 VERIFIED가 아니다(EVD-019).
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
- [ ] 표시용 축약(presentationDetail·presentationLog)이 canonical 사실을 재정의하지 않는다.
      원본 ID·뷰 포함 목록은 상세도와 무관하게 그대로다.
- [ ] 화살표 설명은 방향·동사·목적을 가진다.

## D. View

- [ ] 모든 elementId, relationshipId, nextViewId가 존재한다.
- [ ] View의 relationship endpoint가 모두 elementIds 안에 있다.
- [ ] Context에 내부 Container·Component가 섞이지 않았다.
- [ ] Component View는 하나의 Container만 확대한다.
- [ ] Dynamic View에는 step이 있고 order가 1..N 연속이다.
- [ ] Dynamic step relationship이 같은 View의 relationshipIds에 있다.
- [ ] 비-Dynamic View에는 step이 없다.
- [ ] 다이어그램 입력과 렌더러 영수증은 같은 파일명 해석 규칙을 쓴다. 점을 포함한 View ID를 보존하고, 정확한 ID를 별칭보다 우선하며, 모호한 별칭은 거부한다.
- [ ] 동명 요소는 canonical ID로 구분한다. 렌더러 임시 ID는 이름으로 한 요소만 식별할 수 있을 때 사용한다.
- [ ] 관계 검사는 canonical ID·방향·동적 순서를 확인한다. 관계 ID가 없고 끝점이 같은 관계가 여럿이면 표시 라벨(flowmap의 `call`)로 구분한다. 명시적 관계 ID가 있을 때 표시 문구와 모델 설명의 의미 일치까지 보장하지는 않으므로 사람이 확인한다.
- [ ] 각 View는 답하는 질문과 의도적으로 보여주지 않는 것을 설명한다.
- [ ] 시각 예산 초과 경고를 확인하고 분리 여부를 결정했다.
- [ ] 상세도를 낮춘 View는 `c4.presentationLog`로 원본 수·표시 수·변경 이유(설명 축약·생략·
      뷰 분리 제안)를 원본 모델 ID로 되짚을 수 있다. 이 투영은 표시용 이름 변경을 만들지
      않는다(label === element.name). 축약을 이유로 요소·관계를 합치거나 삭제하지 않았다.
- [ ] 뷰 분리가 필요하면 새 View를 명시하고 nextViewIds로 연결했다(presentationLog의
      view-split-proposal은 권고일 뿐 자동 분리가 아니다).
- [ ] 관계선 끝·꺾임이 실제 연결 대상이 아닌 노드·라벨에 닿아 연결처럼 보이는 근접선이
      없다. 실제 양끝 연결점, 같은 노드 쌍 관계의 겹치는 공유 경로, 배지가 번호로 안내하는
      지점은 모델 근거 예외로만 허용한다(`check_repo_flowmap_browser.py` near-connection-mimics).
- [ ] 라벨 배경이 나중에 그린 노드에 가려지지 않는다. 배경 경계 겹침·노드 표식 겹침·실제
      가림을 구분해 보고하고 화면 DOM과 내보낸 SVG 모두에서 확인했다
      (`check_repo_flowmap_browser.py` label-occlusion).

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
- [ ] 뷰 탐색(내부 보기)은 canonical ID와 뷰 포함 목록·parentId 체인(scopeChain)으로만
      연결했다. 이름·제목 매칭으로 대상 뷰를 추론하지 않았고, 펼친 뷰가 보고서에 없는 요소는
      진입 불가로 표시했다(없는 뷰를 지어내지 않는다).
- [ ] 변경 전후 비교를 넣었다면: comparisonPath가 실제 비교 산출물을 가리키고(CMP 검증
      통과), 비교는 두 canonical 모델을 ID 기준으로만 만들었다. 같은 ID가 다른 대상을 가리킬
      가능성이 큰 변경은 미확정으로 표시했고, 어느 뷰에도 속하지 않은 변경도 표에 남았다.
      비교를 넣지 않았다면 이 항목은 해당 없다(보고서는 무변경).

## H. SVG와 HTML

- [ ] SVG가 parseable하다.
- [ ] SVG에 script, javascript URL, foreignObject, 외부 asset URL이 없다.
- [ ] archify 경로를 썼다면: deliver 성공 영수증이 qa/에 있고, input/specification.sha256과
      output/artifact.sha256이 현재 파일에 일치한다. 임베딩 SVG는 sourceSha256을 포함한
      extract_archify_svg.py 추출 영수증과 함께 있다.
- [ ] repo-flowmap 경로를 썼다면: build_repo_flowmap.py가 검증·빌드 성공과 입력/출력 해시를
      같은 실행에서 기록했다. 구 영수증을 사후 보충하지 않았다. 인쇄 SVG를 연결했다면
      repo-flowmap-svg-<view>.json에 원본 HTML 해시·출력 SVG 해시가 추출 시점에 기록되었다.
- [ ] 화면·인쇄 자산 및 내장 data URI는 모두 같은 canonical View의 검증된 산출물이다.
      해시 검증과 렌더러 실행 진위 증명을 혼동하지 않았다.
- [ ] validate JSON에 입력 연결 정보를 제공했다면 `input`과 `specification.sha256`을 함께 기록하고 현재 입력에 맞췄다. `viewId`를 제공했다면 해당 View와 일치한다.
- [ ] 명시적 인쇄 자산은 SVG/PNG/JPEG/GIF/WebP/BMP 이미지이며 확장자·MIME·바이트 형식이 맞는다. 검증된 HTML도 인쇄 이미지로 사용할 수 없다.
- [ ] archify 산출물에서 추출한 SVG의 스타일이 고유 id로 스코핑되어 있다.
- [ ] HTML에 외부 script, CSS, font, image runtime 의존성이 없다.
- [ ] `__REPORT_DATA_JSON__`, `{{PLACEHOLDER}}`, 미치환 token이 없다.
- [ ] 기본 HTML 문서 marker와 charset이 있다.
- [ ] 다이어그램 title, caption, alt가 있다.
- [ ] repo-flowmap SVG를 추출해 저장했다면 접근성 이름 구조(role="img", 고유 `<title id>`/
      `<desc id>`, `aria-labelledby` 연결, ID 고유성)가 `validate_svg_accessibility`를 통과했다.
      이 검사는 repo-flowmap 추출 산출물에만 적용되며 수제 예제 SVG에 소급 적용하지 않는다.
- [ ] 인터랙티브 다이어그랬의 자동 재생(있다면)은 화면 밖·숨김·대화상자 닫힘·제거에서 정지되고
      자동으로 재개되지 않는다(사용자 버튼으로만 재시작).
- [ ] 텍스트·관계선·포커스 표시의 밝기 대비가 기준(본문 텍스트 4.5:1, 의미 있는 비텍스트
      3:1, 장식 제외)을 충족한다. `scripts/verify_visual_contrast.py`를 실행했고 한계(LIMIT)는
      visual-budgets.md의 한계 기록 목록과 대응된다.
- [ ] 이름 있는 시각 프로필(보고서와 그림이 공유하는 색·글꼴·간격 묶음)을 노출했다면
      `verify_visual_contrast.py --profile <이름>`으로 같은 역할 검사를 통과했고, 프로필 전환이
      임베드 그림(전체 화면 포함)에 함께 적용되며 기본 복귀·렌더더 테마 전환과 직교함을
      확인했다. 미리 렌더링된 인쇄 이미지는 프로필을 반영하지 못한다(한계).
- [ ] 키보드 탐색, 확대·축소, 전체 화면, 검색, 인쇄 기능을 확인했다.
- [ ] 내부 보기 진입·복귀를 확인했다: 부모 경로(breadcrumb)가 확대 경로만 표시하고, 한 번에
      최상위로 돌아갔을 때 떠난 뷰의 선택 요소(canonical ID)와 카메라(또는 문서화된 복원 규칙)
      가 돌아온다. 직접 탭 선택은 이동 스택을 정리한다. 탐색 이동은 안내 재생을 정지한다(자동
      재개 없음). 인쇄에서 탐색 UI(부모 경로·내부 보기 단추)는 나오지 않는다.
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
