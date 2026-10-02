"""Real Blender renders of textured robots and identical-pose LOD comparisons."""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_robots import light, make_material, point_at, sample_pose
from build_surface_atlases import bind_atlases


def setup():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU'
    scene.cycles.samples=24;scene.cycles.use_denoising=True
    scene.render.resolution_x=1600;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
    scene.view_settings.view_transform='AgX'
    world=bpy.data.worlds.new('Neutral workshop');world.use_nodes=True
    world.node_tree.nodes['Background'].inputs['Color'].default_value=(.025,.033,.048,1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35;scene.world=world
    floor=make_material('Review floor','151D28',.25,.5)
    bpy.ops.mesh.primitive_plane_add(size=100,location=(0,0,-.012));bpy.context.object.data.materials.append(floor)
    light('Soft warm key',(-3,-4,5),760,(1,.83,.65),4,(0,0,1.2))
    light('Steel rim',(3,2,4),850,(.52,.75,1),3,(0,0,1.4))
    light('Fill',(1,-4,2.3),350,(.83,.90,1),3,(0,0,1.3))
    bpy.ops.object.camera_add(location=(2.8,-6,2.8))
    camera=bpy.context.object;camera.data.type='ORTHO';camera.data.ortho_scale=4.3
    point_at(camera,(0,0,1.05));scene.camera=camera
    return scene,camera


def append_robot(package,ident,level,position):
    if level==0:
        filename=package/'ArtSource/Blender/Lookdev'/f'{ident}_textured.blend'
        mesh_name='SK_IE_'+ident.capitalize()
    else:
        filename=package/'ArtSource/Blender/LODs'/f'{ident}_lods.blend'
        mesh_name=f'SK_IE_{ident}_LOD{level}'
    with bpy.data.libraries.load(str(filename),link=False) as (src,dst):
        dst.objects=['Armature',mesh_name]
    objects=[o for o in dst.objects if o]
    for o in objects:bpy.context.collection.objects.link(o)
    rig=next(o for o in objects if o.type=='ARMATURE')
    mesh=next(o for o in objects if o.type=='MESH')
    mesh.hide_render=False;mesh.hide_set(False)
    rig.animation_data_clear();rig.location=position
    sample_pose(rig,'Guard',0)
    images={}
    for key,label in (('base','BaseColor'),('orm','ORM'),('normal','Normal')):
        image=bpy.data.images.load(str(package/'ArtSource/Textures/robots'/ident/f'T_IE_{ident}_{label}.png'),check_existing=True)
        image.colorspace_settings.name='sRGB' if key=='base' else 'Non-Color';images[key]=image
    bind_atlases(mesh,images)
    return mesh,rig


def label(text,position):
    data=bpy.data.curves.new('LOD annotation','FONT');data.body=text;data.align_x='CENTER';data.size=.10
    obj=bpy.data.objects.new(text,data);bpy.context.collection.objects.link(obj)
    obj.location=position;obj.rotation_euler=(math.pi/2,0,0)
    material=bpy.data.materials.new('Annotation');material.use_nodes=True
    bsdf=material.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Base Color'].default_value=(.95,.95,.95,1)
    bsdf.inputs['Emission Color'].default_value=(.95,.95,.95,1);bsdf.inputs['Emission Strength'].default_value=.8
    obj.data.materials.append(material)


def render(scene,package,name):
    scene.render.image_settings.file_format='PNG';scene.render.filepath=str(package/'Previews'/name)
    bpy.ops.render.render(write_still=True)


def main():
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=Path(__file__).resolve().parents[2])
    package=parser.parse_args(argv).package.resolve()
    report={"scope":"Actual offline Blender renders, not Unreal screenshots","blender_version":bpy.app.version_string,"previews":[],"unreal_verified":False}
    scene,camera=setup()
    robots=[append_robot(package,'vanguard',0,(-.67,0,0)),append_robot(package,'bulwark',0,(.67,.06,0))]
    deps=bpy.context.evaluated_depsgraph_get();points=[]
    for mesh,rig in robots:
        evaluated=mesh.evaluated_get(deps);geometry=evaluated.to_mesh()
        points += [world_to_camera_view(scene,camera,mesh.matrix_world@v.co) for v in geometry.vertices]
        evaluated.to_mesh_clear()
    bounds={"x":[min(p.x for p in points),max(p.x for p in points)],"y":[min(p.y for p in points),max(p.y for p in points)]}
    if not all(.02<value<.98 for values in bounds.values() for value in values):
        raise RuntimeError('Studio robot framing outside safe margins: '+str(bounds))
    render(scene,package,'robots-textured-studio.png')
    report['previews'].append({"file":"Previews/robots-textured-studio.png","geometry_screen_bounds":bounds})
    for ident in ('vanguard','bulwark'):
        scene,camera=setup();camera.location=(0,-8,2.6);point_at(camera,(0,0,1.0));camera.data.ortho_scale=4.5
        for level,x,count in ((0,-1.30,9432),(1,0,5658),(2,1.30,3300)):
            append_robot(package,ident,level,(x,0,0))
            label(f'LOD{level} / {count} tris',(x,-.85,.03))
        filename=f'{ident}-lod-comparison.png';render(scene,package,filename)
        report['previews'].append({"file":"Previews/"+filename,"pose":"Guard identical on all levels"})
    (package/'Docs/Art/SURFACE_RENDER_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print('IRON_ECHO_SURFACE_RENDER_COMPLETE',len(report['previews']))


if __name__=='__main__':main()
