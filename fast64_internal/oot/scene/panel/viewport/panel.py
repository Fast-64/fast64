from bpy.utils import register_class, unregister_class
from .....utility import customExportWarning, prop_split
from ....c_writer.oot_scene_bootup import OOT_ClearBootupScene, ootSceneBootupRegister, ootSceneBootupUnregister
from .....panels import OOT_Panel
from ....oot_constants import ootEnumSceneID
from ....oot_scene_room import OOT_SearchSceneEnumOperator
from ....oot_utility import getEnumName
from ....oot_level import OOTExportSceneSettingsProperty, OOTImportSceneSettingsProperty, OOTRemoveSceneSettingsProperty
from ....oot_level_parser import OOT_ImportScene
from .operators import OOT_ExportScene, OOT_RemoveScene


class OOT_ExportScenePanel(OOT_Panel):
    bl_idname = "OOT_PT_export_level"
    bl_label = "OOT Scene Exporter"

    def drawSceneSearchOp(self, layout, context, enumValue, opName):
        searchBox = layout.box().row()
        searchBox.operator(OOT_SearchSceneEnumOperator.bl_idname, icon="VIEWZOOM", text="").opName = opName
        searchBox.label(text=getEnumName(ootEnumSceneID, enumValue))

    def draw(self, context):
        col = self.layout.column()
        exportOp: OOT_ExportScene = col.operator(OOT_ExportScene.bl_idname)
        # if not bpy.context.scene.ignoreTextureRestrictions:
        # 	col.prop(context.scene, 'saveTextures')
        settings: OOTExportSceneSettingsProperty = context.scene.ootSceneExportSettings
        if settings.customExport:
            prop_split(col, settings, "exportPath", "Directory")
            prop_split(col, settings, "name", "Name")
            customExportWarning(col)
        else:
            self.drawSceneSearchOp(col, context, settings.option, "Export")
            if settings.option == "Custom":
                prop_split(col, settings, "subFolder", "Subfolder")
                prop_split(col, settings, "name", "Name")

        prop_split(col, context.scene, "ootSceneExportObj", "Scene Object")

        if context.scene.fast64.oot.hackerFeaturesEnabled:
            bootOptions = context.scene.fast64.oot.bootupSceneOptions
            col.prop(bootOptions, "bootToScene", text="Boot To Scene (HackerOOT)")
            if bootOptions.bootToScene:
                col.prop(bootOptions, "newGameOnly")
                prop_split(col, bootOptions, "bootMode", "Boot Mode")
                if bootOptions.bootMode == "Play":
                    prop_split(col, bootOptions, "newGameName", "New Game Name")
                if bootOptions.bootMode != "Map Select":
                    prop_split(col, bootOptions, "spawnIndex", "Spawn")
                    col.prop(bootOptions, "overrideHeader")
                    if bootOptions.overrideHeader:
                        prop_split(col, bootOptions, "headerOption", "Header Option")
                        if bootOptions.headerOption == "Cutscene":
                            prop_split(col, bootOptions, "cutsceneIndex", "Cutscene Index")
            col.label(text="Note: Scene boot config changes aren't detected by the make process.", icon="ERROR")
            col.operator(OOT_ClearBootupScene.bl_idname, text="Undo Boot To Scene (HackerOOT Repo)")

        col.prop(settings, "singleFile")
        col.prop(settings, "customExport")

        importSettings: OOTImportSceneSettingsProperty = context.scene.ootSceneImportSettings
        importOp: OOT_ImportScene = col.operator(OOT_ImportScene.bl_idname)
        if not importSettings.isCustomDest:
            self.drawSceneSearchOp(col, context, importSettings.option, "Import")
        importSettings.draw(col, importSettings.option)

        removeSettings: OOTRemoveSceneSettingsProperty = context.scene.ootSceneRemoveSettings
        removeOp: OOT_RemoveScene = col.operator(OOT_RemoveScene.bl_idname, text="Remove Scene")
        self.drawSceneSearchOp(col, context, removeSettings.option, "Remove")


oot_level_classes = (
    OOT_ExportScene,
    OOT_ImportScene,
    OOT_RemoveScene,
)

oot_level_panel_classes = (OOT_ExportScenePanel,)


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


def oot_level_unregister():
    for cls in reversed(oot_level_classes):
        unregister_class(cls)

    ootSceneBootupUnregister()
