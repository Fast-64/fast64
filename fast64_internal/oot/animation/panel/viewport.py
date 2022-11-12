from bpy.types import Scene, Operator, Armature
from bpy.props import StringProperty, BoolProperty
from bpy.utils import register_class, unregister_class
from bpy.ops import object
from ....utility import PluginError, raisePluginError, prop_split
from ....panels import OOT_Panel
from ...oot_utility import getOOTScale
from ...oot_anim import exportAnimationC, ootImportAnimationC


#############
# Operators #
#############
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


#############
#   Panel   #
#############
class OOT_ExportAnimPanel(OOT_Panel):
    bl_idname = "OOT_PT_export_anim"
    bl_label = "OOT Animation Exporter"

    # called every frame
    def draw(self, context):
        col = self.layout.column()

        col.operator(OOT_ExportAnim.bl_idname)
        exportSettings = context.scene.fast64.oot.animExportSettings
        prop_split(col, exportSettings, "skeletonName", "Anim Name Prefix")

        if exportSettings.isCustom:
            prop_split(col, exportSettings, "customPath", "Folder")
        elif not exportSettings.isLink:
            prop_split(col, exportSettings, "folderName", "Object")

        col.prop(exportSettings, "isLink")
        col.prop(exportSettings, "isCustom")

        col.operator(OOT_ImportAnim.bl_idname)
        importSettings = context.scene.fast64.oot.animImportSettings
        prop_split(col, importSettings, "animName", "Anim Header Name")

        if importSettings.isCustom:
            prop_split(col, importSettings, "customPath", "File")
        elif not importSettings.isLink:
            prop_split(col, importSettings, "folderName", "Object")

        col.prop(importSettings, "isLink")
        col.prop(importSettings, "isCustom")


oot_anim_classes = (
    OOT_ExportAnim,
    OOT_ImportAnim,
)

oot_anim_panels = (OOT_ExportAnimPanel,)


def anim_viewport_panel_register():
    for cls in oot_anim_panels:
        register_class(cls)


def anim_viewport_panel_unregister():
    for cls in oot_anim_panels:
        unregister_class(cls)


def anim_viewport_classes_register():
    Scene.ootAnimIsCustomExport = BoolProperty(name="Use Custom Path")
    Scene.ootAnimExportCustomPath = StringProperty(name="Folder", subtype="FILE_PATH")
    Scene.ootAnimExportFolderName = StringProperty(name="Animation Folder", default="object_geldb")

    Scene.ootAnimIsCustomImport = BoolProperty(name="Use Custom Path")
    Scene.ootAnimImportCustomPath = StringProperty(name="Folder", subtype="FILE_PATH")
    Scene.ootAnimImportFolderName = StringProperty(name="Animation Folder", default="object_geldb")

    Scene.ootAnimSkeletonName = StringProperty(name="Skeleton Name", default="gGerudoRedSkel")
    Scene.ootAnimName = StringProperty(name="Anim Name", default="gGerudoRedSpinAttackAnim")
    for cls in oot_anim_classes:
        register_class(cls)


def anim_viewport_classes_unregister():
    del Scene.ootAnimIsCustomExport
    del Scene.ootAnimExportCustomPath
    del Scene.ootAnimExportFolderName

    del Scene.ootAnimIsCustomImport
    del Scene.ootAnimImportCustomPath
    del Scene.ootAnimImportFolderName

    del Scene.ootAnimSkeletonName
    del Scene.ootAnimName
    for cls in reversed(oot_anim_classes):
        unregister_class(cls)
