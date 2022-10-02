from bpy.types import Operator
from bpy.ops import object
from bpy.path import abspath
from mathutils import Matrix, Vector
from ....f3d.f3d_gbi import DLFormat
from ...c_writer.oot_scene_table_c import modifySceneTable
from ...c_writer.oot_spec import modifySegmentDefinition
from ...c_writer.oot_scene_folder import deleteSceneFiles
from ....utility import PluginError, raisePluginError
from ...oot_utility import ExportInfo
from ...oot_level_writer import sceneNameFromID, ootExportSceneToC


class OOT_ExportScene(Operator):
    bl_idname = "object.oot_export_level"
    bl_label = "Export Scene"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        activeObj = None
        try:
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")
            activeObj = context.view_layer.objects.active

            obj = context.scene.ootSceneExportObj
            if obj is None:
                raise PluginError("Scene object input not set.")
            elif obj.data is not None or obj.ootEmptyType != "Scene":
                raise PluginError("The input object is not an empty with the Scene type.")

            scaleValue = context.scene.ootBlenderScale
            finalTransform = Matrix.Diagonal(Vector((scaleValue, scaleValue, scaleValue))).to_4x4()

        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}
        try:
            levelName = context.scene.ootSceneName
            if context.scene.ootSceneCustomExport:
                exportInfo = ExportInfo(True, abspath(context.scene.ootSceneExportPath), None, levelName)
            else:
                if context.scene.ootSceneOption == "Custom":
                    subfolder = "assets/scenes/" + context.scene.ootSceneSubFolder + "/"
                else:
                    levelName = sceneNameFromID(context.scene.ootSceneOption)
                    subfolder = None
                exportInfo = ExportInfo(False, abspath(context.scene.ootDecompPath), subfolder, levelName)

            bootOptions = context.scene.fast64.oot.bootupSceneOptions
            hackerFeaturesEnabled = context.scene.fast64.oot.hackerFeaturesEnabled
            ootExportSceneToC(
                obj,
                finalTransform,
                context.scene.f3d_type,
                context.scene.isHWv1,
                levelName,
                DLFormat.Static,
                context.scene.saveTextures,
                exportInfo,
                bootOptions if hackerFeaturesEnabled else None,
            )

            self.report({"INFO"}, "Success!")

            context.view_layer.objects.active = activeObj
            if activeObj is not None:
                activeObj.select_set(True)

            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")
            context.view_layer.objects.active = activeObj
            if activeObj is not None:
                activeObj.select_set(True)
            raisePluginError(self, e)
            return {"CANCELLED"}


class OOT_RemoveScene(Operator):
    bl_idname = "object.oot_remove_level"
    bl_label = "OOT Remove Scene"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        levelName = context.scene.ootSceneName
        if context.scene.ootSceneCustomExport:
            self.report({"ERROR"}, "You can only remove scenes from your decomp path.")
            return {"FINISHED"}

        if context.scene.ootSceneOption == "Custom":
            subfolder = "assets/scenes/" + context.scene.ootSceneSubFolder + "/"
        else:
            levelName = sceneNameFromID(context.scene.ootSceneOption)
            subfolder = None
        exportInfo = ExportInfo(False, abspath(context.scene.ootDecompPath), subfolder, levelName)

        # removal logic
        modifySceneTable(None, exportInfo)
        modifySegmentDefinition(None, exportInfo, None)
        deleteSceneFiles(exportInfo)

        self.report({"INFO"}, "Success!")
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Are you sure you want to remove this scene?")
