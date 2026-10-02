"""Read-only imported art checks; run AFTER import_art inside Unreal Editor.

Unsupported API checks remain unverified instead of silently passing.
No gameplay performance, IK solver or contact timing is certified here.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import unreal
from art_common import clip_path, load_manifest, mesh_path, require_editor, write_report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest")
    args = parser.parse_args(argv)
    require_editor()
    manifest, manifest_path = load_manifest(args.manifest)
    checks = []

    def check(name, passed, evidence):
        checks.append({"name": name, "passed": passed, "evidence": evidence})

    skeletons = []
    for robot in manifest["robots"]:
        ident = robot["id"]
        mesh = unreal.EditorAssetLibrary.load_asset(mesh_path(ident))
        check(ident+"_skeletal_asset", isinstance(mesh, unreal.SkeletalMesh), mesh_path(ident))
        if not isinstance(mesh, unreal.SkeletalMesh):
            continue
        skeleton = mesh.get_editor_property("skeleton")
        check(ident+"_skeleton", bool(skeleton), str(skeleton))
        if skeleton:
            skeletons.append(str(skeleton.get_path_name()))
        slots = list(mesh.get_editor_property("materials"))
        names = [str(s.get_editor_property("material_slot_name")) for s in slots]
        check(ident+"_slots", len(names)==5 and set(names)==set(manifest["materials"]), names)
        materials = [s.get_editor_property("material_interface") for s in slots]
        check(ident+"_materials_bound", all(materials), [str(m) for m in materials])
        if hasattr(mesh, "get_imported_bounds"):
            bounds = mesh.get_imported_bounds()
            height_cm = 2.0*float(bounds.box_extent.z)
            target_cm = float(robot["height_m"])*100
            check(ident+"_height_cm", abs(height_cm-target_cm)<3.0, {"actual":height_cm,"target":target_cm})
        else:
            check(ident+"_height_cm", None, "API unavailable; inspect actual bounds in Skeletal Mesh Editor")
        try:
            component = unreal.SkeletalMeshComponent()
            component.set_skeletal_mesh_asset(mesh)
            if hasattr(component, "get_num_bones") and hasattr(component, "get_bone_name"):
                bones = [str(component.get_bone_name(i)) for i in range(component.get_num_bones())]
                check(ident+"_bones", set(manifest["bones"]).issubset(set(bones)), bones)
            else:
                check(ident+"_bones", None, "Enumerate bones manually in Skeleton Editor on this engine")
        except Exception as error:
            check(ident+"_bones", None, str(error))
        available = {}
        for index in range(mesh.num_sockets()):
            socket = mesh.get_socket_by_index(index)
            available[str(socket.get_editor_property("socket_name"))] = str(socket.get_editor_property("bone_name"))
        for spec in manifest.get("sockets", []):
            actual = available.get(spec["name"])
            # Draft zero-offset sockets are not required to preview the mesh;
            # missing sockets remain unverified and block future gameplay acceptance.
            check(ident+"_socket_"+spec["name"], None if actual is None else actual==spec["bone"], available)
    check("common_skeleton", len(skeletons)==len(manifest["robots"]) and len(set(skeletons))==1, skeletons)
    for clip in manifest["animations"]:
        sequence = unreal.EditorAssetLibrary.load_asset(clip_path(clip["name"]))
        check(clip["name"]+"_asset", isinstance(sequence, unreal.AnimSequence), clip_path(clip["name"]))
        if isinstance(sequence, unreal.AnimSequence):
            try:
                seconds = float(sequence.get_editor_property("sequence_length"))
                check(clip["name"]+"_duration", abs(seconds-float(clip["duration_s"]))<.025, seconds)
                skeleton = sequence.get_editor_property("skeleton")
                check(clip["name"]+"_skeleton", bool(skeleton) and str(skeleton.get_path_name()) in skeletons, str(skeleton))
            except Exception as error:
                check(clip["name"]+"_metadata", None, str(error))
    failed = [c["name"] for c in checks if c["passed"] is False]
    unknown = [c["name"] for c in checks if c["passed"] is None]
    report = {
        "status": "requires_fix" if failed else "requires_manual_review",
        "manifest": str(manifest_path), "checks": checks, "failed": failed, "unverified": unknown,
        "manual_checks": ["+X forward after import", "left/right limb mapping", "Guard and straight poses in motion", "joint intersections", "fist contact offsets", "gameplay active window alignment", "arena light exposure and camera framing"],
        "packaged_windows_verified": False, "rtx3050_performance_verified": False,
    }
    write_report("validate_import", report)
    unreal.log("IRON ECHO validation: failures={}, unverified={}; manual visual review remains".format(len(failed),len(unknown)))
    return report


if __name__ == "__main__":
    main()
