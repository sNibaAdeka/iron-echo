"""Blender-side checks of export scale, rigid skinning and animated hand travel.

Run after build_robots.py; this performs actual FBX round trips, not just parsing.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def main():
    argv = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=Path(__file__).resolve().parents[2])
    package = parser.parse_args(argv).package.resolve()
    export = package/"ArtSource"/"exports"
    manifest = json.loads((export/"art_manifest.json").read_text(encoding="utf-8"))
    checks = []

    def check(name, passed, evidence):
        checks.append({"name": name, "passed": bool(passed), "evidence": evidence})

    for robot in manifest["robots"]:
        ident = robot["id"]
        bpy.ops.wm.open_mainfile(filepath=str(package/"ArtSource"/"Blender"/(ident+".blend")))
        rig = next(o for o in bpy.context.scene.objects if o.type=="ARMATURE")
        mesh = next(o for o in bpy.context.scene.objects if o.type=="MESH")
        check(ident+"_rigid_weights", all(len(v.groups)==1 and abs(v.groups[0].weight-1)<1e-6 for v in mesh.data.vertices), len(mesh.data.vertices))
        check(ident+"_bones", set(manifest["bones"])==set(rig.data.bones.keys()), list(rig.data.bones.keys()))
        check(ident+"_materials", [m.name for m in mesh.data.materials]==manifest["materials"], [m.name for m in mesh.data.materials])
        check(ident+"_uv", len(mesh.data.uv_layers)==1, len(mesh.data.uv_layers))
        for side in ("L", "R"):
            action = bpy.data.actions.get("Straight_"+side)
            rig.animation_data.action = action
            rig.animation_data.action_slot = action.slots[0]
            frames = [1, 7, 13, 19, 25, 31]
            wrist_positions, roots, lengths = [], [], []
            for f in frames:
                bpy.context.scene.frame_set(f)
                bpy.context.view_layer.update()
                wrist_positions.append(list(rig.pose.bones["hand_"+side.lower()].head))
                roots.append(list(rig.pose.bones["root"].head))
                lengths.append([rig.pose.bones["upperarm_"+side.lower()].length, rig.pose.bones["lowerarm_"+side.lower()].length])
            travel = max(p[1] for p in wrist_positions)-min(p[1] for p in wrist_positions)
            check(ident+"_"+side+"_forward_travel", travel>.20, {"travel_m": travel, "sample_positions": wrist_positions})
            check(ident+"_"+side+"_no_root_motion", max(Vector(p).length for p in roots)<1e-5, roots)
            check(ident+"_"+side+"_no_limb_stretch", all(abs(v[i]-lengths[0][i])<1e-4 for v in lengths for i in (0,1)), lengths)
        # FBX skeleton and scale should survive export back into Blender.
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(export/robot["fbx"]))
        imported_rig = next(o for o in bpy.context.scene.objects if o.type=="ARMATURE")
        imported_mesh = next(o for o in bpy.context.scene.objects if o.type=="MESH")
        points = [imported_mesh.matrix_world @ v.co for v in imported_mesh.data.vertices]
        height = max(p.z for p in points)-min(p.z for p in points)
        check(ident+"_fbx_scale", abs(height-robot["height_m"])<.015, {"imported_height_m": height, "source_height_m": robot["height_m"]})
        check(ident+"_fbx_bones", set(manifest["bones"]).issubset(set(imported_rig.data.bones.keys())), list(imported_rig.data.bones.keys()))
        check(ident+"_fbx_armature_modifier", any(m.type=="ARMATURE" for m in imported_mesh.modifiers), [m.type for m in imported_mesh.modifiers])
    for clip in manifest["animations"]:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.render.fps = 60
        bpy.ops.import_scene.fbx(filepath=str(export/clip["fbx"]))
        rigs = [o for o in bpy.context.scene.objects if o.type=="ARMATURE"]
        check(clip["name"]+"_fbx_rig", len(rigs)==1, len(rigs))
        actions = list(bpy.data.actions)
        check(clip["name"]+"_fbx_action", len(actions)==1, [a.name for a in actions])
        if actions:
            start, end = actions[0].frame_range
            seconds = (end-start)/60
            check(clip["name"]+"_fbx_duration", abs(seconds-clip["duration_s"])<.02, {"frame_range": [start,end], "seconds": seconds})
    result = {
        "blender_version": bpy.app.version_string,
        "checks": checks, "passed": sum(c["passed"] for c in checks), "total": len(checks),
        "unreal_verified": False, "windows_verified": False,
        "scope": "Offline Blender weights, motion geometry and FBX round-trip only; not gameplay acceptance",
    }
    (package/"Docs"/"Art"/"BLENDER_QA_REPORT.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    failed = [c["name"] for c in checks if not c["passed"]]
    print("IRON_ECHO_QA", result["passed"], "/", result["total"], "failed:", failed)
    if failed:
        raise RuntimeError("Blender QA failed: "+", ".join(failed))


if __name__ == "__main__":
    main()
