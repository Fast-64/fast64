import math
from bpy.types import PropertyGroup, Camera
from bpy.props import IntProperty, StringProperty, EnumProperty, BoolProperty, FloatProperty, PointerProperty

from ....oot_collision_classes import (
    ootEnumFloorSetting,
    ootEnumWallSetting,
    ootEnumFloorProperty,
    ootEnumConveyer,
    ootEnumConveyorSpeed,
    ootEnumCollisionTerrain,
    ootEnumCollisionSound,
    ootEnumCameraSType,
)


class OOTCameraPositionProperty(PropertyGroup):
    index: IntProperty(min=0)
    jfifID: StringProperty(default="-1")
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
