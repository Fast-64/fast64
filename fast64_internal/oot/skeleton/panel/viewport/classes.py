from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import PropertyGroup
from .....f3d.f3d_material import ootEnumDrawLayers


class OOTSkeletonExportSettings(PropertyGroup):
    name: StringProperty(name="Skeleton Name", default="gGerudoRedSkel")
    folder: StringProperty(name="Skeleton Folder", default="object_geldb")
    customPath: StringProperty(name="Custom Skeleton Path", subtype="FILE_PATH")
    isCustom: BoolProperty(name="Use Custom Path")
    removeVanillaData: BoolProperty(name="Replace Vanilla Skeletons On Export", default=True)

    customAssetIncludeDir: StringProperty(
        name="Asset Include Directory",
        default="assets/objects/object_geldb",
        description="Used in #include for including image files",
    )

    optimize: BoolProperty(
        name="Optimize",
        description="Applies various optimizations between the limbs in a skeleton. "
        + "If enabled, the skeleton limbs must be drawn in their normal order, "
        + "with nothing in between and no culling, otherwise the mesh will be corrupted.",
    )


class OOTSkeletonImportSettings(PropertyGroup):
    name: StringProperty(name="Skeleton Name", default="gGerudoRedSkel")
    folder: StringProperty(name="Skeleton Folder", default="object_geldb")
    customPath: StringProperty(name="Custom Skeleton Path", subtype="FILE_PATH")
    isCustom: BoolProperty(name="Use Custom Path")
    removeDoubles: BoolProperty(name="Remove Doubles On Import", default=True)
    importNormals: BoolProperty(name="Import Normals", default=True)
    drawLayer: EnumProperty(name="Import Draw Layer", items=ootEnumDrawLayers)
