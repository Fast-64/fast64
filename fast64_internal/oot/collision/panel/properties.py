import math
from bpy.props import StringProperty, PointerProperty, IntProperty, EnumProperty, BoolProperty, FloatProperty
from bpy.types import PropertyGroup, Panel, Camera, Scene, Object, Material
from bpy.utils import register_class, unregister_class
from ....utility import prop_split
from ...oot_utility import drawEnumWithCustom
from ...oot_collision_classes import (
    ootEnumFloorSetting,
    ootEnumWallSetting,
    ootEnumFloorProperty,
    ootEnumConveyer,
    ootEnumConveyorSpeed,
    ootEnumCollisionTerrain,
    ootEnumCollisionSound,
    ootEnumCameraSType,
)

##############
# Properties #
##############
class OOTCameraPositionProperty(PropertyGroup):
    index: IntProperty(min=0)
    bgImageOverrideIndex: IntProperty(default=-1, min=-1)
    camSType: EnumProperty(items=ootEnumCameraSType, default="CAM_SET_NONE")
    camSTypeCustom: StringProperty(default="CAM_SET_NONE")
    hasPositionData: BoolProperty(default=True, name="Has Position Data")


class OOTCameraPositionPropertyRef(PropertyGroup):
    camera: PointerProperty(type=Camera)

class OOTMaterialCollisionProperty(PropertyGroup):
    expandTab: BoolProperty()

    ignoreCameraCollision: BoolProperty()
    ignoreActorCollision: BoolProperty()
    ignoreProjectileCollision: BoolProperty()

    eponaBlock: BoolProperty()
    decreaseHeight: BoolProperty()
    floorSettingCustom: StringProperty(default="0x00")
    floorSetting: EnumProperty(items=ootEnumFloorSetting, default="0x00")
    wallSettingCustom: StringProperty(default="0x00")
    wallSetting: EnumProperty(items=ootEnumWallSetting, default="0x00")
    floorPropertyCustom: StringProperty(default="0x00")
    floorProperty: EnumProperty(items=ootEnumFloorProperty, default="0x00")
    exitID: IntProperty(default=0, min=0)
    cameraID: IntProperty(default=0, min=0)
    isWallDamage: BoolProperty()
    conveyorOption: EnumProperty(items=ootEnumConveyer)
    conveyorRotation: FloatProperty(min=0, max=2 * math.pi, subtype="ANGLE")
    conveyorSpeed: EnumProperty(items=ootEnumConveyorSpeed, default="0x00")
    conveyorSpeedCustom: StringProperty(default="0x00")
    conveyorKeepMomentum: BoolProperty()
    hookshotable: BoolProperty()
    echo: StringProperty(default="0x00")
    lightingSetting: IntProperty(default=0, min=0)
    terrainCustom: StringProperty(default="0x00")
    terrain: EnumProperty(items=ootEnumCollisionTerrain, default="0x00")
    soundCustom: StringProperty(default="0x00")
    sound: EnumProperty(items=ootEnumCollisionSound, default="0x00")


class OOTWaterBoxProperty(PropertyGroup):
    lighting: IntProperty(name="Lighting", min=0)
    camera: IntProperty(name="Camera", min=0)
    flag19: BoolProperty(name="Flag 19", default=False)


##############
#   Panels   #
##############
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
    Scene.ootColLevelName = StringProperty(name="Name", default="SCENE_YDAN")
    Object.ootCameraPositionProperty = PointerProperty(type=OOTCameraPositionProperty)
    Material.ootCollisionProperty = PointerProperty(type=OOTMaterialCollisionProperty)


def collision_props_classes_unregister():
    # Collision
    del Scene.ootColLevelName

    for cls in reversed(oot_col_classes):
        unregister_class(cls)
