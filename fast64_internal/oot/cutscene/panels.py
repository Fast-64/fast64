from bpy.utils import register_class, unregister_class
from bpy.types import Scene
from bpy.props import BoolProperty
from ...utility import prop_split
from ...panels import OOT_Panel
from .operators import OOT_ExportCutscene, OOT_ExportAllCutscenes


class OOT_CutscenePanel(OOT_Panel):
    bl_idname = "OOT_PT_export_cutscene"
    bl_label = "OOT Cutscene Exporter"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OOT"

    def draw(self, context):
        col = self.layout.column()
        col.operator(OOT_ExportCutscene.bl_idname)
        col.operator(OOT_ExportAllCutscenes.bl_idname)

        if not context.scene.fast64.oot.hackerFeaturesEnabled:
            col.prop(context.scene, "useDecompFeatures")

        prop_split(col, context.scene, "ootCutsceneExportPath", "File")


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
