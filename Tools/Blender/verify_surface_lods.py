"""Actual Blender FBX round trips and reopened texture/UV checks for art v0.3."""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Quaternion


def main():
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=Path(__file__).resolve().parents[2])
    package=parser.parse_args(argv).package.resolve()
    base=json.loads((package/'ArtSource/exports/art_manifest.json').read_text())
    lodroot=package/'ArtSource/exports/lods';texroot=package/'ArtSource/Textures/robots'
    lods=json.loads((lodroot/'lod_manifest.json').read_text())
    textures=json.loads((texroot/'texture_manifest.json').read_text())
    checks=[]
    def check(name,passed,evidence):
        checks.append({"name":name,"passed":bool(passed),"evidence":evidence})
    for root,manifest,kind in ((lodroot,lods,'lod'),(texroot,textures,'texture')):
        for relative,expected in manifest['files_sha256'].items():
            path=(root/relative).resolve();path.relative_to(root.resolve())
            check(kind+'_hash_'+relative,hashlib.sha256(path.read_bytes()).hexdigest()==expected,relative)
    # No old base asset or animation should have been replaced by lookdev/LOD work.
    for relative,expected in base['files_sha256'].items():
        check('base_unchanged_'+relative,hashlib.sha256((package/'ArtSource/exports'/relative).read_bytes()).hexdigest()==expected,relative)
    for robot in lods['robots']:
        ident=robot['id']
        bpy.ops.wm.open_mainfile(filepath=str(package/'ArtSource/Blender'/f'{ident}.blend'))
        source_rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
        rest_heads={b.name:b.head_local.copy() for b in source_rig.data.bones}
        for level in robot['levels']:
            name=f'{ident}_LOD{level["index"]}'
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.import_scene.fbx(filepath=str(lodroot/level['fbx']))
            rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
            mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
            mesh.data.calc_loop_triangles()
            check(name+'_triangles',len(mesh.data.loop_triangles)==level['stats']['triangles'],len(mesh.data.loop_triangles))
            check(name+'_bones',set(rig.data.bones.keys())==set(base['bones']),list(rig.data.bones.keys()))
            errors={b.name:(b.head_local-rest_heads[b.name]).length for b in rig.data.bones if b.name in rest_heads}
            check(name+'_rest_joint_positions',max(errors.values())<.001,errors)
            check(name+'_rigid_weights',all(len(v.groups)==1 and abs(v.groups[0].weight-1)<1e-6 for v in mesh.data.vertices),len(mesh.data.vertices))
            check(name+'_slots',[m.name for m in mesh.data.materials]==base['materials'],[m.name for m in mesh.data.materials])
            check(name+'_uv',len(mesh.data.uv_layers)==1,len(mesh.data.uv_layers))
            check(name+'_armature',any(m.type=='ARMATURE' and m.object==rig for m in mesh.modifiers),[m.type for m in mesh.modifiers])
            groups={}
            for v in mesh.data.vertices:
                if v.groups: groups.setdefault(v.groups[0].group,[]).append(v.index)
            pairs=[(indices[0],indices[-1]) for indices in groups.values() if len(indices)>1]
            deps=bpy.context.evaluated_depsgraph_get()
            before=mesh.evaluated_get(deps).to_mesh()
            distances=[(before.vertices[a].co-before.vertices[b].co).length for a,b in pairs]
            mesh.evaluated_get(deps).to_mesh_clear()
            bone=rig.pose.bones['lowerarm_l'];bone.rotation_mode='QUATERNION';bone.rotation_quaternion=Quaternion((1,0,0),.65)
            bpy.context.view_layer.update()
            after=mesh.evaluated_get(deps).to_mesh()
            errors=[abs((after.vertices[a].co-after.vertices[b].co).length-d) for (a,b),d in zip(pairs,distances)]
            mesh.evaluated_get(deps).to_mesh_clear()
            check(name+'_rigid_panel_motion',max(errors)<1e-5,{"bone_groups_tested":len(pairs),"max_distance_error_m":max(errors)})
    for robot in textures['robots']:
        ident=robot['id']
        bpy.ops.wm.open_mainfile(filepath=str(package/'ArtSource/Blender/Lookdev'/f'{ident}_textured.blend'))
        mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
        images={}
        for spec in robot['textures']:
            expected=(texroot/spec['file']).resolve()
            image=next((i for i in bpy.data.images if i.source=='FILE' and Path(bpy.path.abspath(i.filepath)).resolve()==expected),None)
            name=ident+'_'+spec['semantic']
            check(name+'_portable_file_reference',image is not None and expected.is_file(),str(expected.relative_to(package)))
            if image is None:continue
            image.reload()
            images[spec['semantic']]=image
            check(name+'_size',list(image.size)==[textures['resolution']]*2,list(image.size))
            check(name+'_colorspace',image.colorspace_settings.name==('sRGB' if spec['srgb'] else 'Non-Color'),image.colorspace_settings.name)
            check(name+'_pixels',image.has_data and len(image.pixels)>0,len(image.pixels))
        if len(images)!=3:continue
        mesh.data.calc_loop_triangles();uv=mesh.data.uv_layers.active.data
        width=textures['resolution'];orm=list(images['orm'].pixels);normal=list(images['normal'].pixels)
        covered=0;normal_good=0;sampled=0;slot_metals={}
        for tri in list(mesh.data.loop_triangles)[::9]:
            u=sum(uv[i].uv.x for i in tri.loops)/3;v=sum(uv[i].uv.y for i in tri.loops)/3
            x=min(width-1,max(0,int(u*width)));y=min(width-1,max(0,int(v*width)));index=(y*width+x)*4
            ao,rough,metal=orm[index:index+3];nr,ng,nb=normal[index:index+3]
            sampled+=1
            if ao>.98 and 0<=rough<=1 and 0<=metal<=1: covered+=1
            length=math.sqrt(sum((2*c-1)**2 for c in (nr,ng,nb)))
            if .8<length<1.2 and nb>.45:normal_good+=1
            slot_metals.setdefault(mesh.data.materials[tri.material_index].name,[]).append(metal)
        check(ident+'_uv_surface_coverage',covered/sampled>.985,{"covered":covered,"samples":sampled})
        check(ident+'_tangent_normal_length',normal_good/sampled>.985,{"valid":normal_good,"samples":sampled})
        check(ident+'_paint_metallic_budget',max(slot_metals['Armor'])<.27,{"range":[min(slot_metals['Armor']),max(slot_metals['Armor'])]})
        check(ident+'_steel_metallic',min(slot_metals['Gunmetal'])>.88,{"range":[min(slot_metals['Gunmetal']),max(slot_metals['Gunmetal'])]})
    report={"scope":"Blender actual FBX round trips and reopened external atlas/UV data; not UE runtime",
        "blender_version":bpy.app.version_string,"checks":checks,"passed":sum(c['passed'] for c in checks),"total":len(checks),"unreal_verified":False,"windows_verified":False}
    (package/'Docs/Art/SURFACE_LOD_QA_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    failed=[c['name'] for c in checks if not c['passed']]
    print('IRON_ECHO_SURFACE_LOD_QA',report['passed'],'/',report['total'],'failed:',failed)
    if failed:raise RuntimeError('Art QA failed: '+', '.join(failed))


if __name__=='__main__':main()
