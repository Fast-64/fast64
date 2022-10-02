from bpy.types import Operator, Armature, Mesh
from bpy.ops import object
from bpy.path import abspath
from os import path
from mathutils import Matrix
from ....utility import PluginError, raisePluginError
from ....f3d.f3d_gbi import DLFormat
from .classes import OOTSkeletonImportSettings, OOTSkeletonExportSettings
from ...oot_utility import ootGetObjectPath
from ...oot_skeleton import ootImportSkeletonC, ootConvertArmatureToC


class OOT_ImportSkeleton(Operator):
    # set bl_ properties
    bl_idname = "object.oot_import_skeleton"
    bl_label = "Import Skeleton"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        armatureObj = None
        if context.mode != "OBJECT":
            object.mode_set(mode="OBJECT")

        try:
            importSettings: OOTSkeletonImportSettings = context.scene.fast64.oot.skeletonImportSettings

            importPath = abspath(importSettings.customPath)
            isCustomImport = importSettings.isCustom
            folderName = importSettings.folder
            scale = context.scene.ootActorBlenderScale
            decompPath = abspath(context.scene.ootDecompPath)

            filepaths = [ootGetObjectPath(isCustomImport, importPath, folderName)]
            if not isCustomImport:
                filepaths.append(path.join(context.scene.ootDecompPath, "assets/objects/gameplay_keep/gameplay_keep.c"))

            ootImportSkeletonC(filepaths, scale, decompPath, importSettings)

            self.report({"INFO"}, "Success!")
            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


class OOT_ExportSkeleton(Operator):
    # set bl_ properties
    bl_idname = "object.oot_export_skeleton"
    bl_label = "Export Skeleton"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        armatureObj = None
        if context.mode != "OBJECT":
            object.mode_set(mode="OBJECT")
        if len(context.selected_objects) == 0:
            raise PluginError("Armature not selected.")
        armatureObj = context.active_object
        if type(armatureObj.data) is not Armature:
            raise PluginError("Armature not selected.")

        if len(armatureObj.children) == 0 or not isinstance(armatureObj.children[0].data, Mesh):
            raise PluginError("Armature does not have any mesh children, or " + "has a non-mesh child.")

        obj = armatureObj.children[0]
        finalTransform = Matrix.Scale(context.scene.ootActorBlenderScale, 4)

        try:
            exportSettings: OOTSkeletonExportSettings = context.scene.fast64.oot.skeletonExportSettings

            saveTextures = context.scene.saveTextures
            isHWv1 = context.scene.isHWv1
            f3dType = context.scene.f3d_type
            drawLayer = armatureObj.ootDrawLayer

            ootConvertArmatureToC(
                armatureObj, finalTransform, f3dType, isHWv1, DLFormat.Static, saveTextures, drawLayer, exportSettings
            )

            self.report({"INFO"}, "Success!")
            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set
