from bpy.types import Panel, Mesh, Armature
from bpy.utils import register_class, unregister_class
from ...panels import OOT_Panel
from ...utility import prop_split
from ..oot_f3d_writer import drawOOTMaterialProperty
from .properties import OOTDLExportSettings, OOTDLImportSettings
from .operators import OOT_ImportDL, OOT_ExportDL


class OOT_DisplayListPanel(Panel):
    bl_label = "Display List Inspector"
    bl_idname = "OBJECT_PT_OOT_DL_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "OOT" and (
            context.object is not None and isinstance(context.object.data, Mesh)
        )

    def draw(self, context):
        box = self.layout.box().column()
        box.box().label(text="OOT DL Inspector")
        obj = context.object

        # prop_split(box, obj, "ootDrawLayer", "Draw Layer")
        box.prop(obj, "ignore_render")
        box.prop(obj, "ignore_collision")

        if not (obj.parent is not None and isinstance(obj.parent.data, Armature)):
            actorScaleBox = box.box().column()
            prop_split(actorScaleBox, obj, "ootActorScale", "Actor Scale")
            actorScaleBox.label(text="This applies to actor exports only.", icon="INFO")

        # Doesn't work since all static meshes are pre-transformed
        # box.prop(obj.ootDynamicTransform, "billboard")

        # drawParentSceneRoom(box, obj)


class OOT_MaterialPanel(Panel):
    bl_label = "OOT Material"
    bl_idname = "MATERIAL_PT_OOT_Material_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.material is not None and context.scene.gameEditorMode == "OOT"

    def draw(self, context):
        layout = self.layout
        mat = context.material
        col = layout.column()

        if (
            hasattr(context, "object")
            and context.object is not None
            and context.object.parent is not None
            and isinstance(context.object.parent.data, Armature)
        ):
            drawLayer = context.object.parent.ootDrawLayer
            if drawLayer != mat.f3d_mat.draw_layer.oot:
                col.label(text="Draw layer is being overriden by skeleton.", icon="OUTLINER_DATA_ARMATURE")
        else:
            drawLayer = mat.f3d_mat.draw_layer.oot

        drawOOTMaterialProperty(col.box().column(), mat, drawLayer)


class OOT_DrawLayersPanel(Panel):
    bl_label = "OOT Draw Layers"
    bl_idname = "WORLD_PT_OOT_Draw_Layers_Panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "world"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "OOT"

    def draw(self, context):
        ootDefaultRenderModeProp = context.scene.world.ootDefaultRenderModes
        layout = self.layout

        inputGroup = layout.column()
        inputGroup.prop(
            ootDefaultRenderModeProp,
            "expandTab",
            text="Default Render Modes",
            icon="TRIA_DOWN" if ootDefaultRenderModeProp.expandTab else "TRIA_RIGHT",
        )
        if ootDefaultRenderModeProp.expandTab:
            prop_split(inputGroup, ootDefaultRenderModeProp, "opaqueCycle1", "Opaque Cycle 1")
            prop_split(inputGroup, ootDefaultRenderModeProp, "opaqueCycle2", "Opaque Cycle 2")
            prop_split(inputGroup, ootDefaultRenderModeProp, "transparentCycle1", "Transparent Cycle 1")
            prop_split(inputGroup, ootDefaultRenderModeProp, "transparentCycle2", "Transparent Cycle 2")
            prop_split(inputGroup, ootDefaultRenderModeProp, "overlayCycle1", "Overlay Cycle 1")
            prop_split(inputGroup, ootDefaultRenderModeProp, "overlayCycle2", "Overlay Cycle 2")


class OOT_ExportDLPanel(OOT_Panel):
    bl_idname = "OOT_PT_export_dl"
    bl_label = "OOT DL Exporter"

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.operator(OOT_ExportDL.bl_idname)
        exportSettings: OOTDLExportSettings = context.scene.fast64.oot.DLExportSettings

        col.label(text="Object name used for export.", icon="INFO")
        col.prop(exportSettings, "isCustomFilename")
        if exportSettings.isCustomFilename:
            prop_split(col, exportSettings, "filename", "Filename")
        prop_split(col, exportSettings, "folder", "Object" if not exportSettings.isCustom else "Folder")
        if exportSettings.isCustom:
            prop_split(col, exportSettings, "customAssetIncludeDir", "Asset Include Path")
            prop_split(col, exportSettings, "customPath", "Path")
        else:
            prop_split(col, exportSettings, "actorOverlayName", "Overlay (Optional)")
            col.prop(exportSettings, "flipbookUses2DArray")
            if exportSettings.flipbookUses2DArray:
                box = col.box().column()
                prop_split(box, exportSettings, "flipbookArrayIndex2D", "Flipbook Index")

        prop_split(col, exportSettings, "drawLayer", "Export Draw Layer")
        col.prop(exportSettings, "isCustom")
        col.prop(exportSettings, "removeVanillaData")

        col.operator(OOT_ImportDL.bl_idname)
        importSettings: OOTDLImportSettings = context.scene.fast64.oot.DLImportSettings

        prop_split(col, importSettings, "name", "DL")
        if importSettings.isCustom:
            prop_split(col, importSettings, "customPath", "File")
        else:
            prop_split(col, importSettings, "folder", "Object")
            prop_split(col, importSettings, "actorOverlayName", "Overlay (Optional)")
            col.prop(importSettings, "autoDetectActorScale")
            if not importSettings.autoDetectActorScale:
                prop_split(col, importSettings, "actorScale", "Actor Scale")
            col.prop(importSettings, "flipbookUses2DArray")
            if importSettings.flipbookUses2DArray:
                box = col.box().column()
                prop_split(box, importSettings, "flipbookArrayIndex2D", "Flipbook Index")
        prop_split(col, importSettings, "drawLayer", "Import Draw Layer")

        col.prop(importSettings, "isCustom")
        col.prop(importSettings, "removeDoubles")
        col.prop(importSettings, "importNormals")


oot_dl_writer_panel_classes = (
    OOT_DisplayListPanel,
    OOT_MaterialPanel,
    OOT_DrawLayersPanel,
    OOT_ExportDLPanel,
)

def f3d_panels_register():
    for cls in oot_dl_writer_panel_classes:
        register_class(cls)


def f3d_panels_unregister():
    for cls in oot_dl_writer_panel_classes:
        unregister_class(cls)
