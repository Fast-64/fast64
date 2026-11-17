from bpy.types import UILayout
from bpy.utils import register_class, unregister_class
from ...panels import OOT_Panel
from ...game_data import game_data
from ..constants import ootEnumSceneID, mm_enum_scene_id
from ..utility import getEnumName
from .properties import (
    OOTExportSceneSettingsProperty,
    OOTImportSceneSettingsProperty,
    OOTRemoveSceneSettingsProperty,
)

from .operators import (
    OOT_ImportScene,
    OOT_ExportScene,
    OOT_RemoveScene,
    OOT_SearchSceneEnumOperator,
    MM_SearchSceneEnumOperator,
)


class OOT_ExportScenePanel(OOT_Panel):
    bl_idname = "Z64_PT_export_level"
    bl_label = "Scene Exporter"

    def drawSceneSearchOp(self, layout: UILayout, enumValue: str, opName: str):
        searchBox = layout.box().row()

        if game_data.z64.is_oot():
            searchBox.operator(OOT_SearchSceneEnumOperator.bl_idname, icon="VIEWZOOM", text="").opName = opName
            searchBox.label(text=getEnumName(ootEnumSceneID, enumValue))
        else:
            searchBox.operator(MM_SearchSceneEnumOperator.bl_idname, icon="VIEWZOOM", text="").op_name = opName
            searchBox.label(text=getEnumName(mm_enum_scene_id, enumValue))

    def draw(self, context):
        col = self.layout.column()

        # Scene Exporter
        exportBox = col.box().column()
        exportBox.label(text="Scene Exporter")

        settings: OOTExportSceneSettingsProperty = context.scene.ootSceneExportSettings
        if not settings.customExport:
            self.drawSceneSearchOp(
                exportBox, settings.option if game_data.z64.is_oot() else settings.mm_option, "Export"
            )
        settings.draw_props(exportBox)

        exportBox.operator(OOT_ExportScene.bl_idname)

        # Scene Importer
        importBox = col.box().column()
        importBox.label(text="Scene Importer")

        importSettings: OOTImportSceneSettingsProperty = context.scene.ootSceneImportSettings
        option = importSettings.option if game_data.z64.is_oot() else importSettings.mm_option

        if not importSettings.isCustomDest:
            self.drawSceneSearchOp(importBox, option, "Import")

        importSettings.draw_props(importBox, option)
        importBox.operator(OOT_ImportScene.bl_idname)

        # Remove Scene
        removeBox = col.box().column()
        removeBox.label(text="Remove Scene")

        removeSettings: OOTRemoveSceneSettingsProperty = context.scene.ootSceneRemoveSettings
        option = removeSettings.option if game_data.z64.is_oot() else removeSettings.mm_option
        self.drawSceneSearchOp(removeBox, option, "Remove")
        removeSettings.draw_props(removeBox)

        removeRow = removeBox.row()
        removeRow.operator(OOT_RemoveScene.bl_idname, text="Remove Scene")


classes = (OOT_ExportScenePanel,)


def scene_panels_register():
    for cls in classes:
        register_class(cls)


def scene_panels_unregister():
    for cls in classes:
        unregister_class(cls)
