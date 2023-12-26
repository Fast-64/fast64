from bpy.types import Object, PropertyGroup, UILayout
from bpy.utils import register_class, unregister_class
from bpy.props import EnumProperty, StringProperty, IntProperty, BoolProperty, CollectionProperty, PointerProperty
from ...utility import prop_split, label_split
from ..oot_constants import ootData, ootEnumCamTransition
from ..oot_upgrade import upgradeActors
from ..scene.properties import OOTAlternateSceneHeaderProperty
from ..room.properties import OOTAlternateRoomHeaderProperty
from .operators import OOT_SearchActorIDEnumOperator

from ..oot_utility import (
    getRoomObj,
    getEnumName,
    drawAddButton,
    drawCollectionOps,
    drawEnumWithCustom,
)

ootEnumSceneSetupPreset = [
    ("Custom", "Custom", "Custom"),
    ("All Scene Setups", "All Scene Setups", "All Scene Setups"),
    ("All Non-Cutscene Scene Setups", "All Non-Cutscene Scene Setups", "All Non-Cutscene Scene Setups"),
]


class OOTActorHeaderItemProperty(PropertyGroup):
    headerIndex: IntProperty(name="Scene Setup", min=4, default=4)
    expandTab: BoolProperty(name="Expand Tab")

    def draw_props(
        self,
        layout: UILayout,
        propUser: str,
        index: int,
        altProp: OOTAlternateSceneHeaderProperty | OOTAlternateRoomHeaderProperty,
        objName: str,
    ):
        box = layout.column()
        row = box.row()
        row.prop(self, "headerIndex", text="")
        drawCollectionOps(row.row(align=True), index, propUser, None, objName, compact=True)
        if altProp is not None and self.headerIndex >= len(altProp.cutsceneHeaders) + 4:
            box.label(text="Above header does not exist.", icon="QUESTION")


class OOTActorHeaderProperty(PropertyGroup):
    sceneSetupPreset: EnumProperty(name="Scene Setup Preset", items=ootEnumSceneSetupPreset, default="All Scene Setups")
    childDayHeader: BoolProperty(name="Child Day Header", default=True)
    childNightHeader: BoolProperty(name="Child Night Header", default=True)
    adultDayHeader: BoolProperty(name="Adult Day Header", default=True)
    adultNightHeader: BoolProperty(name="Adult Night Header", default=True)
    cutsceneHeaders: CollectionProperty(type=OOTActorHeaderItemProperty)

    def checkHeader(self, index: int) -> bool:
        if index == 0:
            return self.childDayHeader
        elif index == 1:
            return self.childNightHeader
        elif index == 2:
            return self.adultDayHeader
        elif index == 3:
            return self.adultNightHeader
        else:
            return index in [value.headerIndex for value in self.cutsceneHeaders]

    def draw_props(
        self,
        layout: UILayout,
        propUser: str,
        altProp: OOTAlternateSceneHeaderProperty | OOTAlternateRoomHeaderProperty,
        objName: str,
    ):
        headerSetup = layout.column()
        # headerSetup.box().label(text = "Alternate Headers")
        prop_split(headerSetup, self, "sceneSetupPreset", "Scene Setup Preset")
        if self.sceneSetupPreset == "Custom":
            headerSetupBox = headerSetup.column()
            headerSetupBox.prop(self, "childDayHeader", text="Child Day")
            prevHeaderName = "childDayHeader"
            childNightRow = headerSetupBox.row()
            if altProp is None or altProp.childNightHeader.usePreviousHeader:
                # Draw previous header checkbox (so get previous state), but labeled
                # as current one and grayed out
                childNightRow.prop(self, prevHeaderName, text="Child Night")
                childNightRow.enabled = False
            else:
                childNightRow.prop(self, "childNightHeader", text="Child Night")
                prevHeaderName = "childNightHeader"
            adultDayRow = headerSetupBox.row()
            if altProp is None or altProp.adultDayHeader.usePreviousHeader:
                adultDayRow.prop(self, prevHeaderName, text="Adult Day")
                adultDayRow.enabled = False
            else:
                adultDayRow.prop(self, "adultDayHeader", text="Adult Day")
                prevHeaderName = "adultDayHeader"
            adultNightRow = headerSetupBox.row()
            if altProp is None or altProp.adultNightHeader.usePreviousHeader:
                adultNightRow.prop(self, prevHeaderName, text="Adult Night")
                adultNightRow.enabled = False
            else:
                adultNightRow.prop(self, "adultNightHeader", text="Adult Night")

            headerSetupBox.row().label(text="Cutscene headers to include this actor in:")
            for i in range(len(self.cutsceneHeaders)):
                headerItemProps: OOTActorHeaderItemProperty = self.cutsceneHeaders[i]
                headerItemProps.draw_props(headerSetup, propUser, i, altProp, objName)
            drawAddButton(headerSetup, len(self.cutsceneHeaders), propUser, None, objName)


