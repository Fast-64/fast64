from bpy.types import Scene
from bpy.props import StringProperty, BoolProperty
from bpy.utils import register_class, unregister_class
from .....utility import prop_split
from .....panels import OOT_Panel
from .operators import OOT_ExportAnim, OOT_ImportAnim


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
