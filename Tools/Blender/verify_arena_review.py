"""Actual arena FBX round trip, portable source checks and camera diagnostics.

Visibility is a sparse vertex-ray diagnostic, not visible pixel area or game QA.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_arena_review import configure_camera
from build_robots import sample_pose


def world_dimensions(mesh):
    points = [mesh.matrix_world @ Vector(point) for point in mesh.bound_box]
    return [max(p[axis] for p in points) - min(p[axis] for p in points) for axis in range(3)]


def camera_diagnostics(scene, camera, enemy):
    groups = {name: enemy.vertex_groups[name].index for name in ('head', 'hand_l', 'hand_r')}
    samples = {
        name: [v.index for v in enemy.data.vertices if any(g.group == index for g in v.groups)][::6]
        for name, index in groups.items()
    }
    deps = bpy.context.evaluated_depsgraph_get()
    evaluated = enemy.evaluated_get(deps)
    geometry = evaluated.to_mesh()
    results = {}
    try:
        for name, ids in samples.items():
            visible = inside = blocked_by_player = 0
            xs, ys = [], []
            for index in ids:
                point = enemy.matrix_world @ geometry.vertices[index].co
                screen = world_to_camera_view(scene, camera, point)
                xs.append(screen.x);ys.append(screen.y)
                if .02 < screen.x < .98 and .02 < screen.y < .98 and screen.z > 0:
                    inside += 1
                delta = point - camera.location
                hit, _, _, face, first, _ = scene.ray_cast(
                    deps, camera.location, delta.normalized(), distance=delta.length + .015)
                if hit and first.original.name == 'SK_IE_Vanguard':
                    blocked_by_player += 1
                if hit and first.original == enemy and face >= 0:
                    indices = geometry.polygons[face].vertices
                    if all(any(g.group == groups[name] for g in enemy.data.vertices[i].groups) for i in indices):
                        visible += 1
            results[name] = {
                'sample_vertices': len(ids), 'same_bone_first_hit_fraction': visible / len(ids),
                'inside_safe_frame_fraction': inside / len(ids),
                'player_first_hit_fraction': blocked_by_player / len(ids),
                'screen_bounds_normalized': {'x': [min(xs), max(xs)], 'y': [min(ys), max(ys)]},
            }
    finally:
        evaluated.to_mesh_clear()
    return results


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=Path(__file__).resolve().parents[2])
    package = parser.parse_args(argv).package.resolve()
    export = package / 'ArtSource/exports/arena'
    manifest = json.loads((export / 'arena_manifest.json').read_text())
    checks = []
    def check(name, passed, evidence):
        checks.append({'name': name, 'passed': bool(passed), 'evidence': evidence})
    source = export / manifest['fbx']
    check('fbx_checksum', hashlib.sha256(source.read_bytes()).hexdigest() == manifest['sha256'], source.name)
    blend = (package / manifest['blend']).resolve();blend.relative_to(package)
    check('blend_checksum', hashlib.sha256(blend.read_bytes()).hexdigest() == manifest['blend_sha256'], manifest['blend'])
    for relative, digest in manifest['robot_source_sha256'].items():
        filename = (package / 'ArtSource/exports' / relative).resolve()
        filename.relative_to((package / 'ArtSource/exports').resolve())
        check('robot_unchanged_' + relative, hashlib.sha256(filename.read_bytes()).hexdigest() == digest, relative)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(source))
    objects = list(bpy.context.scene.objects)
    check('only_one_static_mesh', len(objects) == 1 and objects[0].type == 'MESH', [o.type for o in objects])
    mesh = next(o for o in objects if o.type == 'MESH')
    mesh.data.calc_loop_triangles()
    check('triangle_count', len(mesh.data.loop_triangles) == manifest['triangles'], len(mesh.data.loop_triangles))
    check('geometry_budget', len(mesh.data.loop_triangles) < 80000, len(mesh.data.loop_triangles))
    dimensions = world_dimensions(mesh)
    check('metre_scale', max(abs(a - b) for a, b in zip(dimensions, manifest['dimensions_m'])) < .001, dimensions)
    slots = [m.name for m in mesh.data.materials]
    check('material_names_order', slots == manifest['material_names'], slots)
    check('uv_channel', len(mesh.data.uv_layers) == 1, len(mesh.data.uv_layers))
    check('finite_uv_range', all(-.0001 <= c <= 1.0001 for uv in mesh.data.uv_layers.active.data for c in uv.uv), 'All UV coordinates in [0,1]')
    check('nondegenerate_triangles', all(t.area > 1e-10 for t in mesh.data.loop_triangles), min(t.area for t in mesh.data.loop_triangles))
    check('no_vertex_groups', len(mesh.vertex_groups) == 0, len(mesh.vertex_groups))
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    scene = bpy.context.scene
    for ident in ('vanguard', 'bulwark'):
        for label in ('BaseColor', 'ORM', 'Normal'):
            expected = (package / f'ArtSource/Textures/robots/{ident}/T_IE_{ident}_{label}.png').resolve()
            images = [i for i in bpy.data.images if i.source == 'FILE' and Path(bpy.path.abspath(i.filepath)).resolve() == expected]
            check(f'portable_{ident}_{label}', bool(images) and expected.is_file() and all(i.filepath.startswith('//') for i in images), str(expected.relative_to(package)))
    player = bpy.data.objects['SK_IE_Vanguard'].parent
    enemy_mesh = bpy.data.objects['SK_IE_Bulwark'];enemy = enemy_mesh.parent
    camera = scene.camera
    configure_camera(camera, manifest['camera_preview'])
    pose_cases = [('enemy', 'Guard', 0)]
    for actor in ('enemy', 'player'):
        for clip in ('Straight_L', 'Straight_R'):
            pose_cases.extend((actor, clip, t) for t in (.16, .4, .8))
        pose_cases.extend((actor, clip, .5) for clip in ('Dodge_L', 'Dodge_R'))
    frames = []
    for actor, clip, t in pose_cases:
        sample_pose(player, 'Guard', 0);sample_pose(enemy, 'Guard', 0)
        sample_pose(enemy if actor == 'enemy' else player, clip, t)
        metrics = camera_diagnostics(scene, camera, enemy_mesh)
        frames.append({'actor': actor, 'clip': clip, 'normalized_time': t, 'groups': metrics})
        name = f'{actor}_{clip}_{t}'
        check('camera_safe_frame_' + name, all(v['inside_safe_frame_fraction'] == 1 for v in metrics.values()), metrics)
        # Only detects a completely hidden group. Does not certify combat readability.
        check('camera_no_group_completely_hidden_' + name, all(v['same_bone_first_hit_fraction'] > .10 for v in metrics.values()), metrics)
    minimum = min(v['same_bone_first_hit_fraction'] for frame in frames for v in frame['groups'].values())
    report = {
        'scope': 'Blender actual FBX round trip and sparse vertex-ray camera diagnostics; not UE gameplay',
        'blender_version': bpy.app.version_string, 'checks': checks,
        'passed': sum(c['passed'] for c in checks), 'total': len(checks),
        'camera': {'pose_cases': len(frames), 'minimum_same_bone_first_hit_fraction': minimum,
                   'frames': frames, 'combat_readability_approved': False,
                   'limitations': ['Sparse vertex rays do not measure visible pixel area',
                                   'A guard hand overlaps a straight attack in the peak preview',
                                   'Fixed distance and Blender art poses only; no tracking, follow/collision or simultaneous actions',
                                   'Low-contrast, aspect ratios, actual hit windows and HUD overlap await Unreal review']},
        'unreal_verified': False, 'windows_verified': False,
    }
    (package / 'Docs/Art/ARENA_QA_REPORT.json').write_text(json.dumps(report, indent=2) + '\n')
    failed = [c['name'] for c in checks if not c['passed']]
    print('IRON_ECHO_ARENA_QA', report['passed'], '/', report['total'], 'failed:', failed)
    if failed:
        raise RuntimeError('Arena source QA failed: ' + ', '.join(failed))


if __name__ == '__main__':
    main()
