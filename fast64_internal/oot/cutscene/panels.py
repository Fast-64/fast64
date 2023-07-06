from bpy.utils import register_class, unregister_class
from bpy.types import Scene
from bpy.props import BoolProperty
from ...utility import prop_split
from ...panels import OOT_Panel
from .operators import OOT_ExportCutscene, OOT_ExportAllCutscenes, OOT_ImportCutscene


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

        if not context.scene.fast64.oot.hackerFeaturesEnabled:
            exportBox.prop(context.scene, "useDecompFeatures")

        prop_split(exportBox, context.scene, "ootCutsceneExportPath", "Export To")

        col = exportBox.column()
        col.operator(OOT_ExportCutscene.bl_idname)
        col.operator(OOT_ExportAllCutscenes.bl_idname)

        importBox = layout.box()
        importBox.label(text="Cutscene Importer")
        prop_split(importBox, context.scene, "ootCutsceneImportPath", "Import From")

        col = importBox.column()
        col.operator(OOT_ImportCutscene.bl_idname)


oot_cutscene_panel_classes = (OOT_CutscenePanel,)


def cutscene_panels_register():
    Scene.useDecompFeatures = BoolProperty(
        name="Use Decomp for Export", description="Use names and macros from decomp when exporting", default=True
    )

    for cls in oot_cutscene_panel_classes:
        register_class(cls)


def cutscene_panels_unregister():
    for cls in oot_cutscene_panel_classes:
        unregister_class(cls)
