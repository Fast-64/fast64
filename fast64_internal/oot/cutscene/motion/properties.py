from bpy.types import PropertyGroup, Object, UILayout, Armature, Bone, Scene
from bpy.props import IntProperty, StringProperty, PointerProperty, EnumProperty, FloatProperty
from bpy.utils import register_class, unregister_class
from ...oot_upgrade import upgradeCutsceneMotion
from ...oot_utility import drawEnumWithCustom
from .constants import ootEnumCSMotionCamMode, ootEnumCSActorCueListCommandType
from .operators import OOTCSMotionAddActorCuePoint, OOTCSMotionCreateActorCuePreview


class OOTCSMotionActorCueListProperty(PropertyGroup):
    # temp, to remove
    actorCueSlot: IntProperty(
        name="Actor Cue Slot",
        description="Slot used for Actor Cues (``CS_CMD_ACTOR_CUE_channelNumber_slotNumber``)",  # legacy: -1 for player
        default=-1,
        min=-1,
    )

    commandType: EnumProperty(
        items=ootEnumCSActorCueListCommandType, name="CS Actor Cue Command Type", default="0x000F"
    )
    commandTypeCustom: StringProperty(name="CS Actor Cue Command Type Custom")

    def draw_props(self, layout: UILayout, isPreview: bool, labelPrefix: str):
        box = layout.box()
        box.box().label(text=f"{labelPrefix} Cue List")

        if labelPrefix != "Player":
            # Player Cue has only one command type
            drawEnumWithCustom(box, self, "commandType", "Actor Cue Command Type:", "Command Type Custom:")

        if not isPreview:
            split = box.split(factor=0.5)
            split.operator(OOTCSMotionAddActorCuePoint.bl_idname)
            split.operator(OOTCSMotionCreateActorCuePreview.bl_idname)


class OOTCSMotionActorCuePointProperty(PropertyGroup):
    cueStartFrame: IntProperty(
        name="Start Frame", description="Key point start frame within cutscene", default=0, min=0
    )
    cueActionID: StringProperty(
        name="Action ID", default="0x0001", description="Actor action. Meaning is unique for each different actor."
    )

    def draw_props(self, layout: UILayout, labelPrefix: str):
        box = layout.box()
        box.box().label(text=f"{labelPrefix} Cue")
        box.prop(self, "cueStartFrame")

        split = box.split(factor=0.5)
        split.label(text=f"{labelPrefix} Cue (Action) ID")
        split.prop(self, "cueActionID", text="")


class OOTCSMotionCameraShotProperty(PropertyGroup):
    # CS_CAM_EYE_SPLINE, CS_CAM_AT_SPLINE | CS_CAM_EYE_SPLINE_REL_TO_PLAYER, CS_CAM_AT_SPLINE_REL_TO_PLAYER
    shotStartFrame: IntProperty(name="Start Frame", description="Shot start frame", default=0, min=0)
    shotCamMode: EnumProperty(
        items=ootEnumCSMotionCamMode,
        name="Mode",
        description="Camera command mode",
        default="normal",
    )

    def draw_props(self, layout: UILayout, label: str):
        box = layout.box()
        box.label(text=label)
        box.prop(self, "shotStartFrame")
        box.row().prop(self, "shotCamMode", expand=True)


class OOTCSMotionCameraShotPointProperty(PropertyGroup):
    # CS_CAM_POINT
    shotPointFrame: IntProperty(name="Frame", description="Key point frames value", default=1234, min=0)
    shotPointViewAngle: FloatProperty(
        name="FoV", description="Field of view (degrees)", default=179.76, min=0.01, max=179.99
    )
    shotPointRoll: IntProperty(
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
        for propName in ["shotPointFrame", "shotPointViewAngle", "shotPointRoll"]:
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
    Scene.previewPlayerAge = EnumProperty(
        items=[("link_adult", "Adult", "Adult Link (170 cm)", 0), ("link_child", "Child", "Child Link (130 cm)", 1)],
        name="Player Age for Preview",
        description="For setting Link's height for preview",
        default="link_adult",
    )


def csMotion_props_unregister():
    del Scene.previewPlayerAge
    del Bone.ootCamShotPointProp
    del Armature.ootCamShotProp
    del Object.ootCSMotionProperty

    for cls in classes:
        unregister_class(cls)
