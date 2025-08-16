from bpy.types import Panel, Armature
from bpy.utils import register_class, unregister_class
from ...utility import prop_split
from ...panels import OOT_Panel
from .operators import OOT_ExportAnim, OOT_ImportAnim
from .properties import OOTAnimExportSettingsProperty, OOTAnimImportSettingsProperty, OOTLinkTextureAnimProperty


class OOT_LinkAnimPanel(Panel):
    bl_idname = "Z64_PT_link_anim"
    bl_parent_id = "ARMATURE_PT_OOT_Inspector"
    bl_label = "Link Animation Properties"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        linkTextureAnim: OOTLinkTextureAnimProperty = context.object.ootLinkTextureAnim
        linkTextureAnim.draw_props(col)
        col.label(text="Index 0 is for auto, flipbook starts at index 1.", icon="INFO")


class OOT_ExportAnimPanel(OOT_Panel):
    bl_idname = "Z64_PT_export_anim"
    bl_label = "Animation Exporter"

    # called every frame
    def draw(self, context):
        col = self.layout.column()

        col.operator(OOT_ExportAnim.bl_idname)
        exportSettings: OOTAnimExportSettingsProperty = context.scene.fast64.oot.animExportSettings
        exportSettings.draw_props(col)

        col.operator(OOT_ImportAnim.bl_idname)
        importSettings: OOTAnimImportSettingsProperty = context.scene.fast64.oot.animImportSettings
        importSettings.draw_props(col)


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