class OOTActorProperty(PropertyGroup):
    actorID: EnumProperty(name="Actor", items=ootData.actorData.ootEnumActorID, default="ACTOR_PLAYER")
    actorIDCustom: StringProperty(name="Actor ID", default="ACTOR_PLAYER")
    actorParam: StringProperty(name="Actor Parameter", default="0x0000")
    rotOverride: BoolProperty(name="Override Rotation", default=False)
    rotOverrideX: StringProperty(name="Rot X", default="0")
    rotOverrideY: StringProperty(name="Rot Y", default="0")
    rotOverrideZ: StringProperty(name="Rot Z", default="0")
    headerSettings: PointerProperty(type=OOTActorHeaderProperty)

    @staticmethod
    def upgrade_object(obj: Object):
        print(f"Processing '{obj.name}'...")
        upgradeActors(obj)

    def draw_props(self, layout: UILayout, altRoomProp: OOTAlternateRoomHeaderProperty, objName: str):
        # prop_split(layout, actorProp, 'actorID', 'Actor')
        actorIDBox = layout.column()
        # actorIDBox.box().label(text = "Settings")
        searchOp = actorIDBox.operator(OOT_SearchActorIDEnumOperator.bl_idname, icon="VIEWZOOM")
        searchOp.actorUser = "Actor"
        searchOp.objName = objName

        split = actorIDBox.split(factor=0.5)

        if self.actorID == "None":
            actorIDBox.box().label(text="This Actor was deleted from the XML file.")
            return

        split.label(text="Actor ID")
        split.label(text=getEnumName(ootData.actorData.ootEnumActorID, self.actorID))

        if self.actorID == "Custom":
            # actorIDBox.prop(actorProp, 'actorIDCustom', text = 'Actor ID')
            prop_split(actorIDBox, self, "actorIDCustom", "")

        # layout.box().label(text = 'Actor IDs defined in include/z64actors.h.')
        prop_split(actorIDBox, self, "actorParam", "Actor Parameter")

        actorIDBox.prop(self, "rotOverride", text="Override Rotation (ignore Blender rot)")
        if self.rotOverride:
            prop_split(actorIDBox, self, "rotOverrideX", "Rot X")
            prop_split(actorIDBox, self, "rotOverrideY", "Rot Y")
            prop_split(actorIDBox, self, "rotOverrideZ", "Rot Z")

        headerProp: OOTActorHeaderProperty = self.headerSettings
        headerProp.draw_props(actorIDBox, "Actor", altRoomProp, objName)


