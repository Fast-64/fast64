from bpy.types import Scene, Operator, Mesh
from bpy.props import StringProperty, BoolProperty
from bpy.utils import register_class, unregister_class
from bpy.path import abspath
from bpy.ops import object
from mathutils import Matrix, Vector
from ....panels import OOT_Panel
from ....utility import PluginError, raisePluginError, prop_split
from ...oot_utility import ootGetObjectPath, getOOTScale
from ...oot_collision import exportCollisionToC


#############
# Operators #
#############
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

        finalTransform = Matrix.Scale(getOOTScale(obj.ootActorScale), 4)

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


#############
#   Panel   #
#############
class OOT_ExportCollisionPanel(OOT_Panel):
    bl_idname = "OOT_PT_export_collision"
    bl_label = "OOT Collision Exporter"

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.operator(OOT_ExportCollision.bl_idname)

        prop_split(col, context.scene, "ootColName", "Name")
        if context.scene.ootColCustomExport:
            prop_split(col, context.scene, "ootColExportPath", "Custom Folder")
        else:
            prop_split(col, context.scene, "ootColFolder", "Object")
        col.prop(context.scene, "ootColCustomExport")
        col.prop(context.scene, "ootColIncludeChildren")


oot_col_classes = (OOT_ExportCollision,)

oot_col_panel_classes = (OOT_ExportCollisionPanel,)


def collision_viewport_panel_register():
    for cls in oot_col_panel_classes:
        register_class(cls)


def collision_viewport_panel_unregister():
    for cls in oot_col_panel_classes:
        unregister_class(cls)


def collision_viewport_classes_register():
    for cls in oot_col_classes:
        register_class(cls)

    # Collision
    Scene.ootColExportPath = StringProperty(name="Directory", subtype="FILE_PATH")
    Scene.ootColIncludeChildren = BoolProperty(name="Include child objects", default=True)
    Scene.ootColName = StringProperty(name="Name", default="collision")
    Scene.ootColCustomExport = BoolProperty(name="Custom Export Path")
    Scene.ootColFolder = StringProperty(name="Object Name", default="gameplay_keep")


def collision_viewport_classes_unregister():
    # Collision
    del Scene.ootColExportPath
    del Scene.ootColName
    del Scene.ootColIncludeChildren
    del Scene.ootColCustomExport
    del Scene.ootColFolder

    for cls in reversed(oot_col_classes):
        unregister_class(cls)
