import bpy, math, mathutils
from bpy.types import Object, Action, AnimData, FCurve
from bpy.utils import register_class, unregister_class
from bpy.props import StringProperty
from bpy_extras import anim_utils

from .operators import OperatorBase
from .utility import attemptModifierApply, raisePluginError, PluginError

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    if bpy.app.version >= (5, 0, 0):
        from bpy.types import ActionSlot, ActionFCurves
    from .. import Fast64_Properties
    from .. import Fast64Settings_Properties


class ArmatureApplyWithMeshOperator(bpy.types.Operator):
    # set bl_ properties
    bl_description = (
        "Applies current pose as default pose. Useful for "
        + "rigging an armature that is not in T/A pose. Note that when using "
        + " with an SM64 armature, you must revert to the default pose after "
        + "skinning."
    )
    bl_idname = "object.armature_apply_w_mesh"
    bl_label = "Apply As Rest Pose"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        try:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            if len(context.selected_objects) == 0:
                raise PluginError("Armature not selected.")
            elif type(context.selected_objects[0].data) is not bpy.types.Armature:
                raise PluginError("Armature not selected.")

            armatureObj = context.selected_objects[0]
            armatureApplyWithMesh(armatureObj, context)
        except Exception as e:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}

        self.report({"INFO"}, "Applied armature with mesh.")
        return {"FINISHED"}  # must return a set


class CreateAnimData(OperatorBase):
    bl_idname = "scene.fast64_create_anim_data"
    bl_label = "Create Animation Data"
    bl_description = "Create animation data"
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    context_mode = "OBJECT"
    icon = "ANIM"

    def execute_operator(self, context):
        obj = context.object
        if obj is None:
            raise PluginError("No selected object")
        if obj.animation_data is None:
            obj.animation_data_create()


class AddBasicAction(OperatorBase):
    bl_idname = "scene.fast64_add_basic_action"
    bl_label = "Add Basic Action"
    bl_description = "Create animation data and add basic action"
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    context_mode = "OBJECT"
    icon = "ACTION"

    def execute_operator(self, context):
        if context.object is None:
            raise PluginError("No selected object")
        create_basic_action(context.object)


class StashAction(OperatorBase):
    bl_idname = "scene.fast64_stash_action"
    bl_label = "Stash Action"
    bl_description = "Stash an action in an object's nla tracks if not already stashed"
    context_mode = "OBJECT"
    icon = "NLA"

    action: StringProperty()

    def execute_operator(self, context):
        if context.object is None:
            raise PluginError("No selected object")
        stashActionInArmature(context.object, get_action(self.action))


class AddSubAction(OperatorBase):
    bl_idname = "scene.fast64_add_sub_action"
    bl_label = "Add Sub Action"
    bl_description = "Add a sub action"
    bl_options = {"REGISTER", "UNDO", "PRESET"}
    context_mode = "OBJECT"
    icon = "ACTION_SLOT"

    action_name: StringProperty()

    def execute_operator(self, context):
        if context.object is None:
            raise PluginError("No selected object")
        assign_action(context.object, get_action(self.action_name))


# This code only handles root bone with no parent, which is the only bone that translates.
def getTranslationRelativeToRest(bone: bpy.types.Bone, inputVector: mathutils.Vector) -> mathutils.Vector:
    zUpToYUp = mathutils.Quaternion((1, 0, 0), math.radians(-90.0)).to_matrix().to_4x4()
    actualTranslation = (zUpToYUp @ bone.matrix_local).inverted() @ mathutils.Matrix.Translation(inputVector).to_4x4()
    return actualTranslation.decompose()[0]


def getRotationRelativeToRest(bone: bpy.types.Bone, inputEuler: mathutils.Euler) -> mathutils.Euler:
    if bone.parent is None:
        parentRotation = mathutils.Quaternion((1, 0, 0), math.radians(90.0)).to_matrix().to_4x4()
    else:
        parentRotation = bone.parent.matrix_local

    restRotation = (parentRotation.inverted() @ bone.matrix_local).decompose()[1].to_matrix().to_4x4()
    return (restRotation.inverted() @ inputEuler.to_matrix().to_4x4()).to_euler("XYZ", inputEuler)


def armatureApplyWithMesh(armatureObj: bpy.types.Object, context: bpy.types.Context):
    from .utility import selectSingleObject

    for child in armatureObj.children:
        if child.type != "MESH":
            continue
        armatureModifier = None
        for modifier in child.modifiers:
            if isinstance(modifier, bpy.types.ArmatureModifier):
                armatureModifier = modifier
        if armatureModifier is None:
            continue

        selectSingleObject(child)
        bpy.ops.object.modifier_copy(modifier=armatureModifier.name)
        print(len(child.modifiers))
        attemptModifierApply(armatureModifier)

    selectSingleObject(armatureObj)
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.armature_apply()
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


class ValueFrameData:
    def __init__(self, boneIndex, field, frames):
        self.boneIndex = boneIndex
        self.field = field
        self.frames = frames


def saveQuaternionFrame(frameData, rotation):
    for i in range(3):
        field = rotation.to_euler()[i]
        value = (math.degrees(field) % 360) / 360
        frameData[i].frames.append(min(int(round(value * (2**16 - 1))), 2**16 - 1))


