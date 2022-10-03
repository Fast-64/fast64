from bpy.types import Scene
from bpy.props import StringProperty, BoolProperty
from bpy.utils import register_class, unregister_class
from ....utility import prop_split
from ...panel import OOT_Panel
from .operators import OOT_ExportAnim, OOT_ImportAnim


class OOT_ExportAnimPanel(OOT_Panel):
    bl_idname = "OOT_PT_export_anim"
    bl_label = "OOT Animation Exporter"

    # called every frame
    def draw(self, context):
        col = self.layout.column()

        col.operator(OOT_ExportAnim.bl_idname)
        prop_split(col, context.scene, "ootAnimSkeletonName", "Skeleton Name")
        if context.scene.ootAnimIsCustomExport:
            prop_split(col, context.scene, "ootAnimExportCustomPath", "Folder")
        else:
            prop_split(col, context.scene, "ootAnimExportFolderName", "Object")
        col.prop(context.scene, "ootAnimIsCustomExport")

        col.operator(OOT_ImportAnim.bl_idname)
        prop_split(col, context.scene, "ootAnimName", "Anim Name")

        if context.scene.ootAnimIsCustomImport:
            prop_split(col, context.scene, "ootAnimImportCustomPath", "File")
        else:
            prop_split(col, context.scene, "ootAnimImportFolderName", "Object")
        col.prop(context.scene, "ootAnimIsCustomImport")


oot_anim_classes = (
    OOT_ExportAnim,
    OOT_ImportAnim,
)

oot_anim_panels = (OOT_ExportAnimPanel,)


def oot_anim_panel_register():
    for cls in oot_anim_panels:
        register_class(cls)


def oot_anim_panel_unregister():
    for cls in oot_anim_panels:
        unregister_class(cls)


def oot_anim_register():
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


def oot_anim_unregister():
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
