"""Portable source checks; no Blender, Unreal, network or third-party modules.

This checks repository integrity, not game runtime or target hardware performance.
"""
import ast
import hashlib
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[2]
    scripts = [p for p in (root/'Tools').rglob('*.py') if '__pycache__' not in p.parts]
    for path in scripts:
        ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
    export = root/'ArtSource/exports'
    manifest = json.loads((export/'art_manifest.json').read_text(encoding='utf-8'))
    if len(manifest['robots'])!=2 or len(manifest['animations'])!=8:
        raise RuntimeError('Expected two robot exports and eight animation exports')
    hashes = manifest['files_sha256']
    for relative, expected in hashes.items():
        path = (export/relative).resolve()
        path.relative_to(export.resolve())
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError('FBX checksum mismatch: '+relative)
    extra_fbx=0
    texture_count=0
    for quality_root, filename, kind in ((export/'lods','lod_manifest.json','lod'),(root/'ArtSource/Textures/robots','texture_manifest.json','texture')):
        quality=json.loads((quality_root/filename).read_text(encoding='utf-8'))
        if quality['source_base_sha256']!=hashes or quality['contract_version']!=manifest['contract_version']:
            raise RuntimeError('Quality package source snapshot differs from the base: '+kind)
        for relative,expected in quality['files_sha256'].items():
            path=(quality_root/relative).resolve();path.relative_to(quality_root.resolve())
            if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
                raise RuntimeError('Quality checksum mismatch: '+relative)
            if kind=='lod':extra_fbx+=1
            else:texture_count+=1
    for robot in manifest['robots']:
        stats = robot['stats']
        if stats['triangles']>=25000 or stats['unweighted_vertices']!=0:
            raise RuntimeError('Reported robot budget/weights violated: '+robot['id'])
    arena_root=export/'arena'
    arena=json.loads((arena_root/'arena_manifest.json').read_text(encoding='utf-8'))
    arena_fbx=(arena_root/arena['fbx']).resolve();arena_fbx.relative_to(arena_root.resolve())
    arena_blend=(root/arena['blend']).resolve();arena_blend.relative_to(root.resolve())
    for path,expected in ((arena_fbx,arena['sha256']),(arena_blend,arena['blend_sha256'])):
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise RuntimeError('Arena source checksum mismatch: '+str(path.relative_to(root)))
    if arena['robot_source_sha256']!=hashes or not 0<arena['triangles']<80000:
        raise RuntimeError('Arena geometry budget/source robot snapshot differs')
    if len(arena['material_names'])!=8 or set(arena['material_names'])!=set(arena['material_specs']):
        raise RuntimeError('Arena material specification differs from slots')
    for filename in arena['preview_files']:
        path=(root/filename).resolve();path.relative_to(root.resolve())
        if not path.is_file():raise RuntimeError('Arena preview missing: '+filename)
    for name in ('AGENTS.md','CLAUDE.md','PROJECT_STATE.md','WINDOWS_START.md'):
        if not (root/name).is_file():
            raise RuntimeError('Continuation document missing: '+name)
    plugin = root/'IntegrationDraft/IronEchoVisuals'
    descriptor = json.loads((plugin/'IronEchoVisuals.uplugin').read_text(encoding='utf-8'))
    for module in descriptor['Modules']:
        name = module['Name']
        if not (plugin/'Source'/name/(name+'.Build.cs')).is_file():
            raise RuntimeError('Declared plugin module rules missing: '+name)
    if not (plugin/'Source/IronEchoVisuals/Public/IETheme.h').is_file():
        raise RuntimeError('Generated native theme missing')
    print('PASS: {} Python files parsed; {} FBX hashes verified; continuation documents present'.format(len(scripts),len(hashes)))
    print('PASS: {} additional LOD FBX and {} texture hashes/source snapshots verified'.format(extra_fbx,texture_count))
    print('PASS: arena FBX/.blend hashes, geometry budget, material names and robot snapshot verified')
    print('PASS: plugin JSON and declared module files present; C++ compilation NOT performed')
    print('Scope: source package integrity only. Unreal/Windows runtime remains unverified.')


if __name__=='__main__':
    main()
