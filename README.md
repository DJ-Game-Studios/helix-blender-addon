# Helix Blender Tools

A Blender addon for importing, inspecting, animating, and exporting `.helix` character packages.

**Current release:** v0.3.0  
**Requires:** Blender 5.0 or newer; Blender 5.1 is recommended.

## Features

- One-click `.helix` package import with gear attachment and scale handling.
- Direct GLTF/GLB import with Helix pipeline defaults.
- Import presets for preview, animation, reference, and custom workflows.
- Gear visibility controls and attachment-bone inspection.
- Animation playback with loop and one-shot metadata.
- Textured, flat, X-ray, and skeleton display modes.
- `.helix` package and GLTF export with validation.
- Automatic collision-shape hiding and bone-alias handling.

## Install

> Download the addon from **Releases**. GitHub's green **Code → Download ZIP** archive is the source repository, not an installable addon package.

1. Download `helix_blender_tools_v0.3.0.zip` from the [latest release](https://github.com/DJ-Game-Studios/helix-blender-addon/releases/latest).
2. In Blender, open **Edit → Preferences → Add-ons**.
3. Choose **Install from Disk** and select the ZIP file.
4. Search for **Helix** and enable **Helix Blender Tools**.

After installation, the addon appears in Blender's import/export menus and in **View3D → Sidebar → Helix**.

### Verify installation

In Blender's Python console:

```python
import addon_utils
addon_utils.check("helix_blender_tools")
```

A successful enabled installation returns `(True, True)`.

## Import a character

1. Download a sample package from [Helix 3D Viewer Releases](https://github.com/DJ-Game-Studios/helix-viewer-releases/releases).
2. In Blender, choose **File → Import → Helix Package (.helix)**.
3. Select an import preset.
4. Use the Helix sidebar to inspect gear, animations, scale, and skeleton data.

| Preset | Gear | Scale | Animations | Best for |
| --- | --- | --- | --- | --- |
| Full Preview | All | Manifest | All | Reviewing an assembled character |
| Animation Work | None | 100% | Engine set | Animation editing |
| Reference | All | Manifest | All | Locked visual reference |
| Custom | Selectable | Selectable | Selectable | Advanced workflows |

## Export

- **File → Export → Helix Package (.helix)** repackages the character with an updated manifest.
- **File → Export → Helix GLTF (.gltf)** exports validated GLTF assets with pipeline defaults.

## The `.helix` format

A `.helix` package is a portable archive containing a base model, gear parts, textures, animations, skeleton data, and a manifest that describes assembly and engine metadata.

Read the [format specification](https://github.com/DJ-Game-Studios/helix-viewer-releases/blob/main/HELIX_FORMAT_SPEC.md) for the complete schema.

## Troubleshooting

| Problem | Likely cause | Fix |
| --- | --- | --- |
| “Missing manifest” during installation | The repository source ZIP was selected | Install the ZIP attached to the latest release |
| Addon does not appear | The package has the wrong folder structure | Re-download the official release asset |
| Module not found | The addon was installed under the wrong module name | Remove it and reinstall the official release ZIP |

For reproducible problems, [open an issue](https://github.com/DJ-Game-Studios/helix-blender-addon/issues) with your Blender version, operating system, package name, and the full error message.

## License

[MIT](LICENSE)
