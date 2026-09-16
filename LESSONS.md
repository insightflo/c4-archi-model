# Lessons

## Repeated dialogs must show before loading embed content
- Date: 2026-09-16
- Task: Integrated verification of fullscreen diagram dialog fixes.
- What failed: The first fullscreen open rendered, but a sequential open→close→different-view dialog walk on one page load left repeated iframe embeds blank with 0×0 geometry.
- Root cause: openDialog assigned `srcdoc` before `showModal()`; content loaded into a not-yet-shown dialog got no laid-out geometry on repeated opens.
- Category: Report template / browser interaction.
- Fix: Call `showModal()` before assigning `srcdoc`; assert a sequential single-load walk (workaround reload removed) plus dedicated lifecycle-reopen cases for positive bbox, in-bounds geometry and real SVG downloads at 1440 and 360.
- Prevention rule: Test repeated open→close→different-view lifecycles on one page load with geometry and download assertions; a single-open pass says nothing about later opens.
- Reuse trigger: dialog/modal embeds, srcdoc iframes, fullscreen viewers.

## Hidden iframes must re-measure SVG extent before export
- Date: 2026-09-16
- Task: Integrated verification of hidden deployment panel export.
- What failed: A deployment panel initialized while hidden reported a 0×0 bbox (and a stale 1416px width); exporting before ResizeObserver delivery clipped the right edge instead of the full 1450.
- Root cause: getBBox() in a hidden document returns zero or stale geometry, and the extent measured once at render time was trusted at export.
- Category: Renderer export / hidden-document layout.
- Fix: c4MeasureExtent guards (!DATA.c4/!lastLayout/!vp), throws on top/left escape, grows extent only from positive measured geometry, and runs at initial render, ResizeObserver, and the start of serializeCurrentSvg; the hidden-layout test forces hidden init (bbox.width==0), asserts export paths equal hidden paths and byte-identical hidden vs fresh-dialog exports.
- Prevention rule: Re-measure real geometry at export time; never trust extents cached while hidden. Test hidden init, reveal, repeat stability and export bounds at real widths, including the no-ResizeObserver variant.
- Reuse trigger: SVG export, hidden panels/iframes, ResizeObserver-dependent layout.

## Orthogonal segments alone do not prove safe arrow anchors
- Date: 2026-09-16
- Task: Integrate and verify arrow-anchor changes.
- What failed: Existing browser tests passed while clamped slots collapsed, close-node fallback crossed a card, and strand shifts reversed endpoint direction.
- Root cause: Tests checked axis alignment but not unique slots, signed outward direction, or post-processing collisions.
- Category: Geometry / test coverage.
- Fix: Face-wide unique slots, adaptive clearance, validated strand rollback, shared orthogonal self-routing; show an escaped relation-ID warning when no safe route exists.
- Prevention rule: Test endpoint direction and obstacle intersection after all route post-processing; establish failing cases before fixes. Never silently omit an unroutable relationship.
- Reuse trigger: Arrow anchoring, obstacle routing, strand spacing, fallback or SVG export changes.

## Safe routes still need end-to-end label placement verification
- Date: 2026-09-16
- Task: Final actual deployment and self-relationship verification.
- What failed: Geometry tests passed, but badge-space exhaustion threw and erased the whole diagram.
- Root cause: Edge clearance is smaller than badge exclusion space; route validity does not imply a feasible badge position.
- Category: Renderer integration.
- Fix: Keep safe paths; visibly move unplaceable numbered controls and full relationship identity to the legend, preserving selection and SVG export.
- Prevention rule: Verify actual dense views and canonical self relationships through render, numbering, selection and export, not only route points. Regenerate receipts in a temporary package before full-suite provenance checks.
- Reuse trigger: Routing/label spacing or renderer provenance changes.

## Report input fidelity requires browser initialization, not just no errors
- Date: 2026-09-16
- Task: Actual external report review corrections (P1-01, P2-04).
- What failed: Literal `<!-- <script>` swallowed the application script without a pageerror; splitting overview prose with a two-item limit discarded later restrictions.
- Root cause: JSON escaping covered closing tags only, while HTML has script-data double-escaped states. JavaScript split limits truncate the remainder rather than limiting the number of splits.
- Category: Serialization / provenance fidelity.
- Fix: Encode every `<` as JSON `\\u003c`; slice only at the first prose delimiter. Browser regressions assert initialized title/controls and exact Korean, script/comment, artifact and overview text round-trips.
- Prevention rule: Assert positive initialization and exact decoded content with tokenizer edge cases. Styling must never delete source text.
- Reuse trigger: JSON embedded in HTML or highlighted source prose.

## Print verification must cover collapsed content and supported fallback assets
- Date: 2026-09-16
- Task: External print review correction (P1-02).
- What failed: Closed responsibility details omitted relation bodies, mobile CSS applied to print, and normal PNG fallback vanished. The first new PDF probe also falsely reported missing IDs split across printed lines.
- Root cause: Screen-only checks did not exercise native print events or PDF content; the probe initially treated layout whitespace as semantic content.
- Category: Output-medium coverage / test fidelity.
- Fix: Snapshot/open relationship details before print and restore exact states afterward; scope responsive CSS to screen; retain static image print assets and table rows. Test real PDF bodies, row boundaries and 11px minimum table text. For PDF identifier checks, normalize layout whitespace only, retain every identifier character, and inspect rendered pages.
- Prevention rule: Test native print plus state restoration, SVG and non-SVG originals, and a real long row. Console cleanliness and image count alone are insufficient.
- Reuse trigger: Collapsible explanations, print CSS or alternate image formats.

## Connected report experiences need canonical scope and visible focus
- Date: 2026-09-16
- Task: External responsibility/unknown/accessibility corrections (P2-01/02/03/05 and historical QA scope).
- What failed: Unknown affected IDs were not actionable; mobile selection moved only the diagram; hosting and communication were mixed; explicit smooth scroll overrode reduced motion; old QA prose looked current.
- Root cause: Rendering stopped at labels, viewport movement was tested without focus or selected prose, relations ignored view/type scope, and old/new verification contexts were mixed.
- Category: Interaction completeness / scope fidelity / accessibility.
- Fix: Exact affected View/element controls without inferred steps; colocated selected responsibility and keyboard return; preserve every relation in current-view, typed deployment and other-view buckets; honor reduced-motion in JS; label record dates/paths/model scope separately from this build without changing QA originals.
- Prevention rule: Verify the complete click-to-evidence chain with real mobile keyboard geometry and actual reduced-motion clicks. Use canonical types/membership, never ID prefixes or domain prose. Distinguish historical scope from fresh acceptance evidence.
- Reuse trigger: Linked architecture reports, responsive selection panels and reused validation artifacts.

## Semantic focus checks must cover initialization failure and rendered scale
- Date: 2026-09-16
- Task: Independent report visual review fixes.
- What failed: A valid SVG without viewBox left a blank focus frame; returning from the full picture restored crop coordinates but shrank the selected message.
- Root cause: Initialization failure only changed status text, and selection restoration reset zoom instead of applying the initial reading scale. Existing tests checked viewBox rather than rendered dimensions.
- Category: Visual fallback / browser test coverage.
- Fix: Show the unchanged source through an inert image on initialization failure, hide unavailable controls, retain unavailable state on later selections, and reuse the reading-scale calculation on selection return.
- Prevention rule: Test valid-but-unsupported SVG initialization with visible decoded fallback and non-executing active content; compare actual snapshot and highlight dimensions before/after full-picture navigation at desktop and mobile widths.
- Reuse trigger: Progressive diagram enhancement, fallback promises, and crop/zoom mode transitions.

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
