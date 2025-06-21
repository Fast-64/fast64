from bpy.types import Panel, Camera
from bpy.utils import register_class, unregister_class
from ...panels import OOT_Panel
from .properties import OOTCollisionExportSettings, OOTCameraPositionProperty, OOTMaterialCollisionProperty
from .operators import OOT_ExportCollision


class OOT_CameraPosPanel(Panel):
    bl_label = "Camera Position Inspector"
    bl_idname = "OBJECT_PT_OOT_Camera_Position_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "OOT" and isinstance(context.object.data, Camera)

    def draw(self, context):
        box = self.layout.box().column()
        obj = context.object

        box.box().label(text="Camera Data")
        camPosProps: OOTCameraPositionProperty = obj.ootCameraPositionProperty
        camPosProps.draw_props(box, obj)


class OOT_CollisionPanel(Panel):
    bl_label = "Collision Inspector"
    bl_idname = "MATERIAL_PT_OOT_Collision_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "OOT" and context.material is not None

    def draw(self, context):
        box = self.layout.box().column()

        collisionProp: OOTMaterialCollisionProperty = context.material.ootCollisionProperty
        collisionProp.draw_props(box)


class OOT_ExportCollisionPanel(OOT_Panel):
    bl_idname = "OOT_PT_export_collision"
    bl_label = "OOT Collision Exporter"

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.operator(OOT_ExportCollision.bl_idname)

        exportSettings: OOTCollisionExportSettings = context.scene.fast64.oot.collisionExportSettings
        exportSettings.draw_props(col)


oot_col_panel_classes = (
    OOT_CameraPosPanel,
    OOT_CollisionPanel,
    OOT_ExportCollisionPanel,
)


def collision_panels_register():
    for cls in oot_col_panel_classes:
        register_class(cls)


def collision_panels_unregister():
    for cls in oot_col_panel_classes:
        unregister_class(cls)
