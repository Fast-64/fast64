import math
from bpy.props import StringProperty, PointerProperty, IntProperty, EnumProperty, BoolProperty, FloatProperty
from bpy.types import PropertyGroup, Camera, Object, Material
from bpy.utils import register_class, unregister_class
from ..oot_constants import ootEnumSceneID
from ..oot_collision_classes import (
    ootEnumFloorSetting,
    ootEnumWallSetting,
    ootEnumFloorProperty,
    ootEnumConveyer,
    ootEnumConveyorSpeed,
    ootEnumCollisionTerrain,
    ootEnumCollisionSound,
    ootEnumCameraSType,
)


class OOTCollisionExportSettings(PropertyGroup):
    isCustomFilename: BoolProperty(
        name="Use Custom Filename", description="Override filename instead of basing it off of the Blender name"
    )
    filename: StringProperty(name="Filename")
    exportPath: StringProperty(name="Directory", subtype="FILE_PATH")
    exportLevel: EnumProperty(items=ootEnumSceneID, name="Level Used By Collision", default="SCENE_DEKU_TREE")
    includeChildren: BoolProperty(name="Include child objects", default=True)
    levelName: StringProperty(name="Name", default="SCENE_DEKU_TREE")
    customExport: BoolProperty(
        name="Custom Export Path", description="Determines whether or not to export to an explicitly specified folder"
    )
    folder: StringProperty(name="Object Name", default="gameplay_keep")


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


oot_col_classes = (
    OOTCollisionExportSettings,
    OOTCameraPositionProperty,
    OOTCameraPositionPropertyRef,
    OOTMaterialCollisionProperty,
    OOTWaterBoxProperty,
)

def collision_props_register():
    for cls in oot_col_classes:
        register_class(cls)

    # Collision
    Object.ootCameraPositionProperty = PointerProperty(type=OOTCameraPositionProperty)
    Material.ootCollisionProperty = PointerProperty(type=OOTMaterialCollisionProperty)
    Object.ootWaterBoxProperty = PointerProperty(type=OOTWaterBoxProperty)


def collision_props_unregister():
    # Collision
    del Object.ootCameraPositionProperty
    del Material.ootCollisionProperty
    del Object.ootWaterBoxProperty

    for cls in reversed(oot_col_classes):
        unregister_class(cls)
