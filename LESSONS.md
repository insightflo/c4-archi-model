# Lessons

## Regression success must come from the full command
- Date: 2026-09-10
- Task: v0.9 external-review fixes.
- What failed: An earlier report claimed 14/14 regression success; rerunning the original revision returned 12/14 with exit code 1.
- Root cause: The completion report was not grounded in a fresh full-suite result.
- Category: Verification/reporting.
- Fix: Rerun the full regression command and unit suite after integration; preserve output and exit status.
- Prevention rule: Never infer whole-suite success from selected passing lines or a child-agent summary.
- Reuse trigger: Any test/build completion claim, especially after parallel changes.

## Rejection tests need a passing baseline
- Date: 2026-09-10
- Task: External re-review strict builder regression.
- What failed: The mutation regression passed even though its unmodified fixture already failed with missing renderer receipts (RCP-007).
- Root cause: The test only checked a nonzero exit and missing output, without establishing a valid baseline or checking the intended diagnostic.
- Category: Test validity.
- Fix: Require baseline exit 0 and generated HTML; use a separate mutation output and require MOD-003 after parentId mutation.
- Prevention rule: Negative integration tests must first prove the unchanged fixture passes, then assert the specific rejection cause and output side effects.
- Reuse trigger: Validator rejection, strict build, or mutation regression tests.
