from bpy.types import Scene
from bpy.props import StringProperty, BoolProperty
from bpy.utils import register_class, unregister_class
from ...panel import OOT_Panel
from ....utility import prop_split
from .operators import OOT_ExportCollision


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


def collision_panel_register():
    for cls in oot_col_panel_classes:
        register_class(cls)


def collision_panel_unregister():
    for cls in oot_col_panel_classes:
        unregister_class(cls)


def collision_register():
    for cls in oot_col_classes:
        register_class(cls)

    # Collision
    Scene.ootColExportPath = StringProperty(name="Directory", subtype="FILE_PATH")
    Scene.ootColIncludeChildren = BoolProperty(name="Include child objects", default=True)
    Scene.ootColName = StringProperty(name="Name", default="collision")
    Scene.ootColCustomExport = BoolProperty(name="Custom Export Path")
    Scene.ootColFolder = StringProperty(name="Object Name", default="gameplay_keep")


def collision_unregister():
    # Collision
    del Scene.ootColExportPath
    del Scene.ootColName
    del Scene.ootColIncludeChildren
    del Scene.ootColCustomExport
    del Scene.ootColFolder

    for cls in reversed(oot_col_classes):
        unregister_class(cls)
