from bpy.types import Operator
from bpy.utils import register_class, unregister_class
from bpy.ops import object
from mathutils import Matrix

from ...utility import PluginError, raisePluginError
from ..utility import getOOTScale
from ..exporter.collision import CollisionHeader
from .properties import OOTCollisionExportSettings


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
        if obj.type != "MESH":
            raise PluginError("No mesh object selected.")

        try:
            transform = Matrix.Scale(getOOTScale(obj.ootActorScale), 4)
            settings: OOTCollisionExportSettings = context.scene.fast64.oot.collisionExportSettings
            CollisionHeader.export(obj, transform, settings)

            self.report({"INFO"}, "Success!")
            return {"FINISHED"}
        except Exception as e:
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


oot_col_classes = (OOT_ExportCollision,)


def collision_ops_register():
    for cls in oot_col_classes:
        register_class(cls)


def collision_ops_unregister():
    for cls in reversed(oot_col_classes):
        unregister_class(cls)
