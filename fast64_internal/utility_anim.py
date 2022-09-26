import bpy, math, mathutils

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .. import Fast64_Properties
    from .. import Fast64Settings_Properties


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
