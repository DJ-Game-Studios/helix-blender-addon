# AGENTS.md — Helix Blender addon

This repository owns the installable Blender addon for Helix package import, inspection,
editing, and export. It is a maintained low-criticality product, not the general home for
headless Blender automation.

## Read first

1. [`README.md`](README.md) — supported user workflow and installation.
2. [`CHANGELOG.md`](CHANGELOG.md) — shipped release history.
3. [`CLAUDE.md`](CLAUDE.md) — compact maintainer briefing.
4. [`helix_blender_tools/__init__.py`](helix_blender_tools/__init__.py) — the complete addon.

## Repository rules

- Keep the release ZIP rooted at `helix_blender_tools/`; Blender must see
  `helix_blender_tools/__init__.py` at the archive root.
- Keep the addon self-contained inside Blender. Do not add runtime imports from sibling
  Helix checkouts.
- Headless batch scripts currently remain owned by `../helix-tools/helix-blender-tools/`.
  Do not document those scripts as files in this repository.
- Treat Blender 5.0+ as the supported floor unless a release is explicitly tested and
  documented against another version.
- For documentation-only work, run
  `python3 -m py_compile helix_blender_tools/__init__.py`. Behavior changes also require an actual Blender import
  or release-ZIP installation check.
- Do not add GitHub Actions workflows; Helix validation is local/runner-owned.

## Lifecycle

Version 0.3.0 is shipped and preserved. There is no active implementation queue in this
checkout as of 2026-07-18. New feature work should begin with an explicit issue or handoff,
not an assumption that historical script lists are a current roadmap.
