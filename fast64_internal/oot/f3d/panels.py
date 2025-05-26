import bpy
from bpy.types import Panel, Mesh, Armature
from bpy.utils import register_class, unregister_class
from ...panels import OOT_Panel
from ...utility import prop_split
from .operators import OOT_ImportDL, OOT_ExportDL
from .properties import (
    OOTDLExportSettings,
    OOTDLImportSettings,
    OOTDynamicMaterialProperty,
    OOTDefaultRenderModesProperty,
)


class OOT_DisplayListPanel(Panel):
    bl_label = "OOT Display List Inspector"
    bl_idname = "OBJECT_PT_OOT_DL_Inspector"
    bl_parent_id = "OBJECT_PT_context_object"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "OOT" and (
            context.object is not None and isinstance(context.object.data, Mesh)
        )

    def draw(self, context):
        col = self.layout.column()
        obj = context.object

        # prop_split(box, obj, "ootDrawLayer", "Draw Layer")
        col.prop(obj, "ignore_render")
        col.prop(obj, "ignore_collision")
        if bpy.context.scene.f3d_type == "F3DEX3":
            col.prop(obj, "is_occlusion_planes")
            if obj.is_occlusion_planes and (not obj.ignore_render or not obj.ignore_collision):
                col.label(icon="INFO", text="Suggest Ignore Render & Ignore Collision.")

        if not (obj.parent is not None and isinstance(obj.parent.data, Armature)):
            actorScaleBox = col.box().column()
            prop_split(actorScaleBox, obj, "ootActorScale", "Actor Scale")
            actorScaleBox.label(text="This applies to actor exports only.", icon="INFO")

        # Doesn't work since all static meshes are pre-transformed
        # box.prop(obj.ootDynamicTransform, "billboard")


class OOT_DynamicPropertiesPanel(Panel):
    bl_label = "Dynamic Properties"
    bl_idname = "MATERIAL_PT_OOT_Dynamic_Properties"
    bl_parent_id = "MATERIAL_PT_OOT_Material_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"

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

        dynMatProps: OOTDynamicMaterialProperty = mat.ootMaterial
        dynMatProps.draw_props(col, mat, drawLayer)


class OOT_DrawLayersPanel(Panel):
    bl_label = "OOT Default Render Modes"
    bl_idname = "WORLD_PT_OOT_Draw_Layers_Panel"
    bl_parent_id = "WORLD_PT_context_world"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "world"

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "OOT"

    def draw(self, context):
        world = context.scene.world
        if not world:
            return
        ootDefaultRenderModeProp: OOTDefaultRenderModesProperty = world.ootDefaultRenderModes
        ootDefaultRenderModeProp.draw_props(self.layout)


class OOT_ExportDLPanel(OOT_Panel):
    bl_idname = "OOT_PT_export_dl"
    bl_label = "OOT DL Exporter"

    # called every frame
    def draw(self, context):
        col = self.layout.column()

        col.operator(OOT_ExportDL.bl_idname)
        exportSettings: OOTDLExportSettings = context.scene.fast64.oot.DLExportSettings
        exportSettings.draw_props(col)

        col.operator(OOT_ImportDL.bl_idname)
        importSettings: OOTDLImportSettings = context.scene.fast64.oot.DLImportSettings
        importSettings.draw_props(col)


oot_dl_writer_panel_classes = (
    OOT_DisplayListPanel,
    OOT_DynamicPropertiesPanel,
    OOT_DrawLayersPanel,
    OOT_ExportDLPanel,
)


def f3d_panels_register():
    for cls in oot_dl_writer_panel_classes:
        register_class(cls)


def f3d_panels_unregister():
    for cls in oot_dl_writer_panel_classes:
        unregister_class(cls)
