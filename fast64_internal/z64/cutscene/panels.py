from bpy.utils import register_class, unregister_class
from bpy.types import Scene
from bpy.props import BoolProperty
from ...utility import prop_split
from ...panels import Z64_Panel
from ..utility import is_game_oot
from .operators import OOT_ExportCutscene, OOT_ExportAllCutscenes, OOT_ImportCutscene


class OoT_PreviewSettingsPanel(Z64_Panel):
    bl_idname = "Z64_PT_preview_settings"
    bl_label = "CS Preview Settings"

    def draw(self, context):
        context.scene.ootPreviewSettingsProperty.draw_props(self.layout)


class OOT_CutscenePanel(Z64_Panel):
    bl_idname = "Z64_PT_export_cutscene"
    bl_label = "Cutscenes"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        layout = self.layout

        exportBox = layout.box()
        exportBox.label(text="Cutscene Exporter")

        exportBox.enabled = is_game_oot()
        if not exportBox.enabled:
            layout.label(text="Export not implemented yet.")

        prop_split(exportBox, context.scene, "ootCutsceneExportPath", "Export To")

        activeObj = context.view_layer.objects.active
        label = None
        col = exportBox.column()
        colcol = col.column()
        if activeObj is None or activeObj.type != "EMPTY" or activeObj.ootEmptyType != "Cutscene":
            label = "Select a cutscene object"

        if activeObj is not None and activeObj.parent is not None:
            label = "Cutscene object must not be parented to anything"

        if label is not None:
            col.label(text=label)
            colcol.enabled = False

        colcol.operator(OOT_ExportCutscene.bl_idname)
        col.operator(OOT_ExportAllCutscenes.bl_idname)


        importBox = layout.box()
        importBox.label(text="Cutscene Importer")

        importBox.enabled = is_game_oot()
        if not importBox.enabled:
            layout.label(text="Import not implemented yet.")

        prop_split(importBox, context.scene, "ootCSImportName", "Import")
        prop_split(importBox, context.scene, "ootCutsceneImportPath", "From")

        col = importBox.column()
        if len(context.scene.ootCSImportName) == 0:
            col.label(text="All Cutscenes will be imported.")
        col.operator(OOT_ImportCutscene.bl_idname)


oot_cutscene_panel_classes = (
    OoT_PreviewSettingsPanel,
    OOT_CutscenePanel,
)


def cutscene_panels_register():
    for cls in oot_cutscene_panel_classes:
        register_class(cls)


def cutscene_panels_unregister():
    for cls in oot_cutscene_panel_classes:
        unregister_class(cls)
