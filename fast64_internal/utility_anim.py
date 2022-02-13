import bpy, math, mathutils


class ValueFrameData:
    def __init__(self, boneIndex, field, frames):
        self.boneIndex = boneIndex
        self.field = field
        self.frames = frames


def saveQuaternionFrame(frameData, rotation):
    for i in range(3):
        field = rotation.to_euler()[i]
        value = (math.degrees(field) % 360) / 360
        frameData[i].frames.append(min(int(round(value * (2 ** 16 - 1))), 2 ** 16 - 1))


def removeTrailingFrames(frameData):
    for i in range(3):
        if len(frameData[i].frames) < 2:
            continue
        lastUniqueFrame = len(frameData[i].frames) - 1
        while lastUniqueFrame > 0:
            if (
                frameData[i].frames[lastUniqueFrame]
                == frameData[i].frames[lastUniqueFrame - 1]
            ):
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
        frameData[i].frames.append(min(int(round(translation[i])), 2 ** 16 - 1))


def getFrameInterval(anim):
    frameInterval = [0, 0]

    # frame_start is minimum 0
    frameInterval[0] = max(
        bpy.context.scene.frame_start, int(round(anim.frame_range[0]))
    )

    frameInterval[1] = (
        max(
            min(bpy.context.scene.frame_end, int(round(anim.frame_range[1]))),
            frameInterval[0],
        )
        + 1
    )

    return frameInterval
