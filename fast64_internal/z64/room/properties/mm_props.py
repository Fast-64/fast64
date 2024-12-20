import bpy
from bpy.types import PropertyGroup, UILayout, Image, Object
from bpy.utils import register_class, unregister_class
from ....utility import prop_split
from ...utility import (
    drawCollectionOps,
    onMenuTabChange,
    onHeaderMenuTabChange,
    drawEnumWithCustom,
    drawAddButton,
    is_game_oot,
)
from ..operators import MM_SearchObjectEnumOperator

from bpy.props import (
    EnumProperty,
    IntProperty,
    StringProperty,
    FloatProperty,
    CollectionProperty,
    PointerProperty,
    BoolProperty,
    IntVectorProperty,
)

from ...constants import (
    mm_data,
    mm_enum_room_type,
    mm_enum_environvment_type,
    ootEnumRoomShapeType,
)

ootEnumRoomMenuAlternate = [
    ("General", "General", "General"),
    ("Objects", "Objects", "Objects"),
]
ootEnumRoomMenu = ootEnumRoomMenuAlternate + [
    ("Alternate", "Alternate", "Alternate"),
]


class MM_ObjectProperty(PropertyGroup):
    expandTab: BoolProperty(name="Expand Tab")
    objectKey: EnumProperty(items=mm_data.object_data.enum_object_key, default="gameplay_keep")
    objectIDCustom: StringProperty(default="OBJECT_CUSTOM")

    def draw_props(self, layout: UILayout, headerIndex: int, index: int, objName: str):
        if self.objectKey != "Custom":
            objectName = mm_data.object_data.objects_by_key[self.objectKey].name
        else:
            objectName = self.objectIDCustom

        objItemBox = layout.column()
        row = objItemBox.row()
        row.label(text=f"{objectName}")
        buttons = row.row(align=True)
        objSearch = buttons.operator(MM_SearchObjectEnumOperator.bl_idname, icon="VIEWZOOM", text="Select")
        drawCollectionOps(buttons, index, "Object", headerIndex, objName, compact=True)
        objSearch.obj_name = objName
        objSearch.header_index = headerIndex if headerIndex is not None else 0
        objSearch.index = index

        if self.objectKey == "Custom":
            prop_split(objItemBox, self, "objectIDCustom", "Object ID Custom")


class MM_BGProperty(PropertyGroup):
    image: PointerProperty(type=Image)
    # camera: IntProperty(name="Camera Index", min=0)
    otherModeFlags: StringProperty(
        name="DPSetOtherMode Flags", default="0x0000", description="See src/code/z_room.c:func_8009638C()"
    )

    def draw_props(self, layout: UILayout, index: int, objName: str, isMulti: bool):
        box = layout.box().column()

        box.template_ID(self, "image", new="image.new", open="image.open")
        # if isMulti:
        #    prop_split(box, self, "camera", "Camera")
        prop_split(box, self, "otherModeFlags", "Other Mode Flags")
        drawCollectionOps(box, index, "BgImage", None, objName)


