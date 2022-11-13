from bpy.types import PropertyGroup
from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty, FloatProperty
from ......f3d.f3d_material import ootEnumDrawLayers


class OOTDLExportSettings(PropertyGroup):
    name: StringProperty(name="DL Name", default="gBoulderFragmentsDL")
    folder: StringProperty(name="DL Folder", default="gameplay_keep")
    customPath: StringProperty(name="Custom DL Path", subtype="FILE_PATH")
    isCustom: BoolProperty(name="Use Custom Path")
    removeVanillaData: BoolProperty(name="Replace Vanilla DLs")
    drawLayer: EnumProperty(name="Draw Layer", items=ootEnumDrawLayers)
    actorOverlayName: StringProperty(name="Overlay", default="")
    flipbookUses2DArray: BoolProperty(name="Has 2D Flipbook Array", default=False)
    flipbookArrayIndex2D: IntProperty(name="Index if 2D Array", default=0, min=0)
    customAssetIncludeDir: StringProperty(
        name="Asset Include Directory",
        default="assets/objects/gameplay_keep",
        description="Used in #include for including image files",
    )


class OOTDLImportSettings(PropertyGroup):
    name: StringProperty(name="DL Name", default="gBoulderFragmentsDL")
    folder: StringProperty(name="DL Folder", default="gameplay_keep")
    customPath: StringProperty(name="Custom DL Path", subtype="FILE_PATH")
    isCustom: BoolProperty(name="Use Custom Path")
    removeDoubles: BoolProperty(name="Remove Doubles", default=True)
    importNormals: BoolProperty(name="Import Normals", default=True)
    drawLayer: EnumProperty(name="Draw Layer", items=ootEnumDrawLayers)
    actorOverlayName: StringProperty(name="Overlay", default="")
    flipbookUses2DArray: BoolProperty(name="Has 2D Flipbook Array", default=False)
    flipbookArrayIndex2D: IntProperty(name="Index if 2D Array", default=0, min=0)
    autoDetectActorScale: BoolProperty(name="Auto Detect Actor Scale", default=True)
    actorScale: FloatProperty(name="Actor Scale", min=0, default=100)
