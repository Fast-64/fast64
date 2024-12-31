import math
from bpy.props import StringProperty, PointerProperty, IntProperty, EnumProperty, BoolProperty, FloatProperty
from bpy.types import PropertyGroup, Camera, Object, Material, UILayout
from bpy.utils import register_class, unregister_class
from ...utility import prop_split
from ..utility import drawEnumWithCustom, is_game_oot, get_game_prop_name
from ..constants import ootEnumSceneID
from .constants import (
    ootEnumFloorSetting,
    ootEnumWallSetting,
    ootEnumFloorProperty,
    ootEnumConveyer,
    ootEnumConveyorSpeed,
    ootEnumCollisionTerrain,
    ootEnumCollisionSound,
    ootEnumCameraSType,
    mm_enum_floor_property,
    mm_enum_floor_type,
    mm_enum_floor_effect,
    mm_enum_surface_material,
    mm_enum_camera_setting_type,
)


class OOTCollisionExportSettings(PropertyGroup):
    isCustomFilename: BoolProperty(
        name="Use Custom Filename", description="Override filename instead of basing it off of the Blender name"
    )
    filename: StringProperty(name="Filename")
    exportPath: StringProperty(name="Directory", subtype="FILE_PATH")
    includeChildren: BoolProperty(name="Include child objects", default=True)
    levelName: StringProperty(name="Name", default="SCENE_DEKU_TREE")
    customExport: BoolProperty(
        name="Custom Export Path", description="Determines whether or not to export to an explicitly specified folder"
    )
    folder: StringProperty(name="Object Name", default="gameplay_keep")

    def draw_props(self, layout: UILayout):
        layout.label(text="Object name used for export.", icon="INFO")
        layout.prop(self, "isCustomFilename")
        if self.isCustomFilename:
            prop_split(layout, self, "filename", "Filename")
        prop_split(layout, self, "folder", "Object" if not self.customExport else "Folder")
        if self.customExport:
            prop_split(layout, self, "exportPath", "Directory")
        layout.prop(self, "customExport")
        layout.prop(self, "includeChildren")


class OOTCameraPositionProperty(PropertyGroup):
    index: IntProperty(min=0)
    bgImageOverrideIndex: IntProperty(default=-1, min=-1)
    camSType: EnumProperty(items=ootEnumCameraSType, default=2)
    mm_cam_setting_type: EnumProperty(items=mm_enum_camera_setting_type, default=2)
    camSTypeCustom: StringProperty(default="CAM_SET_NORMAL0")
    hasPositionData: BoolProperty(default=True, name="Has Position Data")
    is_actor_cs_cam: BoolProperty(default=False, name="Is Actor CS Camera")

    def draw_props(self, layout: UILayout, cameraObj: Object):
        drawEnumWithCustom(layout, self, get_game_prop_name("cam_setting_type"), "Camera S Type", "", "camSTypeCustom")
        prop_split(layout, self, "index", "Camera Index")
        layout.prop(self, "is_actor_cs_cam")

        if not self.is_actor_cs_cam:
            layout.prop(self, "hasPositionData")

        if self.hasPositionData:
            prop_split(layout, cameraObj.data, "angle", "Field Of View")
            prop_split(layout, self, "bgImageOverrideIndex", "BG Index Override")


