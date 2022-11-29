import os
from bpy.utils import register_class, unregister_class
from bpy.types import Scene, Object
from bpy.props import PointerProperty
from .....utility import customExportWarning, prop_split
from .....panels import OOT_Panel
from ....scene.exporter.to_c import OOT_ClearBootupScene, ootSceneBootupRegister, ootSceneBootupUnregister
from ....oot_constants import ootEnumSceneID
from ....oot_utility import getEnumName
from ..properties import OOT_SearchSceneEnumOperator
from .classes import OOTExportSceneSettingsProperty, OOTImportSceneSettingsProperty, OOTRemoveSceneSettingsProperty
from .operators import OOT_ImportScene, OOT_ExportScene, OOT_RemoveScene


class OOT_ExportScenePanel(OOT_Panel):
    bl_idname = "OOT_PT_export_level"
    bl_label = "OOT Scene Exporter"

    def drawSceneSearchOp(self, layout, enumValue, opName):
        searchBox = layout.box().row()
        searchBox.operator(OOT_SearchSceneEnumOperator.bl_idname, icon="VIEWZOOM", text="").opName = opName
        searchBox.label(text=getEnumName(ootEnumSceneID, enumValue))

    def draw(self, context):
        col = self.layout.column()

        # Scene Exporter
        exportBox = col.box().column()
        exportBox.label(text="Scene Exporter")

        settings: OOTExportSceneSettingsProperty = context.scene.ootSceneExportSettings
        if settings.customExport:
            prop_split(exportBox, settings, "exportPath", "Directory")
            prop_split(exportBox, settings, "name", "Name")
            customExportWarning(exportBox)
        else:
            self.drawSceneSearchOp(exportBox, settings.option, "Export")
            if settings.option == "Custom":
                prop_split(exportBox, settings, "subFolder", "Subfolder")
                prop_split(exportBox, settings, "name", "Name")

        prop_split(exportBox, context.scene, "ootSceneExportObj", "Scene Object")

        exportBox.prop(settings, "singleFile")
        exportBox.prop(settings, "customExport")

        if context.scene.fast64.oot.hackerFeaturesEnabled:
            hackerOoTBox = exportBox.box().column()
            hackerOoTBox.label(text="HackerOoT Options")

            bootOptions = context.scene.fast64.oot.bootupSceneOptions
            hackerOoTBox.prop(bootOptions, "bootToScene", text="Boot To Scene (HackerOOT)")
            if bootOptions.bootToScene:
                hackerOoTBox.prop(bootOptions, "newGameOnly")
                prop_split(hackerOoTBox, bootOptions, "bootMode", "Boot Mode")
                if bootOptions.bootMode == "Play":
                    prop_split(hackerOoTBox, bootOptions, "newGameName", "New Game Name")
                if bootOptions.bootMode != "Map Select":
                    prop_split(hackerOoTBox, bootOptions, "spawnIndex", "Spawn")
                    hackerOoTBox.prop(bootOptions, "overrideHeader")
                    if bootOptions.overrideHeader:
                        prop_split(hackerOoTBox, bootOptions, "headerOption", "Header Option")
                        if bootOptions.headerOption == "Cutscene":
                            prop_split(hackerOoTBox, bootOptions, "cutsceneIndex", "Cutscene Index")
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

        importSettings.draw(importBox, importSettings.option)
        importBox.operator(OOT_ImportScene.bl_idname)

        # Remove Scene
        removeBox = col.box().column()
        removeBox.label(text="Remove Scene")

        removeSettings: OOTRemoveSceneSettingsProperty = context.scene.ootSceneRemoveSettings
        self.drawSceneSearchOp(removeBox, removeSettings.option, "Remove")

        if removeSettings.option == "Custom":
            prop_split(removeBox, removeSettings, "subFolder", "Subfolder")
            prop_split(removeBox, removeSettings, "name", "Name")

            exportPath = (
                context.scene.ootDecompPath + f"assets/scenes/{removeSettings.subFolder}/{removeSettings.name}/"
            )

        removeRow = removeBox.row()
        removeRow.operator(OOT_RemoveScene.bl_idname, text="Remove Scene")

        if removeSettings.option == "Custom" and not os.path.exists(exportPath):
            removeRow.enabled = False
            removeBox.label(text="This path doesn't exist.")
        else:
            removeRow.enabled = True


oot_level_classes = (
    OOT_ExportScene,
    OOT_ImportScene,
    OOT_RemoveScene,
    OOTImportSceneSettingsProperty,
    OOTExportSceneSettingsProperty,
    OOTRemoveSceneSettingsProperty,
)

oot_level_panel_classes = (OOT_ExportScenePanel,)


def isSceneObj(self, obj):
    return obj.data is None and obj.ootEmptyType == "Scene"


def oot_level_panel_register():
    for cls in oot_level_panel_classes:
        register_class(cls)


def oot_level_panel_unregister():
    for cls in oot_level_panel_classes:
        unregister_class(cls)


def oot_level_register():
    for cls in oot_level_classes:
        register_class(cls)

    ootSceneBootupRegister()

    Scene.ootSceneExportObj = PointerProperty(type=Object, poll=isSceneObj)
    Scene.ootSceneExportSettings = PointerProperty(type=OOTExportSceneSettingsProperty)
    Scene.ootSceneImportSettings = PointerProperty(type=OOTImportSceneSettingsProperty)
    Scene.ootSceneRemoveSettings = PointerProperty(type=OOTRemoveSceneSettingsProperty)


def oot_level_unregister():
    del Scene.ootSceneExportObj
    del Scene.ootSceneExportSettings
    del Scene.ootSceneImportSettings
    del Scene.ootSceneRemoveSettings

    for cls in reversed(oot_level_classes):
        unregister_class(cls)

    ootSceneBootupUnregister()
