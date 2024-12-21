from bpy.types import Object, PropertyGroup, UILayout
from bpy.utils import register_class, unregister_class
from bpy.props import EnumProperty, StringProperty, IntProperty, BoolProperty, CollectionProperty, PointerProperty
from ....utility import prop_split, label_split
from ...constants import mm_data, ootEnumCamTransition
from ...upgrade import upgradeActors
from ...room.properties import MM_AlternateRoomHeaderProperty
from ..operators import MM_SearchActorIDEnumOperator

from ...utility import (
    getRoomObj,
    getEnumName,
    drawAddButton,
    drawCollectionOps,
    drawEnumWithCustom,
)


class MM_ActorHeaderItemProperty(PropertyGroup):
    headerIndex: IntProperty(name="Scene Setup", min=1, default=1)

    def draw_props(
        self,
        layout: UILayout,
        propUser: str,
        index: int,
        altProp: MM_AlternateRoomHeaderProperty,
        objName: str,
    ):
        box = layout.column()
        row = box.row()
        row.prop(self, "headerIndex", text="")

        drawCollectionOps(row.row(align=True), index, propUser, None, objName, compact=True)

        if altProp is not None and self.headerIndex >= len(altProp.cutsceneHeaders) + 1:
            box.label(text="Above header does not exist.", icon="QUESTION")


class MM_ActorHeaderProperty(PropertyGroup):
    include_in_all_setups: BoolProperty(name="Include in all scene setups")
    childDayHeader: BoolProperty(name="Child Day Header", default=True)
    cutsceneHeaders: CollectionProperty(type=MM_ActorHeaderItemProperty)
    expand_tab: BoolProperty(name="Expand Tab")

    def checkHeader(self, index: int) -> bool:
        if index == 0:
            return self.childDayHeader
        else:
            return index in [value.headerIndex for value in self.cutsceneHeaders]

    def draw_props(
        self,
        layout: UILayout,
        propUser: str,
        altProp: MM_AlternateRoomHeaderProperty,
        objName: str,
    ):
        headerSetup = layout.column()

        header_settings_box = headerSetup.column().box()
        header_settings_box.label(text="Header Settings")
        header_settings_box.prop(self, "include_in_all_setups")

        if not self.include_in_all_setups:
            header_settings_box.prop(self, "childDayHeader", text="Default Header")

            cs_header_box = header_settings_box.box()
            cs_header_box.row().prop(
                self,
                "expand_tab",
                text="Cutscene Headers",
                icon="TRIA_DOWN" if self.expand_tab else "TRIA_RIGHT",
            )

            if self.expand_tab:
                for i in range(len(self.cutsceneHeaders)):
                    headerItemProps: MM_ActorHeaderItemProperty = self.cutsceneHeaders[i]
                    headerItemProps.draw_props(cs_header_box, propUser, i, altProp, objName)

                drawAddButton(cs_header_box, len(self.cutsceneHeaders), propUser, None, objName)


class MM_ActorProperty(PropertyGroup):
    actorID: EnumProperty(name="Actor", items=mm_data.actor_data.enum_actor_id, default="ACTOR_PLAYER")
    actorIDCustom: StringProperty(name="Actor ID", default="ACTOR_PLAYER")
    actorParam: StringProperty(name="Actor Parameter", default="0x0000")
    rotOverride: BoolProperty(
        name="Override Rotation",
        default=False,
        description="Non-zero values means the rotation is used as additional flags and will set the matching flag in the actor ID automatically",
    )
    rotOverrideX: StringProperty(name="Rot X", default="0")
    rotOverrideY: StringProperty(name="Rot Y", default="0")
    rotOverrideZ: StringProperty(name="Rot Z", default="0")
    headerSettings: PointerProperty(type=MM_ActorHeaderProperty)

    def draw_props(self, layout: UILayout, altRoomProp: MM_AlternateRoomHeaderProperty, objName: str):
        actorIDBox = layout.column()
        searchOp = actorIDBox.operator(MM_SearchActorIDEnumOperator.bl_idname, icon="VIEWZOOM")
        searchOp.actorUser = "Actor"
        searchOp.objName = objName

        split = actorIDBox.split(factor=0.5)

        if self.actorID == "None":
            actorIDBox.box().label(text="This Actor was deleted from the XML file.")
            return

        split.label(text="Actor ID")
        split.label(text=getEnumName(mm_data.actor_data.enum_actor_id, self.actorID))

        if self.actorID == "Custom":
            prop_split(actorIDBox, self, "actorIDCustom", "")

        prop_split(actorIDBox, self, "actorParam", "Actor Parameter")

        rot_box = actorIDBox.box()
        rot_box.prop(self, "rotOverride", text="Use Rotation Flags")
        if self.rotOverride:
            prop_split(rot_box, self, "rotOverrideX", "Rot X")
            prop_split(rot_box, self, "rotOverrideY", "Rot Y")
            prop_split(rot_box, self, "rotOverrideZ", "Rot Z")

        headerProp: MM_ActorHeaderProperty = self.headerSettings
        headerProp.draw_props(actorIDBox, "Actor", altRoomProp, objName)


