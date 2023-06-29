import bpy
import random

from bpy.props import FloatProperty, EnumProperty

from .Common import *
from .CamData import *
from .ActionData import *
from .InitCS import InitCS


def CheckGetCSObj(op, context):
    """Check if we are editing a cutscene."""
    cs_object = context.view_layer.objects.active
    if cs_object is None or cs_object.type != "EMPTY":
        if op:
            op.report({"WARNING"}, "Must have an empty object active (selected)")
        return None
    if not cs_object.name.startswith("Cutscene."):
        if op:
            op.report({"WARNING"}, 'Cutscene empty object must be named "Cutscene.<YourCutsceneName>"')
        return None
    return cs_object


class ZCAMEDIT_OT_init_cs(bpy.types.Operator):
    """Click here after adding an empty Cutscene.YourCutsceneName"""

    bl_idname = "zcamedit.init_cs"
    bl_label = "Init Cutscene Empty"

    def execute(self, context):
        cs_object = CheckGetCSObj(self, context)
        if cs_object is None:
            return {"CANCELLED"}
        InitCS(context, cs_object)
        return {"FINISHED"}


class ZCAMEDIT_OT_create_shot(bpy.types.Operator):
    """Create and initialize a camera shot armature"""

    bl_idname = "zcamedit.create_shot"
    bl_label = "Create camera shot"

    def execute(self, context):
        cs_object = CheckGetCSObj(self, context)
        if cs_object is None:
            return {"CANCELLED"}
        CreateShot(context, cs_object)
        return {"FINISHED"}


class ZCAMEDIT_OT_create_link_action(bpy.types.Operator):
    """Create a cutscene action list for Link"""

    bl_idname = "zcamedit.create_link_action"
    bl_label = "Create Link action list"

    def execute(self, context):
        cs_object = CheckGetCSObj(self, context)
        if cs_object is None:
            return {"CANCELLED"}
        CreateDefaultActorAction(context, -1, cs_object)
        return {"FINISHED"}


class ZCAMEDIT_OT_create_actor_action(bpy.types.Operator):
    """Create a cutscene action list for an actor (NPC)"""

    bl_idname = "zcamedit.create_actor_action"
    bl_label = "Create actor (NPC) action list"

    def execute(self, context):
        cs_object = CheckGetCSObj(self, context)
        if cs_object is None:
            return {"CANCELLED"}
        CreateDefaultActorAction(context, random.randint(1, 100), cs_object)
        return {"FINISHED"}


class ZCAMEDIT_PT_cs_controls_panel(bpy.types.Panel):
    bl_label = "zcamedit Cutscene Controls"
    bl_idname = "ZCAMEDIT_PT_cs_controls_panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        layout = self.layout
        if CheckGetCSObj(None, context):
            layout.prop(context.scene, "ootBlenderScale")
            layout.prop(context.scene, "zc_previewlinkage")
            layout.operator("zcamedit.init_cs")
            layout.operator("zcamedit.create_shot")
            layout.operator("zcamedit.create_link_action")
            layout.operator("zcamedit.create_actor_action")


def CSControls_register():
    bpy.utils.register_class(ZCAMEDIT_OT_init_cs)
    bpy.utils.register_class(ZCAMEDIT_OT_create_shot)
    bpy.utils.register_class(ZCAMEDIT_OT_create_link_action)
    bpy.utils.register_class(ZCAMEDIT_OT_create_actor_action)
    bpy.utils.register_class(ZCAMEDIT_PT_cs_controls_panel)
    if not hasattr(bpy.types.Scene, "ootBlenderScale"):
        bpy.types.Scene.ootBlenderScale = FloatProperty(
            name="Scale",
            description="All stair steps in game are 10 units high. Assuming Hylian "
            + "carpenters follow US building codes, that's about 17 cm or a scale of about "
            + "56 if your scene is in meters.",
            soft_min=1.0,
            soft_max=1000.0,
            default=56.0,
        )
    bpy.types.Scene.zc_previewlinkage = EnumProperty(
        items=[("link_adult", "Adult", "Adult Link (170 cm)", 0), ("link_child", "Child", "Child Link (130 cm)", 1)],
        name="Link age for preview",
        description="For setting Link's height for preview",
        default="link_adult",
    )


def CSControls_unregister():
    del bpy.types.Scene.zc_previewlinkage
    bpy.utils.unregister_class(ZCAMEDIT_PT_cs_controls_panel)
    bpy.utils.unregister_class(ZCAMEDIT_OT_create_actor_action)
    bpy.utils.unregister_class(ZCAMEDIT_OT_create_link_action)
    bpy.utils.unregister_class(ZCAMEDIT_OT_create_shot)
    bpy.utils.unregister_class(ZCAMEDIT_OT_init_cs)
