import bpy
from bpy.types import Operator
from bpy.utils import register_class, unregister_class
from bpy.props import EnumProperty, IntProperty, StringProperty
from ...utility import ootGetSceneOrRoomHeader
from ..constants import oot_data, mm_data


class OOT_SearchObjectEnumOperator(Operator):
    bl_idname = "object.oot_search_object_enum_operator"
    bl_label = "Search Object ID"
    bl_property = "objectKey"
    bl_options = {"REGISTER", "UNDO"}

    objectKey: EnumProperty(items=oot_data.objectData.ootEnumObjectKey, default="obj_human")
    headerIndex: IntProperty(default=0, min=0)
    index: IntProperty(default=0, min=0)
    objName: StringProperty()

    def execute(self, context):
        roomHeader = ootGetSceneOrRoomHeader(bpy.data.objects[self.objName], self.headerIndex, True)
        roomHeader.objectList[self.index].objectKey = self.objectKey
        context.region.tag_redraw()
        self.report({"INFO"}, "Selected: " + self.objectKey)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class MM_SearchObjectEnumOperator(Operator):
    bl_idname = "object.mm_search_object_enum_operator"
    bl_label = "Search Object ID"
    bl_property = "object_key"
    bl_options = {"REGISTER", "UNDO"}

    object_key: EnumProperty(items=mm_data.object_data.enum_object_key, default="gameplay_keep")
    header_index: IntProperty(default=0, min=0)
    index: IntProperty(default=0, min=0)
    obj_name: StringProperty()

    def execute(self, context):
        roomHeader = ootGetSceneOrRoomHeader(bpy.data.objects[self.obj_name], self.header_index, True)
        roomHeader.objectList[self.index].object_key = self.object_key
        context.region.tag_redraw()
        self.report({"INFO"}, "Selected: " + self.object_key)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


classes = (
    OOT_SearchObjectEnumOperator,
    MM_SearchObjectEnumOperator,
)


def room_ops_register():
    for cls in classes:
        register_class(cls)


def room_ops_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
