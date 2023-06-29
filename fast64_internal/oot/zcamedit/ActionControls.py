from bpy.types import PropertyGroup, Operator, Panel, Object
from bpy.props import IntProperty, StringProperty, PointerProperty
from bpy.utils import register_class, unregister_class
from .ActionData import IsActionPoint, IsActionList, CreateDefaultActionPoint, CreateOrInitPreview, IsPreview


class ActionListProps(PropertyGroup):
    actor_id: IntProperty(
        name="Actor ID",
        description="Cutscene actor ID. Use -1 for Link. Not the same as actor number.",
        default=-1,
        min=-1,
    )


class ActionPointProps(PropertyGroup):
    start_frame: IntProperty(name="Start Frame", description="Key point start frame within cutscene", default=0, min=0)
    action_id: StringProperty(
        name="Action ID", default="0x0001", description="Actor action. Meaning is unique for each different actor."
    )


def CheckGetActionList(op, context):
    obj = context.view_layer.objects.active
    if IsActionPoint(obj):
        obj = obj.parent
    if not IsActionList(obj):
        op.report({"WARNING"}, "Select an action list or action point.")
        return None
    return obj


class ZCAMEDIT_OT_add_action_point(Operator):
    """Add a point to a Link or actor action list"""

    bl_idname = "zcamedit.add_action_point"
    bl_label = "Add point to current action"

    def execute(self, context):
        al_object = CheckGetActionList(self, context)
        if not al_object:
            return {"CANCELLED"}
        CreateDefaultActionPoint(context, al_object, True)
        return {"FINISHED"}


class ZCAMEDIT_OT_create_action_preview(Operator):
    """Create a preview empty object for a Link or actor action list"""

    bl_idname = "zcamedit.create_action_preview"
    bl_label = "Create preview object for action"

    def execute(self, context):
        al_object = CheckGetActionList(self, context)
        if not al_object:
            return {"CANCELLED"}
        CreateOrInitPreview(context, al_object.parent, al_object.zc_alist.actor_id, True)
        return {"FINISHED"}


class ZCAMEDIT_PT_action_controls_panel(Panel):
    bl_label = "zcamedit Action Controls"
    bl_idname = "ZCAMEDIT_PT_action_controls_panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        layout = self.layout
        obj = context.view_layer.objects.active
        if IsActionPoint(obj):
            r = layout.row()
            r.label(text="Action point:")
            r.prop(obj.zc_apoint, "start_frame")
            r.prop(obj.zc_apoint, "action_id")
            obj = obj.parent
        if IsActionList(obj):
            r = layout.row()
            r.label(text="Action list:")
            r.prop(obj.zc_alist, "actor_id")
            layout.operator("zcamedit.add_action_point")
            layout.operator("zcamedit.create_action_preview")
        if IsPreview(obj):
            r = layout.row()
            r.label(text="Preview:")
            r.prop(obj.zc_alist, "actor_id")


def ActionControls_register():
    register_class(ZCAMEDIT_OT_add_action_point)
    register_class(ZCAMEDIT_OT_create_action_preview)
    register_class(ZCAMEDIT_PT_action_controls_panel)
    register_class(ActionListProps)
    register_class(ActionPointProps)
    Object.zc_alist = PointerProperty(type=ActionListProps)
    Object.zc_apoint = PointerProperty(type=ActionPointProps)


def ActionControls_unregister():
    del Object.zc_apoint
    del Object.zc_alist
    unregister_class(ActionPointProps)
    unregister_class(ActionListProps)
    unregister_class(ZCAMEDIT_PT_action_controls_panel)
    unregister_class(ZCAMEDIT_OT_create_action_preview)
    unregister_class(ZCAMEDIT_OT_add_action_point)
