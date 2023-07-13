import math
from bpy.props import StringProperty, PointerProperty, IntProperty, EnumProperty, BoolProperty, FloatProperty
from bpy.types import PropertyGroup, Camera, Object, Material, UILayout
from bpy.utils import register_class, unregister_class
from ...utility import prop_split
from ..oot_utility import drawEnumWithCustom
from ..oot_constants import ootEnumSceneID
from .constants import (
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
    camSType: EnumProperty(items=ootEnumCameraSType, default="CAM_SET_NONE")
    camSTypeCustom: StringProperty(default="CAM_SET_NONE")
    hasPositionData: BoolProperty(default=True, name="Has Position Data")

    def draw_props(self, layout: UILayout, cameraObj: Object):
        drawEnumWithCustom(layout, self, "camSType", "Camera S Type", "")
        prop_split(layout, self, "index", "Camera Index")
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

    def draw_props(self, layout: UILayout):
        layout.prop(
            self,
            "expandTab",
            text="OOT Collision Properties",
            icon="TRIA_DOWN" if self.expandTab else "TRIA_RIGHT",
        )
        if self.expandTab:
            prop_split(layout, self, "exitID", "Exit ID")
            prop_split(layout, self, "cameraID", "Camera ID")
            prop_split(layout, self, "echo", "Echo")
            prop_split(layout, self, "lightingSetting", "Lighting")
            drawEnumWithCustom(layout, self, "terrain", "Terrain", "")
            drawEnumWithCustom(layout, self, "sound", "Sound", "")

            layout.prop(self, "eponaBlock", text="Blocks Epona")
            layout.prop(self, "decreaseHeight", text="Decrease Height 1 Unit")
            layout.prop(self, "isWallDamage", text="Is Wall Damage")
            layout.prop(self, "hookshotable", text="Hookshotable")

            drawEnumWithCustom(layout, self, "floorSetting", "Floor Setting", "")
            drawEnumWithCustom(layout, self, "wallSetting", "Wall Setting", "")
            drawEnumWithCustom(layout, self, "floorProperty", "Floor Property", "")

            layout.prop(self, "ignoreCameraCollision", text="Ignore Camera Collision")
            layout.prop(self, "ignoreActorCollision", text="Ignore Actor Collision")
            layout.prop(self, "ignoreProjectileCollision", text="Ignore Projectile Collision")
            prop_split(layout, self, "conveyorOption", "Conveyor Option")
            if self.conveyorOption != "None":
                prop_split(layout, self, "conveyorRotation", "Conveyor Rotation")
                drawEnumWithCustom(layout, self, "conveyorSpeed", "Conveyor Speed", "")
                if self.conveyorSpeed != "Custom":
                    layout.prop(self, "conveyorKeepMomentum", text="Keep Momentum")


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
