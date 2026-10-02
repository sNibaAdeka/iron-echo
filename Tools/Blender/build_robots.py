"""Generate original rigid-panel robots, a shared rig, animation FBXs and previews.

Run: blender --background --factory-startup --python build_robots.py -- --package PATH
All paths are relative to the package; no third-party art or source scene is needed.
The proposed rig/animation timings need acceptance by the gameplay owner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

CONTRACT = "IE-VIS-DRAFT-0.1"
PARTS = []
MATERIAL_NAMES = ["Gunmetal", "Armor", "Brass", "Rubber", "Signal"]
BASE_COLORS = {
    "Gunmetal": "29323B", "Armor": "BF7830", "Brass": "BA9B63",
    "Rubber": "10151C", "Signal": "F8B94E",
}
VARIANTS = {
    "vanguard": {"armor": "BF7830", "signal": "FFD270", "chest_scale": 1.0, "mark": "07"},
    "bulwark": {"armor": "356774", "signal": "8AE6F0", "chest_scale": 1.10, "mark": "12"},
}
CLIPS = {
    "Idle": {"duration_s": 2.0, "loop": True},
    "Guard": {"duration_s": 1.0, "loop": True},
    "Straight_L": {"duration_s": 0.5, "loop": False, "active_window_s": [0.16, 0.24]},
    "Straight_R": {"duration_s": 0.5, "loop": False, "active_window_s": [0.16, 0.24]},
    "Dodge_L": {"duration_s": 0.5, "loop": False},
    "Dodge_R": {"duration_s": 0.5, "loop": False},
    "HitReact": {"duration_s": 0.4, "loop": False},
    "KO": {"duration_s": 1.0, "loop": False},
}
BONES = [
    ("root", (0, 0, 0), (0, 0, .15), None),
    ("pelvis", (0, 0, 1.0), (0, 0, 1.17), "root"),
    ("spine_01", (0, 0, 1.17), (0, 0, 1.40), "pelvis"),
    ("chest", (0, 0, 1.40), (0, 0, 1.75), "spine_01"),
    ("neck", (0, 0, 1.75), (0, 0, 1.89), "chest"),
    ("head", (0, 0, 1.89), (0, 0, 2.08), "neck"),
]
for side, s in [("l", 1), ("r", -1)]:
    BONES += [
        (f"clavicle_{side}", (s*.08, 0, 1.73), (s*.39, 0, 1.73), "chest"),
        (f"upperarm_{side}", (s*.39, 0, 1.73), (s*.52, 0, 1.38), f"clavicle_{side}"),
        (f"lowerarm_{side}", (s*.52, 0, 1.38), (s*.49, -.13, 1.04), f"upperarm_{side}"),
        (f"hand_{side}", (s*.49, -.13, 1.04), (s*.49, -.13, .89), f"lowerarm_{side}"),
        (f"thigh_{side}", (s*.20, 0, 1.01), (s*.22, .01, .57), "pelvis"),
        (f"calf_{side}", (s*.22, .01, .57), (s*.22, .02, .16), f"thigh_{side}"),
        (f"foot_{side}", (s*.22, .02, .16), (s*.22, -.23, .08), f"calf_{side}"),
    ]
BONE_MAP = {r[0]: r for r in BONES}


def linear_rgb(value):
    def linear(c):
        return c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4
    return tuple(linear(int(value[i:i+2], 16)/255) for i in (0, 2, 4))


def make_material(name, color, metallic, roughness, emission=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    rgb = linear_rgb(color)
    m.diffuse_color = (*rgb, 1)
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*rgb, 1)
        bsdf.inputs["Emission Strength"].default_value = 2.0
    else:
        noise = m.node_tree.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 170
        noise.inputs["Detail"].default_value = 2
        bump = m.node_tree.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = .13
        bump.inputs["Distance"].default_value = .0015
        m.node_tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        m.node_tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def materials(variant):
    colors = dict(BASE_COLORS)
    colors["Armor"] = variant["armor"]
    colors["Signal"] = variant["signal"]
    return {
        "Gunmetal": make_material("Gunmetal", colors["Gunmetal"], .85, .34),
        "Armor": make_material("Armor", colors["Armor"], .55, .36),
        "Brass": make_material("Brass", colors["Brass"], .8, .30),
        "Rubber": make_material("Rubber", colors["Rubber"], .0, .68),
        "Signal": make_material("Signal", colors["Signal"], .1, .28, True),
    }


def finish_part(obj, name, material, bone, bevel=0):
    obj.name = name
    obj.data.materials.append(material)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new("Manufactured edge", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        bpy.ops.object.modifier_apply(modifier=mod.name)
        norm = obj.modifiers.new("Panel normals", "WEIGHTED_NORMAL")
        norm.keep_sharp = True
        bpy.ops.object.modifier_apply(modifier=norm.name)
    group = obj.vertex_groups.new(name=bone)
    group.add(list(range(len(obj.data.vertices))), 1, "REPLACE")
    obj["rigid_bone"] = bone
    PARTS.append(obj)
    return obj


def box(name, loc, size, mat, bone, bevel=.018):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.scale = size
    return finish_part(obj, name, mat, bone, bevel)


def tube(name, start, end, radius, mat, bone, vertices=16):
    start, end = Vector(start), Vector(end)
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=(end-start).length, location=(start+end)/2)
    obj = bpy.context.object
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = (end-start).to_track_quat("Z", "Y")
    return finish_part(obj, name, mat, bone, .006)


def create_rig():
    arm = bpy.data.armatures.new("IE_SharedSkeleton")
    rig = bpy.data.objects.new("Armature", arm)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for name, head, tail, parent in BONES:
        b = arm.edit_bones.new(name)
        b.head, b.tail = head, tail
        if parent:
            b.parent = arm.edit_bones[parent]
        b.use_deform = True
    bpy.ops.object.mode_set(mode="OBJECT")
    for p in rig.pose.bones:
        p.rotation_mode = "QUATERNION"
    rig["contract"] = CONTRACT
    rig["forward"] = "-Y"
    return rig


def robot_geometry(m, variant):
    scale = variant["chest_scale"]
    box("Pelvic gearbox", (0, .015, 1.07), (.45, .32, .21), m["Gunmetal"], "pelvis")
    box("Belt armor", (0, -.17, 1.09), (.39, .08, .13), m["Armor"], "pelvis")
    tube("Spine hydraulic", (0, 0, 1.14), (0, 0, 1.46), .09, m["Rubber"], "spine_01")
    for z in [1.22, 1.29, 1.36]:
        box("Abdominal lamella", (0, -.14, z), (.31, .10, .052), m["Gunmetal"], "spine_01", .009)
    box("Thorax core", (0, .025, 1.59), (.59*scale, .32, .37), m["Gunmetal"], "chest", .035)
    box("Sternum stripe", (0, -.19, 1.58), (.065, .09, .28), m["Brass"], "chest", .012)
    for s in (-1, 1):
        p = box("Pectoral plate", (s*.155*scale, -.195, 1.60), (.235*scale, .095, .26), m["Armor"], "chest", .025)
        p.rotation_euler[1] = s*math.radians(9)
        for z in [1.53, 1.58, 1.63]:
            box("Thorax vent", (s*.15, -.248, z), (.15, .012, .014), m["Rubber"], "chest", .002)
        box("Back pressure reservoir", (s*.19, .21, 1.58), (.115, .13, .30), m["Gunmetal"], "chest", .022)
    tube("Neck spindle", (0, 0, 1.74), (0, 0, 1.94), .085, m["Brass"], "neck")
    box("Helmet shell", (0, .012, 1.996), (.30, .245, .305), m["Gunmetal"], "head", .035)
    box("Forehead brow", (0, -.14, 2.075), (.325, .09, .09), m["Armor"], "head", .018)
    box("Visor recess", (0, -.132, 2.01), (.25, .048, .08), m["Rubber"], "head", .012)
    box("Horizontal signal visor", (0, -.159, 2.015), (.21, .014, .024), m["Signal"], "head", .005)
    box("Jaw guard", (0, -.125, 1.905), (.25, .09, .075), m["Armor"], "head", .012)
    for s, side in [(1, "l"), (-1, "r")]:
        upper, lower = BONE_MAP[f"upperarm_{side}"], BONE_MAP[f"lowerarm_{side}"]
        tube("Shoulder hinge", (s*.32, 0, 1.73), (s*.47, 0, 1.73), .135, m["Brass"], f"clavicle_{side}")
        box("Shoulder cap", (s*.415, -.005, 1.775), (.25, .35, .17), m["Armor"], f"clavicle_{side}", .027)
        tube("Upperarm drive", upper[1], upper[2], .080, m["Gunmetal"], f"upperarm_{side}")
        plate = box("Upperarm armor", (s*.46, -.071, 1.545), (.15, .15, .26), m["Armor"], f"upperarm_{side}")
        plate.rotation_euler[1] = s*math.radians(18)
        tube("Elbow hinge", (s*.46, 0, 1.38), (s*.58, 0, 1.38), .089, m["Brass"], f"lowerarm_{side}")
        tube("Forearm drive", lower[1], lower[2], .097, m["Gunmetal"], f"lowerarm_{side}")
        forearm = box("Forearm guard", (s*.505, -.083, 1.24), (.185, .22, .22), m["Armor"], f"lowerarm_{side}", .023)
        forearm.rotation_euler[0] = math.radians(-20)
        tube("Wrist bearing", (s*.49, -.13, 1.095), (s*.49, -.13, 1.0), .086, m["Rubber"], f"hand_{side}")
        box("Armored fist", (s*.49, -.15, .968), (.21, .245, .21), m["Gunmetal"], f"hand_{side}", .03)
        for x in [s*.49-.068, s*.49, s*.49+.068]:
            box("Knuckle pad", (x, -.281, .975), (.050, .055, .15), m["Brass"], f"hand_{side}", .009)
        box("Hand identifier", (s*.49, -.158, 1.075), (.145, .12, .015), m["Signal"], f"hand_{side}", .004)
        thigh, calf = BONE_MAP[f"thigh_{side}"], BONE_MAP[f"calf_{side}"]
        tube("Thigh actuator", thigh[1], thigh[2], .10, m["Gunmetal"], f"thigh_{side}")
        box("Thigh armor", (s*.215, -.07, .795), (.19, .21, .31), m["Armor"], f"thigh_{side}", .025)
        tube("Knee shaft", (s*.15, .01, .57), (s*.29, .01, .57), .09, m["Brass"], f"calf_{side}")
        box("Knee guard", (s*.22, -.095, .58), (.19, .10, .15), m["Gunmetal"], f"calf_{side}")
        tube("Calf piston", calf[1], calf[2], .073, m["Gunmetal"], f"calf_{side}")
        box("Shin armor", (s*.22, -.065, .335), (.17, .17, .26), m["Armor"], f"calf_{side}")
        box("Heel block", (s*.22, .055, .09), (.22, .19, .17), m["Gunmetal"], f"foot_{side}")
        box("Weighted foot", (s*.22, -.15, .065), (.235, .36, .13), m["Gunmetal"], f"foot_{side}", .019)
        box("Sole tread", (s*.22, -.15, .016), (.24, .365, .027), m["Rubber"], f"foot_{side}", .006)
        for y in [-.25, -.17, -.09]:
            box("Boot tread ridge", (s*.22, y, .004), (.225, .016, .008), m["Rubber"], f"foot_{side}", .001)


def join_robot(rig, m, ident):
    bpy.ops.object.select_all(action="DESELECT")
    for o in PARTS:
        o.select_set(True)
    bpy.context.view_layer.objects.active = PARTS[0]
    bpy.ops.object.join()
    mesh = bpy.context.object
    mesh.name = "SK_IE_" + ident.capitalize()
    material_per_poly = [mesh.data.materials[p.material_index].name for p in mesh.data.polygons]
    mesh.data.materials.clear()
    for name in MATERIAL_NAMES:
        mesh.data.materials.append(m[name])
    for poly, name in zip(mesh.data.polygons, material_per_poly):
        poly.material_index = MATERIAL_NAMES.index(name)
    # Collapse the object origin while preserving rest-space vertex positions.
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    mesh.parent = rig
    arm = mesh.modifiers.new("IE_RigidSkin", "ARMATURE")
    arm.object = rig
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=.01)
    bpy.ops.object.mode_set(mode="OBJECT")
    mesh.data.calc_loop_triangles()
    return mesh


def reset_pose(rig):
    for p in rig.pose.bones:
        p.location = (0, 0, 0)
        p.rotation_quaternion = (1, 0, 0, 0)
        p.scale = (1, 1, 1)
    bpy.context.view_layer.update()


def aim_bone(rig, name, direction):
    """Rotate a rigid bone toward a direction in armature coordinates, without scaling."""
    p = rig.pose.bones[name]
    b = p.bone
    q = (b.tail_local-b.head_local).normalized().rotation_difference(Vector(direction).normalized())
    matrix = q.to_matrix().to_4x4() @ b.matrix_local
    head = p.head.copy()
    matrix.translation = head
    p.matrix = matrix
    bpy.context.view_layer.update()


def guard_pose(rig, amount=1.0):
    for side, s in [("l", 1), ("r", -1)]:
        rest_upper = Vector(BONE_MAP[f"upperarm_{side}"][2])-Vector(BONE_MAP[f"upperarm_{side}"][1])
        rest_lower = Vector(BONE_MAP[f"lowerarm_{side}"][2])-Vector(BONE_MAP[f"lowerarm_{side}"][1])
        upper_dir = rest_upper.normalized().lerp(Vector((s*.10, -.35, -.12)).normalized(), amount)
        lower_dir = rest_lower.normalized().lerp(Vector((-s*.05, -.12, .33)).normalized(), amount)
        aim_bone(rig, f"upperarm_{side}", upper_dir)
        aim_bone(rig, f"lowerarm_{side}", lower_dir)
        aim_bone(rig, f"hand_{side}", (0, -.15, .02))


def sample_pose(rig, clip, t):
    reset_pose(rig)
    guard_pose(rig, .72 if clip == "Idle" else 1.0)
    envelope = math.sin(math.pi*t)**2
    if clip == "Idle":
        rig.pose.bones["spine_01"].rotation_quaternion = Vector((1, 0, 0)).rotation_difference(Vector((1, 0, .015*math.sin(2*math.pi*t))))
    elif clip.startswith("Straight_"):
        side = clip[-1].lower()
        s = 1 if side == "l" else -1
        # Start from guard, extend at 40% of the clip, then recover.
        ext = t/.4 if t <= .4 else (1-t)/.6
        ext = max(0, min(1, ext))
        upper = Vector((s*.10, -.35, -.12)).normalized().lerp(Vector((-s*.025, -.35, .04)).normalized(), ext)
        lower = Vector((-s*.05, -.12, .33)).normalized().lerp(Vector((-s*.018, -.35, .025)).normalized(), ext)
        aim_bone(rig, f"upperarm_{side}", upper)
        aim_bone(rig, f"lowerarm_{side}", lower)
        aim_bone(rig, f"hand_{side}", (0, -.15, 0))
    elif clip.startswith("Dodge_"):
        s = 1 if clip.endswith("L") else -1
        rig.pose.bones["spine_01"].rotation_quaternion = (math.cos(.17*envelope), 0, s*math.sin(.17*envelope), 0)
    elif clip == "HitReact":
        rig.pose.bones["chest"].rotation_quaternion = (math.cos(.1*envelope), math.sin(.1*envelope), 0, 0)
    elif clip == "KO":
        guard_pose(rig, max(0, 1-t*1.7))
        rig.pose.bones["spine_01"].rotation_quaternion = (math.cos(.48*t), math.sin(.48*t), 0, 0)
        # KO is a root-motion-free kneeling/bowing reaction, not simulated ragdoll.
    bpy.context.view_layer.update()


def build_actions(rig):
    rig.animation_data_create()
    actions = {}
    for name, meta in CLIPS.items():
        action = bpy.data.actions.new(name)
        action.use_fake_user = True
        rig.animation_data.action = action
        frames = round(meta["duration_s"]*60)
        for frame in range(1, frames+2):
            bpy.context.scene.frame_set(frame)
            sample_pose(rig, name, (frame-1)/frames)
            for p in rig.pose.bones:
                p.keyframe_insert(data_path="rotation_quaternion", frame=frame, group=p.name)
        actions[name] = action
    rig.animation_data.action = None
    reset_pose(rig)
    return actions


def select_robot(rig, mesh=None):
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    if mesh:
        mesh.select_set(True)
    bpy.context.view_layer.objects.active = rig


def export_robot(package, ident, rig, mesh, actions, animation_files):
    root = package/"ArtSource"/"exports"
    select_robot(rig, mesh)
    bpy.ops.export_scene.fbx(
        filepath=str(root/f"{ident}.fbx"), use_selection=True,
        object_types={"ARMATURE", "MESH"}, add_leaf_bones=False,
        axis_forward="-Y", axis_up="Z", apply_unit_scale=True,
        bake_anim=False, use_armature_deform_only=False,
        mesh_smooth_type="FACE", use_mesh_modifiers=True,
        path_mode="AUTO", use_custom_props=True,
    )
    if animation_files:
        (root/"animations").mkdir(exist_ok=True)
        select_robot(rig)
        for name, action in actions.items():
            rig.animation_data.action = action
            rig.animation_data.action_slot = action.slots[0]
            bpy.context.scene.frame_start = 1
            bpy.context.scene.frame_end = round(CLIPS[name]["duration_s"]*60)+1
            bpy.ops.export_scene.fbx(
                filepath=str(root/"animations"/f"{name}.fbx"), use_selection=True,
                object_types={"ARMATURE"}, add_leaf_bones=False,
                axis_forward="-Y", axis_up="Z", apply_unit_scale=True,
                bake_anim=True, bake_anim_use_all_actions=False,
                bake_anim_use_nla_strips=False, bake_anim_simplify_factor=0,
                bake_anim_use_all_bones=True, use_armature_deform_only=False,
            )
        rig.animation_data.action = None
    reset_pose(rig)


def mesh_report(mesh, rig):
    mesh.data.calc_loop_triangles()
    zs = [v.co.z for v in mesh.data.vertices]
    xs = [v.co.x for v in mesh.data.vertices]
    ys = [v.co.y for v in mesh.data.vertices]
    weights = [list(v.groups) for v in mesh.data.vertices]
    return {
        "vertices": len(mesh.data.vertices), "triangles": len(mesh.data.loop_triangles),
        "material_slots": [m.name for m in mesh.data.materials],
        "bone_count": len(rig.data.bones), "bounds_m": {"x": [min(xs), max(xs)], "y": [min(ys), max(ys)], "z": [min(zs), max(zs)]},
        "height_m": max(zs)-min(zs), "uv_layers": len(mesh.data.uv_layers),
        "single_rigid_weight_per_vertex": all(len(w)==1 and abs(w[0].weight-1)<.00001 for w in weights),
        "unweighted_vertices": sum(not w for w in weights),
        "object_scale": list(mesh.scale), "negative_scale": any(s<=0 for s in mesh.scale),
    }


def build_variant(package, ident):
    global PARTS
    PARTS = []
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1
    scene.render.fps = 60
    rig = create_rig()
    m = materials(VARIANTS[ident])
    robot_geometry(m, VARIANTS[ident])
    mesh = join_robot(rig, m, ident)
    actions = build_actions(rig)
    report = mesh_report(mesh, rig)
    assert report["triangles"] < 25000, report
    assert report["single_rigid_weight_per_vertex"] and report["uv_layers"] == 1
    export_robot(package, ident, rig, mesh, actions, ident=="vanguard")
    scene.frame_start, scene.frame_end = 1, 121
    rig.animation_data.action = actions["Idle"]
    rig.animation_data.action_slot = actions["Idle"].slots[0]
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(package/"ArtSource"/"Blender"/f"{ident}.blend"))
    return report


def append_variant(package, ident, location):
    path = str(package/"ArtSource"/"Blender"/f"{ident}.blend")
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n in ("Armature", "SK_IE_"+ident.capitalize())]
    objects = [o for o in dst.objects if o is not None]
    for o in objects:
        bpy.context.collection.objects.link(o)
    rig = next(o for o in objects if o.type == "ARMATURE")
    rig.location = location
    rig.name = ident+"_PresentationRig"
    return rig


def point_at(obj, target):
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat("-Z", "Y").to_euler()


def light(name, loc, power, color, size, target):
    data = bpy.data.lights.new(name, "AREA")
    data.energy, data.color, data.shape, data.size = power, color, "DISK", size
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = loc
    point_at(obj, target)


def render_gallery(package, quick=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24 if quick else 48
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1600, 1100
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("Workshop World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (.022, .032, .05, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = .3
    scene.world = world
    append_variant(package, "vanguard", (-.66, 0, 0))
    append_variant(package, "bulwark", (.66, .09, 0))
    floor_mat = make_material("Presentation floor", "141C26", .4, .48)
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.015))
    bpy.context.object.data.materials.append(floor_mat)
    for x in [-.66, .66]:
        bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=.60, depth=.075, location=(x, 0, -.055))
        bpy.context.object.data.materials.append(floor_mat)
    light("Warm key", (-3, -4, 5), 700, (1, .72, .40), 4, (0, 0, 1.2))
    light("Cold rim", (2.6, 1.4, 3.5), 900, (.32, .70, 1), 3, (0, 0, 1.3))
    light("Front softbox", (1, -4, 2.4), 340, (.73, .86, 1), 3, (0, 0, 1.25))
    bpy.ops.object.camera_add(location=(3.2, -6.3, 3.1))
    camera = bpy.context.object
    point_at(camera, (0, 0, 1.20))
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 3.65
    scene.camera = camera
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(package/"Previews"/"robots-studio.png")
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(package/"ArtSource"/"Blender"/"presentation.blend"))
    bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--quick-render", action="store_true")
    args = parser.parse_args(argv)
    package = args.package.resolve()
    for sub in ["ArtSource/Blender", "ArtSource/exports", "Previews", "Docs/Art"]:
        (package/sub).mkdir(parents=True, exist_ok=True)
    reports = {ident: build_variant(package, ident) for ident in VARIANTS}
    manifest = {
        "schema_version": 1, "contract_version": CONTRACT, "status": "draft_not_opus_accepted",
        "generator": "Tools/Blender/build_robots.py", "blender_version": bpy.app.version_string,
        "export_space": {"units": "meters", "axis_forward": "-Y", "axis_up": "Z", "desired_ue_forward": "+X", "root_motion": False},
        "robots": [{"id": ident, "fbx": f"{ident}.fbx", "height_m": reports[ident]["height_m"], "armor_srgb": variant["armor"], "signal_srgb": variant["signal"], "stats": reports[ident]} for ident, variant in VARIANTS.items()],
        "bones": [b[0] for b in BONES], "materials": MATERIAL_NAMES,
        "sockets": [{"name": "Fist_"+side.upper(), "bone": "hand_"+side, "location_cm": [0,0,0], "rotation_deg": [0,0,0], "status": "provisional_origin_not_contact_center"} for side in ("l", "r")],
        "animations": [{"name": name, "fbx": f"animations/{name}.fbx", **meta} for name, meta in CLIPS.items()],
        "clips": list(CLIPS),
        "limitations": ["Unreal import and target-Windows FPS not verified", "No live IK solver/runtime plugin in this package", "KO clip is stylized bow, not ragdoll", "No LOD meshes yet", "Procedural Blender noise recreated approximately in Unreal materials"],
    }
    export_root = package/"ArtSource"/"exports"
    # Quality exports have their own manifest and dependency snapshot.
    files = [export_root/f"{ident}.fbx" for ident in VARIANTS]
    files += [export_root/"animations"/f"{name}.fbx" for name in CLIPS]
    manifest["files_sha256"] = {str(p.relative_to(package/"ArtSource"/"exports")): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (package/"ArtSource"/"exports"/"art_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (package/"Docs"/"Art"/"BLENDER_BUILD_REPORT.json").write_text(json.dumps({"blender_version": bpy.app.version_string, "robots": reports, "animations_exported": list(CLIPS), "unreal_verified": False}, indent=2), encoding="utf-8")
    if not args.no_render:
        render_gallery(package, args.quick_render)
    print("IRON_ECHO_BUILD_COMPLETE " + str(package))


if __name__ == "__main__":
    main()
