# Repo-flowmap 어댑터 — 기존 렌더러의 typed-view 확장

**Archify 우선 / repo-flowmap 번들 폴백** 정책은 그대로다. 사용자가 repo-flowmap을
명시하면 이 경로를 따른다. `assets/repo-flowmap/`은 원본 0e2aef4 번들의 명시적 포크이며,
출처·라이선스·변경 파일·업데이트 정책은 그 안의 `VENDORED.md`에 있다.

## 1. 실제 실행 경로와 의존성

```text
canonical model + evidence ledger
  → scripts/repo_flowmap_adapter.py (JSON 매핑만; 그래픽 생성 없음)
  → diagrams/<View-ID>.flowmap.json
  → scripts/build_repo_flowmap.py (동결 입력, 실제 Node validate/build, 실행 영수증)
  → assets/repo-flowmap/scripts/build_flowmap.mjs (기존 단일 마커 주입)
  → assets/repo-flowmap/template.html (기존 renderMap / 직각 라우팅 / #vp / camera)
  → diagrams/<View-ID>.flowmap.html
  → 기본 보고서 iframe (내장 bytes를 srcdoc에 전달, sandbox=allow-scripts)
```

Python 3.9+와 Node 18+가 필요하다. 생성 런타임은 양쪽 표준 라이브러리만 사용한다.
**브라우저 검증·SVG 추출만** 선택 의존성인 Python Playwright/Chromium을 사용한다.
외부 CDN, 원격 폰트 요청, 분석용 추적 코드는 추가하지 않는다. 원래 template의 내장
폰트 및 고지는 그대로 보존한다. Node가 없으면 기존 폴백 체인을 따른다.

## 2. 호환성: legacy와 typed는 같은 repo-flowmap

`c4` 필드가 없는 기존 `layers/nodes/flows` JSON과 기존 CLI는 그대로 지원한다.
기존 지도/동작 선택/단계/관련 모듈/연결 편집/테마/줌/팬/SVG 기능은 legacy에서 유지한다.

새 canonical 매핑에는 `c4.extensionVersion: 1`이 들어간다. 그래픽은 외부 어댑터가
그리지 않고, 같은 native template 내부의 보기별 분기가 그린다. typed에서는 canonical
요소를 조용히 생략하지 않도록 관련 모듈 필터와 수동 포트 편집을 비활성화하며 이유를 표시한다.
정적 구조의 번호는 시간순이 아닌 **관계 설명표 참조 번호**다. 시퀀스 번호만 step.order다.

| View | native mode / 표현 |
|---|---|
| Landscape / Context / Container / Component | `structure`: 사람 실루엣, 시스템 이중선, 컨테이너 탭, 컴포넌트 표식; parentId 경계; 기술·설명; 기존 라우터와 번호/설명표 |
| Code | `class`: 이름·속성·메서드 구획, 명시 UML 관계 종류별 선/끝표시 |
| Dynamic | `sequence`: 참가자·생명선·위→아래 메시지, 자기호출·반복 호출을 독립 step으로 유지 |
| Deployment | `deployment`: `physical-instances`는 기존 중첩 경계·명시 instanceOfId, `logical-placement`는 원래 부모 경계·논리 요소·원문 배치 관계를 유지하고 실제 인스턴스 배치가 아님을 명시 |

