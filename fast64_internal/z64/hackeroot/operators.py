from bpy.types import Operator
from bpy.utils import register_class, unregister_class

from ..exporter.decomp_edit.config import Config


class HackerOoT_ClearBootupScene(Operator):
    bl_idname = "object.hackeroot_clear_bootup_scene"
    bl_label = "Undo Boot To Scene"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        Config.clearBootupScene(context.scene.fast64.oot.get_decomp_path() / "include/config/config_debug.h")
        self.report({"INFO"}, "Success!")
        return {"FINISHED"}


classes = (HackerOoT_ClearBootupScene,)


def hackeroot_ops_register():
    for cls in classes:
        register_class(cls)


def hackeroot_ops_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
