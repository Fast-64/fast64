import bpy
from bpy.types import Operator, Object, PropertyGroup
from bpy.utils import register_class, unregister_class
from bpy.props import EnumProperty, StringProperty, IntProperty, BoolProperty, CollectionProperty, PointerProperty
from ....utility import PluginError
from ...oot_constants import ootData, ootEnumSceneSetupPreset, ootEnumCamTransition


class OOT_SearchActorIDEnumOperator(Operator):
    bl_idname = "object.oot_search_actor_id_enum_operator"
    bl_label = "Select Actor ID"
    bl_property = "actorID"
    bl_options = {"REGISTER", "UNDO"}

    actorID: EnumProperty(items=ootData.actorData.ootEnumActorID, default="ACTOR_PLAYER")
    actorUser: StringProperty(default="Actor")
    objName: StringProperty()

    def execute(self, context):
        obj = bpy.data.objects[self.objName]
        if self.actorUser == "Transition Actor":
            obj.ootTransitionActorProperty.actor.actorID = self.actorID
        elif self.actorUser == "Actor":
            obj.ootActorProperty.actorID = self.actorID
        elif self.actorUser == "Entrance":
            obj.ootEntranceProperty.actor.actorID = self.actorID
        else:
            raise PluginError("Invalid actor user for search: " + str(self.actorUser))

        context.region.tag_redraw()
        self.report({"INFO"}, "Selected: " + self.actorID)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class OOTActorHeaderItemProperty(PropertyGroup):
    headerIndex: IntProperty(name="Scene Setup", min=4, default=4)
    expandTab: BoolProperty(name="Expand Tab")


class OOTActorHeaderProperty(PropertyGroup):
    sceneSetupPreset: EnumProperty(
        name="Scene Setup Preset", items=ootEnumSceneSetupPreset, default="All Scene Setups"
    )
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


class OOTActorProperty(PropertyGroup):
    actorID: EnumProperty(name="Actor", items=ootData.actorData.ootEnumActorID, default="ACTOR_PLAYER")
    actorIDCustom: StringProperty(name="Actor ID", default="ACTOR_PLAYER")
    actorParam: StringProperty(name="Actor Parameter", default="0x0000")
    rotOverride: BoolProperty(name="Override Rotation", default=False)
    rotOverrideX: StringProperty(name="Rot X", default="0")
    rotOverrideY: StringProperty(name="Rot Y", default="0")
    rotOverrideZ: StringProperty(name="Rot Z", default="0")
    headerSettings: PointerProperty(type=OOTActorHeaderProperty)


class OOTTransitionActorProperty(PropertyGroup):
    roomIndex: IntProperty(min=0)
    cameraTransitionFront: EnumProperty(items=ootEnumCamTransition, default="0x00")
    cameraTransitionFrontCustom: StringProperty(default="0x00")
    cameraTransitionBack: EnumProperty(items=ootEnumCamTransition, default="0x00")
    cameraTransitionBackCustom: StringProperty(default="0x00")
    dontTransition: BoolProperty(default=False)

    actor: PointerProperty(type=OOTActorProperty)


class OOTEntranceProperty(PropertyGroup):
    # This is also used in entrance list, and roomIndex is obtained from the room this empty is parented to.
    spawnIndex: IntProperty(min=0)
    customActor: BoolProperty(name="Use Custom Actor")
    actor: PointerProperty(type=OOTActorProperty)


classes = (
    OOT_SearchActorIDEnumOperator,
    OOTActorHeaderItemProperty,
    OOTActorHeaderProperty,
    OOTActorProperty,
    OOTTransitionActorProperty,
    OOTEntranceProperty,
)


def actor_props_classes_register():
    for cls in classes:
        register_class(cls)

    Object.ootActorProperty = PointerProperty(type=OOTActorProperty)
    Object.ootTransitionActorProperty = PointerProperty(type=OOTTransitionActorProperty)
    Object.ootEntranceProperty = PointerProperty(type=OOTEntranceProperty)


def actor_props_classes_unregister():
    del Object.ootActorProperty
    del Object.ootTransitionActorProperty
    del Object.ootEntranceProperty

    for cls in reversed(classes):
        unregister_class(cls)