def removeTrailingFrames(frameData):
    for i in range(3):
        if len(frameData[i].frames) < 2:
            continue
        lastUniqueFrame = len(frameData[i].frames) - 1
        while lastUniqueFrame > 0:
            if frameData[i].frames[lastUniqueFrame] == frameData[i].frames[lastUniqueFrame - 1]:
                lastUniqueFrame -= 1
            else:
                break
        frameData[i].frames = frameData[i].frames[: lastUniqueFrame + 1]


def squashFramesIfAllSame(frameData):
    for i in range(3):
        if len(frameData[i].frames) < 2:
            continue
        f0 = frameData[i].frames[0]
        for j in range(1, len(frameData[i].frames)):
            d = abs(frameData[i].frames[j] - f0)
            # Allow a change of +/-1 from original frame due to rounding.
            if d >= 2 and d != 0xFFFF:
                break
        else:
            frameData[i].frames = frameData[i].frames[0:1]


def saveTranslationFrame(frameData, translation):
    for i in range(3):
        frameData[i].frames.append(min(int(round(translation[i])), 2**16 - 1))


def getFrameInterval(action: bpy.types.Action, slot: Optional["ActionSlot"] = None):
    scene = bpy.context.scene

    fast64_props = scene.fast64  # type: Fast64_Properties
    fast64settings_props = fast64_props.settings  # type: Fast64Settings_Properties

    anim_range_choice = fast64settings_props.anim_range_choice

    def get_action_frame_range():
        if slot is not None:
            fcurves = get_fcurves(action, slot)

            min_frame = 0
            max_frame = 0
            for fcu in fcurves:
                for kp in fcu.keyframe_points:
                    f = kp.co.x
                    min_frame = min(min_frame, f)
                    max_frame = max(max_frame, f)

            return int(round(min_frame)), int(round(max_frame))
        return int(round(action.frame_range[0])), int(round(action.frame_range[1]))

    def getIntersectionInterval():
        """
        intersect action range and scene range
        Note: this doesn't handle correctly the case where the two ranges don't intersect, not a big deal
        """
        frame_start, frame_last = get_action_frame_range()

        start = max(scene.frame_start, frame_start)
        end = min(scene.frame_end, frame_last)

        return start, max(end, start)

    range_get_by_choice = {
        "action": lambda: get_action_frame_range(),
        "scene": lambda: (int(round(scene.frame_start)), int(round(scene.frame_end))),
        "intersect_action_and_scene": getIntersectionInterval,
    }

    return range_get_by_choice[anim_range_choice]()


def is_action_stashed(obj: Object, action: Action):
    animation_data: AnimData | None = obj.animation_data
    if animation_data is None:
        return False
    for track in animation_data.nla_tracks:
        for strip in track.strips:
            if strip.action is None:
                continue
            if strip.action.name == action.name:
                return True
    return False


def stashActionInArmature(obj: Object, action: Action):
    """
    Stashes an animation (action) into an armature´s nla tracks.
    This prevents animations from being deleted by blender or
    purged by the user on accident.
    """

    if is_action_stashed(obj, action):
        return

    print(f'Stashing "{action.name}" in the object "{obj.name}".')
    if obj.animation_data is None:
        obj.animation_data_create()
    track = obj.animation_data.nla_tracks.new()
    track.name = action.name
    track.strips.new(action.name, int(action.frame_range[0]), action)


def assign_action(obj: any, action: Action, create_slot=True):
    if obj.animation_data is None:
        obj.animation_data_create()
    obj.animation_data.action = action
    if create_slot and bpy.app.version >= (5, 0, 0):
        slot = action.slots.new(obj.id_type, "Default")
        obj.animation_data.action_slot = slot
        return slot
    return None


def create_basic_action_in_data(obj: any, name="Action"):
    action = bpy.data.actions.new(name)
    slot = assign_action(obj, action)
    return action, slot


def create_basic_action(obj: Object, name="Action"):
    action, slot = create_basic_action_in_data(obj, name)
    stashActionInArmature(obj, action)
    return action, slot


def get_action(name: str):
    if name == "":
        raise ValueError("Empty action name.")
    if not name in bpy.data.actions:
        raise IndexError(f"Action ({name}) is not in this file´s action data.")
    return bpy.data.actions[name]


def get_slots(action: Action):
    return {str(slot.identifier): slot for slot in action.slots if slot.target_id_type == "OBJECT"}


def get_fcurves(action: bpy.types.Action, action_slot: Optional["ActionSlot"] = None) -> "ActionFCurves":
    """If action_slot is None in blender 5.0 an exception will still be raised"""
    if bpy.app.version >= (5, 0, 0):
        if action_slot is None:
            raise PluginError(f'No action slot provided for action "{action.name}"')
        channelbag = anim_utils.action_ensure_channelbag_for_slot(action, action_slot)
        return channelbag.fcurves
    else:
        return action.fcurves


def create_new_fcurve(
    fcurves: "ActionFCurves", data_path: str, *, index: int | None = 0, action_group: str = ""
) -> FCurve:
    if bpy.app.version >= (5, 0, 0):
        return fcurves.new(data_path=data_path, index=index, group_name=action_group)
    else:
        return fcurves.new(data_path=data_path, index=index, action_group=action_group)


classes = (ArmatureApplyWithMeshOperator, CreateAnimData, AddBasicAction, StashAction, AddSubAction)


def utility_anim_register():
    for cls in classes:
        register_class(cls)


# called on add-on disabling
def utility_anim_unregister():
    for cls in classes:
        unregister_class(cls)
