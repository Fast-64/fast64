import bpy
from bpy.types import PropertyGroup, UILayout, Image, Object, Context
from bpy.utils import register_class, unregister_class
from ...utility import prop_split
import fast64_internal.game_data as GD
from ..utility import (
    drawCollectionOps,
    onMenuTabChange,
    onHeaderMenuTabChange,
    drawEnumWithCustom,
    drawAddButton,
    is_oot_features,
    is_game_oot,
    get_game_prop_name,
    get_cs_index_start,
)
from ..upgrade import upgradeRoomHeaders
from .operators import OOT_SearchObjectEnumOperator

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

from ..constants import (
    ootEnumRoomShapeType,
    ootEnumHeaderMenu,
)

ootEnumRoomMenuAlternate = [
    ("General", "General", "General"),
    ("Objects", "Objects", "Objects"),
]
ootEnumRoomMenu = ootEnumRoomMenuAlternate + [
    ("Alternate", "Alternate", "Alternate"),
]


class Z64_ObjectProperty(PropertyGroup):
    expandTab: BoolProperty(name="Expand Tab")
    objectKey: EnumProperty(items=GD.game_data.z64.objectData.ootEnumObjectKey, default=1)
    objectIDCustom: StringProperty(default="OBJECT_CUSTOM")

    @staticmethod
    def upgrade_object(obj: Object):
        if is_game_oot():
            print(f"Processing '{obj.name}'...")
            upgradeRoomHeaders(obj, GD.game_data.z64.objectData)

    def draw_props(self, layout: UILayout, headerIndex: int, index: int, objName: str):
        is_legacy = True if "objectID" in self else False
        obj_key: str = getattr(self, get_game_prop_name("object_key"))

        if is_game_oot() and is_legacy:
            obj_name = GD.game_data.z64.objectData.ootEnumObjectIDLegacy[self["objectID"]][1]
        elif obj_key != "Custom":
            obj_name = GD.game_data.z64.objectData.objects_by_key[obj_key].name
        else:
            obj_name = self.objectIDCustom

        objItemBox = layout.column()
        row = objItemBox.row()
        row.label(text=f"{obj_name}")
        buttons = row.row(align=True)
        objSearch = buttons.operator(OOT_SearchObjectEnumOperator.bl_idname, icon="VIEWZOOM", text="Select")
        drawCollectionOps(buttons, index, "Object", headerIndex, objName, compact=True)
        objSearch.objName = objName
        objSearch.headerIndex = headerIndex if headerIndex is not None else 0
        objSearch.index = index

        if obj_key == "Custom":
            prop_split(objItemBox, self, "objectIDCustom", "Object ID Custom")


class Z64_BGProperty(PropertyGroup):
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


class Z64_RoomHeaderProperty(PropertyGroup):
    expandTab: BoolProperty(name="Expand Tab")
    menuTab: EnumProperty(items=ootEnumRoomMenu, update=onMenuTabChange)
    altMenuTab: EnumProperty(items=ootEnumRoomMenuAlternate)

    # OoT exclusive
    usePreviousHeader: BoolProperty(name="Use Previous Header", default=True)

    # SCENE_CMD_ROOM_BEHAVIOR
    roomIndex: IntProperty(name="Room Index", default=0, min=0)
    roomBehaviour: EnumProperty(items=GD.game_data.z64.ootEnumRoomBehaviour, default=1)
    roomBehaviourCustom: StringProperty(default="0x00")
    showInvisibleActors: BoolProperty(name="Show Invisible Actors")
    linkIdleMode: EnumProperty(name="Environment Type", items=GD.game_data.z64.ootEnumLinkIdle, default=1)
    linkIdleModeCustom: StringProperty(name="Environment Type Custom", default="0x00")

    # OoT exclusive
    disableWarpSongs: BoolProperty(name="Disable Warp Songs")

    # MM exclusive
    enable_pos_lights: BoolProperty(name="Enable Pos Lights")
    enable_storm: BoolProperty(name="Enable Storm")

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
    objectList: CollectionProperty(type=Z64_ObjectProperty)

    # SCENE_CMD_ROOM_SHAPE
    roomShape: EnumProperty(items=ootEnumRoomShapeType, default="ROOM_SHAPE_TYPE_NORMAL")
    defaultCullDistance: IntProperty(name="Default Cull Distance", min=1, default=100)
    bgImageList: CollectionProperty(type=Z64_BGProperty)
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
        from ..props_panel_main import OOT_ManualUpgrade

        cs_index_start = get_cs_index_start()

        if dropdownLabel is not None:
            layout.prop(self, "expandTab", text=dropdownLabel, icon="TRIA_DOWN" if self.expandTab else "TRIA_RIGHT")
            if not self.expandTab:
                return
        if headerIndex is not None and headerIndex > (cs_index_start - 1):
            drawCollectionOps(layout, headerIndex - cs_index_start, "Room", None, objName)

        if is_game_oot() and headerIndex is not None and headerIndex > 0 and headerIndex < cs_index_start:
            layout.prop(self, "usePreviousHeader", text="Use Previous Header")
            if self.usePreviousHeader:
                return

        if headerIndex is None or headerIndex == 0:
            layout.row().prop(self, "menuTab", expand=True)
            menuTab = self.menuTab
        else:
            layout.row().prop(self, "altMenuTab", expand=True)
            menuTab = self.altMenuTab

        if menuTab == "General":
            # General
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
                if self.roomShape == "ROOM_SHAPE_TYPE_NONE" and is_oot_features():
                    general.label(text="This shape type is only implemented on MM", icon="INFO")

            # Behavior
            behaviorBox = layout.column()
            behaviorBox.box().label(text="Behavior")
            drawEnumWithCustom(behaviorBox, self, "roomBehaviour", "Room Type", "", "roomBehaviourCustom")
            drawEnumWithCustom(behaviorBox, self, "linkIdleMode", "Environment Type", "", "linkIdleModeCustom")

            if is_game_oot():
                behaviorBox.prop(self, "disableWarpSongs", text="Disable Warp Songs")

            if not is_oot_features():
                behaviorBox.prop(self, "enable_pos_lights")
                behaviorBox.prop(self, "enable_storm")

            behaviorBox.prop(self, "showInvisibleActors", text="Show Invisible Actors")

            if not is_oot_features():
                if self.mm_room_type in {"ROOM_TYPE_DUNGEON", "ROOM_TYPE_BOSS"}:
                    behaviorBox.label(text="The Three-Day Events actor will be automatically", icon="INFO")
                    behaviorBox.label(text="spawned by `Play_Init` (see 'ACTOR_EN_TEST4' usage).")
                else:
                    behaviorBox.label(text="You will need to add the Three-Day Events actor", icon="INFO")
                    behaviorBox.label(text="to that room (see 'ACTOR_EN_TEST4' usage).")

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

        elif menuTab == "Objects":
            upgradeLayout = layout.column()
            objBox = layout.column()
            objBox.box().label(text="Objects")

            if is_oot_features() and len(self.objectList) > 16:
                objBox.label(text="You are over the 16 object limit.", icon="ERROR")
                objBox.label(text="You must allocate more memory in code.")

            is_legacy = False
            for i, objProp in enumerate(self.objectList):
                objProp.draw_props(objBox, headerIndex, i, objName)

                if is_game_oot() and "objectID" in objProp:
                    is_legacy = True

            if is_game_oot() and is_legacy:
                upgradeLayout.label(text="Legacy data has not been upgraded!")
                upgradeLayout.operator(OOT_ManualUpgrade.bl_idname, text="Upgrade Data Now!")
            objBox.enabled = False if is_legacy else True

            drawAddButton(objBox, len(self.objectList), "Object", headerIndex, objName)


