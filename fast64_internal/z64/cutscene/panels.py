from bpy.utils import register_class, unregister_class
from ...utility import prop_split
from ..utility import is_oot_features
from ...panels import OOT_Panel
from .operators import OOT_ExportCutscene, OOT_ExportAllCutscenes, OOT_ImportCutscene


class OoT_PreviewSettingsPanel(OOT_Panel):
    bl_idname = "Z64_PT_preview_settings"
    bl_label = "CS Preview Settings"

    def draw(self, context):
        context.scene.ootPreviewSettingsProperty.draw_props(self.layout)


class OOT_CutscenePanel(OOT_Panel):
    bl_idname = "Z64_PT_export_cutscene"
    bl_label = "Cutscene Exporter"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        layout = self.layout

        export_box = layout.box().column()
        export_box.label(text="Cutscene Exporter")

        export_box.enabled = is_oot_features()
        if not export_box.enabled:
            layout.label(text="Export not implemented yet.")

        prop_split(export_box, context.scene, "ootCutsceneExportPath", "Export To")
        prop_split(export_box, context.scene.fast64.oot, "export_cutscene_obj", "CS Object")

        cs_obj = context.scene.fast64.oot.export_cutscene_obj

        if cs_obj is None:
            cs_obj = context.view_layer.objects.active

        label = None
        if cs_obj is None or cs_obj.type != "EMPTY" or cs_obj.ootEmptyType != "Cutscene":
            label = "Select a cutscene object"

        if cs_obj is not None and cs_obj.parent is not None:
            label = "Cutscene object must not be parented to anything"

        export_op_layout = export_box.column()

        if label is not None:
            export_box.label(text=label)
            export_op_layout.enabled = False

        export_op_layout.operator(OOT_ExportCutscene.bl_idname)
        export_box.operator(OOT_ExportAllCutscenes.bl_idname)

        import_box = layout.box().column()
        import_box.label(text="Cutscene Importer")

        import_box.enabled = is_oot_features()
        if not import_box.enabled:
            layout.label(text="Import not implemented yet.")

        prop_split(import_box, context.scene, "ootCSImportName", "Import")
        prop_split(import_box, context.scene, "ootCutsceneImportPath", "From")

        if len(context.scene.ootCSImportName) == 0:
            import_box.label(text="All Cutscenes will be imported.")

        import_box.operator(OOT_ImportCutscene.bl_idname)


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
