from bpy.types import Operator, Armature, Mesh
from bpy.ops import object
from bpy.path import abspath
from mathutils import Matrix
from .....utility import PluginError, raisePluginError
from .....f3d.f3d_gbi import DLFormat
from ....oot_utility import getOOTScale
from ....oot_skeleton import ootImportSkeletonC, ootConvertArmatureToC
from .classes import OOTSkeletonImportSettings, OOTSkeletonExportSettings


class OOT_ImportSkeleton(Operator):
    # set bl_ properties
    bl_idname = "object.oot_import_skeleton"
    bl_label = "Import Skeleton"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        if context.mode != "OBJECT":
            object.mode_set(mode="OBJECT")

        try:
            importSettings: OOTSkeletonImportSettings = context.scene.fast64.oot.skeletonImportSettings
            decompPath = abspath(context.scene.ootDecompPath)

            ootImportSkeletonC(decompPath, importSettings)

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
        finalTransform = Matrix.Scale(getOOTScale(armatureObj.ootActorScale), 4)

        # Rotation must be applied before exporting skeleton.
        # For some reason this does not work if done on the duplicate generated later, so we have to do it before then.
        object.select_all(action="DESELECT")
        armatureObj.select_set(True)
        object.transform_apply(location=False, rotation=True, scale=True, properties=False)
        object.select_all(action="DESELECT")

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