class OOTTransitionActorProperty(PropertyGroup):
    fromRoom: PointerProperty(type=Object, poll=lambda self, object: self.isRoomEmptyObject(object))
    toRoom: PointerProperty(type=Object, poll=lambda self, object: self.isRoomEmptyObject(object))
    cameraTransitionFront: EnumProperty(items=ootEnumCamTransition, default="0x00")
    cameraTransitionFrontCustom: StringProperty(default="0x00")
    cameraTransitionBack: EnumProperty(items=ootEnumCamTransition, default="0x00")
    cameraTransitionBackCustom: StringProperty(default="0x00")
    isRoomTransition: BoolProperty(name="Is Room Transition", default=True)

    actor: PointerProperty(type=OOTActorProperty)

    def isRoomEmptyObject(self, obj: Object):
        return obj.type == "EMPTY" and obj.ootEmptyType == "Room"

    def draw_props(
        self, layout: UILayout, altSceneProp: OOTAlternateSceneHeaderProperty, roomObj: Object, objName: str
    ):
        actorIDBox = layout.column()
        searchOp = actorIDBox.operator(OOT_SearchActorIDEnumOperator.bl_idname, icon="VIEWZOOM")
        searchOp.actorUser = "Transition Actor"
        searchOp.objName = objName

        split = actorIDBox.split(factor=0.5)
        split.label(text="Actor ID")
        split.label(text=getEnumName(ootData.actorData.ootEnumActorID, self.actor.actorID))

        if self.actor.actorID == "Custom":
            prop_split(actorIDBox, self.actor, "actorIDCustom", "")

        # layout.box().label(text = 'Actor IDs defined in include/z64actors.h.')
        prop_split(actorIDBox, self.actor, "actorParam", "Actor Parameter")

        if roomObj is None:
            actorIDBox.label(text="This must be part of a Room empty's hierarchy.", icon="OUTLINER")
        else:
            actorIDBox.prop(self, "isRoomTransition")
            if self.isRoomTransition:
                prop_split(actorIDBox, self, "fromRoom", "Room To Transition From")
                prop_split(actorIDBox, self, "toRoom", "Room To Transition To")
                if self.fromRoom == self.toRoom:
                    actorIDBox.label(text="Warning: You selected the same room!", icon="ERROR")
        actorIDBox.label(text='Y+ side of door faces toward the "from" room.', icon="ORIENTATION_NORMAL")
        drawEnumWithCustom(actorIDBox, self, "cameraTransitionFront", "Camera Transition Front", "")
        drawEnumWithCustom(actorIDBox, self, "cameraTransitionBack", "Camera Transition Back", "")

        headerProps: OOTActorHeaderProperty = self.actor.headerSettings
        headerProps.draw_props(actorIDBox, "Transition Actor", altSceneProp, objName)


class OOTEntranceProperty(PropertyGroup):
    # This is also used in entrance list.
    spawnIndex: IntProperty(min=0)
    customActor: BoolProperty(name="Use Custom Actor")
    actor: PointerProperty(type=OOTActorProperty)

    tiedRoom: PointerProperty(
        type=Object,
        poll=lambda self, object: self.isRoomEmptyObject(object),
        description="Used to set the room index",
    )

    def isRoomEmptyObject(self, obj: Object):
        return obj.type == "EMPTY" and obj.ootEmptyType == "Room"

    def draw_props(self, layout: UILayout, obj: Object, altSceneProp: OOTAlternateSceneHeaderProperty, objName: str):
        box = layout.column()
        # box.box().label(text = "Properties")
        roomObj = getRoomObj(obj)
        if roomObj is None:
            box.label(text="This must be part of a Room empty's hierarchy.", icon="OUTLINER")

        entranceProp = obj.ootEntranceProperty
        prop_split(box, entranceProp, "tiedRoom", "Room")
        prop_split(box, entranceProp, "spawnIndex", "Spawn Index")
        prop_split(box, entranceProp.actor, "actorParam", "Actor Param")
        box.prop(entranceProp, "customActor")
        if entranceProp.customActor:
            prop_split(box, entranceProp.actor, "actorIDCustom", "Actor ID Custom")

        headerProps: OOTActorHeaderProperty = entranceProp.actor.headerSettings
        headerProps.draw_props(box, "Entrance", altSceneProp, objName)


classes = (
    OOTActorHeaderItemProperty,
    OOTActorHeaderProperty,
    OOTActorProperty,
    OOTTransitionActorProperty,
    OOTEntranceProperty,
)


def actor_props_register():
    for cls in classes:
        register_class(cls)

    Object.ootActorProperty = PointerProperty(type=OOTActorProperty)
    Object.ootTransitionActorProperty = PointerProperty(type=OOTTransitionActorProperty)
    Object.ootEntranceProperty = PointerProperty(type=OOTEntranceProperty)


def actor_props_unregister():
    del Object.ootActorProperty
    del Object.ootTransitionActorProperty
    del Object.ootEntranceProperty

    for cls in reversed(classes):
        unregister_class(cls)
