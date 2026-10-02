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
    for robot in manifest['robots']:
        stats = robot['stats']
        if stats['triangles']>=25000 or stats['unweighted_vertices']!=0:
            raise RuntimeError('Reported robot budget/weights violated: '+robot['id'])
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
    print('PASS: plugin JSON and declared module files present; C++ compilation NOT performed')
    print('Scope: source package integrity only. Unreal/Windows runtime remains unverified.')


if __name__=='__main__':
    main()