class MM_RoomHeaderProperty(PropertyGroup):
    expandTab: BoolProperty(name="Expand Tab")
    menuTab: EnumProperty(items=ootEnumRoomMenu, update=onMenuTabChange)
    altMenuTab: EnumProperty(items=ootEnumRoomMenuAlternate)

    roomIndex: IntProperty(name="Room Index", default=0, min=0)

    # SCENE_CMD_ROOM_BEHAVIOR
    roomBehaviour: EnumProperty(items=mm_enum_room_type, default="0x00")
    roomBehaviourCustom: StringProperty(default="0x00")
    showInvisibleActors: BoolProperty(name="Show Invisible Actors")
    enable_pos_lights: BoolProperty(name="Enable Pos Lights")
    enable_storm: BoolProperty(name="Enable Storm")
    linkIdleMode: EnumProperty(name="Environment Type", items=mm_enum_environvment_type, default="0x00")
    linkIdleModeCustom: StringProperty(name="Environment Type Custom", default="0x00")

    # SCENE_CMD_WIND_SETTINGS
    setWind: BoolProperty(name="Set Wind")
    windVector: IntVectorProperty(name="Wind Vector", size=3, min=-127, max=127)
    windStrength: IntProperty(name="Wind Strength", min=0, max=255)

    # SCENE_CMD_TIME_SETTINGS
    leaveTimeUnchanged: BoolProperty(name="Leave Time Unchanged", default=True)
    timeHours: IntProperty(name="Hours", default=0, min=0, max=23)  # 0xFFFE
    timeMinutes: IntProperty(name="Minutes", default=0, min=0, max=59)
    timeSpeed: FloatProperty(name="Time Speed", default=1, min=-13, max=13)  # 0xA

    # SCENE_CMD_SKYBOX_DISABLES
    disableSkybox: BoolProperty(name="Disable Skybox")
    disableSunMoon: BoolProperty(name="Disable Sun/Moon")

    # SCENE_CMD_ECHO_SETTINGS
    echo: StringProperty(name="Echo", default="0x00")

    # SCENE_CMD_OBJECT_LIST
    objectList: CollectionProperty(type=MM_ObjectProperty)

    # SCENE_CMD_ROOM_SHAPE
    roomShape: EnumProperty(items=ootEnumRoomShapeType, default="ROOM_SHAPE_TYPE_NORMAL")
    defaultCullDistance: IntProperty(name="Default Cull Distance", min=1, default=100)
    bgImageList: CollectionProperty(type=MM_BGProperty)
    bgImageTab: BoolProperty(name="BG Images")

    def drawBGImageList(self, layout: UILayout, objName: str):
        box = layout.column()
        box.label(text="BG images do not work currently.", icon="ERROR")
        box.prop(self, "bgImageTab", text="BG Images", icon="TRIA_DOWN" if self.bgImageTab else "TRIA_RIGHT")
        if self.bgImageTab:
            box.label(text="Only one room allowed per scene.", icon="INFO")
            box.label(text="Must be framebuffer sized (320x240).", icon="INFO")
            box.label(text="Must be jpg file with file marker.", icon="INFO")
            box.label(text="Ex. MsPaint compatible, Photoshop not.")
            box.label(text="Can't use files generated in Blender.")
            imageCount = len(self.bgImageList)
            for i in range(imageCount):
                self.bgImageList[i].draw_props(box, i, objName, imageCount > 1)

            drawAddButton(box, len(self.bgImageList), "BgImage", None, objName)

    def draw_props(self, layout: UILayout, dropdownLabel: str, headerIndex: int, objName: str):
        from ...props_panel_main import OOT_ManualUpgrade

        if dropdownLabel is not None:
            layout.prop(self, "expandTab", text=dropdownLabel, icon="TRIA_DOWN" if self.expandTab else "TRIA_RIGHT")
            if not self.expandTab:
                return
        if headerIndex is not None and headerIndex > 0:
            drawCollectionOps(layout, headerIndex - 1, "Room", None, objName)

        if headerIndex is None or headerIndex == 0:
            layout.row().prop(self, "menuTab", expand=True)
            menuTab = self.menuTab
        else:
            layout.row().prop(self, "altMenuTab", expand=True)
            menuTab = self.altMenuTab

        if menuTab == "General":
            if headerIndex is None or headerIndex == 0:
                general = layout.column()
                general.box().label(text="General")
                prop_split(general, self, "roomIndex", "Room Index")
                prop_split(general, self, "roomShape", "Room Shape")
                if self.roomShape == "ROOM_SHAPE_TYPE_IMAGE":
                    self.drawBGImageList(general, objName)
                if self.roomShape == "ROOM_SHAPE_TYPE_CULLABLE":
                    general.label(text="The 'Cullable' room shape type is for CPU culling,", icon="INFO")
                    general.label(text="and requires meshes to be parented to Custom Cull Group empties.")
                    general.label(text="RSP culling is done automatically regardless of room shape.")
                    prop_split(general, self, "defaultCullDistance", "Default Cull (Blender Units)")
                if self.roomShape == "ROOM_SHAPE_TYPE_NONE" and is_game_oot():
                    general.label(text="This shape type is only implemented on MM", icon="INFO")

            # Behaviour
            behaviourBox = layout.column()
            behaviourBox.box().label(text="Behaviour")
            drawEnumWithCustom(behaviourBox, self, "roomBehaviour", "Room Type", "")
            drawEnumWithCustom(behaviourBox, self, "linkIdleMode", "Environment Type", "")
            behaviourBox.prop(self, "showInvisibleActors")
            behaviourBox.prop(self, "enable_pos_lights")
            behaviourBox.prop(self, "enable_storm")

            # Time
            skyboxAndTime = layout.column()
            skyboxAndTime.box().label(text="Skybox And Time")

            # Skybox
            skyboxAndTime.prop(self, "disableSkybox", text="Disable Skybox")
            skyboxAndTime.prop(self, "disableSunMoon", text="Disable Sun/Moon")
            skyboxAndTime.prop(self, "leaveTimeUnchanged", text="Leave Time Unchanged")
            if not self.leaveTimeUnchanged:
                skyboxAndTime.label(text="Time")
                timeRow = skyboxAndTime.row()
                timeRow.prop(self, "timeHours", text="Hours")
                timeRow.prop(self, "timeMinutes", text="Minutes")
                # prop_split(skyboxAndTime, self, "timeValue", "Time Of Day")
            prop_split(skyboxAndTime, self, "timeSpeed", "Time Speed")

            # Echo
            prop_split(skyboxAndTime, self, "echo", "Echo")

            # Wind
            windBox = layout.column()
            windBox.box().label(text="Wind")
            windBox.prop(self, "setWind", text="Set Wind")
            if self.setWind:
                windBoxRow = windBox.row()
                windBoxRow.prop(self, "windVector", text="")
                windBox.prop(self, "windStrength", text="Strength")
                # prop_split(windBox, self, "windVector", "Wind Vector")

        elif menuTab == "Objects":
            objBox = layout.column()
            objBox.box().label(text="Objects")

            for i, objProp in enumerate(self.objectList):
                objProp.draw_props(objBox, headerIndex, i, objName)

            drawAddButton(objBox, len(self.objectList), "Object", headerIndex, objName)


