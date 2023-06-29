import bpy, math, mathutils
from bpy.utils import register_class, unregister_class

from typing import TYPE_CHECKING

if TYPE_CHECKING:
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

        from .utility import PluginError, raisePluginError

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


def attemptModifierApply(modifier):
    try:
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    except Exception as e:
        print("Skipping modifier " + str(modifier.name))


def armatureApplyWithMesh(armatureObj: bpy.types.Object, context: bpy.types.Context):
    for child in armatureObj.children:
        if type(child.data) is not bpy.types.Mesh:
            continue
        armatureModifier = None
        for modifier in child.modifiers:
            if isinstance(modifier, bpy.types.ArmatureModifier):
                armatureModifier = modifier
        if armatureModifier is None:
            continue

        bpy.ops.object.select_all(action="DESELECT")
        context.view_layer.objects.active = child
        bpy.ops.object.modifier_copy(modifier=armatureModifier.name)
        print(len(child.modifiers))
        attemptModifierApply(armatureModifier)

    bpy.ops.object.select_all(action="DESELECT")
    context.view_layer.objects.active = armatureObj
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


def getFrameInterval(action: bpy.types.Action):
    scene = bpy.context.scene

    fast64_props = scene.fast64  # type: Fast64_Properties
    fast64settings_props = fast64_props.settings  # type: Fast64Settings_Properties

    anim_range_choice = fast64settings_props.anim_range_choice

    def getIntersectionInterval():
        """
        intersect action range and scene range
        Note: this doesn't handle correctly the case where the two ranges don't intersect, not a big deal
        """

        frame_start = max(
            scene.frame_start,
            int(round(action.frame_range[0])),
        )

        frame_last = max(
            min(
                scene.frame_end,
                int(round(action.frame_range[1])),
            ),
            frame_start,
        )

        return frame_start, frame_last

    range_get_by_choice = {
        "action": lambda: (int(round(action.frame_range[0])), int(round(action.frame_range[1]))),
        "scene": lambda: (int(round(scene.frame_start)), int(round(scene.frame_end))),
        "intersect_action_and_scene": getIntersectionInterval,
    }

    return range_get_by_choice[anim_range_choice]()

def stashActionInArmature(armatureObj: bpy.types.Object, action: bpy.types.Action):
    """
    Stashes an animation (action) into an armature´s nla tracks.
    This prevents animations from being deleted by blender or
    purged by the user on accident.
    """

    for track in armatureObj.animation_data.nla_tracks:
        for strip in track.strips:
            if strip.action is None:
                continue

            if strip.action.name == action.name:
                return

    print(f"Stashing \"{action.name}\" in the object \"{armatureObj.name}\".")

    track = armatureObj.animation_data.nla_tracks.new()
    track.strips.new(action.name, int(action.frame_range[0]), action)

classes = (ArmatureApplyWithMeshOperator,)


def utility_anim_register():
    for cls in classes:
        register_class(cls)


# called on add-on disabling
def utility_anim_unregister():

    for cls in classes:
        unregister_class(cls)
