"""Prepared UE 5.6 editor upgrade: PBR atlases and existing-mesh LOD1/2.

Default is preflight. main(['--apply']) performs the agreed art upgrade under
the existing writer lock. No project, gameplay, skeleton or map is authored.
This script has not been executed in Unreal in the preparation environment.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
import unreal
from art_common import ART_ROOT, PACKAGE_ROOT, ArtLock, art_path, create_asset, linear_rgb, load_manifest, mesh_path, require_clean_editor, save_asset, write_report


def source(root,relative,extension):
    path=(root/relative).resolve();path.relative_to(root.resolve())
    if path.suffix.lower()!=extension or not path.is_file():raise RuntimeError('Missing source: '+str(path))
    return path


def load_quality():
    base,_=load_manifest()
    lodroot=PACKAGE_ROOT/'ArtSource/exports/lods';texroot=PACKAGE_ROOT/'ArtSource/Textures/robots'
    lod=json.loads((lodroot/'lod_manifest.json').read_text())
    tex=json.loads((texroot/'texture_manifest.json').read_text())
    for root,manifest,ext in ((lodroot,lod,'.fbx'),(texroot,tex,'.png')):
        if manifest['contract_version']!=base['contract_version'] or manifest['source_base_sha256']!=base['files_sha256']:
            raise RuntimeError('Quality sources do not match the current base skeleton/export revision')
        for relative,digest in manifest['files_sha256'].items():
            if hashlib.sha256(source(root,relative,ext).read_bytes()).hexdigest()!=digest:
                raise RuntimeError('Quality source checksum mismatch: '+relative)
    for relative,digest in base['files_sha256'].items():
        if hashlib.sha256((PACKAGE_ROOT/'ArtSource/exports'/relative).read_bytes()).hexdigest()!=digest:
            raise RuntimeError('Base export changed after the quality bake: '+relative)
    return lodroot,texroot,lod,tex


def texture(spec,root,replace):
    filename=source(root,spec['file'],'.png')
    destination=art_path(ART_ROOT+'/Textures/Robots/'+filename.parent.name+'/'+filename.stem)
    compression={'base':unreal.TextureCompressionSettings.TC_DEFAULT,'orm':unreal.TextureCompressionSettings.TC_MASKS,'normal':unreal.TextureCompressionSettings.TC_NORMALMAP}
    if unreal.EditorAssetLibrary.does_asset_exist(destination):
        asset=unreal.EditorAssetLibrary.load_asset(destination)
        if not isinstance(asset,unreal.Texture2D):raise RuntimeError('Texture path occupied by another type: '+destination)
        if not replace:
            expected={'srgb':spec['srgb'],'flip_green_channel':spec['flip_green'],'compression_settings':compression[spec['semantic']]}
            for key,value in expected.items():
                if asset.get_editor_property(key)!=value:raise RuntimeError('Existing texture setting differs; current art owner must review/reimport: '+destination+' / '+key)
            return asset
    task=unreal.AssetImportTask();task.set_editor_property('filename',str(filename))
    task.set_editor_property('destination_path',destination.rsplit('/',1)[0])
    task.set_editor_property('destination_name',filename.stem)
    task.set_editor_property('factory',unreal.TextureFactory())
    task.set_editor_property('automated',True);task.set_editor_property('replace_existing',replace)
    task.set_editor_property('save',False)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    asset=unreal.EditorAssetLibrary.load_asset(destination)
    if not isinstance(asset,unreal.Texture2D):raise RuntimeError('Texture import failed: '+destination)
    asset.set_editor_property('srgb',spec['srgb'])
    asset.set_editor_property('flip_green_channel',spec['flip_green'])
    asset.set_editor_property('compression_settings',compression[spec['semantic']])
    asset.set_editor_property('compression_no_alpha',True)
    save_asset(asset)
    return asset


def master(defaults):
    path=ART_ROOT+'/Materials/M_IE_AtlasSurface'
    material,created=create_asset(path,unreal.Material,unreal.MaterialFactoryNew())
    if not created:return material
    lib=unreal.MaterialEditingLibrary
    nodes={}
    sampler={'base':unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,'orm':unreal.MaterialSamplerType.SAMPLERTYPE_MASKS,'normal':unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL}
    for i,key in enumerate(('base','orm','normal')):
        node=lib.create_material_expression(material,unreal.MaterialExpressionTextureSampleParameter2D,-700,i*230)
        node.set_editor_property('parameter_name','Atlas_'+key)
        node.set_editor_property('texture',defaults[key]);node.set_editor_property('sampler_type',sampler[key]);nodes[key]=node
    wear=lib.create_material_expression(material,unreal.MaterialExpressionScalarParameter,-700,700)
    wear.set_editor_property('parameter_name','WearAmount');wear.set_editor_property('default_value',0.)
    wearcolor=lib.create_material_expression(material,unreal.MaterialExpressionVectorParameter,-700,850)
    wearcolor.set_editor_property('parameter_name','WearColor');wearcolor.set_editor_property('default_value',linear_rgb((.34,.38,.42)))
    color=lib.create_material_expression(material,unreal.MaterialExpressionLinearInterpolate,-260,0)
    lib.connect_material_expressions(nodes['base'],'RGB',color,'A')
    lib.connect_material_expressions(wearcolor,'',color,'B');lib.connect_material_expressions(wear,'',color,'Alpha')
    if not lib.connect_material_property(color,'',unreal.MaterialProperty.MP_BASE_COLOR):raise RuntimeError('Atlas color link failed')
    for pin,target,constant,y in (('G',unreal.MaterialProperty.MP_ROUGHNESS,.36,250),('B',unreal.MaterialProperty.MP_METALLIC,.93,400)):
        lerp=lib.create_material_expression(material,unreal.MaterialExpressionLinearInterpolate,-260,y)
        lerp.set_editor_property('const_b',constant)
        lib.connect_material_expressions(nodes['orm'],pin,lerp,'A');lib.connect_material_expressions(wear,'',lerp,'Alpha')
        if not lib.connect_material_property(lerp,'',target):raise RuntimeError('Atlas ORM link failed')
    if not lib.connect_material_property(nodes['orm'],'R',unreal.MaterialProperty.MP_AMBIENT_OCCLUSION):raise RuntimeError('Atlas AO link failed')
    if not lib.connect_material_property(nodes['normal'],'RGB',unreal.MaterialProperty.MP_NORMAL):raise RuntimeError('Atlas normal link failed')
    glow=lib.create_material_expression(material,unreal.MaterialExpressionScalarParameter,-700,1000)
    glow.set_editor_property('parameter_name','EmissionStrength');glow.set_editor_property('default_value',0.)
    emission=lib.create_material_expression(material,unreal.MaterialExpressionMultiply,-260,700)
    lib.connect_material_expressions(nodes['base'],'RGB',emission,'A');lib.connect_material_expressions(glow,'',emission,'B')
    lib.connect_material_property(emission,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    lib.set_material_usage(material,unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH)
    lib.layout_material_expressions(material);lib.recompile_material(material);save_asset(material)
    return material


def instances(ident,textures):
    parent=master(textures);result={};lib=unreal.MaterialEditingLibrary
    for slot in ('Gunmetal','Armor','Brass','Rubber','Signal'):
        path=ART_ROOT+'/Materials/MI_IE_Atlas_'+ident+'_'+slot
        asset,created=create_asset(path,unreal.MaterialInstanceConstant,unreal.MaterialInstanceConstantFactoryNew())
        if created:
            lib.set_material_instance_parent(asset,parent)
            for key,value in textures.items():
                if not lib.set_material_instance_texture_parameter_value(asset,'Atlas_'+key,value):raise RuntimeError('Atlas texture parameter missing: '+key)
            if not lib.set_material_instance_scalar_parameter_value(asset,'EmissionStrength',1.5 if slot=='Signal' else 0.):
                raise RuntimeError('Emission parameter missing')
            lib.update_material_instance(asset);save_asset(asset)
        result[slot]=asset
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--replace',action='store_true',help='Explicit current-owner reimport of existing texture/LOD source assets')
    args=parser.parse_args(argv)
    require_clean_editor();lodroot,texroot,lod,tex=load_quality()
    if not hasattr(unreal,'SkeletalMeshEditorSubsystem'):raise RuntimeError('SkeletalMeshEditorSubsystem unavailable in this UE')
    subsystem=unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
    if not hasattr(subsystem,'get_lod_count') or not hasattr(subsystem,'import_lod'):
        raise RuntimeError('Required LOD editor API unavailable; use explicit Skeletal Mesh Editor import and record actual results')
    plans=[]
    for robot in lod['robots']:
        mesh=unreal.EditorAssetLibrary.load_asset(mesh_path(robot['id']))
        if not isinstance(mesh,unreal.SkeletalMesh):raise RuntimeError('Import the base robot first: '+robot['id'])
        count=subsystem.get_lod_count(mesh)
        slots=[str(s.get_editor_property('material_slot_name')) for s in mesh.get_editor_property('materials')]
        if len(slots)!=5 or set(slots)!=set(tex['robots'][0]['slots']):raise RuntimeError('Base material slots differ from agreed art proposal')
        if args.apply and count>1 and not args.replace:raise RuntimeError('Existing LODs require explicit current-writer --replace: '+robot['id'])
        if args.apply and count>3:raise RuntimeError('Extra LODs exist; do not overwrite another quality setup automatically: '+robot['id'])
        plans.append({"id":robot['id'],"mesh":mesh.get_path_name(),"current_lod_count":count,"desired_lod_count":3})
    report={"scope":"Art quality import only; no gameplay acceptance or FPS guarantee","mode":"apply" if args.apply else "preflight",
        "plans":plans,"results":[],"manual_checks":["Correct centimetres/+X-forward at all LODs", "No joint or silhouette pop on forced LOD0/1/2", "Normal green direction and tangent seams", "LOD screen sizes set after camera/profile test", "Texture cook/mips/streaming and material-slot draw calls", "WearAmount is global cosmetic material state, not separate health"]}
    if args.apply:
        with ArtLock():
            for robot in lod['robots']:
                ident=robot['id'];mesh=unreal.EditorAssetLibrary.load_asset(mesh_path(ident))
                skeleton_before=mesh.get_editor_property('skeleton').get_path_name()
                maps=next(r for r in tex['robots'] if r['id']==ident)
                textures={spec['semantic']:texture(spec,texroot,args.replace) for spec in maps['textures']}
                material_by_slot=instances(ident,textures)
                for level in robot['levels']:
                    imported=subsystem.import_lod(mesh,level['index'],str(source(lodroot,level['fbx'],'.fbx')))
                    if imported!=level['index']:raise RuntimeError('LOD import failed: '+ident+' / '+str(level['index']))
                if mesh.get_editor_property('skeleton').get_path_name()!=skeleton_before:
                    raise RuntimeError('LOD import changed the Skeleton reference; stop and review before saving')
                slots=list(mesh.get_editor_property('materials'))
                for slot in slots:
                    name=str(slot.get_editor_property('material_slot_name'))
                    if name not in material_by_slot:raise RuntimeError('LOD importer changed the material slot mapping')
                    slot.set_editor_property('material_interface',material_by_slot[name])
                mesh.set_editor_property('materials',slots);save_asset(mesh)
                report['results'].append({"id":ident,"lod_count":subsystem.get_lod_count(mesh),"skeleton":skeleton_before,"textures":{key:asset.get_path_name() for key,asset in textures.items()}})
    write_report('import_surface_lods',report)
    return report


if __name__=='__main__':main([])
