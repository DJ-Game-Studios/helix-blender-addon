# Installed package export review and acceptance plan

Date: 2026-10-15  
Status: maintained, low criticality; source-only integration finding  
Reviewed baseline: `f3da6a2fe338cc9f0cd9234232b0123c4be7bdb8` (`main`), rechecked unchanged on 2026-10-15.

## Scope

This review covers the installable addon's advertised `.helix` package-export
contract. It preserves the existing release and lifecycle classification.
It proposes acceptance work; it does not implement a fix or establish an active
feature queue.

All evidence is from this repository's public source and documentation.
Blender and release-ZIP installation were not executed.

## E2: installed export expects an external packager layout

Priority: P2 integration concern.

The [README installation and export workflow](https://github.com/DJ-Game-Studios/helix-blender-addon/blob/f3da6a2fe338cc9f0cd9234232b0123c4be7bdb8/README.md)
advertises installation from a release ZIP followed by `.helix` export.
[Repository rules](https://github.com/DJ-Game-Studios/helix-blender-addon/blob/f3da6a2fe338cc9f0cd9234232b0123c4be7bdb8/AGENTS.md)
require a self-contained addon without runtime imports from sibling checkouts.

The [export operator](https://github.com/DJ-Game-Studios/helix-blender-addon/blob/f3da6a2fe338cc9f0cd9234232b0123c4be7bdb8/helix_blender_tools/__init__.py#L714-L770)
first exports raw glTF into a temporary directory. It then derives
`tools_root` by walking two parents above the addon directory and looks for
`scripts/build_package.py`. The repository tree does not contain that packager,
and the operator provides no configured dependency location.

Observed control flow:
- Missing packager: a warning is reported and the operator returns
  `{"FINISHED"}`, leaving temporary raw glTF rather than the requested
  `.helix` output.
- Nonzero subprocess exit, timeout, or missing executable: a warning is reported,
  temporary files are cleaned up, and the operator still returns
  `{"FINISHED"}`.
- Zero subprocess exit with no requested output file: size becomes zero and an
  `Exported ...` message is still reported. Output existence and package
  validity are not required by that branch.

This establishes a source-level dependency and result-signaling gap. It does
not prove the contents of the published release ZIP or reproduce a failure on
an installed user system.

## Proposed implementation boundary

Keep the addon self-contained under the existing repository rules. Prefer a
bundled, versioned packaging implementation that works from the supported release
ZIP without sibling checkout layout assumptions. If maintainers deliberately
choose an external tool dependency instead, that design must first reconcile
the self-contained rule and specify installation, compatibility, and explicit
configuration.

Package export should succeed only when the selected destination contains a
valid package from this export attempt. A temporary glTF may be useful recovery
output, but it needs a distinct, accurately reported result.

## Acceptance checklist

### Installed dependency

- [ ] Install the release ZIP into a clean supported Blender 5.x profile with no
  sibling Helix checkout or inherited developer scripts.
- [ ] Confirm the archive root remains `helix_blender_tools/`.
- [ ] Export a legal minimal character fixture using only declared dependencies.
- [ ] Record the exact Blender version, addon revision, ZIP contents, and
  packaging implementation version.
- [ ] An unavailable dependency produces an actionable error before a successful
  export result is returned.

### Outcome and output validation

- [ ] Missing packager, missing executable, timeout, nonzero exit, missing output,
  zero-length output, and invalid package all return a failure result.
- [ ] A stale file already at the destination cannot satisfy validation for a
  failed or no-output export attempt.
- [ ] Success requires the requested output to exist and pass structural package
  validation, including referenced members.
- [ ] A valid package can be imported again in the supported Blender workflow.
- [ ] Preserve an existing valid destination on failed export.

### Temporary artifacts and user feedback

- [ ] Use a consistent cleanup policy on every exit path.
- [ ] If a raw glTF recovery file is retained, display its actual path and explain
  that the requested package was not produced.
- [ ] Avoid reporting a zero-size or missing file as an exported package.
- [ ] Include useful bounded diagnostics without exposing unrelated environment
  data.

## Adjacent validation dependency

The [glTF validation helper](https://github.com/DJ-Game-Studios/helix-blender-addon/blob/f3da6a2fe338cc9f0cd9234232b0123c4be7bdb8/helix_blender_tools/__init__.py#L683-L702)
uses the same two-parent layout assumption for
`scripts/validate_skibidi_export.py` and warns before skipping a missing script.
Include this dependency in the installed-package inventory. A skipped validation
step must remain distinguishable from a validated export.

## Verification for this documentation change

- Re-read README, AGENTS, maintainer briefing, changelog, complete tree, and export
  implementation at the exact unchanged default-branch baseline.
- Ran `python3 -m py_compile helix_blender_tools/__init__.py` on the fetched
  baseline source in the cloud workspace. This is syntax validation only.
- No addon behavior, dependency, release artifact, or workflow changed.
- Not run: Blender module enable/import, release-ZIP installation, package export,
  package validation/roundtrip, or GUI checks.
- No repository-defined GitHub Actions workflow exists at the reviewed tree.
  No workflow was added or rerun.

Keep this finding source-only until the installed workflow is exercised.
