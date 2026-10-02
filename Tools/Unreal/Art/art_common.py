"""Shared, editor-only IRON ECHO art helpers. No gameplay or project settings.

API baseline: Epic's Unreal Python 5.6 docs. Engine execution is NOT verified
in the preparation environment. Imported/created packages remain in ART_ROOT.
"""
from __future__ import annotations

import datetime
import json
import os
import re
from pathlib import Path

import unreal

ART_ROOT = "/Game/Art/IronEcho"
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = PACKAGE_ROOT / "ArtSource" / "exports" / "art_manifest.json"
SLOTS = ("Gunmetal", "Armor", "Brass", "Rubber", "Signal")
EXPECTED_BONES = (
    "root", "pelvis", "spine_01", "chest", "neck", "head",
    "clavicle_l", "upperarm_l", "lowerarm_l", "hand_l",
    "clavicle_r", "upperarm_r", "lowerarm_r", "hand_r",
    "thigh_l", "calf_l", "foot_l", "thigh_r", "calf_r", "foot_r",
)


class ArtLock:
    """One writer per project. A crash leaves a lock for the owner to inspect."""
    def __enter__(self):
        self.path = Path(unreal.Paths.project_saved_dir()) / "IronEchoArt.lock"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as error:
            raise RuntimeError("Art editor lock exists. Check the writer before removing " + str(self.path)) from error
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"pid": os.getpid(), "utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}, handle)
        return self

    def __exit__(self, *_):
        self.path.unlink(missing_ok=True)


def safe_name(value):
    value = str(value)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", value):
        raise ValueError("Unsafe asset name: {!r}".format(value))
    return value


def art_path(path):
    """Reject gameplay paths, root-prefix tricks and malformed package paths."""
    if not isinstance(path, str) or not path.startswith(ART_ROOT + "/"):
        raise ValueError("Art destination must be below " + ART_ROOT)
    if ".." in path or "//" in path or "." in path or "\\" in path:
        raise ValueError("Expected an Unreal package path: " + path)
    for segment in path.split("/")[1:]:
        safe_name(segment)
    return path


