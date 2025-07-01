import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, StringProperty
from bpy.utils import register_class, unregister_class
from ...utility import PluginError
from ...game_data import game_data


class OOT_SearchChestContentEnumOperator(Operator):
    bl_idname = "object.oot_search_chest_content_enum_operator"
    bl_label = "Select Chest Content"
    bl_property = "chest_content"
    bl_options = {"REGISTER", "UNDO"}

    chest_content: EnumProperty(items=lambda self, context: game_data.z64.get_enum("chest_content"), default=1)
    obj_name: StringProperty()
    prop_name: StringProperty()

    def execute(self, context):
        setattr(bpy.data.objects[self.obj_name].ootActorProperty, self.prop_name, self.chest_content)
        context.region.tag_redraw()
        self.report({"INFO"}, f"Selected: {self.chest_content}")
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class OOT_SearchNaviMsgIDEnumOperator(Operator):
    bl_idname = "object.oot_search_navi_msg_id_enum_operator"
    bl_label = "Select Message ID"
    bl_property = "navi_msg_id"
    bl_options = {"REGISTER", "UNDO"}

    navi_msg_id: EnumProperty(items=lambda self, context: game_data.z64.get_enum("navi_msg_id"), default=1)
    obj_name: StringProperty()
    prop_name: StringProperty()

    def execute(self, context):
        setattr(bpy.data.objects[self.obj_name].ootActorProperty, self.prop_name, self.navi_msg_id)
        context.region.tag_redraw()
        self.report({"INFO"}, f"Selected: {self.navi_msg_id}")
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class OOT_SearchActorIDEnumOperator(Operator):
    bl_idname = "object.oot_search_actor_id_enum_operator"
    bl_label = "Select Actor ID"
    bl_property = "actor_id"
    bl_options = {"REGISTER", "UNDO"}

    actor_id: EnumProperty(items=lambda self, context: game_data.z64.actors.getItems(self.actor_user))
    actor_user: StringProperty(default="Actor")
    obj_name: StringProperty()

    def execute(self, context):
        obj = bpy.data.objects[self.obj_name]

        if self.actor_user == "Transition Actor":
            obj.ootTransitionActorProperty.actor.actor_id = self.actor_id
        elif self.actor_user == "Actor":
            obj.ootActorProperty.actor_id = self.actor_id
        else:
            raise PluginError("Invalid actor user for search: " + str(self.actor_user))

        context.region.tag_redraw()
        self.report({"INFO"}, f"Selected: {self.actor_id}")
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
