# Lessons

## Report regeneration needs explicit destinations and renewed inventory
- Date: 2026-09-15
- Task: A-centered report visual integration.
- What failed: Relative `--output index.html` wrote to the working directory, not the package; package validation then rejected stale sizes/hashes. `--update-manifest` updates validation metadata, not the file inventory.
- Root cause: Assumed CLI path and update semantics without tracing the writer.
- Category: Tool contract / artifact verification.
- Fix: Preserve the accidental output outside the repo, rebuild to an absolute package path, regenerate inventory with build_output_manifest.py before validate_package.py.
- Prevention rule: Use absolute build output paths; regenerate inventory after all artifact writes, then validate with evidence outside the package or the declared excluded receipt.
- Reuse trigger: Rebuilding an existing hash-locked report package.

## Mobile report checks must include long audience list items
- Date: 2026-09-15
- Task: Actual report mobile visual verification.
- What failed: At 360px the document widened to 386px although the new flow panels fit.
- Root cause: Audience cards retained grid min-content width; list items lacked word wrapping.
- Category: Responsive layout.
- Fix: Set audience-card min-width:0 and overflow-wrap:anywhere; add a failing-then-passing 360px regression with a long audience list item.
- Prevention rule: Test the whole report width with real content and long tokens, not only the changed section or 390px fixtures.
- Reuse trigger: Responsive grid cards containing prose and lists.

## Clean packaging must exclude every declared cache
- Date: 2026-09-15
- Task: Final native renderer skill package verification.
- What failed: Clean staging excluded Python bytecode but retained `.mypy_cache`; package validation rejected 345 cache files.
- Root cause: Staging exclusions were hand-picked instead of derived from the manifest generator's forbidden patterns.
- Category: Packaging verification.
- Fix: Build a fresh staging copy using every declared forbidden pattern; preserve original workspace caches. Direct module import also failed on a sibling import (`c4_validation`); read the constant with `ast.literal_eval` instead of executing the generator module.
- Prevention rule: Use `DEFAULT_FORBIDDEN` from `generate_manifest.py` for clean staging, then regenerate and validate its manifest.
- Reuse trigger: Skill package validation in a development workspace with tool caches.

## Renderer capability must not redefine valid canonical deployment
- Date: 2026-09-15
- Task: Actual publishing deployment and guarded interaction rendering.
- What failed: Valid logical deployment was rejected by an instance-only adapter; after mapping acceptance the native renderer silently omitted a boundary-endpoint relation (Chrome test: 2 paths vs 3). Native Node also rejected an already source-preserving interaction guard.
- Root cause: Adapter, Node validator and drawing branches had different representation contracts; expanded boundaries existed only as anonymous routing obstacles.
- Category: Semantic fidelity / cross-layer contract.
- Fix: Explicit logical-placement presentation retains parentId, elements and relations, routes canonical boundary headers and labels the view as not actual instances. Physical restrictions remain. Node verifies guard-prefixed display note against unchanged canonicalStep.
- Prevention rule: Before accepting a new canonical shape, test adapter preservation, native validator mutations, and actual browser edge count/export together. Never manufacture instances or reparent logical elements from hosting prose.
- Reuse trigger: Valid source model exceeds a renderer's representation subset.

## Report collision checks must include installed skill dependencies
- Date: 2026-09-10
- Task: Protect report builder skill dependencies from both output destinations.
- What failed: A passing report could overwrite its architecture schema through `--validation-output`, returning exit 0; 24 direct/hardlink probes reproduced dependency destruction.
- Root cause: Collision inventory covered package inputs but omitted the supplied skill root and executing installation dependencies.
- Category: Source/provenance integrity.
- Fix: Inventory existing references/assets/scripts trees and SKILL.md, manifest.json, VERSION in both roots before any output write.
- Prevention rule: Run destructive probes against a temporary skill copy; first require a passing baseline, then check rejection diagnostics and unchanged dependency/package bytes for both output flags and hardlinks. Do not inventory the whole skill root, because examples may contain legitimate output packages.
- Reuse trigger: Builders that consume schemas, templates, or renderer code outside their package root.

## Collision inventories must follow consumed fields and all provenance
- Date: 2026-09-10
- Task: Report and repo-flowmap SVG output collision fixes.
- What failed: Report output protection inventoried artifact `path`, but embedding reads `contentPath`; SVG export could overwrite the evidence ledger or renderer validation receipt before browser launch failed.
- Root cause: Protection lists used guessed field names and an incomplete provenance inventory, rather than tracing actual readers and every writer (including early failure receipts).
- Category: Source/provenance integrity.
- Fix: Protect artifact `contentPath`, all report QA files, and SVG package model/HTML/diagram/QA inputs against both output destinations with `assert_distinct_paths`; allow only the current view's default derived SVG and own export receipt to regenerate.
- Prevention rule: Inventory consumed field names and all QA provenance before any write; test both destinations, direct paths, symlinks and hardlinks against a passing baseline, asserting collision diagnostics and unchanged bytes. Negative fixtures must satisfy the complete schema before mutation.
- Reuse trigger: Any command accepting output or receipt paths inside an input package.

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
