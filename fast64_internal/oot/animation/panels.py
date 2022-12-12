from bpy.types import Panel, Armature
from bpy.utils import register_class, unregister_class
from ...utility import prop_split
from ...panels import OOT_Panel
from .operators import OOT_ExportAnim, OOT_ImportAnim


class OOT_LinkAnimPanel(Panel):
    bl_idname = "OOT_PT_link_anim"
    bl_label = "OOT Link Animation Properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return (
            context.scene.gameEditorMode == "OOT"
            and hasattr(context, "object")
            and context.object is not None
            and isinstance(context.object.data, Armature)
        )

    # called every frame
    def draw(self, context):
        col = self.layout.box().column()
        col.box().label(text="OOT Link Animation Inspector")
        prop_split(col, context.object.ootLinkTextureAnim, "eyes", "Eyes")
        prop_split(col, context.object.ootLinkTextureAnim, "mouth", "Mouth")
        col.label(text="Index 0 is for auto, flipbook starts at index 1.", icon="INFO")


class OOT_ExportAnimPanel(OOT_Panel):
    bl_idname = "OOT_PT_export_anim"
    bl_label = "OOT Animation Exporter"

    # called every frame
    def draw(self, context):
        col = self.layout.column()

        col.operator(OOT_ExportAnim.bl_idname)
        exportSettings = context.scene.fast64.oot.animExportSettings
        col.label(text="Exports active animation on selected object.", icon="INFO")
        col.prop(exportSettings, "isCustomFilename")
        if exportSettings.isCustomFilename:
            prop_split(col, exportSettings, "filename", "Filename")
        if exportSettings.isCustom:
            prop_split(col, exportSettings, "customPath", "Folder")
        elif not exportSettings.isLink:
            prop_split(col, exportSettings, "folderName", "Object")
        col.prop(exportSettings, "isLink")
        col.prop(exportSettings, "isCustom")

        col.operator(OOT_ImportAnim.bl_idname)
        importSettings = context.scene.fast64.oot.animImportSettings
        prop_split(col, importSettings, "animName", "Anim Header Name")
        if importSettings.isCustom:
            prop_split(col, importSettings, "customPath", "File")
        elif not importSettings.isLink:
            prop_split(col, importSettings, "folderName", "Object")
        col.prop(importSettings, "isLink")
        col.prop(importSettings, "isCustom")


panels = (
    OOT_LinkAnimPanel,
    OOT_ExportAnimPanel,
)


def anim_panels_register():
    for cls in panels:
        register_class(cls)


def anim_panels_unregister():
    for cls in panels:
        unregister_class(cls)