def load_manifest(filename=None):
    path = Path(filename).expanduser().resolve() if filename else DEFAULT_MANIFEST
    with path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest.get("robots"), list) or not manifest["robots"]:
        raise ValueError("Manifest needs a non-empty robots list")
    ids = [safe_name(robot["id"]) for robot in manifest["robots"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate robot ids")
    return manifest, path


def source_file(manifest_path, relative_name):
    """All export references must stay inside the manifest's export folder."""
    root = Path(manifest_path).parent.resolve()
    path = (root / relative_name).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError("Source escaped the export folder: " + str(path)) from error
    if path.suffix.lower() != ".fbx" or not path.is_file():
        raise ValueError("FBX source not found: " + str(path))
    return path


def mesh_path(robot_id):
    robot_id = safe_name(robot_id)
    return art_path(ART_ROOT + "/Robots/" + robot_id + "/SK_IE_" + robot_id)


def clip_path(clip_name):
    return art_path(ART_ROOT + "/Animations/A_IE_" + safe_name(clip_name))


def require_editor():
    for name in ("EditorAssetLibrary", "AssetToolsHelpers", "LevelEditorSubsystem"):
        if not hasattr(unreal, name):
            raise RuntimeError("Missing Unreal editor API: " + name)
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if levels.is_in_play_in_editor():
        raise RuntimeError("Stop Play In Editor before art operations")


def require_clean_editor():
    """Never drop another author's unsaved level on new_level/load_level."""
    require_editor()
    dirty_maps = unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
    dirty_assets = unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
    dirty = [str(package.get_name()) for package in list(dirty_maps) + list(dirty_assets)]
    if dirty:
        raise RuntimeError("Save or discard your own edits before running: " + ", ".join(dirty[:10]))


def write_report(name, report):
    folder = Path(unreal.Paths.project_saved_dir()) / "IronEchoArtReports"
    folder.mkdir(parents=True, exist_ok=True)
    report["generated_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    report["engine_version"] = str(unreal.SystemLibrary.get_engine_version())
    report["art_root"] = ART_ROOT
    filename = folder / (safe_name(name) + ".json")
    filename.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    unreal.log("IRON ECHO report: " + str(filename))
    return filename


def save_asset(asset):
    if not str(asset.get_path_name()).startswith(ART_ROOT + "/"):
        raise RuntimeError("Refusing to save external content: " + str(asset.get_path_name()))
    if not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError("Could not save " + str(asset.get_path_name()))


def create_asset(path, asset_class, factory):
    art_path(path)
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        asset = unreal.EditorAssetLibrary.load_asset(path)
        if not isinstance(asset, asset_class):
            raise RuntimeError("Existing asset has incompatible class: " + path)
        return asset, False
    folder, name = path.rsplit("/", 1)
    unreal.EditorAssetLibrary.make_directory(folder)
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, asset_class, factory)
    if not asset:
        raise RuntimeError("Asset creation failed: " + path)
    return asset, True


def linear_rgb(rgb):
    """Input palette is sRGB, material parameters are linear scene values."""
    def convert(value):
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
    return unreal.LinearColor(*[convert(float(value)) for value in rgb], 1.0)


def material_master():
    path = ART_ROOT + "/Materials/M_IE_Surface"
    material, created = create_asset(path, unreal.Material, unreal.MaterialFactoryNew())
    if not created:
        return material
    lib = unreal.MaterialEditingLibrary
    color = lib.create_material_expression(material, unreal.MaterialExpressionVectorParameter, -480, -180)
    color.set_editor_property("parameter_name", "BaseColor")
    color.set_editor_property("default_value", linear_rgb((0.20, 0.22, 0.24)))
    wear_color = lib.create_material_expression(material, unreal.MaterialExpressionVectorParameter, -480, -30)
    wear_color.set_editor_property("parameter_name", "WearColor")
    wear_color.set_editor_property("default_value", linear_rgb((0.26, 0.28, 0.30)))
    wear = lib.create_material_expression(material, unreal.MaterialExpressionScalarParameter, -480, 120)
    wear.set_editor_property("parameter_name", "WearAmount")
    wear.set_editor_property("default_value", 0.0)
    blend = lib.create_material_expression(material, unreal.MaterialExpressionLinearInterpolate, -180, -100)
    lib.connect_material_expressions(color, "", blend, "A")
    lib.connect_material_expressions(wear_color, "", blend, "B")
    lib.connect_material_expressions(wear, "", blend, "Alpha")
    lib.connect_material_property(blend, "", unreal.MaterialProperty.MP_BASE_COLOR)
    for index, (parameter, default, output) in enumerate((
        ("Metallic", 0.8, unreal.MaterialProperty.MP_METALLIC),
        ("Roughness", 0.45, unreal.MaterialProperty.MP_ROUGHNESS),
    )):
        node = lib.create_material_expression(material, unreal.MaterialExpressionScalarParameter, -180, 150 + index * 120)
        node.set_editor_property("parameter_name", parameter)
        node.set_editor_property("default_value", default)
        lib.connect_material_property(node, "", output)
    emissive = lib.create_material_expression(material, unreal.MaterialExpressionVectorParameter, -480, 450)
    emissive.set_editor_property("parameter_name", "EmissionColor")
    emissive.set_editor_property("default_value", unreal.LinearColor(0.0, 0.0, 0.0, 1.0))
    glow = lib.create_material_expression(material, unreal.MaterialExpressionScalarParameter, -480, 580)
    glow.set_editor_property("parameter_name", "EmissionStrength")
    glow.set_editor_property("default_value", 0.0)
    multiply = lib.create_material_expression(material, unreal.MaterialExpressionMultiply, -180, 450)
    lib.connect_material_expressions(emissive, "", multiply, "A")
    lib.connect_material_expressions(glow, "", multiply, "B")
    lib.connect_material_property(multiply, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    lib.set_material_usage(material, unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH)
    lib.layout_material_expressions(material)
    lib.recompile_material(material)
    save_asset(material)
    return material


def surface_instance(name, color, metallic, roughness, glow=0.0):
    path = ART_ROOT + "/Materials/MI_IE_" + safe_name(name)
    instance, created = create_asset(path, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    if not created:
        return instance  # Preserve adjustments by the current binary owner.
    lib = unreal.MaterialEditingLibrary
    lib.set_material_instance_parent(instance, material_master())
    for parameter, value in (("BaseColor", linear_rgb(color)), ("EmissionColor", linear_rgb(color))):
        if not lib.set_material_instance_vector_parameter_value(instance, parameter, value):
            raise RuntimeError("Missing material vector parameter: " + parameter)
    for parameter, value in (("Metallic", metallic), ("Roughness", roughness), ("EmissionStrength", glow)):
        if not lib.set_material_instance_scalar_parameter_value(instance, parameter, float(value)):
            raise RuntimeError("Missing material scalar parameter: " + parameter)
    lib.update_material_instance(instance)
    save_asset(instance)
    return instance


def robot_materials(robot_id, palette=None):
    robot_id = safe_name(robot_id)
    palette = palette or {}
    orange = robot_id.lower() == "vanguard"
    def rgb(value):
        if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
            raise ValueError("Expected six-digit sRGB palette value")
        return tuple(int(value[i:i+2], 16)/255.0 for i in (0, 2, 4))
    armor = rgb(palette.get("armor_srgb", "BF7830" if orange else "356774"))
    signal = rgb(palette.get("signal_srgb", "FFD270" if orange else "8AE6F0"))
    specs = {
        "Gunmetal": ((0.23, 0.25, 0.27), 0.92, 0.40, 0.0),
        "Armor": (armor, 0.32, 0.46, 0.0),
        "Brass": ((0.58, 0.44, 0.22), 0.92, 0.38, 0.0),
        "Rubber": ((0.07, 0.08, 0.09), 0.0, 0.78, 0.0),
        "Signal": (signal, 0.1, 0.3, 1.5),
    }
    return {slot: surface_instance(robot_id + "_" + slot, *specs[slot]) for slot in SLOTS}


def bind_robot_materials(mesh, robot_id, palette=None):
    instances = robot_materials(robot_id, palette)
    materials = list(mesh.get_editor_property("materials"))
    observed = []
    for material in materials:
        slot = str(material.get_editor_property("material_slot_name"))
        imported = str(material.get_editor_property("imported_material_slot_name"))
        name = next((candidate for candidate in SLOTS if slot == candidate or imported == candidate), None)
        if not name:
            raise RuntimeError("Unexpected robot material slot {} / {}".format(slot, imported))
        material.set_editor_property("material_interface", instances[name])
        observed.append(name)
    if set(observed) != set(SLOTS) or len(observed) != len(SLOTS):
        raise RuntimeError("Expected five unique robot material slots; observed " + repr(observed))
    mesh.set_editor_property("materials", materials)
    save_asset(mesh)
    return observed


def install_mesh_sockets(mesh, specs):
    """Use public APIs; fail visibly if an engine hides socket naming from Python."""
    warnings = []
    installed = []
    if not hasattr(mesh, "add_socket"):
        return [], ["This engine does not expose SkeletalMesh.add_socket; create sockets in Skeleton Editor"]
    current = {}
    for index in range(mesh.num_sockets()):
        socket = mesh.get_socket_by_index(index)
        current[str(socket.get_editor_property("socket_name"))] = socket
    for spec in specs:
        name = safe_name(spec["name"])
        bone = safe_name(spec["bone"])
        if name in current:
            existing = current[name]
            if str(existing.get_editor_property("bone_name")) != bone:
                raise RuntimeError("Existing socket parent differs from draft contract: " + name)
            installed.append(name)
            continue
        try:
            socket = unreal.SkeletalMeshSocket(outer=mesh, name=name)
            socket.set_editor_property("socket_name", name)
            socket.set_socket_parent(mesh, bone)
            socket.set_editor_property("relative_location", unreal.Vector(*spec.get("location_cm", [0.0, 0.0, 0.0])))
            socket.set_editor_property("relative_rotation", unreal.Rotator(*spec.get("rotation_deg", [0.0, 0.0, 0.0])))
            socket.set_editor_property("force_always_animated", True)
            if str(socket.get_editor_property("bone_name")) != bone:
                raise RuntimeError("Socket parent validation failed")
            mesh.add_socket(socket, add_to_skeleton=False)
            installed.append(name)
        except Exception as error:
            warnings.append("Socket {} needs Skeleton Editor setup: {}".format(name, error))
    save_asset(mesh)
    return installed, warnings
