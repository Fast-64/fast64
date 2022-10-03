from ...panel import OOT_Panel
from bpy.utils import register_class, unregister_class
from ....utility import prop_split
from .classes import OOTDLExportSettings, OOTDLImportSettings
from .operators import OOT_ImportDL, OOT_ExportDL


class OOT_ExportDLPanel(OOT_Panel):
    bl_idname = "OOT_PT_export_dl"
    bl_label = "OOT DL Exporter"

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.operator(OOT_ExportDL.bl_idname)
        exportSettings: OOTDLExportSettings = context.scene.fast64.oot.DLExportSettings

        prop_split(col, exportSettings, "name", "DL")
        prop_split(col, exportSettings, "folder", "Object" if not exportSettings.isCustom else "Folder")
        if exportSettings.isCustom:
            prop_split(col, exportSettings, "customAssetIncludeDir", "Asset Include Path")
            prop_split(col, exportSettings, "customPath", "Path")

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
        prop_split(col, importSettings, "drawLayer", "Import Draw Layer")

        col.prop(importSettings, "isCustom")
        col.prop(importSettings, "removeDoubles")
        col.prop(importSettings, "importNormals")


oot_dl_writer_classes = (
    OOT_ExportDL,
    OOT_ImportDL,
    OOTDLExportSettings,
    OOTDLImportSettings,
)


oot_dl_writer_panel_classes = (OOT_ExportDLPanel,)


def dl_writer_panel_register():
    for cls in oot_dl_writer_panel_classes:
        register_class(cls)


def dl_writer_panel_unregister():
    for cls in oot_dl_writer_panel_classes:
        unregister_class(cls)


def dl_writer_register():
    for cls in oot_dl_writer_classes:
        register_class(cls)


def dl_writer_unregister():
    for cls in reversed(oot_dl_writer_classes):
        unregister_class(cls)
