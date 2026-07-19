# helix-blender-addon maintainer briefing

## Status

**Maintained, low criticality.** Version 0.3.0 is the current shipped addon. The checkout
contains one self-contained Blender module plus release documentation; it has no active
feature queue as of 2026-07-18.

## Scope

- Owns the installable `helix_blender_tools` addon.
- Imports and exports `.helix` packages and glTF assets inside Blender.
- Owns the Blender sidebar, package assembly, gear attachment, and animation inspection UX.
- Does not own general headless Blender batch automation. Those scripts currently live in
  `../helix-tools/helix-blender-tools/scripts/`; `../helix-blender-tools/` is only an
  experimental future home until a migration is deliberately executed.

## Validation

```bash
python3 -m py_compile helix_blender_tools/__init__.py
```

That check only proves Python syntax and the module's non-Blender import guard. Any behavior
or packaging change also needs a Blender 5.x import/install check using a ZIP whose root is
`helix_blender_tools/`.

See [`AGENTS.md`](AGENTS.md) for repository rules and [`README.md`](README.md) for the user
workflow.
