from bpy.types import Operator, Armature
from bpy.ops import object
from bpy.path import abspath
from ....utility import PluginError, raisePluginError
from ...oot_utility import ootGetObjectPath
from ...oot_anim import exportAnimationC, ootImportAnimationC


class OOT_ExportAnim(Operator):
    bl_idname = "object.oot_export_anim"
    bl_label = "Export Animation"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        try:
            if len(context.selected_objects) == 0 or not isinstance(context.selected_objects[0].data, Armature):
                raise PluginError("Armature not selected.")
            if len(context.selected_objects) > 1:
                raise PluginError("Multiple objects selected, make sure to select only one.")
            armatureObj = context.selected_objects[0]
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        try:
            isCustomExport = context.scene.ootAnimIsCustomExport
            exportPath = abspath(context.scene.ootAnimExportCustomPath)
            folderName = context.scene.ootAnimExportFolderName
            skeletonName = context.scene.ootAnimSkeletonName

            path = ootGetObjectPath(isCustomExport, exportPath, folderName)

            exportAnimationC(armatureObj, path, isCustomExport, folderName, skeletonName)
            self.report({"INFO"}, "Success!")

        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set

        return {"FINISHED"}  # must return a set


class OOT_ImportAnim(Operator):
    bl_idname = "object.oot_import_anim"
    bl_label = "Import Animation"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        try:
            if len(context.selected_objects) == 0 or not isinstance(context.selected_objects[0].data, Armature):
                raise PluginError("Armature not selected.")
            if len(context.selected_objects) > 1:
                raise PluginError("Multiple objects selected, make sure to select only one.")
            armatureObj = context.selected_objects[0]
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        try:
            isCustomImport = context.scene.ootAnimIsCustomImport
            folderName = context.scene.ootAnimImportFolderName
            importPath = abspath(context.scene.ootAnimImportCustomPath)
            animName = context.scene.ootAnimName
            actorScale = context.scene.ootActorBlenderScale

            path = ootGetObjectPath(isCustomImport, importPath, folderName)

            ootImportAnimationC(armatureObj, path, animName, actorScale)
            self.report({"INFO"}, "Success!")

        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set

        return {"FINISHED"}  # must return a set
