from bpy.types import Panel, Camera
from bpy.utils import register_class, unregister_class
from ...utility import prop_split
from ...panels import OOT_Panel
from ..oot_utility import drawEnumWithCustom
from .properties import OOTCollisionExportSettings
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
        drawEnumWithCustom(box, obj.ootCameraPositionProperty, "camSType", "Camera S Type", "")
        prop_split(box, obj.ootCameraPositionProperty, "index", "Camera Index")
        box.prop(obj.ootCameraPositionProperty, "hasPositionData")
        if obj.ootCameraPositionProperty.hasPositionData:
            prop_split(box, obj.data, "angle", "Field Of View")
            prop_split(box, obj.ootCameraPositionProperty, "bgImageOverrideIndex", "BG Index Override")

        # drawParentSceneRoom(box, context.object)


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
        collisionProp = context.material.ootCollisionProperty

        box.prop(
            collisionProp,
            "expandTab",
            text="OOT Collision Properties",
            icon="TRIA_DOWN" if collisionProp.expandTab else "TRIA_RIGHT",
        )
        if collisionProp.expandTab:
            prop_split(box, collisionProp, "exitID", "Exit ID")
            prop_split(box, collisionProp, "cameraID", "Camera ID")
            prop_split(box, collisionProp, "echo", "Echo")
            prop_split(box, collisionProp, "lightingSetting", "Lighting")
            drawEnumWithCustom(box, collisionProp, "terrain", "Terrain", "")
            drawEnumWithCustom(box, collisionProp, "sound", "Sound", "")

            box.prop(collisionProp, "eponaBlock", text="Blocks Epona")
            box.prop(collisionProp, "decreaseHeight", text="Decrease Height 1 Unit")
            box.prop(collisionProp, "isWallDamage", text="Is Wall Damage")
            box.prop(collisionProp, "hookshotable", text="Hookshotable")

            drawEnumWithCustom(box, collisionProp, "floorSetting", "Floor Setting", "")
            drawEnumWithCustom(box, collisionProp, "wallSetting", "Wall Setting", "")
            drawEnumWithCustom(box, collisionProp, "floorProperty", "Floor Property", "")

            box.prop(collisionProp, "ignoreCameraCollision", text="Ignore Camera Collision")
            box.prop(collisionProp, "ignoreActorCollision", text="Ignore Actor Collision")
            box.prop(collisionProp, "ignoreProjectileCollision", text="Ignore Projectile Collision")
            prop_split(box, collisionProp, "conveyorOption", "Conveyor Option")
            if collisionProp.conveyorOption != "None":
                prop_split(box, collisionProp, "conveyorRotation", "Conveyor Rotation")
                drawEnumWithCustom(box, collisionProp, "conveyorSpeed", "Conveyor Speed", "")
                if collisionProp.conveyorSpeed != "Custom":
                    box.prop(collisionProp, "conveyorKeepMomentum", text="Keep Momentum")


class OOT_ExportCollisionPanel(OOT_Panel):
    bl_idname = "OOT_PT_export_collision"
    bl_label = "OOT Collision Exporter"

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.operator(OOT_ExportCollision.bl_idname)

        exportSettings: OOTCollisionExportSettings = context.scene.fast64.oot.collisionExportSettings
        col.label(text="Object name used for export.", icon="INFO")
        col.prop(exportSettings, "isCustomFilename")
        if exportSettings.isCustomFilename:
            prop_split(col, exportSettings, "filename", "Filename")
        prop_split(col, exportSettings, "folder", "Object" if not exportSettings.customExport else "Folder")
        if exportSettings.customExport:
            prop_split(col, exportSettings, "exportPath", "Directory")
        col.prop(exportSettings, "customExport")
        col.prop(exportSettings, "includeChildren")


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