class MM_AlternateRoomHeaderProperty(PropertyGroup):
    cutsceneHeaders: CollectionProperty(type=MM_RoomHeaderProperty)
    currentCutsceneIndex: IntProperty(min=1, default=1, update=onHeaderMenuTabChange)

    def draw_props(self, layout: UILayout, objName: str):
        headerSetup = layout.column()

        prop_split(headerSetup, self, "currentCutsceneIndex", "Cutscene Index")
        drawAddButton(headerSetup, len(self.cutsceneHeaders), "Room", None, objName)
        index = self.currentCutsceneIndex
        if index - 1 < len(self.cutsceneHeaders):
            self.cutsceneHeaders[index - 1].draw_props(headerSetup, None, index, objName)
        else:
            headerSetup.label(text="No cutscene header for this index.", icon="QUESTION")


classes = (
    MM_ObjectProperty,
    MM_BGProperty,
    MM_RoomHeaderProperty,
    MM_AlternateRoomHeaderProperty,
)


def mm_room_props_register():
    for cls in classes:
        register_class(cls)

    Object.mm_room_header = PointerProperty(type=MM_RoomHeaderProperty)
    Object.mm_alternate_room_headers = PointerProperty(type=MM_AlternateRoomHeaderProperty)


def mm_room_props_unregister():
    del bpy.types.Object.mm_room_header
    del bpy.types.Object.mm_alternate_room_headers

    for cls in reversed(classes):
        unregister_class(cls)
