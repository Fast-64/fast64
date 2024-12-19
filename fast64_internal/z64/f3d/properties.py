import bpy

from bpy.types import PropertyGroup, Object, World, Material, UILayout
from bpy.props import PointerProperty, StringProperty, BoolProperty, EnumProperty, IntProperty, FloatProperty
from bpy.utils import register_class, unregister_class
from ...f3d.f3d_material import update_world_default_rendermode
from ...f3d.f3d_parser import ootEnumDrawLayers
from ...utility import prop_split


class OOTDLExportSettings(PropertyGroup):
    isCustomFilename: BoolProperty(
        name="Use Custom Filename", description="Override filename instead of basing it off of the Blender name"
    )
    filename: StringProperty(name="Filename")
    folder: StringProperty(name="DL Folder", default="gameplay_keep")
    customPath: StringProperty(name="Custom DL Path", subtype="FILE_PATH")
    isCustom: BoolProperty(
        name="Use Custom Path", description="Determines whether or not to export to an explicitly specified folder"
    )
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

    def draw_props(self, layout: UILayout):
        layout.label(text="Object name used for export.", icon="INFO")
        layout.prop(self, "isCustomFilename")
        if self.isCustomFilename:
            prop_split(layout, self, "filename", "Filename")
        prop_split(layout, self, "folder", "Object" if not self.isCustom else "Folder")
        if self.isCustom:
            prop_split(layout, self, "customAssetIncludeDir", "Asset Include Path")
            prop_split(layout, self, "customPath", "Path")
        else:
            prop_split(layout, self, "actorOverlayName", "Overlay (Optional)")
            layout.prop(self, "flipbookUses2DArray")
            if self.flipbookUses2DArray:
                box = layout.box().column()
                prop_split(box, self, "flipbookArrayIndex2D", "Flipbook Index")

        prop_split(layout, self, "drawLayer", "Export Draw Layer")
        layout.prop(self, "isCustom")
        layout.prop(self, "removeVanillaData")


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

    def draw_props(self, layout: UILayout):
        prop_split(layout, self, "name", "DL")
        if self.isCustom:
            prop_split(layout, self, "customPath", "File")
        else:
            prop_split(layout, self, "folder", "Object")
            prop_split(layout, self, "actorOverlayName", "Overlay (Optional)")
            layout.prop(self, "autoDetectActorScale")
            if not self.autoDetectActorScale:
                prop_split(layout, self, "actorScale", "Actor Scale")
            layout.prop(self, "flipbookUses2DArray")
            if self.flipbookUses2DArray:
                box = layout.box().column()
                prop_split(box, self, "flipbookArrayIndex2D", "Flipbook Index")
        prop_split(layout, self, "drawLayer", "Import Draw Layer")

        layout.prop(self, "isCustom")
        layout.prop(self, "removeDoubles")
        layout.prop(self, "importNormals")


class OOTDynamicMaterialDrawLayerProperty(PropertyGroup):
    segment8: BoolProperty()
    segment9: BoolProperty()
    segmentA: BoolProperty()
    segmentB: BoolProperty()
    segmentC: BoolProperty()
    segmentD: BoolProperty()
    customCall0: BoolProperty()
    customCall0_seg: StringProperty(description="Segment address of a display list to call, e.g. 0x08000010")
    customCall1: BoolProperty()
    customCall1_seg: StringProperty(description="Segment address of a display list to call, e.g. 0x08000010")

    def key(self):
        return (
            self.segment8,
            self.segment9,
            self.segmentA,
            self.segmentB,
            self.segmentC,
            self.segmentD,
            self.customCall0_seg if self.customCall0 else None,
            self.customCall1_seg if self.customCall1 else None,
        )

    def draw_props(self, layout: UILayout, suffix: str):
        row = layout.row()
        for colIndex in range(2):
            col = row.column()
            for rowIndex in range(3):
                i = 8 + colIndex * 3 + rowIndex
                name = "Segment " + format(i, "X") + " " + suffix
                col.prop(self, "segment" + format(i, "X"), text=name)
            name = "Custom call (" + str(colIndex + 1) + ") " + suffix
            p = "customCall" + str(colIndex)
            col.prop(self, p, text=name)
            if getattr(self, p):
                col.prop(self, p + "_seg", text="")


