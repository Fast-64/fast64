from bpy.types import PropertyGroup, Object
from bpy.props import IntProperty, StringProperty, PointerProperty
from bpy.utils import register_class, unregister_class


class OOTCSMotionActorCueListProperty(PropertyGroup):
    actor_id: IntProperty(
        name="Actor ID",
        description="Cutscene actor ID. Use -1 for Link. Not the same as actor number.",
        default=-1,
        min=-1,
    )


class OOTCSMotionActorCuePointProperty(PropertyGroup):
    start_frame: IntProperty(name="Start Frame", description="Key point start frame within cutscene", default=0, min=0)
    action_id: StringProperty(
        name="Action ID", default="0x0001", description="Actor action. Meaning is unique for each different actor."
    )


def csMotion_props_register():
    register_class(OOTCSMotionActorCueListProperty)
    register_class(OOTCSMotionActorCuePointProperty)
    Object.zc_alist = PointerProperty(type=OOTCSMotionActorCueListProperty)
    Object.zc_apoint = PointerProperty(type=OOTCSMotionActorCuePointProperty)


def csMotion_props_unregister():
    del Object.zc_apoint
    del Object.zc_alist
    unregister_class(OOTCSMotionActorCuePointProperty)
    unregister_class(OOTCSMotionActorCueListProperty)
