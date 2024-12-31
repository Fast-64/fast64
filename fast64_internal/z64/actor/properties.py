from bpy.types import Object, PropertyGroup, UILayout, Context
from bpy.utils import register_class, unregister_class
from bpy.props import EnumProperty, StringProperty, IntProperty, BoolProperty, CollectionProperty, PointerProperty
from ...utility import prop_split, label_split
from ..constants import oot_data, ootEnumCamTransition, mm_data
from ..upgrade import upgradeActors
from ..scene.properties import Z64_AlternateSceneHeaderProperty
from ..room.properties import Z64_AlternateRoomHeaderProperty
from .operators import OOT_SearchActorIDEnumOperator, MM_SearchActorIDEnumOperator

from ..utility import (
    getRoomObj,
    getEnumName,
    drawAddButton,
    drawCollectionOps,
    drawEnumWithCustom,
    get_game_prop_name,
    get_cs_index_start,
    is_oot_features,
    is_game_oot,
    get_game_enum,
)

ootEnumSceneSetupPreset = [
    ("Custom", "Custom", "Custom"),
    ("All Scene Setups", "All Scene Setups", "All Scene Setups"),
    ("All Non-Cutscene Scene Setups", "All Non-Cutscene Scene Setups", "All Non-Cutscene Scene Setups"),
]


# TODO: remove
def update_cutscene_index(self, context: Context):
    cs_index_start = get_cs_index_start()

    if self.headerIndex < cs_index_start:
        self.headerIndex = cs_index_start


class Z64_ActorHeaderItemProperty(PropertyGroup):
    headerIndex: IntProperty(name="Scene Setup", min=1, default=1, update=update_cutscene_index)

    def draw_props(
        self,
        layout: UILayout,
        propUser: str,
        index: int,
        altProp: Z64_AlternateSceneHeaderProperty | Z64_AlternateRoomHeaderProperty,
        objName: str,
    ):
        box = layout.column()
        row = box.row()
        row.prop(self, "headerIndex", text="")

        drawCollectionOps(row.row(align=True), index, propUser, None, objName, compact=True)

        if altProp is not None and self.headerIndex >= len(altProp.cutsceneHeaders) + get_cs_index_start():
            box.label(text="Above header does not exist.", icon="QUESTION")


class Z64_ActorHeaderProperty(PropertyGroup):
    childDayHeader: BoolProperty(name="Child Day Header", default=True)
    cutsceneHeaders: CollectionProperty(type=Z64_ActorHeaderItemProperty)

    # OoT exclusive
    sceneSetupPreset: EnumProperty(name="Scene Setup Preset", items=ootEnumSceneSetupPreset, default="All Scene Setups")
    childNightHeader: BoolProperty(name="Child Night Header", default=True)
    adultDayHeader: BoolProperty(name="Adult Day Header", default=True)
    adultNightHeader: BoolProperty(name="Adult Night Header", default=True)

    # MM exclusive
    include_in_all_setups: BoolProperty(name="Include in all scene setups")
    expand_tab: BoolProperty(name="Expand Tab")

    def checkHeader(self, index: int) -> bool:
        if index == 0:
            return self.childDayHeader
        elif is_game_oot():
            if index == 1:
                return self.childNightHeader
            elif index == 2:
                return self.adultDayHeader
            elif index == 3:
                return self.adultNightHeader

        return index in [value.headerIndex for value in self.cutsceneHeaders]

    def draw_props(
        self,
        layout: UILayout,
        propUser: str,
        altProp: Z64_AlternateSceneHeaderProperty | Z64_AlternateRoomHeaderProperty,
        objName: str,
    ):
        headerSetup = layout.column()

        if is_game_oot():
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
                    headerItemProps: Z64_ActorHeaderItemProperty = self.cutsceneHeaders[i]
                    headerItemProps.draw_props(headerSetup, propUser, i, altProp, objName)
                drawAddButton(headerSetup, len(self.cutsceneHeaders), propUser, None, objName)
        else:
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
                        headerItemProps: Z64_ActorHeaderItemProperty = self.cutsceneHeaders[i]
                        headerItemProps.draw_props(cs_header_box, propUser, i, altProp, objName)

                    drawAddButton(cs_header_box, len(self.cutsceneHeaders), propUser, None, objName)


class Z64_ActorProperty(PropertyGroup):
    actorID: EnumProperty(name="Actor", items=oot_data.actorData.ootEnumActorID, default="ACTOR_PLAYER")
    mm_actor_id: EnumProperty(name="Actor", items=mm_data.actor_data.enum_actor_id, default="ACTOR_PLAYER")
    actorIDCustom: StringProperty(name="Actor ID", default="ACTOR_PLAYER")
    actorParam: StringProperty(name="Actor Parameter", default="0x0000")
    rotOverride: BoolProperty(
        name="Override Rotation",
        default=False,
        description="For MM, non-zero values means the rotation is used as additional flags and will set the matching flag in the actor ID automatically",
    )
    rotOverrideX: StringProperty(name="Rot X", default="0")
    rotOverrideY: StringProperty(name="Rot Y", default="0")
    rotOverrideZ: StringProperty(name="Rot Z", default="0")
    headerSettings: PointerProperty(type=Z64_ActorHeaderProperty)

    @staticmethod
    def upgrade_object(obj: Object):
        if is_game_oot():
            print(f"Processing '{obj.name}'...")
            upgradeActors(obj)

    def draw_props(self, layout: UILayout, altRoomProp: Z64_AlternateRoomHeaderProperty, objName: str):
        actorIDBox = layout.column()
        actor_id: str = getattr(self, get_game_prop_name("actor_id"))

        if is_game_oot():
            op_name = OOT_SearchActorIDEnumOperator.bl_idname
        else:
            op_name = MM_SearchActorIDEnumOperator.bl_idname

        searchOp = actorIDBox.operator(op_name, icon="VIEWZOOM")
        searchOp.actorUser = "Actor"
        searchOp.objName = objName

        split = actorIDBox.split(factor=0.5)

        if actor_id == "None":
            actorIDBox.box().label(text="This Actor was deleted from the XML file.")
            return

        split.label(text="Actor ID")
        split.label(text=getEnumName(get_game_enum("enum_actor_id"), actor_id))

        if actor_id == "Custom":
            prop_split(actorIDBox, self, "actorIDCustom", "")

        prop_split(actorIDBox, self, "actorParam", "Actor Parameter")

        rot_box = actorIDBox.box()
        prop_text = "Override Rotation (ignore Blender rot)" if is_oot_features() else "Use Rotation Flags"
        rot_box.prop(self, "rotOverride", text=prop_text)
        if self.rotOverride:
            prop_split(rot_box, self, "rotOverrideX", "Rot X")
            prop_split(rot_box, self, "rotOverrideY", "Rot Y")
            prop_split(rot_box, self, "rotOverrideZ", "Rot Z")

        headerProp: Z64_ActorHeaderProperty = self.headerSettings
        headerProp.draw_props(actorIDBox, "Actor", altRoomProp, objName)


