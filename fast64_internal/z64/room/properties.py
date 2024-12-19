import bpy
from bpy.types import PropertyGroup, UILayout, Image, Object
from bpy.utils import register_class, unregister_class
from ...utility import prop_split
from ..oot_utility import drawCollectionOps, onMenuTabChange, onHeaderMenuTabChange, drawEnumWithCustom, drawAddButton
from ..oot_upgrade import upgradeRoomHeaders
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

from ..oot_constants import (
    ootData,
    ootEnumRoomBehaviour,
    ootEnumLinkIdle,
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


class OOTObjectProperty(PropertyGroup):
    expandTab: BoolProperty(name="Expand Tab")
    objectKey: EnumProperty(items=ootData.objectData.ootEnumObjectKey, default="obj_human")
    objectIDCustom: StringProperty(default="OBJECT_CUSTOM")

    @staticmethod
    def upgrade_object(obj: Object):
        print(f"Processing '{obj.name}'...")
        upgradeRoomHeaders(obj, ootData.objectData)

    def draw_props(self, layout: UILayout, headerIndex: int, index: int, objName: str):
        isLegacy = True if "objectID" in self else False

        if isLegacy:
            objectName = ootData.objectData.ootEnumObjectIDLegacy[self["objectID"]][1]
        elif self.objectKey != "Custom":
            objectName = ootData.objectData.objectsByKey[self.objectKey].name
        else:
            objectName = self.objectIDCustom

        objItemBox = layout.column()
        row = objItemBox.row()
        row.label(text=f"{objectName}")
        buttons = row.row(align=True)
        objSearch = buttons.operator(OOT_SearchObjectEnumOperator.bl_idname, icon="VIEWZOOM", text="Select")
        drawCollectionOps(buttons, index, "Object", headerIndex, objName, compact=True)
        objSearch.objName = objName
        objSearch.headerIndex = headerIndex if headerIndex is not None else 0
        objSearch.index = index

        if self.objectKey == "Custom":
            prop_split(objItemBox, self, "objectIDCustom", "Object ID Custom")


class OOTBGProperty(PropertyGroup):
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


class OOTRoomHeaderProperty(PropertyGroup):
    expandTab: BoolProperty(name="Expand Tab")
    menuTab: EnumProperty(items=ootEnumRoomMenu, update=onMenuTabChange)
    altMenuTab: EnumProperty(items=ootEnumRoomMenuAlternate)
    usePreviousHeader: BoolProperty(name="Use Previous Header", default=True)

    roomIndex: IntProperty(name="Room Index", default=0, min=0)
    roomBehaviour: EnumProperty(items=ootEnumRoomBehaviour, default="0x00")
    roomBehaviourCustom: StringProperty(default="0x00")
    disableWarpSongs: BoolProperty(name="Disable Warp Songs")
    showInvisibleActors: BoolProperty(name="Show Invisible Actors")
    linkIdleMode: EnumProperty(name="Link Idle Mode", items=ootEnumLinkIdle, default="0x00")
    linkIdleModeCustom: StringProperty(name="Link Idle Mode Custom", default="0x00")
    roomIsHot: BoolProperty(
        name="Use Hot Room Behavior",
        description="Use heat timer/screen effect, overrides Link Idle Mode",
        default=False,
    )

    setWind: BoolProperty(name="Set Wind")
    windVector: IntVectorProperty(name="Wind Vector", size=3, min=-127, max=127)
    windStrength: IntProperty(name="Wind Strength", min=0, max=255)

    leaveTimeUnchanged: BoolProperty(name="Leave Time Unchanged", default=True)
    timeHours: IntProperty(name="Hours", default=0, min=0, max=23)  # 0xFFFE
    timeMinutes: IntProperty(name="Minutes", default=0, min=0, max=59)
    timeSpeed: FloatProperty(name="Time Speed", default=1, min=-13, max=13)  # 0xA

    disableSkybox: BoolProperty(name="Disable Skybox")
    disableSunMoon: BoolProperty(name="Disable Sun/Moon")

    echo: StringProperty(name="Echo", default="0x00")

    objectList: CollectionProperty(type=OOTObjectProperty)

    roomShape: EnumProperty(items=ootEnumRoomShapeType, default="ROOM_SHAPE_TYPE_NORMAL")
    defaultCullDistance: IntProperty(name="Default Cull Distance", min=1, default=100)
    bgImageList: CollectionProperty(type=OOTBGProperty)
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

        if dropdownLabel is not None:
            layout.prop(self, "expandTab", text=dropdownLabel, icon="TRIA_DOWN" if self.expandTab else "TRIA_RIGHT")
            if not self.expandTab:
                return
        if headerIndex is not None and headerIndex > 3:
            drawCollectionOps(layout, headerIndex - 4, "Room", None, objName)

        if headerIndex is not None and headerIndex > 0 and headerIndex < 4:
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
            # Behaviour
            behaviourBox = layout.column()
            behaviourBox.box().label(text="Behaviour")
            drawEnumWithCustom(behaviourBox, self, "roomBehaviour", "Room Behaviour", "")
            drawEnumWithCustom(behaviourBox, self, "linkIdleMode", "Link Idle Mode", "")
            behaviourBox.prop(self, "disableWarpSongs", text="Disable Warp Songs")
            behaviourBox.prop(self, "showInvisibleActors", text="Show Invisible Actors")

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
            upgradeLayout = layout.column()
            objBox = layout.column()
            objBox.box().label(text="Objects")

            if len(self.objectList) > 16:
                objBox.label(text="You are over the 16 object limit.", icon="ERROR")
                objBox.label(text="You must allocate more memory in code.")

            isLegacy = False
            for i, objProp in enumerate(self.objectList):
                objProp.draw_props(objBox, headerIndex, i, objName)

                if "objectID" in objProp:
                    isLegacy = True

            if isLegacy:
                upgradeLayout.label(text="Legacy data has not been upgraded!")
                upgradeLayout.operator(OOT_ManualUpgrade.bl_idname, text="Upgrade Data Now!")
            objBox.enabled = False if isLegacy else True

            drawAddButton(objBox, len(self.objectList), "Object", headerIndex, objName)


class OOTAlternateRoomHeaderProperty(PropertyGroup):
    childNightHeader: PointerProperty(name="Child Night Header", type=OOTRoomHeaderProperty)
    adultDayHeader: PointerProperty(name="Adult Day Header", type=OOTRoomHeaderProperty)
    adultNightHeader: PointerProperty(name="Adult Night Header", type=OOTRoomHeaderProperty)
    cutsceneHeaders: CollectionProperty(type=OOTRoomHeaderProperty)

    headerMenuTab: EnumProperty(name="Header Menu", items=ootEnumHeaderMenu, update=onHeaderMenuTabChange)
    currentCutsceneIndex: IntProperty(min=4, default=4, update=onHeaderMenuTabChange)

    def draw_props(self, layout: UILayout, objName: str):
        headerSetup = layout.column()
        # headerSetup.box().label(text = "Alternate Headers")
        headerSetupBox = headerSetup.column()

        headerSetupBox.row().prop(self, "headerMenuTab", expand=True)
        if self.headerMenuTab == "Child Night":
            self.childNightHeader.draw_props(headerSetupBox, None, 1, objName)
        elif self.headerMenuTab == "Adult Day":
            self.adultDayHeader.draw_props(headerSetupBox, None, 2, objName)
        elif self.headerMenuTab == "Adult Night":
            self.adultNightHeader.draw_props(headerSetupBox, None, 3, objName)
        elif self.headerMenuTab == "Cutscene":
            prop_split(headerSetup, self, "currentCutsceneIndex", "Cutscene Index")
            drawAddButton(headerSetup, len(self.cutsceneHeaders), "Room", None, objName)
            index = self.currentCutsceneIndex
            if index - 4 < len(self.cutsceneHeaders):
                self.cutsceneHeaders[index - 4].draw_props(headerSetup, None, index, objName)
            else:
                headerSetup.label(text="No cutscene header for this index.", icon="QUESTION")


classes = (
    OOTObjectProperty,
    OOTBGProperty,
    OOTRoomHeaderProperty,
    OOTAlternateRoomHeaderProperty,
)


def room_props_register():
    for cls in classes:
        register_class(cls)

    Object.ootRoomHeader = PointerProperty(type=OOTRoomHeaderProperty)
    Object.ootAlternateRoomHeaders = PointerProperty(type=OOTAlternateRoomHeaderProperty)


def room_props_unregister():
    del bpy.types.Object.ootRoomHeader
    del bpy.types.Object.ootAlternateRoomHeaders

    for cls in reversed(classes):
        unregister_class(cls)
