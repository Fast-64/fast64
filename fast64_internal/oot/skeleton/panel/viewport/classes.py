from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty, FloatProperty
from bpy.types import PropertyGroup
from .....f3d.f3d_material import ootEnumDrawLayers
from ....oot_skeleton_import_data import ootEnumSkeletonImportMode


class OOTSkeletonExportSettings(PropertyGroup):
    mode: EnumProperty(name="Mode", items=ootEnumSkeletonImportMode)
    name: StringProperty(name="Skeleton Name", default="gGerudoRedSkel")
    folder: StringProperty(name="Skeleton Folder", default="object_geldb")
    customPath: StringProperty(name="Custom Skeleton Path", subtype="FILE_PATH")
    isCustom: BoolProperty(name="Use Custom Path")
    removeVanillaData: BoolProperty(name="Replace Vanilla Skeletons On Export", default=True)
    actorOverlayName: StringProperty(name="Overlay", default="ovl_En_GeldB")
    flipbookUses2DArray: BoolProperty(name="Has 2D Flipbook Array", default=False)
    flipbookArrayIndex2D: IntProperty(name="Index if 2D Array", default=0, min=0)
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
    mode: EnumProperty(name="Mode", items=ootEnumSkeletonImportMode)
    applyRestPose: BoolProperty(name="Apply Friendly Rest Pose (If Available)", default=True)
    name: StringProperty(name="Skeleton Name", default="gGerudoRedSkel")
    folder: StringProperty(name="Skeleton Folder", default="object_geldb")
    customPath: StringProperty(name="Custom Skeleton Path", subtype="FILE_PATH")
    isCustom: BoolProperty(name="Use Custom Path")
    removeDoubles: BoolProperty(name="Remove Doubles On Import", default=True)
    importNormals: BoolProperty(name="Import Normals", default=True)
    drawLayer: EnumProperty(name="Import Draw Layer", items=ootEnumDrawLayers)
    actorOverlayName: StringProperty(name="Overlay", default="ovl_En_GeldB")
    flipbookUses2DArray: BoolProperty(name="Has 2D Flipbook Array", default=False)
    flipbookArrayIndex2D: IntProperty(name="Index if 2D Array", default=0, min=0)
    autoDetectActorScale: BoolProperty(name="Auto Detect Actor Scale", default=True)
    actorScale: FloatProperty(name="Actor Scale", min=0, default=100)
