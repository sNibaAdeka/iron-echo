"""Original compact industrial arena, static FBX and real shoulder-camera render.

This is offline art/lookdev, not a collision/gameplay level or UE screenshot.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_robots import light, make_material, point_at, sample_pose
from render_surface_review import append_robot

PARTS=[]
SHOULDER_CAMERA={"location_m":[-3.5,-1.4,2.8],"target_m":[1,0,1.55],"lens_mm":23.5,"sensor_width_mm":36}
OVERVIEW_CAMERA={"location_m":[-4.3,-4.3,3.5],"target_m":[0,0,1.05],"lens_mm":24,"sensor_width_mm":36}
MATERIALS={
    'Arena_Steel':('303D48',.88,.42,0),
    'Arena_Concrete':('343C44',.05,.84,0),
    'Arena_Deck':('18232F',.2,.57,0),
    'Arena_Trim':('B07B38',.1,.55,0),
    'Arena_Rubber':('101820',0,.84,0),
    'Arena_Wall':('222C35',.15,.7,0),
    'Arena_Lamp':('F2C37B',0,.5,2),
    'Arena_ColdLamp':('73BAC9',0,.5,2),
}


def configure_camera(camera,spec):
    camera.location=spec['location_m'];camera.data.lens=spec['lens_mm']
    camera.data.sensor_width=spec['sensor_width_mm'];camera.data.sensor_fit='HORIZONTAL'
    point_at(camera,spec['target_m'])


def finish(obj,material,bevel):
    obj.data.materials.append(material)
    bpy.context.view_layer.objects.active=obj
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if bevel:
        modifier=obj.modifiers.new('Industrial chamfer','BEVEL')
        # A bevel exactly half a thin panel's depth collapses its centre faces.
        modifier.width=min(bevel,.45*min(obj.dimensions));modifier.segments=1
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    PARTS.append(obj)
    return obj


def box(name,position,size,material,bevel=.025):
    bpy.ops.mesh.primitive_cube_add(size=1,location=position)
    obj=bpy.context.object;obj.name=name;obj.scale=size
    return finish(obj,material,bevel)


def tube(name,start,end,radius,material):
    a,b=Vector(start),Vector(end)
    bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=radius,depth=(b-a).length,location=(a+b)/2)
    obj=bpy.context.object;obj.name=name;obj.rotation_mode='QUATERNION';obj.rotation_quaternion=(b-a).to_track_quat('Z','Y')
    return finish(obj,material,0)


def main():
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=Path(__file__).resolve().parents[2])
    package=parser.parse_args(argv).package.resolve()
    PARTS.clear()
    for path in ('ArtSource/Blender/Arena','ArtSource/exports/arena'):(package/path).mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    materials={name:make_material(name,*spec[:3],bool(spec[3])) for name,spec in MATERIALS.items()}
    steel,floor,deck,trim,rubber,panel,warm,cold=[materials['Arena_'+name] for name in ('Steel','Concrete','Deck','Trim','Rubber','Wall','Lamp','ColdLamp')]
    box('Workshop floor',(0,0,-.31),(12,12,.2),floor)
    box('Ring plinth',(0,0,-.15),(6.8,6.8,.28),steel)
    box('Ring canvas',(0,0,-.014),(6.4,6.4,.028),deck,.012)
    for axis in (0,1):
        for sign in (-1,1):
            position=[0,0,.003];position[axis]=sign*2.96
            size=[5.94,.04,.009] if axis==1 else [.04,5.94,.009]
            box('Safe ring edge',position,size,trim,.002)
    for x in (-3.24,3.24):
        for y in (-3.24,3.24):
            box('Corner post',(x,y,.68),(.16,.16,1.7),steel,.018)
            box('Corner padding',(x*.96,y*.96,.86),(.22,.22,.76),rubber,.035)
    for z in (.38,.72,1.06):
        for sign in (-1,1):
            tube('Ring cable',(sign*3.24,-3.24,z),(sign*3.24,3.24,z),.016,rubber)
            tube('Ring cable',(-3.24,sign*3.24,z),(3.24,sign*3.24,z),.016,rubber)
    # Large, readable structural forms: no crowd, particle fog or unique 4K props.
    box('Back wall',(0,5.3,2.2),(11,.18,5),panel)
    for x in (-5.3,5.3):box('Side wall',(x,0,2.2),(.18,10.6,5),panel)
    for x in (-4.8,-2.4,2.4,4.8):
        for y in (-4.6,4.6):
            box('Column',(x,y,2),(.22,.3,4.6),steel)
            box('Column foot',(x,y,-.10),(.42,.48,.24),trim)
            box('Column brace',(x,y,3.95),(.44,.46,.13),steel)
    for x in (-4.7,4.7):
        tube('Overhead service pipe',(x,-5,3.9),(x,5,3.9),.065,steel)
        for y in (-3,0,3):tube('Pipe drop',(x,y,3.9),(x,y,2.7),.038,steel)
    for y in (-4.6,0,4.6):
        box('Roof beam',(0,y,4.35),(10.7,.16,.20),steel)
    box('Loading gate',(0,5.16,1.55),(3.4,.05,3.1),steel,.01)
    for z in [.25+i*.25 for i in range(12)]:box('Gate slat',(0,5.11,z),(3.38,.025,.035),panel,.003)
    for x in (-4.35,4.35):
        box('Maintenance cabinet',(x,3.5,.75),(.8,.55,1.7),steel)
        box('Cabinet door',(x,3.20,.75),(.66,.05,1.45),panel)
        box('Cabinet status',(x,3.16,1.18),(.18,.02,.03),warm if x<0 else cold,.002)
    for y in (-4.5,4.5):
        for x in (-1.8,1.8):
            box('Wall fixture',(x,y,2.8),(1.1,.18,.16),steel)
            box('Lamp strip',(x,y*.98,2.78),(.94,.04,.07),warm if y>0 else cold,.01)
    for i in range(3):box('Service steps',(0,-3.65-i*.22,-.20-i*.055),(1.4,.27,.10),steel,.014)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in PARTS:obj.select_set(True)
    bpy.context.view_layer.objects.active=PARTS[0];bpy.ops.object.join()
    arena=bpy.context.object;arena.name='SM_IE_IndustrialArena'
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.01)
    bpy.ops.object.mode_set(mode='OBJECT');arena.data.calc_loop_triangles()
    triangles=len(arena.data.loop_triangles)
    if triangles>80000:raise RuntimeError('Arena triangle budget exceeded')
    if any(tri.area<=1e-10 for tri in arena.data.loop_triangles):
        raise RuntimeError('Arena has degenerate source triangles; repair the generator before export')
    filename=package/'ArtSource/exports/arena/industrial_arena.fbx'
    bpy.ops.export_scene.fbx(filepath=str(filename),use_selection=True,object_types={'MESH'},
        axis_forward='-Y',axis_up='Z',apply_unit_scale=True,bake_anim=False,mesh_smooth_type='FACE',path_mode='AUTO')
    actors=[append_robot(package,'vanguard',0,(-1,0,0)),append_robot(package,'bulwark',0,(1,0,0))]
    actors[0][1].rotation_euler.z=math.pi/2;actors[1][1].rotation_euler.z=-math.pi/2
    light('Main ring light',(0,0,4.2),1000,(.96,.94,.89),4,(0,0,0))
    light('Warm rim',(1,3.5,3.1),750,(1,.61,.26),2,(0,0,1.2))
    light('Cool fill',(-2,-3.5,2.7),550,(.30,.66,1),3,(0,0,1.2))
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=32;scene.cycles.use_denoising=True
    scene.render.resolution_x=1600;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    world=bpy.data.worlds.new('Industrial night');world.use_nodes=True
    world.node_tree.nodes['Background'].inputs['Color'].default_value=(.013,.018,.027,1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value=.2;scene.world=world
    scene.view_settings.view_transform='AgX';scene.render.image_settings.file_format='PNG'
    bpy.ops.object.camera_add();camera=bpy.context.object;camera.name='IE_ArtReviewCamera'
    configure_camera(camera,SHOULDER_CAMERA);scene.camera=camera
    scene.render.filepath=str(package/'Previews/arena-shoulder.png');bpy.ops.render.render(write_still=True)
    sample_pose(actors[1][1],'Straight_L',.4)
    scene.render.filepath=str(package/'Previews/arena-straight-left.png');bpy.ops.render.render(write_still=True)
    sample_pose(actors[1][1],'Guard',0)
    configure_camera(camera,OVERVIEW_CAMERA)
    scene.render.filepath=str(package/'Previews/arena-overview.png');bpy.ops.render.render(write_still=True)
    # Save portable image references relative to the Arena scene location.
    for image in bpy.data.images:
        if image.source=='FILE' and image.filepath.endswith('.png'):
            path=Path(bpy.path.abspath(image.filepath));ident=path.parent.name
            if ident in ('vanguard','bulwark'):image.filepath='//../../Textures/robots/'+ident+'/'+path.name
    scene_path=package/'ArtSource/Blender/Arena/industrial_arena.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(scene_path),relative_remap=False)
    slots=[]
    for material in arena.data.materials:
        if material.name not in slots:slots.append(material.name)
    def rgb(hex_value):return [int(hex_value[i:i+2],16)/255 for i in (0,2,4)]
    report={"schema":"iron-echo-arena-source/0.1","generator":"Tools/Blender/build_arena_review.py",
        "blender_version":bpy.app.version_string,"fbx":"industrial_arena.fbx","sha256":hashlib.sha256(filename.read_bytes()).hexdigest(),
        "blend":"ArtSource/Blender/Arena/industrial_arena.blend","blend_sha256":hashlib.sha256(scene_path.read_bytes()).hexdigest(),
        "triangles":triangles,"vertices":len(arena.data.vertices),"uv_layers":len(arena.data.uv_layers),"material_names":slots,
        "dimensions_m":list(arena.dimensions),
        "material_specs":{name:{"color_srgb":rgb(spec[0]),"metallic":spec[1],"roughness":spec[2],"glow":spec[3]} for name,spec in MATERIALS.items()},
        "robot_source_sha256":json.loads((package/'ArtSource/exports/art_manifest.json').read_text())['files_sha256'],
        "export_space":{"units":"meters","axis_forward":"-Y","axis_up":"Z","desired_ue_forward":"+X"},
        "camera_preview":SHOULDER_CAMERA,"overview_camera":OVERVIEW_CAMERA,
        "preview_files":["Previews/arena-shoulder.png","Previews/arena-straight-left.png","Previews/arena-overview.png"],
        "fighters_blender_space":[{"id":"vanguard","location_m":[-1,0,0],"yaw_degrees":90},{"id":"bulwark","location_m":[1,0,0],"yaw_degrees":-90}],
        "unreal_verified":False,"scope":"One static art mesh, original materials and offline lighting/camera previews",
        "limitations":["No gameplay/collision authored", "Room joined for art preview: not a final modular streaming setup", "Cycles light cost is not UE light cost", "Camera framing requires actual robot movement/occlusion checks", "Blender noise is not automatically transferred to Unreal"]}
    (package/'ArtSource/exports/arena/arena_manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    (package/'Docs/Art/ARENA_SOURCE_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print('IRON_ECHO_ARENA_COMPLETE',triangles)


if __name__=='__main__':main()