class MM_TransitionActorProperty(PropertyGroup):
    fromRoom: PointerProperty(type=Object, poll=lambda self, object: self.isRoomEmptyObject(object))
    toRoom: PointerProperty(type=Object, poll=lambda self, object: self.isRoomEmptyObject(object))
    cameraTransitionFront: EnumProperty(items=ootEnumCamTransition, default="0x00")
    cameraTransitionFrontCustom: StringProperty(default="0x00")
    cameraTransitionBack: EnumProperty(items=ootEnumCamTransition, default="0x00")
    cameraTransitionBackCustom: StringProperty(default="0x00")
    isRoomTransition: BoolProperty(name="Is Room Transition", default=True)
    cutscene_id: StringProperty(
        name="Cutscene ID", default="CS_ID_GLOBAL_END", description="See the `CutsceneId` enum for more values"
    )

    actor: PointerProperty(type=MM_ActorProperty)

    def isRoomEmptyObject(self, obj: Object):
        return obj.type == "EMPTY" and obj.ootEmptyType == "Room"

    def draw_props(self, layout: UILayout, altSceneProp, roomObj: Object, objName: str):
        actorIDBox = layout.column()
        searchOp = actorIDBox.operator(MM_SearchActorIDEnumOperator.bl_idname, icon="VIEWZOOM")
        searchOp.actorUser = "Transition Actor"
        searchOp.objName = objName

        split = actorIDBox.split(factor=0.5)
        split.label(text="Actor ID")
        split.label(text=getEnumName(mm_data.actor_data.enum_actor_id, self.actor.actorID))

        if self.actor.actorID == "Custom":
            prop_split(actorIDBox, self.actor, "actorIDCustom", "")

        prop_split(actorIDBox, self, "cutscene_id", "Cutscene ID")
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

        headerProps: MM_ActorHeaderProperty = self.actor.headerSettings
        headerProps.draw_props(actorIDBox, "Transition Actor", altSceneProp, objName)


class MM_EntranceProperty(PropertyGroup):
    # This is also used in entrance list.
    spawnIndex: IntProperty(min=0)
    customActor: BoolProperty(name="Use Custom Actor")
    actor: PointerProperty(type=MM_ActorProperty)

    tiedRoom: PointerProperty(
        type=Object,
        poll=lambda self, object: self.isRoomEmptyObject(object),
        description="Used to set the room index",
    )

    def isRoomEmptyObject(self, obj: Object):
        return obj.type == "EMPTY" and obj.ootEmptyType == "Room"

    def draw_props(self, layout: UILayout, obj: Object, altSceneProp, objName: str):
        box = layout.column()

        roomObj = getRoomObj(obj)
        if roomObj is None:
            box.label(text="This must be part of a Room empty's hierarchy.", icon="OUTLINER")

        entranceProp = obj.mm_entrance_property
        box.prop(entranceProp, "customActor")

        if entranceProp.customActor:
            prop_split(box, entranceProp.actor, "actorIDCustom", "Actor ID Custom")

        prop_split(box, entranceProp, "tiedRoom", "Room")
        prop_split(box, entranceProp, "spawnIndex", "Spawn Index")
        prop_split(box, self, "actorParam", "Actor Parameter")

        headerProps: MM_ActorHeaderProperty = entranceProp.actor.headerSettings
        headerProps.draw_props(box, "Entrance", altSceneProp, objName)


classes = (
    MM_ActorHeaderItemProperty,
    MM_ActorHeaderProperty,
    MM_ActorProperty,
    MM_TransitionActorProperty,
    MM_EntranceProperty,
)


def mm_actor_props_register():
    for cls in classes:
        register_class(cls)

    Object.mm_actor_property = PointerProperty(type=MM_ActorProperty)
    Object.mm_transition_actor_property = PointerProperty(type=MM_TransitionActorProperty)
    Object.mm_entrance_property = PointerProperty(type=MM_EntranceProperty)


def mm_actor_props_unregister():
    del Object.mm_actor_property
    del Object.mm_transition_actor_property
    del Object.mm_entrance_property

    for cls in reversed(classes):
        unregister_class(cls)
