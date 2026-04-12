# Helix Blender Tools

Blender addon for the Helix MMORPG 3D asset pipeline. Import `.helix` hero packages, work with animations, export for the engine.

**Requires Blender 5.0+** (5.1 recommended)

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

### Option A: Symlink (development)

```bash
ln -s /path/to/helix-blender-tools/addon \
  ~/.config/blender/5.1/scripts/addons/helix_blender_tools
```

### Option B: Download from Releases

1. Download the latest `.zip` from [Releases](https://github.com/djmsqrvve/helix-blender-addon/releases)
2. In Blender: **Edit > Preferences > Add-ons > Install from Disk**
3. Select the downloaded `.zip`
4. Enable: search **"Helix"** and check the box

### Verify Installation

In Blender's Python console:
```python
import addon_utils
addon_utils.check('helix_blender_tools')  # Should return (True, True)
```

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

## CLI Scripts

6 headless Blender scripts for automation (no GUI needed):

| Script | What It Does |
|--------|-------------|
| `blender_import_test.py` | Import + report bones/meshes/animations as JSON |
| `blender_render_preview.py` | Import + auto-camera + EEVEE render → PNG |
| `blender_roundtrip_test.py` | Import → export → re-import, diff for data loss |
| `blender_batch_process.py` | Run import/roundtrip/render across multiple heroes |
| `blender_create_jump_anims.py` | Generate placeholder jump animations |
| `blender_open_hero.py` | Interactive import with full gear reparenting |

All scripts use `guess_original_bind_pose=False` for Source 2 GLTF compatibility.

## Related Projects

| Repo | Role |
|------|------|
| [helix-tools](https://github.com/djmsqrvve/helix-tools) | Asset pipeline — builds `.helix` packages (private) |
| [helix-viewer-releases](https://github.com/djmsqrvve/helix-viewer-releases) | Standalone 3D viewer + sample packages |
| [helix_3d](https://github.com/djmsqrvve/helix_3d) | Bevy engine that consumes `.helix` packages (private) |

## License

MIT License — see [LICENSE](LICENSE).
