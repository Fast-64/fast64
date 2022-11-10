from bpy.types import Scene, Object
from bpy.props import StringProperty, EnumProperty, BoolProperty, PointerProperty
from bpy.utils import register_class, unregister_class
from .....utility import customExportWarning, prop_split
from ....c_writer.oot_scene_bootup import OOT_ClearBootupScene, ootSceneBootupRegister, ootSceneBootupUnregister
from .....panels import OOT_Panel
from ....oot_constants import ootEnumSceneID
from ....oot_scene_room import OOT_SearchSceneEnumOperator
from ....oot_utility import getEnumName
from .operators import OOT_ExportScene, OOT_RemoveScene


class OOT_ExportScenePanel(OOT_Panel):
    bl_idname = "OOT_PT_export_level"
    bl_label = "OOT Scene Exporter"

    def draw(self, context):
        col = self.layout.column()
        col.operator(OOT_ExportScene.bl_idname)
        # if not bpy.context.scene.ignoreTextureRestrictions:
        # 	col.prop(context.scene, 'saveTextures')
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

        col.prop(context.scene, "ootSceneSingleFile")
        col.prop(context.scene, "ootSceneCustomExport")
        if context.scene.ootSceneCustomExport:
            prop_split(col, context.scene, "ootSceneExportPath", "Directory")
            prop_split(col, context.scene, "ootSceneName", "Name")
            customExportWarning(col)
        else:
            col.operator(OOT_SearchSceneEnumOperator.bl_idname, icon="VIEWZOOM")
            col.box().column().label(text=getEnumName(ootEnumSceneID, context.scene.ootSceneOption))
            # col.prop(context.scene, 'ootSceneOption')
            if context.scene.ootSceneOption == "Custom":
                prop_split(col, context.scene, "ootSceneSubFolder", "Subfolder")
                prop_split(col, context.scene, "ootSceneName", "Name")
            col.operator(OOT_RemoveScene.bl_idname, text="Remove Scene")


oot_level_classes = (
    OOT_ExportScene,
    OOT_RemoveScene,
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

    Scene.ootSceneName = StringProperty(name="Name", default="spot03")
    Scene.ootSceneSubFolder = StringProperty(name="Subfolder", default="overworld")
    Scene.ootSceneOption = EnumProperty(name="Scene", items=ootEnumSceneID, default="SCENE_YDAN")
    Scene.ootSceneExportPath = StringProperty(name="Directory", subtype="FILE_PATH")
    Scene.ootSceneCustomExport = BoolProperty(name="Custom Export Path")
    Scene.ootSceneExportObj = PointerProperty(type=Object, poll=isSceneObj)
    Scene.ootSceneSingleFile = BoolProperty(
        name="Export as Single File",
        default=False,
        description="Does not split the scene and rooms into multiple files.",
    )


def oot_level_unregister():
    for cls in reversed(oot_level_classes):
        unregister_class(cls)

    ootSceneBootupUnregister()

    del Scene.ootSceneName
    del Scene.ootSceneExportPath
    del Scene.ootSceneCustomExport
    del Scene.ootSceneOption
    del Scene.ootSceneSubFolder
    del Scene.ootSceneSingleFile