class Z64_TransitionActorProperty(PropertyGroup):
    fromRoom: PointerProperty(type=Object, poll=lambda self, object: self.isRoomEmptyObject(object))
    toRoom: PointerProperty(type=Object, poll=lambda self, object: self.isRoomEmptyObject(object))
    cameraTransitionFront: EnumProperty(items=ootEnumCamTransition, default="0x00")
    cameraTransitionFrontCustom: StringProperty(default="0x00")
    cameraTransitionBack: EnumProperty(items=ootEnumCamTransition, default="0x00")
    cameraTransitionBackCustom: StringProperty(default="0x00")
    isRoomTransition: BoolProperty(name="Is Room Transition", default=True)

    actor: PointerProperty(type=Z64_ActorProperty)

    # MM exclusive
    cutscene_id: StringProperty(
        name="Cutscene ID", default="CS_ID_GLOBAL_END", description="See the `CutsceneId` enum for more values"
    )

    def isRoomEmptyObject(self, obj: Object):
        return obj.type == "EMPTY" and obj.ootEmptyType == "Room"

    def draw_props(
        self, layout: UILayout, altSceneProp: Z64_AlternateSceneHeaderProperty, roomObj: Object, objName: str
    ):
        actorIDBox = layout.column()

        if is_game_oot():
            op_name = OOT_SearchActorIDEnumOperator.bl_idname
        else:
            op_name = MM_SearchActorIDEnumOperator.bl_idname

        searchOp = actorIDBox.operator(op_name, icon="VIEWZOOM")
        searchOp.actorUser = "Transition Actor"
        searchOp.objName = objName

        split = actorIDBox.split(factor=0.5)
        split.label(text="Actor ID")
        actor_id = getattr(self.actor, get_game_prop_name("actor_id"))
        split.label(text=getEnumName(get_game_enum("enum_actor_id"), actor_id))

        if actor_id == "Custom":
            prop_split(actorIDBox, self.actor, "actorIDCustom", "")

        if not is_oot_features():
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

        headerProps: Z64_ActorHeaderProperty = self.actor.headerSettings
        headerProps.draw_props(actorIDBox, "Transition Actor", altSceneProp, objName)


class Z64_EntranceProperty(PropertyGroup):
    # This is also used in entrance list.
    spawnIndex: IntProperty(min=0)
    customActor: BoolProperty(name="Use Custom Actor")
    actor: PointerProperty(type=Z64_ActorProperty)

    tiedRoom: PointerProperty(
        type=Object,
        poll=lambda self, object: self.isRoomEmptyObject(object),
        description="Used to set the room index",
    )

    def isRoomEmptyObject(self, obj: Object):
        return obj.type == "EMPTY" and obj.ootEmptyType == "Room"

    def draw_props(self, layout: UILayout, obj: Object, altSceneProp: Z64_AlternateSceneHeaderProperty, objName: str):
        box = layout.column()

        roomObj = getRoomObj(obj)
        if roomObj is None:
            box.label(text="This must be part of a Room empty's hierarchy.", icon="OUTLINER")

        entranceProp = obj.ootEntranceProperty
        box.prop(entranceProp, "customActor")

        if entranceProp.customActor:
            prop_split(box, entranceProp.actor, "actorIDCustom", "Actor ID Custom")

        prop_split(box, entranceProp, "tiedRoom", "Room")
        prop_split(box, entranceProp, "spawnIndex", "Spawn Index")
        prop_split(box, entranceProp.actor, "actorParam", "Actor Param")

        headerProps: Z64_ActorHeaderProperty = entranceProp.actor.headerSettings
        headerProps.draw_props(box, "Entrance", altSceneProp, objName)


classes = (
    Z64_ActorHeaderItemProperty,
    Z64_ActorHeaderProperty,
    Z64_ActorProperty,
    Z64_TransitionActorProperty,
    Z64_EntranceProperty,
)


def actor_props_register():
    for cls in classes:
        register_class(cls)

    Object.ootActorProperty = PointerProperty(type=Z64_ActorProperty)
    Object.ootTransitionActorProperty = PointerProperty(type=Z64_TransitionActorProperty)
    Object.ootEntranceProperty = PointerProperty(type=Z64_EntranceProperty)


def actor_props_unregister():
    del Object.ootActorProperty
    del Object.ootTransitionActorProperty
    del Object.ootEntranceProperty

    for cls in reversed(classes):
        unregister_class(cls)
