# Invalid regression fixtures

`run_regression_tests.py`는 정상 Ordering System 예제를 복사해 다음 오류를 주입하고,
각 validator와 strict HTML builder가 반드시 거부하는지 확인한다.

| Fixture | 주입 오류 | 기대 코드 |
|---|---|---|
| model-schema-violation | interactionStyle을 허용되지 않은 값으로 변경 | SCHEMA-001 |
| bad-parent | Container parent를 Person으로 변경 | MOD-003 |
| missing-endpoint | relationship destination을 존재하지 않는 ID로 변경 | MOD-007 |
| unknown-view-reference | View에 존재하지 않는 element ID 추가 | VIEW-001 |
| nonconsecutive-dynamic-order | Dynamic order를 1,3,...으로 변경 | VIEW-010 |
| unregistered-source | Claim support가 미등록 Source를 참조 | EVD-008 |
| report-fact-redefinition | element presentation에 name 필드 추가 | SCHEMA-001 |
| unknown-report-model-id | 카드가 미등록 modelId를 참조 | HTML-DATA-011 |
| malicious-svg | script와 외부 URL을 포함 | SVG-002 / SVG-004 |
| strict-builder-rejection | bad-parent bundle로 strict HTML build 실행 | non-zero exit |

이 파일들은 정상 산출물이 아니다. 회귀 테스트가 잘못된 입력을 통과시키지 않는지 확인하는 반증 자료다.
