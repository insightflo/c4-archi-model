# 빌드 시점 영수증 예제

대상: 렌더링 영수증을 생성·검증하는 개발자. 이 예제는 가상 데이터로 생성기 계약만 확인한다.
canonical model·전체 보고서 예제가 아니므로 전체 C4 품질 통과 증거로 쓰지 않는다.
기존 예제의 수제 SVG와 다른 경로이며, 성공 영수증을 손으로 작성하거나 저장해 재활용하지 않는다.

## 실행

저장소 루트에서 실행한다. Python 3와 Node 18+가 필요하다.

```bash
out=$(mktemp -d)
mkdir -p "$out/diagrams"
cp examples/receipt-flowmap/diagrams/context.flowmap.json "$out/diagrams/"
python3 scripts/build_repo_flowmap.py --root "$out" \
  --input diagrams/context.flowmap.json --output diagrams/context.flowmap.html
python3 scripts/validate_render_receipts.py --root "$out"
printf '생성 경로: %s\n' "$out"
```

생성 파일:

- `diagrams/context.flowmap.html`: 이번 실행이 만든 HTML
- `qa/repo-flowmap-validate-context.json`: 명시적 성공 상태, 실행 출력
- `qa/repo-flowmap-build-context.json`: 입력 경로·`specification.sha256`, 출력 경로·`artifact.sha256`, 성공 상태

입력·출력 경로는 출력 패키지 기준 상대경로다. 패키지를 옮겨도 파일이 그대로면 검증된다.
입력 또는 HTML을 변경하면 영수증 검사는 실패한다. 같은 빌드 명령을 다시 실행해 재생성한다.
실패한 실행은 이전 HTML을 보존하지만 성공 영수증은 보존하지 않는다. 실패 원인을 고치기 전에는
남은 HTML을 이번 실행 결과로 제출하지 않는다.

## 인쇄와 신뢰 한계

이 생성기는 인쇄 SVG를 만들지 않는다. 별도 브라우저 추출기가 없다면 `printAssetPath`를
생략하고 인쇄 시 그림 누락을 명시한다. [어댑터](../../references/repo-flowmap-adapter.md)의
추출 영수증 계약을 따른다. 해시는 파일 변경을 탐지하지만, 사용자가 편집할 수 있는 영수증이
렌더러 실행 진위를 암호학적으로 보증하지는 않는다.
