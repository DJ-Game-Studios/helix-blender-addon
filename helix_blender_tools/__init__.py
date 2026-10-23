# Helix Blender Tools - Blender Addon
# Optimizes the Blender pipeline for Helix MMORPG animation workflow

bl_info = {
    "name": "Helix Blender Tools",
    "author": "DJMSQRVVE",
    "version": (0, 3, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > Helix",
    "description": "Import/export and animation tools for the Helix MMORPG pipeline",
    "category": "Import-Export",
}

# ---------------------------------------------------------------------------
# Animation vocabulary (v3). `_vocab.py` is GENERATED from helix-core
# helix-anim-vocab by scripts/gen_vocab.py so the addon stays standalone inside
# Blender; tests/test_vocab.py fails when it drifts.
#
# Action names are the vocabulary names themselves (`jump_start`, `walk`),
# so the packager maps them exactly. The pre-v3 title-case names
# (`Jump Start`, `Run Backward`) are still recognised through ALIASES.
# ---------------------------------------------------------------------------

from ._vocab import ALIASES, KNOWN_ANIMATIONS, TEMPLATE_NAMES, VOCAB_VERSION  # noqa: E402

PRIORITY_ANIMATIONS = ["walk", "jump_start", "jump_air", "jump_land"]

ANIMATION_DISPLAY_NAMES = {k: k.replace("_", " ").title() for k in KNOWN_ANIMATIONS}


def vocab_name(action_name: str) -> str | None:
    """The vocabulary name an action stands for (old spellings and `.N`
    variants included), or None."""
    raw = action_name.strip().lower()
    if raw in ALIASES:
        return ALIASES[raw]
    base, _, tail = raw.rpartition(".")
    if base and tail.isdigit():
        raw = base
    raw = ALIASES.get(raw, raw)
    return raw if raw in KNOWN_ANIMATIONS else None


# Import presets
IMPORT_PRESETS = {
    "FULL_PREVIEW": {
        "label": "Full Preview",
        "desc": "All gear, scale applied, Material Preview",
        "import_gear": True, "apply_scale": True, "set_viewport": True,
        "anim_filter": "ALL", "lock_transforms": False,
    },
    "ANIM_WORK": {
        "label": "Animation Work",
        "desc": "No gear, no scale, base skeleton only",
        "import_gear": False, "apply_scale": False, "set_viewport": True,
        "anim_filter": "ENGINE_ONLY", "lock_transforms": False,
    },
    "REFERENCE": {
        "label": "Reference",
        "desc": "All gear, locked transforms",
        "import_gear": True, "apply_scale": True, "set_viewport": True,
        "anim_filter": "ALL", "lock_transforms": True,
    },
    "CUSTOM": {
        "label": "Custom",
        "desc": "Configure all options manually",
        "import_gear": True, "apply_scale": True, "set_viewport": True,
        "anim_filter": "ALL", "lock_transforms": False,
    },
}


def _check_blender():
    """Guard import so the module can be loaded outside Blender for testing."""
    try:
        import bpy  # noqa: F401
        return True
    except ImportError:
        return False


# ── Only register Blender classes when running inside Blender ──────────────
if _check_blender():
    import bpy
    from bpy.props import StringProperty, BoolProperty, EnumProperty
    from bpy_extras.io_utils import ImportHelper, ExportHelper
    import json
    import os
    import subprocess
    import tempfile
    import zipfile

    # ── Helpers ──────────────────────────────────────────────────────────

    _COLLISION_KEYWORDS = ("icosphere", "physics", "collision", "collider")

    def _is_collision_mesh(obj):
        """Check if a mesh object is a physics/collision shape that should be hidden."""
        if obj.type != "MESH":
            return False
        name_lower = obj.name.lower()
        return any(kw in name_lower for kw in _COLLISION_KEYWORDS)

    def _apply_bone_aliases(mesh_obj, alias_map):
        """Rename vertex groups on a mesh to match the base skeleton using aliases.

        alias_map: dict mapping part bone name → base bone name.
        Blender's armature modifier matches vertex group names to bone names,
        so renaming the groups makes the skinning work across skeletons.
        """
        if not alias_map:
            return 0
        renamed = 0
        for vg in mesh_obj.vertex_groups:
            if vg.name in alias_map:
                vg.name = alias_map[vg.name]
                renamed += 1
        return renamed

    def _reparent_mesh_to_armature(mesh_obj, target_armature, alias_map=None):
        """Re-parent a skinned mesh from its own armature onto a shared base armature.

        For fully-skinned parts (multiple joints): retarget the Armature modifier
        to the base skeleton. The skinning system handles positioning.

        alias_map: optional dict of part_bone_name → base_bone_name for renaming
        vertex groups before retargeting.
        """
        old_armature = mesh_obj.parent

        # Apply bone aliases — rename vertex groups so they match base skeleton
        if alias_map:
            _apply_bone_aliases(mesh_obj, alias_map)

        # Retarget the Armature modifier to the base skeleton
        for mod in mesh_obj.modifiers:
            if mod.type == "ARMATURE":
                mod.object = target_armature
                break

        # Preserve the mesh's world-space position through the reparenting.
        # Without this, parts lose their rest-pose offset and pile up at origin.
        world_matrix = mesh_obj.matrix_world.copy()
        mesh_obj.parent = target_armature
        mesh_obj.matrix_parent_inverse = target_armature.matrix_world.inverted()
        mesh_obj.matrix_world = world_matrix

        # Delete the now-orphaned part armature
        if old_armature and old_armature.type == "ARMATURE" and old_armature != target_armature:
            bpy.data.objects.remove(old_armature, do_unlink=True)

    def _attach_static_prop(mesh_obj, target_armature, bone_name):
        """Attach a static prop (1-2 joints) to a specific bone via bone parenting.

        Used for parts like arrows or projectiles that don't need full skin
        retargeting — they just follow one bone.
        """
        old_armature = mesh_obj.parent

        # Remove any armature modifier (static props don't need skinning)
        for mod in list(mesh_obj.modifiers):
            if mod.type == "ARMATURE":
                mesh_obj.modifiers.remove(mod)

        # Parent to specific bone, preserving world position
        world_matrix = mesh_obj.matrix_world.copy()
        mesh_obj.parent = target_armature
        mesh_obj.parent_type = "BONE"
        if bone_name in target_armature.data.bones:
            mesh_obj.parent_bone = bone_name
        mesh_obj.matrix_parent_inverse = target_armature.matrix_world.inverted()
        mesh_obj.matrix_world = world_matrix

        if old_armature and old_armature.type == "ARMATURE" and old_armature != target_armature:
            bpy.data.objects.remove(old_armature, do_unlink=True)

    def _set_viewport_material_preview():
        """Set the 3D viewport to Material Preview mode and frame all."""
        for area in bpy.context.screen.areas:
            if area.type == "VIEW_3D":
                for space in area.spaces:
                    if space.type == "VIEW_3D":
                        space.shading.type = "MATERIAL"
                        space.shading.use_scene_lights = False
                        space.shading.use_scene_world = False
                override = {"area": area, "region": area.regions[-1]}
                with bpy.context.temp_override(**override):
                    bpy.ops.view3d.view_all()
                break

    def _set_viewport_xray():
        """Set viewport to wireframe with visible armature."""
        for area in bpy.context.screen.areas:
            if area.type == "VIEW_3D":
                for space in area.spaces:
                    if space.type == "VIEW_3D":
                        space.shading.type = "WIREFRAME"
                        space.overlay.show_bones = True
                break

    def _set_viewport_solid_flat():
        """Set viewport to solid mode with flat single color."""
        for area in bpy.context.screen.areas:
            if area.type == "VIEW_3D":
                for space in area.spaces:
                    if space.type == "VIEW_3D":
                        space.shading.type = "SOLID"
                        space.shading.color_type = "OBJECT"
                break

    def _find_helix_armature(context):
        """Find the helix armature in the scene (has helix_hero property)."""
        for obj in context.scene.objects:
            if obj.type == "ARMATURE" and "helix_hero" in obj:
                return obj
        return None

    def _find_packages_dir():
        """Find the packages/ directory relative to the addon."""
        addon_dir = os.path.dirname(os.path.realpath(__file__))
        tools_root = os.path.dirname(os.path.dirname(addon_dir))
        pkg_dir = os.path.join(tools_root, "packages")
        if os.path.isdir(pkg_dir):
            return pkg_dir
        return None

    def _get_available_heroes():
        """List available .helix packages."""
        pkg_dir = _find_packages_dir()
        if not pkg_dir:
            return []
        heroes = []
        for f in sorted(os.listdir(pkg_dir)):
            if f.endswith(".helix"):
                heroes.append(f[:-6])  # strip .helix
        return heroes

    def _filter_animations(anim_filter, animations_detail):
        """Return set of animation indices to keep based on filter mode."""
        if anim_filter == "ALL":
            return None  # keep all
        indices_to_remove = set()
        engine_indices = set()

        for anim in animations_detail:
            if anim.get("additive", False):
                indices_to_remove.add(anim["index"])
            if "engine_name" in anim:
                engine_indices.add(anim["index"])

        if anim_filter == "ENGINE_ONLY":
            # Remove everything that's not engine-mapped
            all_indices = {a["index"] for a in animations_detail}
            return all_indices - engine_indices
        elif anim_filter == "NON_ADDITIVE":
            return indices_to_remove

        return None

    def _remove_filtered_actions(indices_to_remove, all_actions_before, all_actions_after):
        """Remove Actions that correspond to filtered animation indices."""
        if not indices_to_remove:
            return 0
        new_actions = [a for a in bpy.data.actions if a not in all_actions_before]
        removed = 0
        for i, action in enumerate(new_actions):
            if i in indices_to_remove:
                bpy.data.actions.remove(action)
                removed += 1
        return removed

    # ── Import Operator (plain GLTF) ─────────────────────────────────────
    class HELIX_OT_import_gltf(bpy.types.Operator, ImportHelper):
        """Import a Helix Standard GLTF with correct settings."""
        bl_idname = "helix.import_gltf"
        bl_label = "Import Helix GLTF"
        bl_options = {"REGISTER", "UNDO"}

        filter_glob: StringProperty(default="*.gltf;*.glb", options={"HIDDEN"})

        def execute(self, context):
            filepath = self.filepath
            if not os.path.isfile(filepath):
                self.report({"ERROR"}, f"File not found: {filepath}")
                return {"CANCELLED"}

            bpy.ops.import_scene.gltf(
                filepath=filepath,
                guess_original_bind_pose=False,
            )
            self.report({"INFO"}, f"Imported Helix GLTF: {os.path.basename(filepath)}")
            return {"FINISHED"}

    # ── Package Import Operator ──────────────────────────────────────────
    class HELIX_OT_import_package(bpy.types.Operator, ImportHelper):
        """Import a .helix package with configurable preset and options."""
        bl_idname = "helix.import_package"
        bl_label = "Import Helix Package"
        bl_options = {"REGISTER", "UNDO"}

        filter_glob: StringProperty(default="*.helix", options={"HIDDEN"})

        import_preset: EnumProperty(
            name="Preset",
            description="Import configuration preset",
            items=[
                ("FULL_PREVIEW", "Full Preview", "All gear, scale, Material Preview"),
                ("ANIM_WORK", "Animation Work", "No gear, no scale, engine anims only"),
                ("REFERENCE", "Reference", "All gear, locked transforms"),
                ("CUSTOM", "Custom", "Configure all options manually"),
            ],
            default="FULL_PREVIEW",
        )

        import_gear: BoolProperty(
            name="Import Gear Parts",
            description="Import all gear/accessory parts alongside the base model",
            default=True,
        )

        apply_scale: BoolProperty(
            name="Apply Model Scale",
            description="Apply model_scale_pct from manifest",
            default=True,
        )

        set_viewport: BoolProperty(
            name="Set Material Preview",
            description="Switch viewport to Material Preview after import",
            default=True,
        )

        anim_filter: EnumProperty(
            name="Animation Filter",
            description="Which animations to import",
            items=[
                ("ALL", "All Animations", "Import every animation from the model"),
                ("ENGINE_ONLY", "Engine Only", "Only import engine-recognized animations (idle, run, etc.)"),
                ("NON_ADDITIVE", "Non-Additive", "Skip additive/overlay animations"),
            ],
            default="ALL",
        )

        lock_transforms: BoolProperty(
            name="Lock Transforms",
            description="Lock location/rotation/scale on all objects (reference mode)",
            default=False,
        )

        viewport_mode: EnumProperty(
            name="Viewport Mode",
            description="How to display the model after import",
            items=[
                ("MATERIAL", "Material Preview", "Show textures and materials"),
                ("SOLID", "Flat Color", "Solid color per object, no textures"),
                ("WIREFRAME", "X-Ray Skeleton", "Wireframe mesh with visible bones"),
            ],
            default="MATERIAL",
        )

        # Gear part selection — populated dynamically from manifest
        # We use a single string to store comma-separated part IDs to skip
        skip_parts: StringProperty(
            name="Skip Parts",
            description="Comma-separated part IDs to skip (e.g. 'cape,quiver')",
            default="",
        )

        def draw(self, context):
            layout = self.layout

            # Preset selector
            layout.prop(self, "import_preset")
            layout.separator()

            # Show options based on preset
            if self.import_preset == "CUSTOM":
                box = layout.box()
                box.label(text="Import Options", icon="IMPORT")
                box.prop(self, "import_gear")
                box.prop(self, "apply_scale")
                box.prop(self, "lock_transforms")

                box = layout.box()
                box.label(text="Viewport", icon="SHADING_RENDERED")
                box.prop(self, "viewport_mode")

                box = layout.box()
                box.label(text="Animations", icon="ACTION")
                box.prop(self, "anim_filter")

                box = layout.box()
                box.label(text="Gear Selection", icon="MESH_DATA")
                box.prop(self, "skip_parts")
                box.label(text="Leave empty for all parts", icon="INFO")
            else:
                preset = IMPORT_PRESETS[self.import_preset]
                box = layout.box()
                box.label(text=preset["desc"], icon="INFO")

                if self.import_preset != "ANIM_WORK":
                    box = layout.box()
                    box.label(text="Gear Selection", icon="MESH_DATA")
                    box.prop(self, "skip_parts")
                    box.label(text="Leave empty for all parts", icon="INFO")

        def execute(self, context):
            filepath = self.filepath
            if not os.path.isfile(filepath):
                self.report({"ERROR"}, f"File not found: {filepath}")
                return {"CANCELLED"}

            # Apply preset settings
            if self.import_preset != "CUSTOM":
                preset = IMPORT_PRESETS[self.import_preset]
                self.import_gear = preset["import_gear"]
                self.apply_scale = preset["apply_scale"]
                self.set_viewport = preset["set_viewport"]
                self.anim_filter = preset["anim_filter"]
                self.lock_transforms = preset["lock_transforms"]

            # Extract package
            extract_dir = tempfile.mkdtemp(prefix="helix_pkg_")
            try:
                with zipfile.ZipFile(filepath, "r") as zf:
                    zf.extractall(extract_dir)
            except zipfile.BadZipFile:
                self.report({"ERROR"}, "Invalid .helix package (not a valid archive)")
                return {"CANCELLED"}

            manifest_path = os.path.join(extract_dir, "manifest.json")
            if not os.path.isfile(manifest_path):
                self.report({"ERROR"}, "No manifest.json in package — not a valid .helix file")
                return {"CANCELLED"}

            with open(manifest_path) as f:
                manifest = json.load(f)

            hero = manifest.get("hero", "unknown")
            base_model = manifest.get("base_model")
            parts = manifest.get("parts", [])
            scale_pct = manifest.get("model_scale_pct", 100)
            engine_anims = manifest.get("engine_animations", [])
            bone_aliases = manifest.get("bone_aliases", [])
            animations_detail = manifest.get("animations_detail", [])

            if not base_model:
                self.report({"ERROR"}, f"No base model defined in {hero} package")
                return {"CANCELLED"}

            base_path = os.path.join(extract_dir, base_model)
            if not os.path.isfile(base_path):
                self.report({"ERROR"}, f"Base model not found: {base_model}")
                return {"CANCELLED"}

            # Parse skip list
            skip_ids = set()
            if self.skip_parts.strip():
                skip_ids = {s.strip().lower() for s in self.skip_parts.split(",")}

            # Track actions before import for animation filtering
            actions_before = set(bpy.data.actions)

            # ── Import base model ────────────────────────────────────
            before_objects = set(bpy.data.objects)

            bpy.ops.import_scene.gltf(
                filepath=base_path,
                guess_original_bind_pose=False,
            )
            imported_count = 1
            hidden_count = 0

            new_objects = set(bpy.data.objects) - before_objects
            base_armature = None
            for obj in new_objects:
                if obj.type == "ARMATURE":
                    obj.name = f"{hero}_skeleton"
                    base_armature = obj
                    obj["helix_hero"] = hero
                    obj["helix_scale_pct"] = scale_pct
                    obj["helix_format_version"] = manifest.get("format_version", 0)
                    obj["helix_package_path"] = filepath
                    if engine_anims:
                        obj["helix_engine_anims"] = json.dumps(engine_anims)
                    if bone_aliases:
                        obj["helix_bone_aliases"] = json.dumps(bone_aliases)
                    # v2 fields
                    build_info = manifest.get("build_info")
                    if build_info:
                        obj["helix_build_info"] = json.dumps(build_info)
                    texture_count = manifest.get("texture_count", 0)
                    obj["helix_texture_count"] = texture_count
                    if parts:
                        obj["helix_parts"] = json.dumps([
                            {"id": p["id"], "display_name": p["display_name"],
                             "attach_bone": p.get("attach_bone", "root")}
                            for p in parts
                        ])
                elif _is_collision_mesh(obj):
                    obj.name = f"{hero}_collision_{obj.name}"
                    obj.hide_set(True)
                    obj.hide_render = True
                    hidden_count += 1
                elif obj.type == "MESH":
                    obj.name = f"{hero}_body"

            # Apply model scale
            if self.apply_scale and scale_pct != 100 and base_armature:
                scale_factor = scale_pct / 100.0
                base_armature.scale = (scale_factor, scale_factor, scale_factor)

            # ── Build alias map from manifest ────────────────────────
            # bone_aliases: [["part_bone", "base_bone"], ...]
            alias_map = {}
            for alias_pair in bone_aliases:
                if len(alias_pair) == 2:
                    alias_map[alias_pair[0]] = alias_pair[1]

            # Static prop threshold: parts with this few joints use bone
            # parenting instead of full skin retargeting
            STATIC_PROP_JOINT_THRESHOLD = 2

            # ── Import gear parts ────────────────────────────────────
            skipped_parts = []
            if self.import_gear and parts and base_armature:
                for part in parts:
                    part_id = part.get("id", "")
                    part_file = part.get("file")

                    # Check skip list
                    if part_id.lower() in skip_ids:
                        skipped_parts.append(part_id)
                        continue

                    part_path = os.path.join(extract_dir, part_file)
                    if not os.path.isfile(part_path):
                        continue

                    before_part = set(bpy.data.objects)
                    bpy.ops.import_scene.gltf(
                        filepath=part_path,
                        guess_original_bind_pose=False,
                    )
                    new_part_objects = set(bpy.data.objects) - before_part
                    display = part.get("display_name", part_id)
                    attach_bone = part.get("attach_bone", "root")
                    joint_count = part.get("joint_count", 0)
                    is_static_prop = joint_count <= STATIC_PROP_JOINT_THRESHOLD

                    part_meshes = []
                    part_armatures = []
                    for obj in new_part_objects:
                        if obj.type == "ARMATURE":
                            part_armatures.append(obj)
                        elif _is_collision_mesh(obj):
                            obj.hide_set(True)
                            obj.hide_render = True
                            hidden_count += 1
                        elif obj.type == "MESH":
                            obj.name = f"{hero}_{display}"
                            obj["helix_attach_bone"] = attach_bone
                            obj["helix_part_id"] = part_id
                            part_meshes.append(obj)

                    # Attach parts to base armature
                    for mesh_obj in part_meshes:
                        if is_static_prop:
                            # Low-joint parts (arrows, projectiles): bone-parent
                            _attach_static_prop(mesh_obj, base_armature, attach_bone)
                        else:
                            # Fully skinned parts: retarget armature modifier
                            _reparent_mesh_to_armature(
                                mesh_obj, base_armature, alias_map,
                            )

                    for arm in part_armatures:
                        try:
                            if arm.name and arm.name in bpy.data.objects:
                                bpy.data.objects.remove(arm, do_unlink=True)
                        except ReferenceError:
                            pass

                    imported_count += 1

            # ── Animation filtering ──────────────────────────────────
            removed_anims = 0
            if self.anim_filter != "ALL" and animations_detail:
                indices_to_remove = _filter_animations(self.anim_filter, animations_detail)
                if indices_to_remove:
                    actions_after = set(bpy.data.actions)
                    removed_anims = _remove_filtered_actions(
                        indices_to_remove, actions_before, actions_after,
                    )

            # ── Lock transforms (reference mode) ─────────────────────
            if self.lock_transforms:
                for obj in context.scene.objects:
                    if obj.type in ("MESH", "ARMATURE"):
                        obj.lock_location = (True, True, True)
                        obj.lock_rotation = (True, True, True)
                        obj.lock_scale = (True, True, True)

            # ── Set viewport mode ────────────────────────────────────
            if self.set_viewport:
                if self.import_preset == "CUSTOM":
                    if self.viewport_mode == "MATERIAL":
                        _set_viewport_material_preview()
                    elif self.viewport_mode == "WIREFRAME":
                        _set_viewport_xray()
                    elif self.viewport_mode == "SOLID":
                        _set_viewport_solid_flat()
                else:
                    _set_viewport_material_preview()

            # ── Report ───────────────────────────────────────────────
            anim_count = manifest.get("animation_count", 0)
            engine_count = len(engine_anims)
            msgs = [f"Imported {hero}: {imported_count} models"]
            msgs.append(f"{anim_count} animations ({engine_count} engine-mapped)")
            if removed_anims:
                msgs.append(f"{removed_anims} filtered out")
            msgs.append(f"{len(parts) - len(skipped_parts)} gear parts")
            if skipped_parts:
                msgs.append(f"skipped: {', '.join(skipped_parts)}")
            msgs.append(f"{hidden_count} collision hidden")
            if scale_pct != 100 and self.apply_scale:
                msgs.append(f"scale {scale_pct}%")
            self.report({"INFO"}, ", ".join(msgs))
            return {"FINISHED"}

    # ── Export Operator ───────────────────────────────────────────────────
    class HELIX_OT_export_gltf(bpy.types.Operator, ExportHelper):
        """Export Helix GLTF with correct settings and post-export validation."""
        bl_idname = "helix.export_gltf"
        bl_label = "Export Helix GLTF"
        bl_options = {"REGISTER"}

        filename_ext = ".gltf"
        filter_glob: StringProperty(default="*.gltf", options={"HIDDEN"})

        export_preset: EnumProperty(
            name="Preset",
            description="Export configuration",
            items=[
                ("ENGINE", "For Engine", "GLTF Separate with all animations and validation"),
                ("ANIM_ONLY", "Animation Only", "Export only animations, skip mesh validation"),
                ("CUSTOM", "Custom", "Manual settings"),
            ],
            default="ENGINE",
        )

        run_validation: BoolProperty(
            name="Run Post-Export Validation",
            description="Run validate_skibidi_export.py after export",
            default=True,
        )

        def execute(self, context):
            filepath = self.filepath

            export_args = dict(
                filepath=filepath,
                export_format="GLTF_SEPARATE",
                export_animations=True,
                export_skins=True,
                export_normals=True,
                export_tangents=False,
            )

            if self.export_preset == "ANIM_ONLY":
                export_args["export_skins"] = False
                export_args["export_normals"] = False

            try:
                bpy.ops.export_scene.gltf(**export_args, export_colors=True)
            except TypeError:
                bpy.ops.export_scene.gltf(**export_args)
            self.report({"INFO"}, f"Exported: {os.path.basename(filepath)}")

            if self.run_validation and self.export_preset != "ANIM_ONLY":
                self._run_validation(filepath)

            return {"FINISHED"}

        def _run_validation(self, filepath):
            addon_dir = os.path.dirname(os.path.realpath(__file__))
            tools_root = os.path.dirname(os.path.dirname(addon_dir))
            validator = os.path.join(tools_root, "scripts", "validate_skibidi_export.py")

            if not os.path.isfile(validator):
                self.report({"WARNING"}, "Validation script not found — skipping")
                return

            try:
                result = subprocess.run(
                    ["python3", validator, filepath],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode == 0:
                    self.report({"INFO"}, "Post-export validation: PASSED")
                else:
                    self.report({"WARNING"}, f"Validation warnings:\n{result.stdout}")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                self.report({"WARNING"}, "Could not run validation script")

    # ── Export Helix Package Operator ────────────────────────────────────
    class HELIX_OT_export_package(bpy.types.Operator, ExportHelper):
        """Export the current scene as a .helix package with enriched manifest."""
        bl_idname = "helix.export_package"
        bl_label = "Export Helix Package"
        bl_options = {"REGISTER"}

        filename_ext = ".helix"
        filter_glob: StringProperty(default="*.helix", options={"HIDDEN"})

        def execute(self, context):
            filepath = self.filepath

            # Find hero name from armature
            arm = _find_helix_armature(context)
            hero = arm.get("helix_hero", "hero") if arm else "hero"

            # Export scene as GLTF to temp dir first
            export_dir = tempfile.mkdtemp(prefix="helix_export_")
            gltf_path = os.path.join(export_dir, f"{hero}_base.gltf")

            export_args = dict(
                filepath=gltf_path,
                export_format="GLTF_SEPARATE",
                export_animations=True,
                export_skins=True,
                export_normals=True,
                export_tangents=False,
            )
            try:
                bpy.ops.export_scene.gltf(**export_args, export_colors=True)
            except TypeError:
                bpy.ops.export_scene.gltf(**export_args)

            # Call the packager via subprocess (can't import helix_utils in Blender)
            addon_dir = os.path.dirname(os.path.realpath(__file__))
            tools_root = os.path.dirname(os.path.dirname(addon_dir))
            build_script = os.path.join(tools_root, "scripts", "build_package.py")

            if not os.path.isfile(build_script):
                self.report({"WARNING"}, "build_package.py not found — saving raw GLTF export")
                return {"FINISHED"}

            try:
                env = os.environ.copy()
                env["PREP"] = export_dir
                env["HERO"] = hero
                env["OUT"] = filepath
                result = subprocess.run(
                    ["python3", build_script],
                    capture_output=True, text=True, timeout=60,
                    env=env, cwd=tools_root,
                )
                if result.returncode == 0:
                    size = os.path.getsize(filepath) if os.path.isfile(filepath) else 0
                    size_str = f"{size / 1024 / 1024:.1f} MB" if size > 1024 * 1024 else f"{size / 1024:.0f} KB"
                    self.report({"INFO"}, f"Exported {hero}.helix ({size_str})")
                else:
                    self.report({"WARNING"}, f"Package build issue: {result.stderr[:200]}")
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                self.report({"WARNING"}, f"Could not run packager: {e}")

            # Cleanup temp dir
            import shutil
            shutil.rmtree(export_dir, ignore_errors=True)

            return {"FINISHED"}

    # ── Batch Render Operator ────────────────────────────────────────────
    class HELIX_OT_batch_render(bpy.types.Operator):
        """Render a preview PNG for every .helix package in packages/."""
        bl_idname = "helix.batch_render"
        bl_label = "Render All Heroes"
        bl_options = {"REGISTER"}

        output_dir: StringProperty(
            name="Output Directory",
            default="/tmp/helix_batch_render",
        )

        render_size: EnumProperty(
            name="Size",
            items=[
                ("256", "256px", "Quick thumbnails"),
                ("512", "512px", "Standard preview"),
                ("1024", "1024px", "High quality"),
            ],
            default="512",
        )

        def execute(self, context):
            addon_dir = os.path.dirname(os.path.realpath(__file__))
            tools_root = os.path.dirname(os.path.dirname(addon_dir))
            render_script = os.path.join(
                tools_root, "helix-blender-tools", "scripts", "blender_render_preview.py",
            )

            if not os.path.isfile(render_script):
                self.report({"ERROR"}, "blender_render_preview.py not found")
                return {"CANCELLED"}

            heroes = _get_available_heroes()
            if not heroes:
                self.report({"ERROR"}, "No .helix packages found")
                return {"CANCELLED"}

            os.makedirs(self.output_dir, exist_ok=True)

            # Launch batch render as subprocess (can't re-enter Blender from itself)
            pkg_dir = _find_packages_dir()
            rendered = 0
            failed = 0
            for hero in heroes:
                pkg_path = os.path.join(pkg_dir, f"{hero}.helix")
                out_path = os.path.join(self.output_dir, f"{hero}.png")

                # Extract package to get GLTF path for render script
                try:
                    extract_dir = tempfile.mkdtemp(prefix=f"helix_br_{hero}_")
                    with zipfile.ZipFile(pkg_path, "r") as zf:
                        zf.extractall(extract_dir)
                    manifest_path = os.path.join(extract_dir, "manifest.json")
                    with open(manifest_path) as f:
                        manifest = json.load(f)
                    base_gltf = os.path.join(extract_dir, manifest["base_model"])

                    result = subprocess.run(
                        [
                            "blender", "--background",
                            "--python", render_script, "--",
                            "--file", base_gltf,
                            "--output", out_path,
                            "--size", self.render_size,
                        ],
                        capture_output=True, text=True, timeout=120,
                    )
                    if result.returncode == 0 and os.path.isfile(out_path):
                        rendered += 1
                    else:
                        failed += 1

                    import shutil
                    shutil.rmtree(extract_dir, ignore_errors=True)
                except Exception:
                    failed += 1

            self.report(
                {"INFO"},
                f"Batch render complete: {rendered}/{len(heroes)} rendered, "
                f"{failed} failed. Output: {self.output_dir}",
            )
            return {"FINISHED"}

    # ── Animation Template Generator ─────────────────────────────────────
    class HELIX_OT_generate_anim_template(bpy.types.Operator):
        """Generate pre-named empty Actions for all Helix MMORPG animations."""
        bl_idname = "helix.generate_anim_template"
        bl_label = "Generate Animation Template"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context):
            armatures = [o for o in context.scene.objects if o.type == "ARMATURE"]
            if not armatures:
                self.report({"ERROR"}, "No armature in scene — import a hero first")
                return {"CANCELLED"}

            created = 0
            skipped = 0

            present = {vocab_name(a.name) for a in bpy.data.actions}
            for anim_key in TEMPLATE_NAMES:
                meta = KNOWN_ANIMATIONS[anim_key]
                if anim_key in present:
                    skipped += 1
                    continue

                action = bpy.data.actions.new(name=anim_key)
                action.use_fake_user = True
                action["helix_type"] = meta["type"]
                action["helix_vocab_version"] = VOCAB_VERSION
                created += 1

            self.report(
                {"INFO"},
                f"Created {created} animation templates ({skipped} already existed)",
            )
            return {"FINISHED"}

    # ── Gear Visibility Toggle ───────────────────────────────────────────
    class HELIX_OT_toggle_gear(bpy.types.Operator):
        """Toggle visibility of a specific gear part."""
        bl_idname = "helix.toggle_gear"
        bl_label = "Toggle Gear Part"
        bl_options = {"REGISTER", "UNDO"}

        part_id: StringProperty()

        def execute(self, context):
            for obj in context.scene.objects:
                if obj.type == "MESH" and obj.get("helix_part_id") == self.part_id:
                    obj.hide_set(not obj.hide_get())
                    obj.hide_render = obj.hide_get()
            return {"FINISHED"}

    class HELIX_OT_gear_show_all(bpy.types.Operator):
        """Show all gear parts."""
        bl_idname = "helix.gear_show_all"
        bl_label = "Show All Gear"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context):
            for obj in context.scene.objects:
                if obj.type == "MESH" and "helix_part_id" in obj:
                    obj.hide_set(False)
                    obj.hide_render = False
            return {"FINISHED"}

    class HELIX_OT_gear_hide_all(bpy.types.Operator):
        """Hide all gear parts."""
        bl_idname = "helix.gear_hide_all"
        bl_label = "Hide All Gear"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context):
            for obj in context.scene.objects:
                if obj.type == "MESH" and "helix_part_id" in obj:
                    obj.hide_set(True)
                    obj.hide_render = True
            return {"FINISHED"}

    # ── Scale Operators ──────────────────────────────────────────────────
    class HELIX_OT_reset_scale_manifest(bpy.types.Operator):
        """Reset scale to manifest value."""
        bl_idname = "helix.reset_scale_manifest"
        bl_label = "Reset to Manifest Scale"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context):
            arm = _find_helix_armature(context)
            if not arm:
                self.report({"ERROR"}, "No Helix armature in scene")
                return {"CANCELLED"}
            pct = arm.get("helix_scale_pct", 100)
            s = pct / 100.0
            arm.scale = (s, s, s)
            self.report({"INFO"}, f"Scale reset to {pct}%")
            return {"FINISHED"}

    class HELIX_OT_reset_scale_100(bpy.types.Operator):
        """Reset scale to 100% (native)."""
        bl_idname = "helix.reset_scale_100"
        bl_label = "Reset to 100%"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context):
            arm = _find_helix_armature(context)
            if not arm:
                self.report({"ERROR"}, "No Helix armature in scene")
                return {"CANCELLED"}
            arm.scale = (1, 1, 1)
            self.report({"INFO"}, "Scale reset to 100%")
            return {"FINISHED"}

    # ── Viewport Mode Operators ──────────────────────────────────────────
    class HELIX_OT_viewport_material(bpy.types.Operator):
        """Switch to Material Preview."""
        bl_idname = "helix.viewport_material"
        bl_label = "Material Preview"

        def execute(self, context):
            _set_viewport_material_preview()
            return {"FINISHED"}

    class HELIX_OT_viewport_flat(bpy.types.Operator):
        """Switch to flat color mode."""
        bl_idname = "helix.viewport_flat"
        bl_label = "Flat Color"

        def execute(self, context):
            _set_viewport_solid_flat()
            return {"FINISHED"}

    class HELIX_OT_viewport_xray(bpy.types.Operator):
        """Switch to X-Ray skeleton mode."""
        bl_idname = "helix.viewport_xray"
        bl_label = "X-Ray Skeleton"

        def execute(self, context):
            _set_viewport_xray()
            return {"FINISHED"}

    # ── Play Animation Operator ──────────────────────────────────────────
    class HELIX_OT_play_animation(bpy.types.Operator):
        """Set an animation as the active Action on the armature."""
        bl_idname = "helix.play_animation"
        bl_label = "Play Animation"
        bl_options = {"REGISTER", "UNDO"}

        action_name: StringProperty()

        def execute(self, context):
            arm = _find_helix_armature(context)
            if not arm:
                self.report({"ERROR"}, "No Helix armature in scene")
                return {"CANCELLED"}

            action = bpy.data.actions.get(self.action_name)
            if not action:
                self.report({"ERROR"}, f"Action not found: {self.action_name}")
                return {"CANCELLED"}

            if not arm.animation_data:
                arm.animation_data_create()
            arm.animation_data.action = action

            context.scene.frame_set(context.scene.frame_start)
            bpy.ops.screen.animation_play()
            return {"FINISHED"}

    class HELIX_OT_stop_animation(bpy.types.Operator):
        """Stop animation playback."""
        bl_idname = "helix.stop_animation"
        bl_label = "Stop Animation"

        def execute(self, context):
            if context.screen.is_animation_playing:
                bpy.ops.screen.animation_cancel()
            arm = _find_helix_armature(context)
            if arm and arm.animation_data:
                arm.animation_data.action = None
            return {"FINISHED"}

    # ── Hero Switcher ────────────────────────────────────────────────────
    class HELIX_OT_switch_hero(bpy.types.Operator):
        """Clear scene and import a different hero."""
        bl_idname = "helix.switch_hero"
        bl_label = "Switch Hero"
        bl_options = {"REGISTER", "UNDO"}

        hero_name: StringProperty()

        def execute(self, context):
            pkg_dir = _find_packages_dir()
            if not pkg_dir:
                self.report({"ERROR"}, "packages/ directory not found")
                return {"CANCELLED"}

            pkg_path = os.path.join(pkg_dir, f"{self.hero_name}.helix")
            if not os.path.isfile(pkg_path):
                self.report({"ERROR"}, f"Package not found: {self.hero_name}.helix")
                return {"CANCELLED"}

            # Clear scene
            bpy.ops.object.select_all(action="SELECT")
            bpy.ops.object.delete()
            for action in list(bpy.data.actions):
                bpy.data.actions.remove(action)

            # Import via the package operator
            bpy.ops.helix.import_package(
                filepath=pkg_path,
                import_preset="FULL_PREVIEW",
            )
            return {"FINISHED"}

    # ── Skeleton Cleanup Operators ───────────────────────────────────────
    class HELIX_OT_hide_nondeform_bones(bpy.types.Operator):
        """Hide non-deform bones in the viewport."""
        bl_idname = "helix.hide_nondeform_bones"
        bl_label = "Hide Non-Deform Bones"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context):
            arm = _find_helix_armature(context)
            if not arm:
                self.report({"ERROR"}, "No Helix armature in scene")
                return {"CANCELLED"}

            hidden = 0
            for bone in arm.data.bones:
                if not bone.use_deform:
                    bone.hide = True
                    hidden += 1
            self.report({"INFO"}, f"Hidden {hidden} non-deform bones")
            return {"FINISHED"}

    class HELIX_OT_show_all_bones(bpy.types.Operator):
        """Show all bones."""
        bl_idname = "helix.show_all_bones"
        bl_label = "Show All Bones"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context):
            arm = _find_helix_armature(context)
            if not arm:
                return {"CANCELLED"}
            for bone in arm.data.bones:
                bone.hide = False
            return {"FINISHED"}

    class HELIX_OT_lock_root_bone(bpy.types.Operator):
        """Lock the root bone to prevent accidental movement."""
        bl_idname = "helix.lock_root_bone"
        bl_label = "Lock Root Bone"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context):
            arm = _find_helix_armature(context)
            if not arm:
                return {"CANCELLED"}
            root = arm.data.bones.get("root")
            if root:
                # Lock via pose bone
                pose_bone = arm.pose.bones.get("root")
                if pose_bone:
                    pose_bone.lock_location = (True, True, True)
                    pose_bone.lock_rotation = (True, True, True)
                    pose_bone.lock_scale = (True, True, True)
                self.report({"INFO"}, "Root bone locked")
            else:
                self.report({"WARNING"}, "No 'root' bone found")
            return {"FINISHED"}

    # ═══════════════════════════════════════════════════════════════════════
    # SIDEBAR PANELS
    # ═══════════════════════════════════════════════════════════════════════

    # ── Hero Info Panel ──────────────────────────────────────────────────
    class HELIX_PT_hero_info(bpy.types.Panel):
        """Package info and hero switcher."""
        bl_label = "Hero"
        bl_idname = "HELIX_PT_hero_info"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "Helix"
        bl_order = 0

        def draw(self, context):
            layout = self.layout
            arm = _find_helix_armature(context)

            if not arm:
                layout.label(text="No Helix hero in scene", icon="INFO")
                layout.label(text="File > Import > Helix Package")

                # Hero switcher even without a loaded hero
                heroes = _get_available_heroes()
                if heroes:
                    layout.separator()
                    layout.label(text=f"Quick Load ({len(heroes)} available):", icon="PACKAGE")
                    grid = layout.grid_flow(columns=3, align=True)
                    for h in heroes[:18]:
                        op = grid.operator("helix.switch_hero", text=h.title())
                        op.hero_name = h
                    if len(heroes) > 18:
                        layout.label(text=f"  ... and {len(heroes) - 18} more")
                return

            hero = arm.get("helix_hero", "?")
            scale_pct = arm.get("helix_scale_pct", 100)
            fmt_ver = arm.get("helix_format_version", 0)

            # Hero info
            box = layout.box()
            box.label(text=hero.replace("_", " ").title(), icon="ARMATURE_DATA")
            col = box.column(align=True)
            col.label(text=f"Bones: {len(arm.data.bones)}")
            col.label(text=f"Animations: {len(bpy.data.actions)}")
            col.label(text=f"Scale: {scale_pct}%  (current: {arm.scale[0]:.2f})")
            col.label(text=f"Format: v{fmt_ver}")

            # Engine animations count
            engine_anims_str = arm.get("helix_engine_anims", "")
            if engine_anims_str:
                engine_anims = json.loads(engine_anims_str)
                col.label(text=f"Engine anims: {len(engine_anims)}")

            # v2 build info
            build_info_str = arm.get("helix_build_info", "")
            if build_info_str:
                try:
                    bi = json.loads(build_info_str)
                    col.separator()
                    col.label(text=f"Built: {bi.get('timestamp', '?')[:10]}", icon="TIME")
                    commit = bi.get("source_commit", "")
                    if commit:
                        col.label(text=f"Commit: {commit}")
                except (json.JSONDecodeError, TypeError):
                    pass

            # Hero switcher
            heroes = _get_available_heroes()
            if heroes:
                layout.separator()
                layout.label(text=f"Switch Hero ({len(heroes)}):", icon="FILE_REFRESH")
                grid = layout.grid_flow(columns=3, align=True)
                for h in heroes[:18]:
                    if h == hero:
                        grid.label(text=f"[{h.title()}]")
                    else:
                        op = grid.operator("helix.switch_hero", text=h.title())
                        op.hero_name = h
                if len(heroes) > 18:
                    layout.label(text=f"  ... and {len(heroes) - 18} more")

                layout.separator()
                layout.operator("helix.batch_render", text="Render All Heroes", icon="RENDER_STILL")

    # ── Gear Panel ───────────────────────────────────────────────────────
    class HELIX_PT_gear(bpy.types.Panel):
        """Gear part visibility controls."""
        bl_label = "Gear Parts"
        bl_idname = "HELIX_PT_gear"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "Helix"
        bl_order = 1

        @classmethod
        def poll(cls, context):
            return _find_helix_armature(context) is not None

        def draw(self, context):
            layout = self.layout

            # Find gear parts
            parts = {}
            for obj in context.scene.objects:
                if obj.type == "MESH" and "helix_part_id" in obj:
                    pid = obj["helix_part_id"]
                    parts[pid] = {
                        "name": obj.name,
                        "visible": not obj.hide_get(),
                        "attach_bone": obj.get("helix_attach_bone", "?"),
                    }

            if not parts:
                layout.label(text="No gear parts loaded", icon="INFO")
                return

            # Show/Hide all
            row = layout.row(align=True)
            row.operator("helix.gear_show_all", text="Show All", icon="HIDE_OFF")
            row.operator("helix.gear_hide_all", text="Hide All", icon="HIDE_ON")
            layout.separator()

            # Per-part toggles
            for pid, info in sorted(parts.items()):
                row = layout.row(align=True)
                icon = "HIDE_OFF" if info["visible"] else "HIDE_ON"
                op = row.operator("helix.toggle_gear", text="", icon=icon)
                op.part_id = pid
                row.label(text=pid.replace("_", " ").title())
                row.label(text=info["attach_bone"])

    # ── Animation Panel ──────────────────────────────────────────────────
    class HELIX_PT_animations(bpy.types.Panel):
        """Animation playback controls."""
        bl_label = "Animations"
        bl_idname = "HELIX_PT_animations"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "Helix"
        bl_order = 2

        @classmethod
        def poll(cls, context):
            return _find_helix_armature(context) is not None

        def draw(self, context):
            layout = self.layout
            arm = _find_helix_armature(context)

            # Stop button
            if context.screen.is_animation_playing:
                layout.operator("helix.stop_animation", text="Stop", icon="PAUSE")
                layout.separator()

            # Template generator
            layout.operator("helix.generate_anim_template", icon="ACTION")
            layout.separator()

            # Engine animations (from manifest)
            engine_anims_str = arm.get("helix_engine_anims", "")
            engine_names = set()
            if engine_anims_str:
                engine_anims = json.loads(engine_anims_str)
                if engine_anims:
                    box = layout.box()
                    box.label(text="Engine Animations", icon="SOLO_ON")
                    for ea in engine_anims:
                        name = ea["name"]
                        engine_names.add(name.lower())
                        loop_type = ea.get("loop_type", "?")
                        badge = "LOOP" if loop_type == "loop" else "ONE"

                        row = box.row(align=True)
                        # Find matching action
                        action = None
                        for a in bpy.data.actions:
                            if a.name.lower() == name.lower():
                                action = a
                                break

                        if action:
                            is_active = (arm.animation_data
                                         and arm.animation_data.action == action)
                            icon = "PLAY" if not is_active else "RADIOBUT_ON"
                            op = row.operator("helix.play_animation",
                                              text="", icon=icon)
                            op.action_name = action.name
                        else:
                            row.label(text="", icon="X")
                        row.label(text=name.title())
                        row.label(text=f"[{badge}]")

            # Other actions
            other_actions = [
                a for a in bpy.data.actions
                if a.name.lower() not in engine_names
            ]
            if other_actions:
                box = layout.box()
                box.label(text=f"Other ({len(other_actions)})", icon="ACTION")
                for action in sorted(other_actions, key=lambda a: a.name)[:20]:
                    row = box.row(align=True)
                    is_active = (arm.animation_data
                                 and arm.animation_data.action == action)
                    icon = "PLAY" if not is_active else "RADIOBUT_ON"
                    op = row.operator("helix.play_animation",
                                      text="", icon=icon)
                    op.action_name = action.name
                    row.label(text=action.name)
                if len(other_actions) > 20:
                    box.label(text=f"  ... and {len(other_actions) - 20} more")

    # ── Viewport Panel ───────────────────────────────────────────────────
    class HELIX_PT_viewport(bpy.types.Panel):
        """Viewport and scale controls."""
        bl_label = "Display"
        bl_idname = "HELIX_PT_viewport"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "Helix"
        bl_order = 3

        @classmethod
        def poll(cls, context):
            return _find_helix_armature(context) is not None

        def draw(self, context):
            layout = self.layout

            # Viewport modes
            box = layout.box()
            box.label(text="Viewport Mode", icon="SHADING_RENDERED")
            row = box.row(align=True)
            row.operator("helix.viewport_material", text="Textured", icon="SHADING_TEXTURE")
            row.operator("helix.viewport_flat", text="Flat", icon="SHADING_SOLID")
            row.operator("helix.viewport_xray", text="X-Ray", icon="SHADING_WIRE")

            # Scale controls
            box = layout.box()
            box.label(text="Scale", icon="FULLSCREEN_ENTER")
            row = box.row(align=True)
            row.operator("helix.reset_scale_manifest", text="Manifest Scale")
            row.operator("helix.reset_scale_100", text="100%")

            # Skeleton
            box = layout.box()
            box.label(text="Skeleton", icon="BONE_DATA")
            row = box.row(align=True)
            row.operator("helix.hide_nondeform_bones", text="Hide Helper Bones")
            row.operator("helix.show_all_bones", text="Show All")
            box.operator("helix.lock_root_bone", text="Lock Root Bone", icon="LOCKED")

    # ── Animation Status Panel (existing, now reordered) ─────────────────
    class HELIX_PT_naming_enforcer(bpy.types.Panel):
        """Animation naming compliance with Helix conventions."""
        bl_label = "Animation Status"
        bl_idname = "HELIX_PT_naming_enforcer"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "Helix"
        bl_order = 4
        bl_options = {"DEFAULT_CLOSED"}

        def draw(self, context):
            layout = self.layout

            actions = list(bpy.data.actions)

            if not actions:
                layout.label(text="No animations in scene", icon="INFO")
                return

            matched = []
            unmatched = []
            for action in actions:
                if vocab_name(action.name):
                    matched.append(action.name)
                else:
                    unmatched.append(action.name)

            present = {vocab_name(a.name) for a in actions}
            missing = [name for name in TEMPLATE_NAMES if name not in present]

            # Priority animations status
            box = layout.box()
            box.label(text="Priority Animations", icon="SOLO_ON")
            for pname in PRIORITY_ANIMATIONS:
                icon = "CHECKMARK" if pname in present else "X"
                box.label(text=f"  {pname}", icon=icon)

            if matched:
                box = layout.box()
                box.label(text=f"Helix Animations ({len(matched)})", icon="CHECKMARK")
                for name in sorted(matched):
                    box.label(text=f"  {name}")

            if unmatched:
                box = layout.box()
                box.label(text=f"Custom ({len(unmatched)})", icon="INFO")
                for name in sorted(unmatched)[:10]:
                    box.label(text=f"  {name}")
                if len(unmatched) > 10:
                    box.label(text=f"  ... and {len(unmatched) - 10} more")

            if missing:
                box = layout.box()
                box.label(text=f"Missing ({len(missing)})", icon="ERROR")
                for name in sorted(missing)[:8]:
                    box.label(text=f"  {name}")
                if len(missing) > 8:
                    box.label(text=f"  ... and {len(missing) - 8} more")

    # ── Import/Export Menu Integration ─────────────────────────────────────
    def menu_func_import(self, context):
        self.layout.operator(HELIX_OT_import_package.bl_idname, text="Helix Package (.helix)")
        self.layout.operator(HELIX_OT_import_gltf.bl_idname, text="Helix GLTF (.gltf/.glb)")

    def menu_func_export(self, context):
        self.layout.operator(HELIX_OT_export_package.bl_idname, text="Helix Package (.helix)")
        self.layout.operator(HELIX_OT_export_gltf.bl_idname, text="Helix GLTF (.gltf)")

    # ── Registration ──────────────────────────────────────────────────────
    _classes = [
        HELIX_OT_import_package,
        HELIX_OT_import_gltf,
        HELIX_OT_export_gltf,
        HELIX_OT_export_package,
        HELIX_OT_batch_render,
        HELIX_OT_generate_anim_template,
        HELIX_OT_toggle_gear,
        HELIX_OT_gear_show_all,
        HELIX_OT_gear_hide_all,
        HELIX_OT_reset_scale_manifest,
        HELIX_OT_reset_scale_100,
        HELIX_OT_viewport_material,
        HELIX_OT_viewport_flat,
        HELIX_OT_viewport_xray,
        HELIX_OT_play_animation,
        HELIX_OT_stop_animation,
        HELIX_OT_switch_hero,
        HELIX_OT_hide_nondeform_bones,
        HELIX_OT_show_all_bones,
        HELIX_OT_lock_root_bone,
        HELIX_PT_hero_info,
        HELIX_PT_gear,
        HELIX_PT_animations,
        HELIX_PT_viewport,
        HELIX_PT_naming_enforcer,
    ]

    def register():
        for cls in _classes:
            bpy.utils.register_class(cls)
        bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
        bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

    def unregister():
        bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
        for cls in reversed(_classes):
            bpy.utils.unregister_class(cls)

else:
    # Outside Blender — expose constants for testing
    def register():
        pass

    def unregister():
        pass