class OOTMaterialCollisionProperty(PropertyGroup):
    expandTab: BoolProperty()

    ignoreCameraCollision: BoolProperty()
    ignoreActorCollision: BoolProperty()
    ignoreProjectileCollision: BoolProperty()

    eponaBlock: BoolProperty()
    decreaseHeight: BoolProperty()
    floorSettingCustom: StringProperty(default="0x00")
    floorSetting: EnumProperty(items=ootEnumFloorSetting, default=1)
    mm_floor_property: EnumProperty(items=mm_enum_floor_property, default=1)
    wallSettingCustom: StringProperty(default="0x00")
    wallSetting: EnumProperty(items=ootEnumWallSetting, default=1)
    floorPropertyCustom: StringProperty(default="0x00")
    floorProperty: EnumProperty(items=ootEnumFloorProperty, default=1)
    mm_floor_type: EnumProperty(items=mm_enum_floor_type, default=1)
    exitID: IntProperty(default=0, min=0)
    cameraID: IntProperty(default=0, min=0)
    isWallDamage: BoolProperty()
    conveyorOption: EnumProperty(items=ootEnumConveyer)
    conveyorRotation: FloatProperty(min=0, max=2 * math.pi, subtype="ANGLE")
    conveyorSpeed: EnumProperty(items=ootEnumConveyorSpeed, default=1)
    conveyorSpeedCustom: StringProperty(default="0x00")
    conveyorKeepMomentum: BoolProperty()
    hookshotable: BoolProperty()
    echo: StringProperty(default="0x00")
    lightingSetting: IntProperty(default=0, min=0)
    terrainCustom: StringProperty(default="0x00")
    terrain: EnumProperty(items=ootEnumCollisionTerrain, default=1)
    mm_floor_effect: EnumProperty(items=mm_enum_floor_effect, default=1)
    soundCustom: StringProperty(default="0x00")
    sound: EnumProperty(items=ootEnumCollisionSound, default=1)
    mm_surface_material: EnumProperty(items=mm_enum_surface_material, default=1)

    def draw_props(self, layout: UILayout):
        layout.prop(
            self,
            "expandTab",
            text="Collision Properties",
            icon="TRIA_DOWN" if self.expandTab else "TRIA_RIGHT",
        )
        if self.expandTab:
            prop_split(layout, self, "exitID", "Exit Index")
            prop_split(layout, self, "cameraID", "Camera Index")
            prop_split(layout, self, "lightingSetting", "Lighting Index")
            prop_split(layout, self, "echo", "Echo")

            enum_box = layout.box().column()
            enum_box.label(text="Surface Settings")
            drawEnumWithCustom(
                enum_box, self, get_game_prop_name("floor_type"), "Floor Type", "", "floorPropertyCustom"
            )
            drawEnumWithCustom(
                enum_box, self, get_game_prop_name("floor_property"), "Floor Property", "", "floorSettingCustom"
            )
            drawEnumWithCustom(enum_box, self, get_game_prop_name("floor_effect"), "Floor Effect", "", "terrainCustom")
            drawEnumWithCustom(
                enum_box, self, get_game_prop_name("surface_material"), "Surface Material", "", "soundCustom"
            )
            drawEnumWithCustom(enum_box, self, "wallSetting", "Wall Type", "")

            layout.prop(self, "eponaBlock", text="Blocks Epona")
            layout.prop(self, "decreaseHeight", text="Decrease Height 1 Unit")
            layout.prop(self, "isWallDamage", text="Is Wall Damage")
            layout.prop(self, "hookshotable", text="Hookshotable")
            layout.prop(self, "ignoreCameraCollision", text="Ignore Camera Collision")
            layout.prop(self, "ignoreActorCollision", text="Ignore Actor Collision")
            layout.prop(self, "ignoreProjectileCollision", text="Ignore Projectile Collision")

            conveyor_box = layout.box().column()
            prop_split(conveyor_box, self, "conveyorOption", "Conveyor Option")
            if self.conveyorOption != "None":
                prop_split(conveyor_box, self, "conveyorRotation", "Conveyor Rotation")
                drawEnumWithCustom(conveyor_box, self, "conveyorSpeed", "Conveyor Speed", "")
                if self.conveyorSpeed != "Custom":
                    conveyor_box.prop(self, "conveyorKeepMomentum", text="Keep Momentum")


class OOTWaterBoxProperty(PropertyGroup):
    lighting: IntProperty(name="Lighting", min=0)
    camera: IntProperty(name="Camera", min=0)
    flag19: BoolProperty(name="Flag 19", default=False)

    def draw_props(self, layout: UILayout):
        box = layout.column()
        prop_split(box, self, "lighting", "Lighting")
        prop_split(box, self, "camera", "Camera")
        box.prop(self, "flag19")
        box.label(text="Defined by top face of box empty.")
        box.label(text="No rotation allowed.")


oot_col_classes = (
    OOTCollisionExportSettings,
    OOTCameraPositionProperty,
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
