import bpy
from bpy.types import Panel, Camera, Scene, Object, Material
from bpy.utils import register_class, unregister_class
from .....utility import prop_split
from ....oot_utility import drawEnumWithCustom

from .classes import (
    OOTWaterBoxProperty,
    OOTCameraPositionPropertyRef,
    OOTCameraPositionProperty,
    OOTMaterialCollisionProperty,
)


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
        box = self.layout.box()
        obj = context.object

        box.box().label(text="Camera Data")
        drawEnumWithCustom(box, obj.ootCameraPositionProperty, "camSType", "Camera S Type", "")
        prop_split(box, obj.ootCameraPositionProperty, "index", "Camera Index")
        if obj.ootCameraPositionProperty.hasPositionData:
            prop_split(box, obj.data, "angle", "Field Of View")
            prop_split(box, obj.ootCameraPositionProperty, "jfifID", "JFIF ID")
        box.prop(obj.ootCameraPositionProperty, "hasPositionData")


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


oot_col_classes = (
    OOTWaterBoxProperty,
    OOTCameraPositionPropertyRef,
    OOTCameraPositionProperty,
    OOTMaterialCollisionProperty,
)

oot_col_panel_classes = (
    OOT_CollisionPanel,
    OOT_CameraPosPanel,
)


def collision_props_panel_register():
    for cls in oot_col_panel_classes:
        register_class(cls)


def collision_props_panel_unregister():
    for cls in oot_col_panel_classes:
        unregister_class(cls)


def collision_props_classes_register():
    for cls in oot_col_classes:
        register_class(cls)

    # Collision
    Scene.ootColLevelName = bpy.props.StringProperty(name="Name", default="SCENE_YDAN")
    Object.ootCameraPositionProperty = bpy.props.PointerProperty(type=OOTCameraPositionProperty)
    Material.ootCollisionProperty = bpy.props.PointerProperty(type=OOTMaterialCollisionProperty)


def collision_props_classes_unregister():
    # Collision
    del Scene.ootColLevelName

    for cls in reversed(oot_col_classes):
        unregister_class(cls)
