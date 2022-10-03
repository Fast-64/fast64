from bpy.props import StringProperty
from bpy.types import Scene
from bpy.utils import register_class, unregister_class
from ....utility import prop_split
from ...panel import OOT_Panel
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
        prop_split(col, context.scene, "ootCutsceneExportPath", "File")


oot_cutscene_panel_classes = [
    OOT_CutscenePanel,
]

oot_cutscene_classes = [
    OOT_ExportCutscene,
    OOT_ExportAllCutscenes,
]


def oot_cutscene_panel_register():
    for cls in oot_cutscene_panel_classes:
        register_class(cls)


def oot_cutscene_panel_unregister():
    for cls in oot_cutscene_panel_classes:
        unregister_class(cls)


def oot_cutscene_register():
    for cls in oot_cutscene_classes:
        register_class(cls)

    Scene.ootCutsceneExportPath = StringProperty(name="File", subtype="FILE_PATH")


def oot_cutscene_unregister():
    for cls in reversed(oot_cutscene_classes):
        unregister_class(cls)

    del Scene.ootCutsceneExportPath
