from bpy.types import Operator, Mesh
from bpy.path import abspath
from bpy.ops import object
from mathutils import Matrix, Vector
from .....utility import PluginError, raisePluginError
from ....oot_utility import ootGetObjectPath
from ....oot_collision import exportCollisionToC


class OOT_ExportCollision(Operator):
    # set bl_ properties
    bl_idname = "object.oot_export_collision"
    bl_label = "Export Collision"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        obj = None
        if context.mode != "OBJECT":
            object.mode_set(mode="OBJECT")
        if len(context.selected_objects) == 0:
            raise PluginError("No object selected.")
        obj = context.active_object
        if type(obj.data) is not Mesh:
            raise PluginError("No mesh object selected.")

        finalTransform = Matrix.Scale(context.scene.ootActorBlenderScale, 4)

        try:
            scaleValue = context.scene.ootBlenderScale
            finalTransform = Matrix.Diagonal(Vector((scaleValue, scaleValue, scaleValue))).to_4x4()

            includeChildren = context.scene.ootColIncludeChildren
            name = context.scene.ootColName
            isCustomExport = context.scene.ootColCustomExport
            folderName = context.scene.ootColFolder
            exportPath = abspath(context.scene.ootColExportPath)

            filepath = ootGetObjectPath(isCustomExport, exportPath, folderName)
            exportCollisionToC(obj, finalTransform, includeChildren, name, isCustomExport, folderName, filepath)

            self.report({"INFO"}, "Success!")
            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set
