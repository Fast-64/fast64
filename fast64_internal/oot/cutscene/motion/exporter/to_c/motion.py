import bpy, math
from bpy.types import Object
from ......utility import indent

from ..classes import (
    OOTCSMotionActorCueList,
    OOTCSMotionActorCue,
    OOTCSMotionCamPoint,
    OOTCSMotionCamEyeSpline,
    OOTCSMotionCamATSpline,
    OOTCSMotionCamEyeSplineRelToPlayer,
    OOTCSMotionCamATSplineRelToPlayer,
    OOTCSMotionCamEye,
    OOTCSMotionCamAT,
)

from .motion_commands import (
    getActorCueListCmd,
    getActorCueCmd,
    getCamListCmd,
    getCamEyeSplineCmd,
    getCamATSplineCmd,
    getCamEyeSplineRelToPlayerCmd,
    getCamATSplineRelToPlayerCmd,
    getCamEyeCmd,
    getCamATCmd,
    getCamPointCmd,
)


def isPlayerActor(obj: Object):
    return "Player" in obj.ootEmptyType


def getCSMotionObjects():
    csMotionObjects: dict[str, list[Object]] = {
        "csMain": [],
        "actorCueList": [],
        "playerCueList": [],
        "actorCue": [],
        "playerCue": [],
        "camShot": [],
    }

    for obj in bpy.data.objects:
        if obj.type == "EMPTY":
            if obj.ootEmptyType == "Cutscene":
                csMotionObjects["csMain"].append(obj)

            if obj.ootEmptyType == "CS Actor Cue List":
                csMotionObjects["actorCueList"].append(obj)

            if obj.ootEmptyType == "CS Player Cue List":
                csMotionObjects["playerCueList"].append(obj)

            if obj.ootEmptyType == "CS Actor Cue":
                csMotionObjects["actorCue"].append(obj)

            if obj.ootEmptyType == "CS Player Cue":
                csMotionObjects["playerCue"].append(obj)

        if obj.type == "ARMATURE" and obj.parent.ootEmptyType == "Cutscene":
            csMotionObjects["camShot"].append(obj)

    return csMotionObjects


def getOoTRotation(obj: Object):
    def conv(r):
        r /= 2.0 * math.pi
        r -= math.floor(r)
        r = round(r * 0x10000)

        if r >= 0x8000:
            r += 0xFFFF0000

        assert r >= 0 and r <= 0xFFFFFFFF and (r <= 0x7FFF or r >= 0xFFFF8000)

        return hex(r)

    rotXYZ = [conv(obj.rotation_euler[0]), conv(obj.rotation_euler[2]), conv(obj.rotation_euler[1])]
    return [f"DEG_TO_BINANG({(int(rot, base=16) * (180 / 0x8000)):.3f})" for rot in rotXYZ]


def getOoTPosition(obj: Object):
    scale = bpy.context.scene.ootBlenderScale
    pos = obj.location

    x = int(round(pos[0] * scale))
    y = int(round(pos[2] * scale))
    z = int(round(-pos[1] * scale))

    if any(v < -0x8000 or v >= 0x8000 for v in (x, y, z)):
        raise RuntimeError(f"Position(s) too large, out of range: {x}, {y}, {z}")

    return [x, y, z]


def getActorCueListData(actorCueListObjects: list[Object], actorCueObjects: list[Object]):
    actorCueData = ""

    for obj in actorCueListObjects:
        entryTotal = len(actorCueObjects) - 1
        actorCueList = OOTCSMotionActorCueList(obj.ootCSMotionProperty.actorCueListProp.commandType, entryTotal)
        actorCueData += getActorCueListCmd(actorCueList, isPlayerActor(obj))

        for i in range(len(actorCueObjects) - 1):
            objElem = actorCueObjects[i]
            actorCue = OOTCSMotionActorCue(
                objElem.ootCSMotionProperty.actorCueProp.cueStartFrame,
                objElem.ootCSMotionProperty.actorCueProp.cueEndFrame,
                objElem.ootCSMotionProperty.actorCueProp.cueActionID,
                getOoTRotation(objElem),
                getOoTPosition(objElem),
                getOoTPosition(actorCueObjects[i + 1])
            )
            actorCueData += getActorCueCmd(actorCue, isPlayerActor(objElem))
    
    return actorCueData


def getCutsceneMotionData():
    csMotionObjects = getCSMotionObjects()

    return (
        getActorCueListData(csMotionObjects["actorCueList"], csMotionObjects["actorCue"])
        + getActorCueListData(csMotionObjects["playerCueList"], csMotionObjects["playerCue"])
    )
