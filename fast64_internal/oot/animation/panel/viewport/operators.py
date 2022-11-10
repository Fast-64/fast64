from bpy.types import Operator, Armature
from bpy.ops import object
from .....utility import PluginError, raisePluginError
from ....oot_utility import getOOTScale
from ....oot_anim import exportAnimationC, ootImportAnimationC


class OOT_ExportAnim(Operator):
    bl_idname = "object.oot_export_anim"
    bl_label = "Export Animation"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        try:
            if len(context.selected_objects) == 0 or not isinstance(
                context.selected_objects[0].data, Armature
            ):
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
            settings = context.scene.fast64.oot.animExportSettings
            exportAnimationC(armatureObj, settings)
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
            if len(context.selected_objects) == 0 or not isinstance(
                context.selected_objects[0].data, Armature
            ):
                raise PluginError("Armature not selected.")
            if len(context.selected_objects) > 1:
                raise PluginError("Multiple objects selected, make sure to select only one.")
            armatureObj = context.selected_objects[0]
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")

            # We need to apply scale otherwise translation imports won't be correct.
            object.select_all(action="DESELECT")
            armatureObj.select_set(True)
            context.view_layer.objects.active = armatureObj
            object.transform_apply(location=False, rotation=False, scale=True, properties=False)

        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        try:
            actorScale = getOOTScale(armatureObj.ootActorScale)
            settings = context.scene.fast64.oot.animImportSettings
            ootImportAnimationC(armatureObj, settings, actorScale)
            self.report({"INFO"}, "Success!")

        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set

        return {"FINISHED"}  # must return a set
