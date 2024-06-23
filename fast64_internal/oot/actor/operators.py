import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, StringProperty
from bpy.utils import register_class, unregister_class
from ...utility import PluginError
from ..oot_constants import ootData


class OOT_SearchChestContentEnumOperator(Operator):
    bl_idname = "object.oot_search_chest_content_enum_operator"
    bl_label = "Select Chest Content"
    bl_property = "chestContent"
    bl_options = {"REGISTER", "UNDO"}

    chestContent: EnumProperty(items=ootData.actorData.ootEnumChestContent, default="item_heart")
    objName: StringProperty()
    propName: StringProperty()

    def execute(self, context):
        setattr(bpy.data.objects[self.objName].ootActorProperty, self.propName, self.chestContent)
        context.region.tag_redraw()
        self.report({"INFO"}, "Selected: " + self.chestContent)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class OOT_SearchNaviMsgIDEnumOperator(Operator):
    bl_idname = "object.oot_search_navi_msg_id_enum_operator"
    bl_label = "Select Message ID"
    bl_property = "naviMsgID"
    bl_options = {"REGISTER", "UNDO"}

    naviMsgID: EnumProperty(items=ootData.actorData.ootEnumNaviMessageData, default="msg_00")
    objName: StringProperty()
    propName: StringProperty()

    def execute(self, context):
        setattr(bpy.data.objects[self.objName].ootActorProperty, self.propName, self.naviMsgID)
        context.region.tag_redraw()
        self.report({"INFO"}, "Selected: " + self.naviMsgID)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class OOT_SearchActorIDEnumOperator(Operator):
    bl_idname = "object.oot_search_actor_id_enum_operator"
    bl_label = "Select Actor ID"
    bl_property = "actorID"
    bl_options = {"REGISTER", "UNDO"}

    actorID: EnumProperty(items=lambda self, context: ootData.actorData.getItems(self.actorUser))
    actorUser: StringProperty(default="Actor")
    objName: StringProperty()

    def execute(self, context):
        obj = bpy.data.objects[self.objName]
        if self.actorUser == "Transition Actor":
            obj.ootTransitionActorProperty.actor.actorID = self.actorID
        elif self.actorUser == "Actor":
            obj.ootActorProperty.actorID = self.actorID
        else:
            raise PluginError("Invalid actor user for search: " + str(self.actorUser))

        context.region.tag_redraw()
        self.report({"INFO"}, "Selected: " + self.actorID)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


classes = (
    OOT_SearchActorIDEnumOperator,
    OOT_SearchChestContentEnumOperator,
    OOT_SearchNaviMsgIDEnumOperator,
)


def actor_ops_register():
    for cls in classes:
        register_class(cls)


def actor_ops_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
