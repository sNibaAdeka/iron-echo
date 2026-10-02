"""Bake original paint/steel lookdev to portable robot PBR atlases.

Reads the verified source .blend without modifying it or the base FBX. Cycles
bakes BaseColor, packed ORM (AO=1 deliberately) and OpenGL tangent normals.
Unreal should import the normal texture with Flip Green Channel enabled.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy


def linear(hex_color):
    channels=[int(hex_color[i:i+2],16)/255 for i in (0,2,4)]
    return tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in channels)+(1,)


def build_shader(material, spec, slot):
    material.use_nodes=True
    tree=material.node_tree;tree.nodes.clear()
    n=tree.nodes;link=tree.links.new
    output=n.new('ShaderNodeOutputMaterial')
    bsdf=n.new('ShaderNodeBsdfPrincipled');bsdf.name='IE_Surface'
    link(bsdf.outputs['BSDF'],output.inputs['Surface'])
    coord=n.new('ShaderNodeTexCoord')
    macro=n.new('ShaderNodeTexNoise');macro.inputs['Scale'].default_value=8
    macro.inputs['Detail'].default_value=2
    link(coord.outputs['Object'],macro.inputs['Vector'])
    micro=n.new('ShaderNodeTexNoise');micro.inputs['Scale'].default_value=160
    micro.inputs['Detail'].default_value=2
    link(coord.outputs['Object'],micro.inputs['Vector'])
    bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.13
    bump.inputs['Distance'].default_value=.0011
    link(micro.outputs['Fac'],bump.inputs['Height'])
    link(bump.outputs['Normal'],bsdf.inputs['Normal'])
    colors={'Gunmetal':('38414A',.93,.38),'Armor':(spec['armor_srgb'],0.,.49),
        'Brass':('AD915C',.92,.42),'Rubber':('18212B',0.,.84),'Signal':(spec['signal_srgb'],.05,.3)}
    color,metallic,roughness=colors[slot]
    tone=n.new('ShaderNodeMixRGB');tone.blend_type='MULTIPLY'
    tone.inputs[0].default_value=.13;tone.inputs[1].default_value=linear(color)
    link(macro.outputs['Fac'],tone.inputs[2])
    color_out=tone.outputs['Color']
    rough=n.new('ShaderNodeMath');rough.operation='MULTIPLY_ADD'
    link(micro.outputs['Fac'],rough.inputs[0]);rough.inputs[1].default_value=.07
    rough.inputs[2].default_value=roughness-.035
    metal=n.new('ShaderNodeValue');metal.outputs[0].default_value=metallic
    metal_out=metal.outputs[0]
    if slot=='Armor':
        geometry=n.new('ShaderNodeNewGeometry')
        wear=n.new('ShaderNodeValToRGB')
        wear.color_ramp.elements[0].position=.52
        wear.color_ramp.elements[1].position=.61
        link(geometry.outputs['Pointiness'],wear.inputs['Fac'])
        strength=n.new('ShaderNodeMath');strength.operation='MULTIPLY'
        link(wear.outputs['Color'],strength.inputs[0]);strength.inputs[1].default_value=.25
        edge=n.new('ShaderNodeMixRGB');edge.blend_type='MIX'
        link(strength.outputs[0],edge.inputs[0]);link(color_out,edge.inputs[1])
        edge.inputs[2].default_value=linear('58616A');color_out=edge.outputs['Color']
        exposed=n.new('ShaderNodeMath');exposed.operation='MULTIPLY'
        exposed.inputs[1].default_value=.93;link(strength.outputs[0],exposed.inputs[0])
        metal_out=exposed.outputs[0]
    link(color_out,bsdf.inputs['Base Color'])
    link(rough.outputs[0],bsdf.inputs['Roughness'])
    link(metal_out,bsdf.inputs['Metallic'])
    if slot=='Signal':
        link(color_out,bsdf.inputs['Emission Color']);bsdf.inputs['Emission Strength'].default_value=1.5
    packed=n.new('ShaderNodeCombineColor');packed.mode='RGB'
    packed.inputs['Red'].default_value=1.
    link(rough.outputs[0],packed.inputs['Green']);link(metal_out,packed.inputs['Blue'])
    return {"material":material,"output":output,"bsdf":bsdf,"base":color_out,"orm":packed.outputs[0]}


def bake(mesh, shaders, name, mode, folder, resolution):
    image=bpy.data.images.new(name,width=resolution,height=resolution,alpha=False,float_buffer=False)
    image.colorspace_settings.name='sRGB' if mode=='base' else 'Non-Color'
    targets=[]
    for entry in shaders:
        tree=entry['material'].node_tree
        target=tree.nodes.new('ShaderNodeTexImage');target.image=image;target.name='IE_BakeTarget'
        tree.nodes.active=target;targets.append((tree,target))
        if mode=='normal':
            tree.links.new(entry['bsdf'].outputs['BSDF'],entry['output'].inputs['Surface'])
        else:
            emission=tree.nodes.new('ShaderNodeEmission');emission.name='IE_BakeEmission'
            tree.links.new(entry[mode],emission.inputs['Color'])
            tree.links.new(emission.outputs[0],entry['output'].inputs['Surface'])
    bpy.context.view_layer.objects.active=mesh
    bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True)
    bpy.ops.object.bake(type='NORMAL' if mode=='normal' else 'EMIT',margin=8,margin_type='EXTEND',
        use_clear=True,use_selected_to_active=False,normal_space='TANGENT',normal_g='POS_Y')
    filename=folder/(name+'.png');image.filepath_raw=str(filename);image.file_format='PNG';image.save()
    for entry in shaders:
        tree=entry['material'].node_tree
        tree.links.new(entry['bsdf'].outputs['BSDF'],entry['output'].inputs['Surface'])
        for node in list(tree.nodes):
            if node.name in ('IE_BakeTarget','IE_BakeEmission'):tree.nodes.remove(node)
    print('BAKED',name,flush=True)
    # Use actual external PNG data blocks: generated images are not a portable
    # substitute for reopening the saved textures after a fresh Blender launch.
    loaded=bpy.data.images.load(str(filename),check_existing=False)
    loaded.colorspace_settings.name='sRGB' if mode=='base' else 'Non-Color'
    bpy.data.images.remove(image)
    loaded.name=name
    return loaded,filename


def bind_atlases(mesh,images):
    for material in mesh.data.materials:
        slot=material.name.split('.')[0]
        tree=material.node_tree;tree.nodes.clear();n=tree.nodes;link=tree.links.new
        output=n.new('ShaderNodeOutputMaterial');bsdf=n.new('ShaderNodeBsdfPrincipled')
        link(bsdf.outputs['BSDF'],output.inputs['Surface'])
        textures={}
        for semantic,image in images.items():
            textures[semantic]=n.new('ShaderNodeTexImage');textures[semantic].image=image
        link(textures['base'].outputs['Color'],bsdf.inputs['Base Color'])
        split=n.new('ShaderNodeSeparateColor');split.mode='RGB'
        link(textures['orm'].outputs['Color'],split.inputs['Color'])
        link(split.outputs['Green'],bsdf.inputs['Roughness']);link(split.outputs['Blue'],bsdf.inputs['Metallic'])
        normal=n.new('ShaderNodeNormalMap');normal.space='TANGENT'
        link(textures['normal'].outputs['Color'],normal.inputs['Color']);link(normal.outputs['Normal'],bsdf.inputs['Normal'])
        if slot=='Signal':
            link(textures['base'].outputs['Color'],bsdf.inputs['Emission Color']);bsdf.inputs['Emission Strength'].default_value=1.5


def main():
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--resolution',type=int,choices=(512,1024,2048),default=2048)
    args=parser.parse_args(argv);package=args.package.resolve()
    manifest=json.loads((package/'ArtSource/exports/art_manifest.json').read_text())
    root=package/'ArtSource/Textures/robots';root.mkdir(parents=True,exist_ok=True)
    scenes=package/'ArtSource/Blender/Lookdev';scenes.mkdir(parents=True,exist_ok=True)
    report={"schema":"iron-echo-pbr-atlas/0.1","generator":"Tools/Blender/build_surface_atlases.py",
        "contract_version":manifest['contract_version'],"blender_version":bpy.app.version_string,
        "resolution":args.resolution,"source_base_sha256":manifest['files_sha256'],"robots":[],"files_sha256":{},
        "orm_channels":{"R":"AO constant 1 (no pose-dependent AO baked)","G":"roughness","B":"metallic"},
        "normal_space":"tangent OpenGL +Y; Unreal flip_green_channel=true",
        "unreal_verified":False,"limitations":["Pointiness-based wear is static cosmetic lookdev, not gameplay damage", "UV/tangent consistency on reduced LODs requires Unreal visual checks", "Textures are original procedural outputs; no external assets"]}
    for spec in manifest['robots']:
        ident=spec['id'];folder=root/ident;folder.mkdir(parents=True,exist_ok=True)
        bpy.ops.wm.open_mainfile(filepath=str(package/'ArtSource/Blender'/f'{ident}.blend'))
        rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
        mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
        rig.animation_data.action=None
        for bone in rig.pose.bones:bone.matrix_basis.identity()
        bpy.context.view_layer.update()
        scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=8
        shaders=[build_shader(material,spec,material.name) for material in mesh.data.materials]
        images={};textures=[]
        for semantic,label in (('base','BaseColor'),('orm','ORM'),('normal','Normal')):
            image,filename=bake(mesh,shaders,f'T_IE_{ident}_{label}',semantic,folder,args.resolution)
            images[semantic]=image
            relative=str(filename.relative_to(root))
            report['files_sha256'][relative]=hashlib.sha256(filename.read_bytes()).hexdigest()
            textures.append({"semantic":semantic,"file":relative,"srgb":semantic=='base',"flip_green":semantic=='normal'})
            image.filepath='//../../Textures/robots/'+relative
        bind_atlases(mesh,images)
        idle=bpy.data.actions.get('Idle');rig.animation_data.action=idle
        rig.animation_data.action_slot=idle.slots[0];scene.frame_set(1)
        bpy.ops.wm.save_as_mainfile(filepath=str(scenes/f'{ident}_textured.blend'),relative_remap=False)
        report['robots'].append({"id":ident,"textures":textures,"slots":manifest['materials']})
    (root/'texture_manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    (package/'Docs/Art/TEXTURE_BUILD_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print('IRON_ECHO_ATLASES_COMPLETE',args.resolution,flush=True)


if __name__=='__main__':main()
