"""Import IRON ECHO robot FBXs using the classic, explicit FBX factory.

Run in Unreal Editor Python console:
    import import_art; import_art.main([])
Pass ["--replace"] only after the binary author has handed over ownership.
This does not edit .uproject, Config, gameplay, collision or animation rules.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import unreal
from art_common import (
    ART_ROOT, ArtLock, bind_robot_materials, clip_path, install_mesh_sockets,
    load_manifest, mesh_path, require_clean_editor, save_asset, source_file,
    write_report,
)


def property_set(obj, name, value):
    try:
        obj.set_editor_property(name, value)
    except Exception as error:
        raise RuntimeError("Unsupported FBX option {}.{}: {}".format(type(obj).__name__, name, error)) from error


def require_classic_fbx():
    for name in ("FbxFactory", "FbxImportUI", "FbxSkeletalMeshImportData", "AssetImportTask"):
        if not hasattr(unreal, name):
            raise RuntimeError(
                "Classic FBX API is not available: {}. This script does not silently "
                "switch to Interchange. Opus must select the supported importer for this engine.".format(name)
            )


def options_for(skeleton=None, animation=False):
    options = unreal.FbxImportUI()
    import_type = unreal.FBXImportType.FBXIT_ANIMATION if animation else unreal.FBXImportType.FBXIT_SKELETAL_MESH
    for name, value in (
        ("automated_import_should_detect_type", False),
        ("mesh_type_to_import", import_type),
        ("original_import_type", import_type),
        ("import_as_skeletal", True),
        ("import_mesh", not animation),
        ("import_animations", animation),
        ("import_materials", False),
        ("import_textures", False),
        ("create_physics_asset", False),
        ("override_full_name", True),
    ):
        property_set(options, name, value)
    if skeleton is not None:
        property_set(options, "skeleton", skeleton)
    data = options.get_editor_property("anim_sequence_import_data" if animation else "skeletal_mesh_import_data")
    for name, value in (
        ("convert_scene", True),
        ("convert_scene_unit", True),
        ("force_front_x_axis", True),
        ("import_uniform_scale", 1.0),
        ("import_translation", unreal.Vector(0.0, 0.0, 0.0)),
        ("import_rotation", unreal.Rotator(0.0, 0.0, 0.0)),
    ):
        property_set(data, name, value)
    if animation:
        property_set(data, "use_default_sample_rate", False)
        property_set(data, "custom_sample_rate", 60)
        property_set(data, "remove_redundant_keys", False)
        property_set(data, "animation_length", unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME)
    else:
        for name, value in (
            ("import_mesh_lods", False),
            ("import_morph_targets", False),
            ("import_meshes_in_bone_hierarchy", True),
            ("update_skeleton_reference_pose", False),
            ("use_t0_as_ref_pose", False),
            ("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS),
            ("normal_generation_method", unreal.FBXNormalGenerationMethod.MIKK_T_SPACE),
            ("reorder_material_to_fbx_order", True),
        ):
            property_set(data, name, value)
    return options


def import_one(source, destination, options, replace):
    folder, name = destination.rsplit("/", 1)
    task = unreal.AssetImportTask()
    for key, value in (
        ("filename", str(source)), ("destination_path", folder),
        ("destination_name", name), ("automated", True),
        ("replace_existing", replace), ("replace_existing_settings", False),
        ("save", True), ("async_", False), ("factory", unreal.FbxFactory()),
        ("options", options),
    ):
        property_set(task, key, value)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    objects = list(task.get_objects())
    records = [{"path": str(obj.get_path_name()), "class": str(obj.get_class().get_name())} for obj in objects]
    if any(not record["path"].startswith(ART_ROOT + "/") for record in records):
        raise RuntimeError("Importer produced assets outside the art root: " + json.dumps(records))
    asset = unreal.EditorAssetLibrary.load_asset(destination)
    if not asset:
        raise RuntimeError(
            "Expected deterministic destination missing: {}. Engine may have selected Interchange "
            "or changed FBX naming. Imported results: {}".format(destination, records)
        )
    return asset, records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", help="Default: ArtSource/exports/art_manifest.json relative to this package")
    parser.add_argument("--replace", action="store_true", help="Explicit opt-in to replace owned robot/clip assets")
    args = parser.parse_args(argv)
    require_clean_editor()
    require_classic_fbx()
    manifest, manifest_path = load_manifest(args.manifest)
    export_space = manifest.get("export_space", {})
    if export_space.get("axis_forward", export_space.get("forward", "-Y")) != "-Y" or export_space.get("axis_up", export_space.get("up", "Z")) != "Z":
        raise ValueError("This importer is for Blender -Y-forward/Z-up export; verify the draft contract")
    robots = manifest["robots"]
    animations = manifest.get("animations", [])
    if not animations:
        raise ValueError("Manifest needs single-take animation exports in animations[]")
    if any(not isinstance(clip, dict) or not clip.get("fbx") for clip in animations):
        raise ValueError("Every animation needs {name, fbx, duration_s}")
    # Finish all file/existence checks before the first asset mutation.
    robot_sources = [source_file(manifest_path, robot["fbx"]) for robot in robots]
    clip_sources = [source_file(manifest_path, clip["fbx"]) for clip in animations]
    destinations = [mesh_path(robot["id"]) for robot in robots] + [clip_path(clip["name"]) for clip in animations]
    if len(destinations) != len(set(destinations)):
        raise ValueError("Duplicate asset destinations")
    if not args.replace:
        conflicts = [destination for destination in destinations if unreal.EditorAssetLibrary.does_asset_exist(destination)]
        for robot in robots:
            folder = mesh_path(robot["id"]).rsplit("/", 1)[0]
            conflicts += list(unreal.EditorAssetLibrary.list_assets(folder, recursive=True, include_folder=False))
        if conflicts:
            raise RuntimeError("Art assets already exist; use --replace after ownership handoff: " + repr(sorted(set(conflicts))))
    report = {
        "status": "started", "contract_version": manifest.get("contract_version", "draft-unapproved"),
        "manifest": str(manifest_path), "replace": args.replace,
        "importer": "FbxFactory (explicit classic)", "robots": [], "animations": [], "warnings": [],
        "not_verified": ["packaged Windows build", "in-game IK", "gameplay hit timing", "contact offsets", "RTX 3050 profiling"],
    }
    with ArtLock():
        try:
            skeleton = None
            preview_mesh = None
            first_existing = unreal.EditorAssetLibrary.load_asset(mesh_path(robots[0]["id"])) if args.replace else None
            if isinstance(first_existing, unreal.SkeletalMesh):
                skeleton = first_existing.get_editor_property("skeleton")
            default_sockets = [
                {"name": "Fist_L", "bone": "hand_l", "location_cm": [0.0, 0.0, 0.0]},
                {"name": "Fist_R", "bone": "hand_r", "location_cm": [0.0, 0.0, 0.0]},
            ]
            for robot, source in zip(robots, robot_sources):
                mesh, imported = import_one(source, mesh_path(robot["id"]), options_for(skeleton), args.replace)
                if not isinstance(mesh, unreal.SkeletalMesh):
                    raise RuntimeError("Expected SkeletalMesh: " + mesh.get_path_name())
                imported_skeleton = mesh.get_editor_property("skeleton")
                if not imported_skeleton:
                    raise RuntimeError("Robot import did not create a skeleton")
                if skeleton is None:
                    skeleton = imported_skeleton
                elif imported_skeleton.get_path_name() != skeleton.get_path_name():
                    raise RuntimeError("Robot variant did not reuse the common skeleton")
                slots = bind_robot_materials(mesh, robot["id"], robot)
                if preview_mesh is None:
                    preview_mesh = mesh
                sockets, warnings = install_mesh_sockets(mesh, manifest.get("sockets", default_sockets))
                report["warnings"] += warnings
                save_asset(imported_skeleton)
                report["robots"].append({
                    "id": robot["id"], "mesh": mesh.get_path_name(), "source": str(source),
                    "skeleton": imported_skeleton.get_path_name(), "material_slots": slots,
                    "sockets": sockets, "imported_objects": imported,
                })
            for clip, source in zip(animations, clip_sources):
                options = options_for(skeleton, animation=True)
                property_set(options, "override_animation_name", "A_IE_" + clip["name"])
                sequence, imported = import_one(source, clip_path(clip["name"]), options, args.replace)
                if not isinstance(sequence, unreal.AnimSequence):
                    raise RuntimeError("Expected AnimSequence: " + sequence.get_path_name())
                sequence.set_editor_property("loop", bool(clip.get("loop", False)))
                sequence.set_preview_skeletal_mesh(preview_mesh)
                save_asset(sequence)
                report["animations"].append({
                    "name": clip["name"], "asset": sequence.get_path_name(), "source": str(source),
                    "imported_objects": imported,
                })
            report["status"] = "imported_requires_validation"
            write_report("import_art", report)
            unreal.log("IRON ECHO import complete. Run validate_import.main([]); sockets/wear/IK remain draft.")
        except Exception as error:
            report["status"] = "failed"
            report["error"] = str(error)
            write_report("import_art", report)
            raise
    return report


if __name__ == "__main__":
    main()
