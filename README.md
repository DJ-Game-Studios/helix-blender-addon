# Helix Blender Tools

Blender addon for the Helix MMORPG 3D asset pipeline. Import `.helix` hero packages, work with animations, export for the engine.

**Requires Blender 5.0+** (5.1 recommended)

## Status

**Maintained.** Version 0.3.0 is the current shipped addon. This repository remains the
installable Blender product, but it has no active implementation queue as of 2026-07-18.
See [`AGENTS.md`](AGENTS.md) for the maintainer cold start.

## Features

### Import
- **File > Import > Helix Package (.helix)** — one-click full hero import with gear attachment, scale, collision hiding
- **File > Import > Helix GLTF (.gltf/.glb)** — single file with correct Source 2 settings

### Import Presets
| Preset | Gear | Scale | Animations | Use Case |
|--------|------|-------|------------|----------|
| Full Preview | All | Manifest | All | Looking at the hero |
| Animation Work | None | 100% | Engine only | Animating |
| Reference | All | Manifest | All | Locked transforms, reference |
| Custom | Your choice | Your choice | Your choice | Advanced |

### Export
- **File > Export > Helix Package (.helix)** — re-export as .helix with updated manifest
- **File > Export > Helix GLTF (.gltf)** — GLTF Separate with auto-validation

### Sidebar Panels (View3D > Sidebar > Helix)

| Panel | What It Does |
|-------|-------------|
| **Hero** | Hero info, bone/anim counts, hero switcher grid (click to load any of 120+ heroes) |
| **Gear Parts** | Per-part visibility toggles, show/hide all, attach bone display |
| **Animations** | Engine animation playback with loop/oneshot badges, stop button |
| **Display** | Viewport modes (Textured/Flat/X-Ray), scale reset, skeleton controls |
| **Animation Status** | Naming compliance checklist |

### Under the Hood
- Gear parts are **reparented onto the base armature** (shared skeleton, not separate objects)
- **Bone aliases** are applied automatically (e.g., `arrow_root` → `Bow1_0`)
- **Collision shapes** (icosphere/physics meshes) are auto-hidden
- Manifest metadata stored as **custom properties** on the armature
- World transforms preserved during reparenting (no floating parts)

## Installation

### Option A: Download from Releases (recommended)

> **Do NOT use the green "Code > Download ZIP" button** — that downloads the repo, not the addon.
> Use the Releases page instead.

1. Go to [**Releases**](https://github.com/djmsqrvve/helix-blender-addon/releases/latest)
2. Download **`helix_blender_tools_v0.3.0.zip`** from the Assets section
3. In Blender: **Edit > Preferences > Add-ons > Install from Disk**
4. Select the downloaded `.zip`
5. Enable: search **"Helix"** and check the box

### Option B: Install from repo source

If you cloned or downloaded this repo, you can install from the included source:

```bash
# From the repo root:
cd helix_blender_tools
zip -r ../helix_blender_tools.zip .
# Then install helix_blender_tools.zip in Blender
```

Or symlink for development:

```bash
ln -s /path/to/helix-blender-addon/helix_blender_tools \
  ~/.config/blender/5.1/scripts/addons/helix_blender_tools
```

### Verify Installation

In Blender's Python console:
```python
import addon_utils
addon_utils.check('helix_blender_tools')  # Should return (True, True)
```

### Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| "Missing manifest" on install | Used "Code > Download ZIP" instead of Releases | Download from [Releases](https://github.com/djmsqrvve/helix-blender-addon/releases/latest) |
| Addon doesn't appear after install | ZIP has wrong folder structure | Ensure ZIP contains `helix_blender_tools/__init__.py` at the root |
| Module not found | Installed as wrong module name | Uninstall, then reinstall with the correct ZIP |

## What is a .helix File?

A `.helix` file is a single-file hero package (ZIP archive) containing:

- `manifest.json` — hero metadata, gear parts with attach bones, animation indices
- Base model GLTF + binary data
- Gear part GLTFs (armor, weapons, cape, etc.)
- Textures (color, normal, specular maps)

The addon reads `manifest.json` to know how to assemble the hero — which bones to attach gear to, what scale to apply, which animations are engine-recognized.

See [HELIX_FORMAT_SPEC.md](https://github.com/djmsqrvve/helix-viewer-releases/blob/main/HELIX_FORMAT_SPEC.md) for the full format specification.

## Sample Packages

Download `.helix` packages from [helix-viewer-releases](https://github.com/djmsqrvve/helix-viewer-releases/releases):

- `drow.helix` — 8 gear parts, 76 animations, 82 joints
- `axe.helix` — 5 gear parts, 75 animations, 56 joints

The full library of 124 heroes is built from the [helix-tools](https://github.com/djmsqrvve/helix-tools) pipeline.

## Automation companions

This checkout does **not** contain the historical headless Blender scripts. Their current
owner is the independent `helix-tools/helix-blender-tools/scripts/` package in the
[`helix-tools`](https://github.com/djmsqrvve/helix-tools) repository. The separate
`helix-blender-tools` repository is an experimental future home for general automation, but
no migration should be assumed until the files and validation are moved deliberately.

## Related Projects

| Repo | Role |
|------|------|
| [helix-tools](https://github.com/djmsqrvve/helix-tools) | Asset pipeline — builds `.helix` packages (private) |
| `helix-blender-tools` | Experimental standalone home for future general Blender automation; no current runtime dependency. |
| [helix-viewer-releases](https://github.com/djmsqrvve/helix-viewer-releases) | Standalone 3D viewer + sample packages |
| [helix_3d](https://github.com/djmsqrvve/helix_3d) | Bevy engine that consumes `.helix` packages (private) |

## License

MIT License — see [LICENSE](LICENSE).