선 위 긴 문구는 구조/클래스/배치의 번호별 설명표로 옮겨 겹침을 줄인다. 다중성은 입력이
있을 때만 관계 설명표에 양 끝 ID와 함께 표시한다. 임의의 1/* 또는 항행 방향을 추가하지 않는다.

## 3. 코드 상세의 선택적 canonical 확장

schemaVersion 0.4.0의 기존 필수 필드는 그대로다. `codeElement.codeDetails`는 선택이다.
단, class를 실제 렌더링하려면 명시해야 한다.

```json
{
  "codeDetails": {
    "kind": "class",
    "attributes": [{"declaration": "- quantity: int", "claimIds": ["CL-01"]}],
    "methods": [{"declaration": "+ subtotal(): Decimal", "claimIds": ["CL-01"]}]
  }
}
```

kind는 class/interface. 구획 null은 자료 없음, []는 명시적 빈 목록이다.
관계에는 `codeRelation: {kind, claimIds, sourceMultiplicity?, destinationMultiplicity?}`를
명시한다. kind는 inheritance/realization/association/composition/dependency다.
상속·구현은 source가 하위/구현체, destination이 상위/인터페이스이며, 합성은 source가
소유자(채운 마름모)다. 연관에 방향을 추측하지 않는다. 다중성은 association/composition만
허용한다. 모든 멤버/관계 Claim은 실제 ledger에 있어야 한다. 샘플의 멤버는 가상이라고 명시한다.

## 4. 생성 명령과 strict 검증

```bash
# canonical에서 native 입력을 매핑하고 실제 repo-flowmap으로 생성
python3 <skill>/scripts/build_repo_flowmap.py \
  --root <package> --model model/architecture-model.json --view exact-view-id

# 기존 명령도 유지. typed 입력이면 authoritative model/ledger를 다시 대조한다.
python3 <skill>/scripts/build_repo_flowmap.py \
  --root <package> --input diagrams/exact-view-id.flowmap.json \
  --output diagrams/exact-view-id.flowmap.html

python3 <skill>/scripts/validate_all.py --root <package> --data html/report-data.json
python3 <skill>/scripts/build_html_report.py --root <package> --data html/report-data.json \
  --template <skill>/assets/html-report-template.html --output <package>/index.html
```

ledger 기본 경로는 qa/evidence-ledger.json이며 `--ledger`로 지정할 수 있다.
새 입력의 filename은 exact View ID로 생성한다. Canonical ID를 슬러그로 바꾸지 않는다.
출력은 실제 root/diagrams 안에서 동일 stem이어야 한다.

모든 입력/출력/영수증 경로의 resolve 및 inode 충돌(심볼릭·하드링크 포함)을 **첫 쓰기 전**
거부한다. 충돌 실패는 입력과 기존 결과 바이트를 보존한다. 다른 검증/실행 실패는 기존
HTML을 남겨도 성공 영수증을 무효화한다. 적대적 파일시스템 동시 변경에 대한 락/암호학적
진위 보증을 주장하지 않는다.

DIA-008은 authoritative model 경로·현재 bytes SHA·exact View·전체 projection을 비교한다.
노드/부모/instance target/관계/멤버/Claim/step/order와 표시 문구도 복제 사실로 대조한다.
input hash를 새로 적어도 canonical과 다르면 실패한다. 기존 DIA/RCP와 공통 strict 게이트를
생략하지 않는다. RCP-010은 native template/validate/build 구현 해시와 View 연결을 확인한다.
영수증은 기존 repo-flowmap family를 사용하고 input/output SHA-256·성공 상태를 기록한다.
문서상 숫자나 테스트 PASS를 렌더링/사람 이해도 PASS로 바꾸어 기록하지 않는다.

## 5. 보고서 임베딩과 native SVG 추출

보고서 diagram은 `assetPath`, `mimeType: "text/html"`, exact `viewId`를 사용한다.
빌더는 원본 HTML bytes를 data URI로 저장한다. template은 그 bytes를 그대로 decode해
iframe `srcdoc`에 넣으며 `sandbox="allow-scripts"`를 유지한다. 부모 버튼은 View ID가
일치하는 native 카메라 메시지를 보내므로 iframe 자체를 확대해 버튼을 잘라내지 않는다.

```bash
# 기본은 실제 file://로 생성 HTML 실행. 지원 환경이 없으면 NOT_RUN/실패한다.
python3 <skill>/scripts/export_repo_flowmap_svg.py --root <package> \
  --html diagrams/exact-view-id.flowmap.html --chromium /path/to/chromium
```

추출기는 **기존 renderer의 exportSvg()**를 실행한다. 별도 SVG 엔진이 아니다.
실행 중 원본 bytes를 잡고 HTML이 바뀌지 않았을 때만 sourceSha256/output SVG hash
영수증을 만든다. 성공 후 report-data의 `printAssetPath`를 해당 `.flowmap.svg`로 연결하고
strict builder를 재실행한다. null/생략은 인쇄 그림 미제공이며 한계를 HANDOFF에 남긴다.

환경 정책으로 file://가 막히면 통과로 처리하지 않는다. 진단용
`--transport injected-test`는 동일 bytes를 about:blank에 주입하는 **별도 테스트 운송 방식**이다.
영수증에 fileUrlVerified=false를 기록하며, 이것을 file:// 검증으로 계산하지 않는다.

## 6. 지원 범위와 실패

한 View 24요소 / 32관계 / 40step, sequence 12참가자 이하의 읽기 예산을 사용한다.
초과하거나 안전한 관계 번호 배치가 불가능하면 오류로 알리고 View 분리를 요구한다.
긴 텍스트는 줄바꿈해 높이를 늘리고 실제 glyph bbox를 다시 측정한다. 마지막 자기호출을
포함한 실제 geometry 밖으로 export canvas가 작아지지 않도록 너비·높이를 확장한다.

class 상세가 없는 codeElement, 함수/ERD를 class로 바꾸는 입력, decision/failure/recovery/return/alt 등의
시퀀스 fragment, 논리 요소를 배치 인스턴스로 간주하는 입력은 명시적으로 실패한다.
structure와 physical-instances에서 펼친 경계 자체를 관계 endpoint로 쓰는 View는 계속 거부한다.
logical-placement에서만 원래 경계의 머리글을 관계 연결점으로 사용한다. Async/return은 추측하지 않는다.

`interaction`의 `condition`은 fragment와 다르다. 어댑터는 원문 조건을 해당 단계의
표시용 `note` 앞에 `조건: <원문>`으로 붙이고, `canonicalStep.condition`,
`canonicalStep.note`, 관계 설명과 Claim은 그대로 보존한다. 조건 범위를 후속 단계 전체로
확장하거나 alt/opt 분기를 만들어내지 않는다. Native Node 검증기도 같은 표시용 note 규칙과
원본 단계 일치를 확인하며, 조건 삭제·변조 및 decision/failure/recovery는 거부한다.

논리 요소와 배치 후보 관계가 있는 deployment View는 잘못된 canonical 모델이라는 뜻이
아니다. 논리 softwareSystem/container가 포함되면 어댑터는 명시적인
`c4.deploymentPresentation: "logical-placement"`를 출력한다. 원래 parentId 중첩 경계,
선택 요소, 관계 방향·ID·설명·Claim을 그대로 표시한다. 경계 끝점은 머리글에 연결한다.
화면·SVG에 **실제 인스턴스 배치 아님**을 표시하며 후보인지 여부는 원문 관계 설명에 맡긴다.
`host-*`라는 ID나 설명만 보고 parentId를 바꾸거나 infrastructureNode/instanceOfId를 만들지 않는다.
논리 요소가 없으면 `physical-instances`이며 기존 타입·대상·경계 끝점 제한을 유지한다.
기존 native 입력에서 필드 생략은 물리 모드로 취급한다. 명시 논리 모드는 논리 요소가 있어야 한다.
실제 인스턴스 모델로 바꾸려면 작성자의 확인과 근거가 필요하며, 자동 변환하지 않는다.
Runtime에서 배치 실패 시 렌더 오류를 표시한다. CLI의 validate/build는 입력과 HTML 생성 검사이며,
브라우저 표시 확인을 대신하지 않는다. 손상되지 않은 HTML 영수증은 임의 그래프의 가독성 보증이 아니다.

## 7. 재현 가능한 검사

```bash
python3 <skill>/scripts/generate_repo_flowmap_demo.py --output <new-empty-directory>
python3 <skill>/scripts/check_repo_flowmap_browser.py --root <package> \
  --output <new-qa-directory-outside-package> --chromium /path/to/chromium
```

브라우저 검사는 실제 text/path/node bbox, 마지막 자기호출의 export 경계, 1440/360 화면,
native 줌/팬/표시, 보고서 iframe/줌/전체 화면, 인쇄 이미지 decode, 외부 요청 여부를 기록한다.
printAssetPath를 연결하기 전이면 print 검사는 실패하므로 먼저 추출하거나 해당 단계를 미실행으로
분리해 실행한다. 여러 브라우저·PDF 페이지 분할·실제 사람 이해도는 별도 검사다.
