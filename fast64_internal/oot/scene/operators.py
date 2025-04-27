import bpy
import os

from bpy.path import abspath
from bpy.types import Operator
from bpy.props import EnumProperty, IntProperty, StringProperty
from bpy.utils import register_class, unregister_class
from bpy.ops import object
from mathutils import Matrix, Vector
from ...f3d.f3d_gbi import TextureExportSettings, DLFormat
from ...utility import PluginError, raisePluginError, ootGetSceneOrRoomHeader
from ..oot_utility import ExportInfo, RemoveInfo, sceneNameFromID
from ..oot_constants import ootEnumMusicSeq, ootEnumSceneID
from ..importer import parseScene
from ..exporter.decomp_edit.config import Config
from ..exporter import SceneExport, Files


def run_ops_without_view_layer_update(func):
    from bpy.ops import _BPyOpsSubModOp

    view_layer_update = _BPyOpsSubModOp._view_layer_update

    def dummy_view_layer_update(context):
        pass

    try:
        _BPyOpsSubModOp._view_layer_update = dummy_view_layer_update
        func()

    finally:
        _BPyOpsSubModOp._view_layer_update = view_layer_update


def parseSceneFunc():
    settings = bpy.context.scene.ootSceneImportSettings
    parseScene(settings, settings.option)


class OOT_SearchSceneEnumOperator(Operator):
    bl_idname = "object.oot_search_scene_enum_operator"
    bl_label = "Choose Scene"
    bl_property = "ootSceneID"
    bl_options = {"REGISTER", "UNDO"}

    ootSceneID: EnumProperty(items=ootEnumSceneID, default="SCENE_DEKU_TREE")
    opName: StringProperty(default="Export")

    def execute(self, context):
        if self.opName == "Export":
            context.scene.ootSceneExportSettings.option = self.ootSceneID
        elif self.opName == "Import":
            context.scene.ootSceneImportSettings.option = self.ootSceneID
        elif self.opName == "Remove":
            context.scene.ootSceneRemoveSettings.option = self.ootSceneID
        else:
            raise Exception(f'Invalid OOT scene search operator name: "{self.opName}"')

        context.region.tag_redraw()
        self.report({"INFO"}, "Selected: " + self.ootSceneID)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class OOT_SearchMusicSeqEnumOperator(Operator):
    bl_idname = "object.oot_search_music_seq_enum_operator"
    bl_label = "Search Music Sequence"
    bl_property = "ootMusicSeq"
    bl_options = {"REGISTER", "UNDO"}

    ootMusicSeq: EnumProperty(items=ootEnumMusicSeq, default="NA_BGM_FIELD_LOGIC")
    headerIndex: IntProperty(default=0, min=0)
    objName: StringProperty()

    def execute(self, context):
        sceneHeader = ootGetSceneOrRoomHeader(bpy.data.objects[self.objName], self.headerIndex, False)
        sceneHeader.musicSeq = self.ootMusicSeq
        context.region.tag_redraw()
        self.report({"INFO"}, "Selected: " + self.ootMusicSeq)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class OOT_ClearBootupScene(Operator):
    bl_idname = "object.oot_clear_bootup_scene"
    bl_label = "Undo Boot To Scene"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        Config.clearBootupScene(os.path.join(abspath(context.scene.ootDecompPath), "include/config/config_debug.h"))
        self.report({"INFO"}, "Success!")
        return {"FINISHED"}


class OOT_ImportScene(Operator):
    """Import an OOT scene from C."""

    bl_idname = "object.oot_import_level"
    bl_label = "Import Scene"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        try:
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")
            object.select_all(action="DESELECT")

            run_ops_without_view_layer_update(parseSceneFunc)

            self.report({"INFO"}, "Success!")
            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}


class OOT_ExportScene(Operator):
    """Export an OOT scene."""

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
            elif obj.type != "EMPTY" or obj.ootEmptyType != "Scene":
                raise PluginError("The input object is not an empty with the Scene type.")

            scaleValue = context.scene.ootBlenderScale
            finalTransform = Matrix.Diagonal(Vector((scaleValue, scaleValue, scaleValue))).to_4x4()

        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}
        try:
            settings = context.scene.ootSceneExportSettings
            levelName = settings.name
            option = settings.option

            bootOptions = context.scene.fast64.oot.bootupSceneOptions
            hackerFeaturesEnabled = context.scene.fast64.oot.hackerFeaturesEnabled

            if settings.customExport:
                isCustomExport = True
                exportPath = bpy.path.abspath(settings.exportPath)
                customSubPath = None
            else:
                if option == "Custom":
                    customSubPath = "assets/scenes/" + settings.subFolder + "/"
                else:
                    levelName = sceneNameFromID(option)
                    customSubPath = None
                isCustomExport = False
                exportPath = bpy.path.abspath(context.scene.ootDecompPath)

            exportInfo = ExportInfo(
                isCustomExport,
                exportPath,
                customSubPath,
                levelName,
                option,
                bpy.context.scene.saveTextures,
                settings.singleFile,
                context.scene.fast64.oot.useDecompFeatures if not hackerFeaturesEnabled else hackerFeaturesEnabled,
                bootOptions if hackerFeaturesEnabled else None,
            )

            SceneExport.export(
                obj,
                finalTransform,
                exportInfo,
            )

            self.report({"INFO"}, "Success!")

            # don't select the scene
            for elem in context.selectable_objects:
                elem.select_set(False)

            context.view_layer.objects.active = activeObj
            if activeObj is not None:
                activeObj.select_set(True)

            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")
            # don't select the scene
            for elem in context.selectable_objects:
                elem.select_set(False)
            context.view_layer.objects.active = activeObj
            if activeObj is not None:
                activeObj.select_set(True)
            raisePluginError(self, e)
            return {"CANCELLED"}


class OOT_RemoveScene(Operator):
    """Remove an OOT scene from an existing decomp directory."""

    bl_idname = "object.oot_remove_level"
    bl_label = "OOT Remove Scene"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = context.scene.ootSceneRemoveSettings  # Type: OOTRemoveSceneSettingsProperty
        option = settings.option

        if settings.customExport:
            self.report({"ERROR"}, "You can only remove scenes from your decomp path.")
            return {"FINISHED"}

        if option == "Custom":
            levelName = settings.name
            subfolder = f"assets/scenes/{settings.subFolder}/"
        else:
            levelName = sceneNameFromID(option)
            subfolder = None

        # the scene files will be removed from `assets` if it's present
        Files.remove_scene(RemoveInfo(abspath(context.scene.ootDecompPath), subfolder, levelName))

        self.report({"INFO"}, "Success!")
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Are you sure you want to remove this scene?")


classes = (
    OOT_SearchMusicSeqEnumOperator,
    OOT_SearchSceneEnumOperator,
    OOT_ClearBootupScene,
    OOT_ImportScene,
    OOT_ExportScene,
    OOT_RemoveScene,
)


def scene_ops_register():
    for cls in classes:
        register_class(cls)


def scene_ops_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
