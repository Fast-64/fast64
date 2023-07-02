from bpy.types import PropertyGroup, Object, UILayout, Armature, Bone
from bpy.props import IntProperty, StringProperty, PointerProperty, EnumProperty, FloatProperty
from bpy.utils import register_class, unregister_class
from ...oot_upgrade import upgradeCutsceneMotion
from .constants import ootEnumCSMotionCamMode


class OOTCSMotionActorCueListProperty(PropertyGroup):
    actor_id: IntProperty(
        name="Actor ID",
        description="Cutscene actor ID. Use -1 for Link. Not the same as actor number.",
        default=-1,
        min=-1,
    )

    def draw_props(self, layout: UILayout, isPreview: bool):
        row = layout.row()
        row.label(text="Preview:" if isPreview else "Actor Cue List:")
        row.prop(self, "actor_id")


class OOTCSMotionActorCuePointProperty(PropertyGroup):
    start_frame: IntProperty(name="Start Frame", description="Key point start frame within cutscene", default=0, min=0)
    action_id: StringProperty(
        name="Action ID", default="0x0001", description="Actor action. Meaning is unique for each different actor."
    )

    def draw_props(self, layout: UILayout):
        row = layout.row()
        row.label(text="Actor Cue Point:")
        row.prop(self, "start_frame")
        row.prop(self, "action_id")


class OOTCSMotionCameraShotProperty(PropertyGroup):
    # Armature
    start_frame: IntProperty(name="Start Frame", description="Shot start frame", default=0, min=0)
    cam_mode: EnumProperty(
        items=ootEnumCSMotionCamMode,
        name="Mode",
        description="Camera command mode",
        default="normal",
    )

    def draw_props(self, layout: UILayout, label: str):
        box = layout.box()
        box.label(text=label)
        box.prop(self, "start_frame")
        box.row().prop(self, "cam_mode", expand=True)


class OOTCSMotionCameraShotPointProperty(PropertyGroup):
    # Bone
    frames: IntProperty(name="Frames", description="Key point frames value", default=1234, min=0)
    fov: FloatProperty(name="FoV", description="Field of view (degrees)", default=179.76, min=0.01, max=179.99)
    camroll: IntProperty(
        name="Roll",
        description="Camera roll (degrees), positive turns image clockwise",
        default=-0x7E,
        min=-0x80,
        max=0x7F,
    )

    def draw_props(self, layout: UILayout):
        box = layout.box()
        box.label(text="Bone / Key point:")
        row = box.row()
        for propName in ["frames", "fov", "camroll"]:
            row.prop(self, propName)


class OOTCutsceneMotionProperty(PropertyGroup):
    actorCueListProp: PointerProperty(type=OOTCSMotionActorCueListProperty)
    actorCueProp: PointerProperty(type=OOTCSMotionActorCuePointProperty)

    @staticmethod
    def upgrade_object(csObj: Object):
        print(f"Processing '{csObj.name}'...")
        upgradeCutsceneMotion(csObj)
        print("Done!")


classes = (
    OOTCSMotionActorCueListProperty,
    OOTCSMotionActorCuePointProperty,
    OOTCSMotionCameraShotProperty,
    OOTCSMotionCameraShotPointProperty,
    OOTCutsceneMotionProperty,
)


def csMotion_props_register():
    for cls in classes:
        register_class(cls)

    Object.ootCSMotionProperty = PointerProperty(type=OOTCutsceneMotionProperty)
    Armature.ootCamShotProp = PointerProperty(type=OOTCSMotionCameraShotProperty)
    Bone.ootCamShotPointProp = PointerProperty(type=OOTCSMotionCameraShotPointProperty)


def csMotion_props_unregister():
    del Bone.ootCamShotPointProp
    del Armature.ootCamShotProp
    del Object.ootCSMotionProperty

    for cls in classes:
        unregister_class(cls)
