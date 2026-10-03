"""Editor-only preparation of a bounded-pool cosmetic spark material.

Prepared against public UE Python API; actual engine execution is unverified.
Does not enable the runtime plugin or modify gameplay/project configuration.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import unreal
from art_common import ART_ROOT, ArtLock, create_asset, linear_rgb, require_clean_editor, save_asset, write_report


def main():
    require_clean_editor()
    path = ART_ROOT + "/Materials/M_IE_ImpactSparks"
    report = {"scope": "Editor material only; runtime effect not tested", "material": path, "created": False, "runtime_verified": False}
    with ArtLock():
        material, created = create_asset(path, unreal.Material, unreal.MaterialFactoryNew())
        report["created"] = created
        if created:
            material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
            material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
            lib = unreal.MaterialEditingLibrary
            color = lib.create_material_expression(material, unreal.MaterialExpressionVectorParameter, -400, 0)
            color.set_editor_property("parameter_name", "SparkColor")
            color.set_editor_property("default_value", linear_rgb((1.0, .76, .35)))
            strength = lib.create_material_expression(material, unreal.MaterialExpressionScalarParameter, -400, 180)
            strength.set_editor_property("parameter_name", "SparkEmission")
            strength.set_editor_property("default_value", 3.0)
            multiply = lib.create_material_expression(material, unreal.MaterialExpressionMultiply, -120, 0)
            for source, pin in ((color, "A"), (strength, "B")):
                if not lib.connect_material_expressions(source, "", multiply, pin):
                    raise RuntimeError("Failed to connect spark material pin: " + pin)
            if not lib.connect_material_property(multiply, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR):
                raise RuntimeError("Failed to connect spark emissive output")
            lib.set_material_usage(material, unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
            lib.layout_material_expressions(material)
            lib.recompile_material(material)
            save_asset(material)
        report["existing_asset_preserved"] = not created
        report["manual_checks"] = ["Compile material in the installed UE version", "Opaque/unlit and Used with Instanced Static Meshes", "Assign SparkMaterial on the runtime visual actor", "Check no sustained flash or excessive bloom on the actual display"]
        write_report("prepare_vfx_material", report)
    return report


if __name__ == "__main__":
    main()
