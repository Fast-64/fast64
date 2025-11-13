from bpy.utils import register_class, unregister_class
from bpy.types import Operator

from ...utility import raisePluginError


class Z64_ExportAnimatedMaterials(Operator):
    bl_idname = "object.z64_export_animated_materials"
    bl_label = "Export Animated Materials"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        from ..exporter.scene.animated_mats import SceneAnimatedMaterial

        try:
            SceneAnimatedMaterial.export()
            self.report({"INFO"}, "Success!")
            return {"FINISHED"}
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}


class Z64_ImportAnimatedMaterials(Operator):
    bl_idname = "object.z64_import_animated_materials"
    bl_label = "Import Animated Materials"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        from ..exporter.scene.animated_mats import SceneAnimatedMaterial

        try:
            SceneAnimatedMaterial.from_data()
            self.report({"INFO"}, "Success!")
            return {"FINISHED"}
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}


classes = (
    Z64_ExportAnimatedMaterials,
    Z64_ImportAnimatedMaterials,
)


def animated_mats_ops_register():
    for cls in classes:
        register_class(cls)


def animated_mats_ops_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