def update_cutscene_index(self: "Z64_AlternateRoomHeaderProperty", context: Context):
    cs_index_start = get_cs_index_start()

    if self.currentCutsceneIndex < cs_index_start:
        self.currentCutsceneIndex = cs_index_start

    onHeaderMenuTabChange(self, context)


class Z64_AlternateRoomHeaderProperty(PropertyGroup):
    cutsceneHeaders: CollectionProperty(type=Z64_RoomHeaderProperty)
    currentCutsceneIndex: IntProperty(default=1, update=update_cutscene_index)

    # OoT exclusive
    childNightHeader: PointerProperty(name="Child Night Header", type=Z64_RoomHeaderProperty)
    adultDayHeader: PointerProperty(name="Adult Day Header", type=Z64_RoomHeaderProperty)
    adultNightHeader: PointerProperty(name="Adult Night Header", type=Z64_RoomHeaderProperty)
    headerMenuTab: EnumProperty(name="Header Menu", items=ootEnumHeaderMenu, update=onHeaderMenuTabChange)

    def draw_props(self, layout: UILayout, objName: str):
        headerSetup = layout.column()
        cs_index_start = get_cs_index_start()
        can_draw_cs_header = not is_game_oot()

        if not can_draw_cs_header:
            headerSetupBox = headerSetup.column()
            headerSetupBox.row().prop(self, "headerMenuTab", expand=True)

            if self.headerMenuTab == "Child Night":
                self.childNightHeader.draw_props(headerSetupBox, None, 1, objName)
            elif self.headerMenuTab == "Adult Day":
                self.adultDayHeader.draw_props(headerSetupBox, None, 2, objName)
            elif self.headerMenuTab == "Adult Night":
                self.adultNightHeader.draw_props(headerSetupBox, None, 3, objName)
            elif self.headerMenuTab == "Cutscene":
                can_draw_cs_header = True

        if can_draw_cs_header:
            prop_split(headerSetup, self, "currentCutsceneIndex", "Cutscene Index")
            drawAddButton(headerSetup, len(self.cutsceneHeaders), "Room", None, objName)
            index = self.currentCutsceneIndex
            if index - cs_index_start < len(self.cutsceneHeaders):
                self.cutsceneHeaders[index - cs_index_start].draw_props(headerSetup, None, index, objName)
            else:
                headerSetup.label(text="No cutscene header for this index.", icon="QUESTION")


classes = (
    Z64_ObjectProperty,
    Z64_BGProperty,
    Z64_RoomHeaderProperty,
    Z64_AlternateRoomHeaderProperty,
)


def room_props_register():
    for cls in classes:
        register_class(cls)

    Object.ootRoomHeader = PointerProperty(type=Z64_RoomHeaderProperty)
    Object.ootAlternateRoomHeaders = PointerProperty(type=Z64_AlternateRoomHeaderProperty)


def room_props_unregister():
    del bpy.types.Object.ootRoomHeader
    del bpy.types.Object.ootAlternateRoomHeaders

    for cls in reversed(classes):
        unregister_class(cls)