# The reason these are separate is for the case when the user changes the material draw layer, but not the
# dynamic material calls. This could cause crashes which would be hard to detect.
class OOTDynamicMaterialProperty(PropertyGroup):
    opaque: PointerProperty(type=OOTDynamicMaterialDrawLayerProperty)
    transparent: PointerProperty(type=OOTDynamicMaterialDrawLayerProperty)

    def key(self):
        return (self.opaque.key(), self.transparent.key())

    def draw_props(self, layout: UILayout, mat: Object, drawLayer: str):
        drawLayerSuffix = {"Opaque": "OPA", "Transparent": "XLU", "Overlay": "OVL"}

        if drawLayer == "Overlay":
            return

        suffix = "(" + drawLayerSuffix[drawLayer] + ")"
        layout.box().column().label(text="OOT Dynamic Material Properties " + suffix)
        layout.label(text="See gSPSegment calls in z_scene_table.c.")
        layout.label(text="Based off draw config index in gSceneTable.")
        dynMatLayerProp: OOTDynamicMaterialDrawLayerProperty = getattr(self, drawLayer.lower())
        dynMatLayerProp.draw_props(layout.column(), suffix)
        if not mat.is_f3d:
            return
        f3d_mat = mat.f3d_mat


class OOTDefaultRenderModesProperty(PropertyGroup):
    expandTab: BoolProperty()
    opaqueCycle1: StringProperty(default="G_RM_AA_ZB_OPA_SURF", update=update_world_default_rendermode)
    opaqueCycle2: StringProperty(default="G_RM_AA_ZB_OPA_SURF2", update=update_world_default_rendermode)
    transparentCycle1: StringProperty(default="G_RM_AA_ZB_XLU_SURF", update=update_world_default_rendermode)
    transparentCycle2: StringProperty(default="G_RM_AA_ZB_XLU_SURF2", update=update_world_default_rendermode)
    overlayCycle1: StringProperty(default="G_RM_AA_ZB_OPA_SURF", update=update_world_default_rendermode)
    overlayCycle2: StringProperty(default="G_RM_AA_ZB_OPA_SURF2", update=update_world_default_rendermode)

    def draw_props(self, layout: UILayout):
        inputGroup = layout.column()
        inputGroup.prop(
            self,
            "expandTab",
            text="Default Render Modes",
            icon="TRIA_DOWN" if self.expandTab else "TRIA_RIGHT",
        )
        if self.expandTab:
            prop_split(inputGroup, self, "opaqueCycle1", "Opaque Cycle 1")
            prop_split(inputGroup, self, "opaqueCycle2", "Opaque Cycle 2")
            prop_split(inputGroup, self, "transparentCycle1", "Transparent Cycle 1")
            prop_split(inputGroup, self, "transparentCycle2", "Transparent Cycle 2")
            prop_split(inputGroup, self, "overlayCycle1", "Overlay Cycle 1")
            prop_split(inputGroup, self, "overlayCycle2", "Overlay Cycle 2")


oot_dl_writer_classes = (
    OOTDLExportSettings,
    OOTDLImportSettings,
    OOTDynamicMaterialDrawLayerProperty,
    OOTDynamicMaterialProperty,
    OOTDefaultRenderModesProperty,
)


def f3d_props_register():
    ootEnumObjectMenu = [
        ("Scene", "Parent Scene Settings", "Scene"),
        ("Room", "Parent Room Settings", "Room"),
    ]

    for cls in oot_dl_writer_classes:
        register_class(cls)

    Object.ootDrawLayer = EnumProperty(items=ootEnumDrawLayers, default="Opaque")

    # Doesn't work since all static meshes are pre-transformed
    # Object.ootDynamicTransform = PointerProperty(type = OOTDynamicTransformProperty)
    World.ootDefaultRenderModes = PointerProperty(type=OOTDefaultRenderModesProperty)
    Material.ootMaterial = PointerProperty(type=OOTDynamicMaterialProperty)
    Object.ootObjectMenu = EnumProperty(items=ootEnumObjectMenu)


def f3d_props_unregister():
    for cls in reversed(oot_dl_writer_classes):
        unregister_class(cls)

    del Material.ootMaterial
    del Object.ootObjectMenu
