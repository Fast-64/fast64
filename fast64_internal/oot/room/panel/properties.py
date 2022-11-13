import bpy
from bpy.types import PropertyGroup, Operator, UILayout, Image, Object
from bpy.utils import register_class, unregister_class
from bpy.props import EnumProperty, IntProperty, StringProperty, FloatProperty, CollectionProperty, PointerProperty, BoolProperty, IntVectorProperty
from ....utility import ootGetSceneOrRoomHeader, prop_split
from ...oot_utility import drawCollectionOps, onMenuTabChange, onHeaderMenuTabChange

from ...oot_constants import (
    ootEnumObjectID,
    ootEnumRoomMenu,
    ootEnumRoomMenuAlternate,
    ootEnumRoomBehaviour,
    ootEnumLinkIdle,
    ootEnumRoomShapeType,
    ootEnumHeaderMenu,
)

class OOT_SearchObjectEnumOperator(Operator):
    bl_idname = "object.oot_search_object_enum_operator"
    bl_label = "Search Object ID"
    bl_property = "ootObjectID"
    bl_options = {"REGISTER", "UNDO"}

    ootObjectID: EnumProperty(items=ootEnumObjectID, default="OBJECT_HUMAN")
    headerIndex: IntProperty(default=0, min=0)
    index: IntProperty(default=0, min=0)
    objName: StringProperty()

    def execute(self, context):
        roomHeader = ootGetSceneOrRoomHeader(bpy.data.objects[self.objName], self.headerIndex, True)
        roomHeader.objectList[self.index].objectID = self.ootObjectID
        bpy.context.region.tag_redraw()
        self.report({"INFO"}, "Selected: " + self.ootObjectID)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class OOTObjectProperty(PropertyGroup):
    expandTab: BoolProperty(name="Expand Tab")
    objectID: EnumProperty(items=ootEnumObjectID, default="OBJECT_HUMAN")
    objectIDCustom: StringProperty(default="OBJECT_HUMAN")


class OOTBGProperty(PropertyGroup):
    image: PointerProperty(type=Image)
    # camera: IntProperty(name="Camera Index", min=0)
    otherModeFlags: StringProperty(
        name="DPSetOtherMode Flags", default="0x0000", description="See src/code/z_room.c:func_8009638C()"
    )

    def draw(self, layout: UILayout, index: int, objName: str, isMulti: bool):
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

    useCustomBehaviourX: BoolProperty(name="Use Custom Behaviour X")
    useCustomBehaviourY: BoolProperty(name="Use Custom Behaviour Y")

    customBehaviourX: StringProperty(name="Custom Behaviour X", default="0x00")

    customBehaviourY: StringProperty(name="Custom Behaviour Y", default="0x00")

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


class OOTAlternateRoomHeaderProperty(PropertyGroup):
    childNightHeader: PointerProperty(name="Child Night Header", type=OOTRoomHeaderProperty)
    adultDayHeader: PointerProperty(name="Adult Day Header", type=OOTRoomHeaderProperty)
    adultNightHeader: PointerProperty(name="Adult Night Header", type=OOTRoomHeaderProperty)
    cutsceneHeaders: CollectionProperty(type=OOTRoomHeaderProperty)

    headerMenuTab: EnumProperty(name="Header Menu", items=ootEnumHeaderMenu, update=onHeaderMenuTabChange)
    currentCutsceneIndex: IntProperty(min=4, default=4, update=onHeaderMenuTabChange)


classes = (
    OOT_SearchObjectEnumOperator,

    OOTObjectProperty,
    OOTBGProperty,
    OOTRoomHeaderProperty,
    OOTAlternateRoomHeaderProperty,
)


def room_props_classes_register():
    for cls in classes:
        register_class(cls)

    Object.ootRoomHeader = PointerProperty(type=OOTRoomHeaderProperty)
    Object.ootAlternateRoomHeaders = PointerProperty(type=OOTAlternateRoomHeaderProperty)


def room_props_classes_unregister():
    del bpy.types.Object.ootRoomHeader
    del bpy.types.Object.ootAlternateRoomHeaders

    for cls in reversed(classes):
        unregister_class(cls)
