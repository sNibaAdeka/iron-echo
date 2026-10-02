"""Editor-only static art import; default preflight, explicit --apply to write.

Epic Python 5.6 classic FBX API baseline; execution in Unreal is unverified.
Does not change a map, .uproject, gameplay, collision rules or project lighting.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import unreal
from art_common import (
    ART_ROOT, PACKAGE_ROOT, ArtLock, art_path, require_clean_editor, save_asset,
    source_file, surface_instance, write_report,
)
from import_art import import_one, property_set, require_classic_fbx

DESTINATION = art_path(ART_ROOT + '/Arena/SM_IE_IndustrialArena')


def options():
    ui = unreal.FbxImportUI()
    for name, value in (
        ('automated_import_should_detect_type', False),
        ('mesh_type_to_import', unreal.FBXImportType.FBXIT_STATIC_MESH),
        ('original_import_type', unreal.FBXImportType.FBXIT_STATIC_MESH),
        ('import_as_skeletal', False), ('import_mesh', True),
        ('import_animations', False), ('import_materials', False),
        ('import_textures', False), ('override_full_name', True),
    ):
        property_set(ui, name, value)
    data = ui.get_editor_property('static_mesh_import_data')
    for name, value in (
        ('convert_scene', True), ('convert_scene_unit', True),
        ('force_front_x_axis', True), ('import_uniform_scale', 1.0),
        ('import_translation', unreal.Vector(0, 0, 0)),
        ('import_rotation', unreal.Rotator(0, 0, 0)),
        ('combine_meshes', True), ('auto_generate_collision', False),
        ('build_nanite', False), ('generate_lightmap_u_vs', False),
        ('import_mesh_lods', False), ('remove_degenerates', True),
        ('normal_import_method', unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS),
        ('normal_generation_method', unreal.FBXNormalGenerationMethod.MIKK_T_SPACE),
        ('reorder_material_to_fbx_order', True),
    ):
        property_set(data, name, value)
    return ui


def inspect(mesh, manifest, subsystem):
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError('Expected StaticMesh at ' + DESTINATION)
    box = mesh.get_bounding_box()
    extent = box.max - box.min
    bounds = [extent.x, extent.y, extent.z]
    # XY is symmetric in the source, so this is independent of front-axis mapping.
    expected = sorted(size * 100 for size in manifest['dimensions_m'])
    if any(abs(value - target) > 2.0 for value, target in zip(sorted(bounds), expected)):
        raise RuntimeError('Arena bounds do not match centimetres: ' + repr(bounds))
    slots = list(mesh.get_editor_property('static_materials'))
    names = [str(slot.get_editor_property('material_slot_name')) for slot in slots]
    if names != manifest['material_names']:
        raise RuntimeError('Arena slot names/order differ: ' + repr(names))
    uv_count = subsystem.get_num_uv_channels(mesh, 0)
    if uv_count < 1:
        raise RuntimeError('Arena UV channel is missing')
    collision_count = subsystem.get_simple_collision_count(mesh)
    if collision_count != 0:
        raise RuntimeError('Unexpected imported simple collision: ' + str(collision_count))
    nanite = bool(mesh.get_editor_property('nanite_settings').get_editor_property('enabled'))
    if nanite:
        raise RuntimeError('Existing/imported arena has Nanite enabled; review its writer settings before continuing')
    return {
        'asset': mesh.get_path_name(), 'bounds_cm': bounds,
        'material_names': names, 'uv_channels': uv_count,
        'render_vertices': subsystem.get_number_verts(mesh, 0),
        'lod_count': subsystem.get_lod_count(mesh),
        'simple_collisions': collision_count, 'nanite_enabled': nanite,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--replace', action='store_true', help='Current binary writer explicitly replaces arena mesh')
    args = parser.parse_args(argv)
    if args.replace and not args.apply:
        raise ValueError('--replace requires --apply')
    require_clean_editor()
    require_classic_fbx()
    filename = PACKAGE_ROOT / 'ArtSource/exports/arena/arena_manifest.json'
    manifest = json.loads(filename.read_text(encoding='utf-8'))
    if manifest['schema'] != 'iron-echo-arena-source/0.1':
        raise ValueError('Unsupported arena manifest')
    space = manifest['export_space']
    if (space['units'], space['axis_forward'], space['axis_up']) != ('meters', '-Y', 'Z'):
        raise ValueError('Unexpected arena export space')
    source = source_file(filename, manifest['fbx'])
    if hashlib.sha256(source.read_bytes()).hexdigest() != manifest['sha256']:
        raise ValueError('Arena FBX checksum differs from manifest')
    specs = manifest['material_specs']
    if set(specs) != set(manifest['material_names']) or not 0 < manifest['triangles'] < 80000:
        raise ValueError('Invalid arena materials or geometry budget')
    # Validate every material before the first asset mutation.
    for name, spec in specs.items():
        rgb = spec['color_srgb']
        if len(rgb) != 3 or not all(0 <= float(value) <= 1 for value in rgb):
            raise ValueError('Invalid sRGB palette for ' + name)
        if not all(0 <= float(spec[key]) <= 1 for key in ('metallic', 'roughness')):
            raise ValueError('Invalid PBR value for ' + name)
        if not 0 <= float(spec['glow']) <= 10:
            raise ValueError('Invalid glow for ' + name)
    exists = unreal.EditorAssetLibrary.does_asset_exist(DESTINATION)
    if args.apply and exists and not args.replace:
        raise RuntimeError('Arena already exists; use --apply --replace after writer handoff')
    if not hasattr(unreal, 'StaticMeshEditorSubsystem'):
        raise RuntimeError('StaticMeshEditorSubsystem unavailable')
    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    for name in ('get_num_uv_channels', 'get_number_verts', 'get_lod_count', 'get_simple_collision_count'):
        if not callable(getattr(subsystem, name, None)):
            raise RuntimeError('Missing static mesh API: ' + name)
    import_options = options()  # Preflight checks required option names even without --apply.
    report = {
        'status': 'preflight', 'source_sha256': manifest['sha256'],
        'destination': DESTINATION, 'existing_asset': exists, 'apply': args.apply,
        'source_triangles': manifest['triangles'], 'unreal_import_verified': False,
        'not_verified': ['Map placement/orientation', 'Actual lighting and camera',
                         'Gameplay collision', 'Packaged rendering', 'RTX 3050 FPS/VRAM'],
        'limitations': ['Single joined art mesh: no modular culling/lightmaps authored',
                       'Arena material instances use simple PBR; Blender noise is not transferred',
                       'Import is not atomic; inspect reports/assets after failure'],
    }
    if args.apply:
        with ArtLock():
            try:
                mesh, records = import_one(source, DESTINATION, import_options, args.replace)
                result = inspect(mesh, manifest, subsystem)
                slots = list(mesh.get_editor_property('static_materials'))
                for slot in slots:
                    name = str(slot.get_editor_property('material_slot_name'))
                    spec = specs[name]
                    material = surface_instance(name, spec['color_srgb'], spec['metallic'],
                                                spec['roughness'], spec['glow'])
                    slot.set_editor_property('material_interface', material)
                mesh.set_editor_property('static_materials', slots)
                save_asset(mesh)
                report.update(status='imported', unreal_import_verified=True, result=result, imports=records)
            except Exception:
                report.update(status='failed', error=traceback.format_exc())
                write_report('import_arena_source', report)
                raise
    write_report('import_arena_source', report)
    return report


if __name__ == '__main__':
    main([])
