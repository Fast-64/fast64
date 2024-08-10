import bpy
import os

from bpy.types import UILayout
from bpy.utils import register_class, unregister_class
from ...panels import OOT_Panel
from ..oot_constants import ootEnumSceneID
from ..oot_utility import getEnumName
from .properties import (
    OOTExportSceneSettingsProperty,
    OOTImportSceneSettingsProperty,
    OOTRemoveSceneSettingsProperty,
    OOTBootupSceneOptions,
)

from .operators import (
    OOT_ImportScene,
    OOT_ExportScene,
    OOT_RemoveScene,
    OOT_ClearBootupScene,
    OOT_SearchSceneEnumOperator,
)


class OOT_ExportScenePanel(OOT_Panel):
    bl_idname = "OOT_PT_export_level"
    bl_label = "OOT Scene Exporter"

    def drawSceneSearchOp(self, layout: UILayout, enumValue: str, opName: str):
        searchBox = layout.box().row()
        searchBox.operator(OOT_SearchSceneEnumOperator.bl_idname, icon="VIEWZOOM", text="").opName = opName
        searchBox.label(text=getEnumName(ootEnumSceneID, enumValue))

    def draw(self, context):
        col = self.layout.column()

        # Scene Exporter
        exportBox = col.box().column()
        exportBox.label(text="Scene Exporter")

        settings: OOTExportSceneSettingsProperty = context.scene.ootSceneExportSettings
        if not settings.customExport:
            self.drawSceneSearchOp(exportBox, settings.option, "Export")
        settings.draw_props(exportBox)

        if context.scene.fast64.oot.hackerFeaturesEnabled:
            hackerOoTBox = exportBox.box().column()
            hackerOoTBox.label(text="HackerOoT Options")

            bootOptions: OOTBootupSceneOptions = context.scene.fast64.oot.bootupSceneOptions
            bootOptions.draw_props(hackerOoTBox)

            hackerOoTBox.label(
                text="Note: Scene boot config changes aren't detected by the make process.", icon="ERROR"
            )
            hackerOoTBox.operator(OOT_ClearBootupScene.bl_idname, text="Undo Boot To Scene (HackerOOT Repo)")

        exportBox.operator(OOT_ExportScene.bl_idname)

        # Scene Importer
        importBox = col.box().column()
        importBox.label(text="Scene Importer")

        importSettings: OOTImportSceneSettingsProperty = context.scene.ootSceneImportSettings

        if not importSettings.isCustomDest:
            self.drawSceneSearchOp(importBox, importSettings.option, "Import")

        importSettings.draw_props(importBox, importSettings.option)
        importBox.operator(OOT_ImportScene.bl_idname)

        # Remove Scene
        removeBox = col.box().column()
        removeBox.label(text="Remove Scene")

        removeSettings: OOTRemoveSceneSettingsProperty = context.scene.ootSceneRemoveSettings
        self.drawSceneSearchOp(removeBox, removeSettings.option, "Remove")
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
