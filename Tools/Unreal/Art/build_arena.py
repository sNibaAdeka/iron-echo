"""Build the owned art sandbox: 6.4 m industrial ring, modest lights, cameras.

Creates /Game/Art/IronEcho/Arena/L_IE_ArtSandbox by default. No GameMode,
gameplay actors, damage, VFX hits, input mapping or .uproject edits.
--replace permits replacement of this generator's tagged actors only, and
refuses maps containing another author's actors. --map-name creates a fresh
comparison map without overwriting the previous result.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import unreal
from art_common import (
    ART_ROOT, ArtLock, art_path, clip_path, load_manifest, mesh_path,
    require_clean_editor, safe_name, surface_instance, write_report,
)

TAG = "IronEchoArtGeneratedV1"
RING_TOP_CM = 60.0
RING_HALF_CM = 320.0


def spawn(actor_class, label, location, rotation=(0.0, 0.0, 0.0)):
    actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(
        actor_class, unreal.Vector(*location), unreal.Rotator(*rotation)
    )
    if not actor:
        raise RuntimeError("Actor spawn failed: " + label)
    actor.set_actor_label(label)
    actor.set_editor_property("tags", [unreal.Name(TAG)])
    return actor


def primitive(label, dimensions, location, material, shape="Cube", rotation=(0.0, 0.0, 0.0), collision=False):
    mesh = unreal.EditorAssetLibrary.load_asset("/Engine/BasicShapes/" + shape)
    if not mesh:
        raise RuntimeError("Engine primitive missing: " + shape)
    actor = spawn(unreal.StaticMeshActor, label, location, rotation)
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    component.set_static_mesh(mesh)
    actor.set_actor_scale3d(unreal.Vector(*[value / 100.0 for value in dimensions]))
    component.set_material(0, material)
    component.set_mobility(unreal.ComponentMobility.STATIC)
    component.set_editor_property("cast_shadow", True)
    component.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS if collision else unreal.CollisionEnabled.NO_COLLISION)
    return actor


def light(label, location, target, intensity, color, shadow):
    rotation = unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*location), unreal.Vector(*target))
    actor = spawn(unreal.SpotLight, label, location, (rotation.pitch, rotation.yaw, rotation.roll))
    component = actor.get_component_by_class(unreal.SpotLightComponent)
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    component.set_editor_property("intensity_units", unreal.LightUnits.LUMENS)
    component.set_intensity(intensity)
    component.set_light_color(unreal.LinearColor(*color, 1.0))
    component.set_editor_property("attenuation_radius", 1400.0)
    component.set_editor_property("inner_cone_angle", 35.0)
    component.set_editor_property("outer_cone_angle", 65.0)
    component.set_editor_property("cast_shadows", shadow)
    component.set_editor_property("volumetric_scattering_intensity", 0.0)
    return actor


def camera(label, location, target, fov):
    rotation = unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*location), unreal.Vector(*target))
    actor = spawn(unreal.CameraActor, label, location, (rotation.pitch, rotation.yaw, rotation.roll))
    component = actor.get_component_by_class(unreal.CameraComponent)
    component.set_field_of_view(fov)
    component.set_editor_property("constrain_aspect_ratio", False)
    return actor


def robot_preview(robot, position, yaw):
    mesh = unreal.EditorAssetLibrary.load_asset(mesh_path(robot["id"]))
    if not isinstance(mesh, unreal.SkeletalMesh):
        return None
    actor = spawn(unreal.SkeletalMeshActor, "IE_ArtPreview_" + robot["id"], position, (0.0, yaw, 0.0))
    component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    component.set_skeletal_mesh_asset(mesh)
    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    guard = unreal.EditorAssetLibrary.load_asset(clip_path("Guard"))
    if isinstance(guard, unreal.AnimSequence):
        component.set_animation_mode(unreal.AnimationMode.ANIMATION_SINGLE_NODE)
        data = unreal.SingleAnimationPlayData(
            anim_to_play=guard, saved_looping=True, saved_playing=True,
            saved_position=0.0, saved_play_rate=1.0,
        )
        component.set_editor_property("animation_data", data)
        component.play_animation(guard, True)
    return actor


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest")
    parser.add_argument("--map-name", default="L_IE_ArtSandbox")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args(argv)
    require_clean_editor()
    safe_name(args.map_name)
    if not args.map_name.startswith("L_IE_ArtSandbox"):
        raise ValueError("Map name must start with L_IE_ArtSandbox")
    map_path = art_path(ART_ROOT + "/Arena/" + args.map_name)
    manifest, manifest_path = load_manifest(args.manifest)
    exists = unreal.EditorAssetLibrary.does_asset_exist(map_path)
    if exists and not args.replace:
        raise RuntimeError("Map exists. Use a new --map-name or --replace after ownership handoff")
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    report = {
        "status": "started", "map": map_path, "manifest": str(manifest_path),
        "contract_version": manifest.get("contract_version", "draft-unapproved"),
        "ring_cm": {"side": 640.0, "top_z": RING_TOP_CM}, "warnings": [],
        "budgets": {"shadowed_movable_spot_lights": 2, "unshadowed_spot_lights": 2, "volumetric_fog": False},
        "not_verified": ["visual exposure in target project", "shadow/light cost on RTX 3050", "camera occlusion during gameplay", "packaged build"],
    }
    with ArtLock():
        try:
            unreal.EditorAssetLibrary.make_directory(ART_ROOT + "/Arena")
            if exists:
                if not levels.load_level(map_path):
                    raise RuntimeError("Could not open owned sandbox map")
                existing = list(actors.get_all_level_actors())
                unowned = [actor for actor in existing if TAG not in [str(tag) for tag in actor.tags]
                           and str(actor.get_class().get_name()) not in ("WorldSettings", "Brush")]
                if unowned:
                    raise RuntimeError("Map has non-generator actors; replacement refused: " + repr([actor.get_actor_label() for actor in unowned]))
                for actor in existing:
                    if TAG in [str(tag) for tag in actor.tags] and not actors.destroy_actor(actor):
                        raise RuntimeError("Could not remove owned actor: " + actor.get_actor_label())
            elif not levels.new_level(map_path):
                raise RuntimeError("Could not create sandbox map")

            # A small set of reusable PBR instances; no textures or expensive shader noise.
            dark = surface_instance("ArenaSteel", (0.16, 0.18, 0.20), 0.86, 0.55)
            concrete = surface_instance("Concrete", (0.26, 0.27, 0.28), 0.0, 0.91)
            mat = surface_instance("RingCanvas", (0.31, 0.35, 0.37), 0.0, 0.82)
            marking = surface_instance("CanvasLines", (0.67, 0.70, 0.69), 0.0, 0.84)
            teal = surface_instance("TealCorner", (0.10, 0.42, 0.49), 0.35, 0.48)
            orange = surface_instance("OrangeCorner", (0.76, 0.29, 0.10), 0.35, 0.48)
            warm = surface_instance("WarmFixture", (1.0, 0.66, 0.30), 0.0, 0.35, 3.0)
            cool = surface_instance("CoolFixture", (0.45, 0.75, 0.88), 0.0, 0.35, 2.0)

            primitive("IE_FactoryFloor", (1800.0, 1600.0, 30.0), (0.0, 0.0, -35.0), concrete, collision=True)
            primitive("IE_RingBase", (680.0, 680.0, 80.0), (0.0, 0.0, 10.0), dark, collision=True)
            primitive("IE_RingCanvas", (640.0, 640.0, 10.0), (0.0, 0.0, 55.0), mat, collision=True)
            # Flat markings remain outside the duel centre; readability before decoration.
            for index, x in enumerate((-180.0, 180.0)):
                primitive("IE_CornerMark_" + str(index), (100.0, 6.0, 0.4), (x, 0.0, 60.25), marking)
            for side in (-1, 1):
                material = teal if side < 0 else orange
                for y in (-RING_HALF_CM, RING_HALF_CM):
                    primitive("IE_Post_{}_{}".format(side, int(y)), (24.0, 24.0, 175.0), (side * RING_HALF_CM, y, 137.5), material)
                # Rails along X sides leave front/back open for shoulder camera visibility.
                for row, z in enumerate((105.0, 145.0, 185.0)):
                    primitive("IE_Rail_{}_{}".format(side, row), (8.0, 625.0, 8.0), (side * RING_HALF_CM, 0.0, z), dark)
            # Vertical ropes would obscure arms from the shoulder camera; use low front/back rails.
            for y in (-RING_HALF_CM, RING_HALF_CM):
                primitive("IE_LowRail_" + str(int(y)), (625.0, 8.0, 8.0), (0.0, y, 105.0), dark)
            for step in range(3):
                primitive("IE_EntryStep_" + str(step), (110.0, 45.0, 15.0 + step * 15.0), (-240.0, -400.0 + step * 40.0, (15.0 + step * 15.0) * 0.5), dark, collision=True)

            # Background architecture: industrial rhythm without dense small meshes.
            primitive("IE_BackWall", (1800.0, 40.0, 620.0), (0.0, 780.0, 275.0), concrete)
            primitive("IE_LeftWall", (40.0, 1600.0, 620.0), (-880.0, 0.0, 275.0), concrete)
            primitive("IE_RightWall", (40.0, 1600.0, 620.0), (880.0, 0.0, 275.0), concrete)
            for index, x in enumerate((-760.0, -380.0, 0.0, 380.0, 760.0)):
                primitive("IE_BackColumn_" + str(index), (32.0, 40.0, 600.0), (x, 750.0, 275.0), dark)
                primitive("IE_BackPanel_" + str(index), (260.0, 12.0, 210.0), (x, 752.0, 180.0), dark)
            for index, y in enumerate((-560.0, 0.0, 560.0)):
                primitive("IE_OverheadBeam_" + str(index), (1600.0, 24.0, 35.0), (0.0, y, 545.0), dark)
            for index, (x, y) in enumerate(((-550.0, 560.0), (550.0, 560.0), (-660.0, 250.0), (650.0, -220.0))):
                primitive("IE_Crate_" + str(index), (100.0, 110.0, 90.0), (x, y, 10.0), dark)
                primitive("IE_CrateBand_" + str(index), (102.0, 12.0, 91.0), (x, y, 10.0), teal if index % 2 == 0 else orange)
            for index, (x, y, material) in enumerate(((-210.0, -80.0, cool), (210.0, 120.0, warm))):
                primitive("IE_LightHousing_" + str(index), (130.0, 32.0, 18.0), (x, y, 480.0), dark)
                primitive("IE_LightEmitter_" + str(index), (112.0, 24.0, 1.0), (x, y, 470.5), material)

            light("IE_KeyCool", (-230.0, -170.0, 465.0), (-100.0, 0.0, 170.0), 5200.0, (0.76, 0.88, 1.0), True)
            light("IE_KeyWarm", (230.0, 150.0, 465.0), (100.0, 0.0, 170.0), 4600.0, (1.0, 0.88, 0.73), True)
            light("IE_FillFront", (-540.0, -350.0, 330.0), (0.0, 0.0, 165.0), 1800.0, (0.80, 0.88, 1.0), False)
            light("IE_FillBack", (420.0, 530.0, 370.0), (0.0, 0.0, 150.0), 1700.0, (1.0, 0.83, 0.67), False)

            # Markers are plain visual actors. Opus chooses gameplay spawn logic separately.
            spawn(unreal.Actor, "IE_PlayerStartMarker", (-120.0, 0.0, RING_TOP_CM))
            spawn(unreal.Actor, "IE_OpponentStartMarker", (120.0, 0.0, RING_TOP_CM), (0.0, 180.0, 0.0))
            for index, robot in enumerate(manifest["robots"][:2]):
                if not robot_preview(robot, ((-120.0 if index == 0 else 120.0), 0.0, RING_TOP_CM), 0.0 if index == 0 else 180.0):
                    report["warnings"].append("Robot preview missing; import " + robot["id"] + " first")

            shoulder = camera("IE_CameraShoulderPreview", (-430.0, 105.0, 235.0), (120.0, 0.0, 175.0), 80.0)
            camera("IE_CameraEntranceWide", (-650.0, -600.0, 340.0), (0.0, 0.0, 160.0), 55.0)
            camera("IE_CameraResult", (0.0, -420.0, 205.0), (0.0, 0.0, 170.0), 65.0)
            if not levels.save_current_level():
                raise RuntimeError("Sandbox level save failed")
            report["generated_actor_count"] = sum(TAG in [str(tag) for tag in actor.tags] for actor in actors.get_all_level_actors())
            report["cameras"] = ["IE_CameraShoulderPreview", "IE_CameraEntranceWide", "IE_CameraResult"]
            report["status"] = "generated_requires_visual_review"
            write_report("build_arena", report)
            if hasattr(levels, "pilot_level_actor"):
                levels.pilot_level_actor(shoulder)
            unreal.log("IRON ECHO art sandbox ready for manual exposure/framing review; not a gameplay map.")
        except Exception as error:
            report["status"] = "failed"
            report["error"] = str(error)
            write_report("build_arena", report)
            raise
    return report


if __name__ == "__main__":
    main()
