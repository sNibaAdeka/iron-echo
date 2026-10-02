"""Build rigid, UV-preserving robot LODs from the verified source meshes.

The base FBX and source .blend are read-only. New LOD FBX/working scenes have
the same rest skeleton and material slot order. Unreal runtime is unverified.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def surface_tree(mesh):
    mesh.data.calc_loop_triangles()
    return BVHTree.FromPolygons([v.co.copy() for v in mesh.data.vertices],
        [tuple(t.vertices) for t in mesh.data.loop_triangles], all_triangles=True)


def sampled_deviation(source, reduced):
    """Symmetric sampled surface distance, not an exact Hausdorff bound."""
    values=[]
    for a,b in ((source,reduced),(reduced,source)):
        tree=surface_tree(b)
        points=[v.co.copy() for v in a.data.vertices]
        a.data.calc_loop_triangles()
        points += [sum((a.data.vertices[i].co for i in t.vertices),Vector())/3 for t in a.data.loop_triangles]
        stride=max(1,len(points)//2500)
        values.extend(tree.find_nearest(point)[3] for point in points[::stride])
    values.sort()
    return {"samples":len(values),"max_m":max(values),"p95_m":values[int(.95*(len(values)-1))],"mean_m":sum(values)/len(values)}


def stats(mesh):
    mesh.data.calc_loop_triangles()
    return {"vertices":len(mesh.data.vertices),"triangles":len(mesh.data.loop_triangles),
        "rigid_weights":all(len(v.groups)==1 and abs(v.groups[0].weight-1)<1e-6 for v in mesh.data.vertices),
        "uv_layers":len(mesh.data.uv_layers),"materials":[m.name for m in mesh.data.materials]}


def main():
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=Path(__file__).resolve().parents[2])
    package=parser.parse_args(argv).package.resolve()
    source_manifest=json.loads((package/'ArtSource/exports/art_manifest.json').read_text())
    root=package/'ArtSource/exports/lods'
    root.mkdir(parents=True,exist_ok=True)
    scenes=package/'ArtSource/Blender/LODs'
    scenes.mkdir(parents=True,exist_ok=True)
    report={"schema":"iron-echo-lod/0.1","contract_version":source_manifest['contract_version'],
        "blender_version":bpy.app.version_string,"generator":"Tools/Blender/build_lods.py",
        "source_base_sha256":source_manifest['files_sha256'],"unreal_verified":False,"robots":[],"files_sha256":{}}
    for spec in source_manifest['robots']:
        ident=spec['id']
        bpy.ops.wm.open_mainfile(filepath=str(package/'ArtSource/Blender'/f'{ident}.blend'))
        rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
        source=next(o for o in bpy.context.scene.objects if o.type=='MESH')
        rig.animation_data.action=None
        for bone in rig.pose.bones:
            bone.matrix_basis.identity()
        bpy.context.view_layer.update()
        original=stats(source)
        record={"id":ident,"lod0":original,"levels":[]}
        for index,ratio,limit in ((1,.60,.035),(2,.35,.07)):
            mesh=source.copy(); mesh.data=source.data.copy()
            mesh.name=f'SK_IE_{ident}_LOD{index}'
            bpy.context.collection.objects.link(mesh)
            for modifier in list(mesh.modifiers): mesh.modifiers.remove(modifier)
            bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True)
            bpy.context.view_layer.objects.active=mesh
            decimate=mesh.modifiers.new('Offline controlled reduction','DECIMATE')
            decimate.ratio=ratio;decimate.use_collapse_triangulate=True
            bpy.ops.object.modifier_apply(modifier=decimate.name)
            bpy.ops.object.shade_smooth_by_angle(angle=math.radians(45),keep_sharp_edges=True)
            normals=mesh.modifiers.new('Reduced panel normals','WEIGHTED_NORMAL')
            normals.keep_sharp=True
            bpy.ops.object.modifier_apply(modifier=normals.name)
            info=stats(mesh)
            deviation=sampled_deviation(source,mesh)
            if not info['rigid_weights'] or info['uv_layers']!=1 or info['materials']!=original['materials']:
                raise RuntimeError(f'{ident} LOD{index}: rigid skin/UV/slot contract changed')
            if deviation['max_m']>limit or info['triangles']>=original['triangles']:
                raise RuntimeError(f'{ident} LOD{index}: reduction exceeded sampled shape budget: {deviation}')
            skin=mesh.modifiers.new('IE_RigidSkin','ARMATURE');skin.object=rig
            rig.select_set(True)
            filename=f'{ident}_LOD{index}.fbx'
            bpy.ops.export_scene.fbx(filepath=str(root/filename),use_selection=True,
                object_types={'ARMATURE','MESH'},add_leaf_bones=False,axis_forward='-Y',axis_up='Z',
                apply_unit_scale=True,bake_anim=False,use_armature_deform_only=False,
                mesh_smooth_type='FACE',use_mesh_modifiers=True,path_mode='AUTO')
            record['levels'].append({"index":index,"fbx":filename,"requested_ratio":ratio,
                "actual_ratio":info['triangles']/original['triangles'],"stats":info,"sampled_deviation":deviation,
                "shape_budget_m":limit})
            report['files_sha256'][filename]=hashlib.sha256((root/filename).read_bytes()).hexdigest()
            mesh.hide_set(True);mesh.hide_render=True
        bpy.ops.wm.save_as_mainfile(filepath=str(scenes/f'{ident}_lods.blend'))
        report['robots'].append(record)
    (root/'lod_manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    (package/'Docs/Art/LOD_BUILD_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print('IRON_ECHO_LODS_COMPLETE',[(r['id'],[l['stats']['triangles'] for l in r['levels']]) for r in report['robots']])


if __name__=='__main__': main()
