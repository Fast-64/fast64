from bpy.utils import register_class, unregister_class
from bpy.types import Scene
from bpy.props import BoolProperty
from ...utility import prop_split
from ...panels import OOT_Panel
from .operators import OOT_ExportCutscene, OOT_ExportAllCutscenes, OOT_ImportCutscene


class OoT_PreviewSettingsPanel(OOT_Panel):
    bl_idname = "OOT_PT_preview_settings"
    bl_label = "OOT CS Preview Settings"

    def draw(self, context):
        context.scene.ootPreviewSettingsProperty.draw_props(self.layout)


class OOT_CutscenePanel(OOT_Panel):
    bl_idname = "OOT_PT_export_cutscene"
    bl_label = "OOT Cutscene Exporter"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OOT"

    def draw(self, context):
        layout = self.layout

        exportBox = layout.box()
        exportBox.label(text="Cutscene Exporter")

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
