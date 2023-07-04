import bpy, math

from bpy.types import Object
from ...constants import ootCSMotionCommandTypeRawToEnum

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
        "Cutscene": [],
        "CS Actor Cue List": [],
        "CS Player Cue List": [],
        "CS Actor Cue": [],
        "CS Player Cue": [],
        "camShot": [],
    }

    for obj in bpy.data.objects:
        if obj.type == "EMPTY" and obj.ootEmptyType in csMotionObjects.keys():
            csMotionObjects[obj.ootEmptyType].append(obj)

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

        return hex(r & 0xFFFF)

    rotXYZ = [conv(obj.rotation_euler[0]), conv(obj.rotation_euler[2]), conv(obj.rotation_euler[1])]
    print(rotXYZ)
    return [f"DEG_TO_BINANG({(int(rot, base=16) * (180 / 0x8000)):.3f})" for rot in rotXYZ]


def getOoTPosition(pos):
    scale = bpy.context.scene.ootBlenderScale

    x = int(round(pos[0] * scale))
    y = int(round(pos[2] * scale))
    z = int(round(-pos[1] * scale))

    if any(v < -0x8000 or v >= 0x8000 for v in (x, y, z)):
        raise RuntimeError(f"Position(s) too large, out of range: {x}, {y}, {z}")

    return [x, y, z]


def getActorCueListData(actorCueListObjects: list[Object], actorCueObjects: list[Object]):
    actorCueData = ""

    if len(actorCueObjects) > 0:
        for obj in actorCueListObjects:
            entryTotal = len(actorCueObjects) - 1
            commandType = obj.ootCSMotionProperty.actorCueListProp.commandType

            if commandType == "Custom":
                commandType = obj.ootCSMotionProperty.actorCueListProp.commandTypeCustom
            else:
                commandType = ootCSMotionCommandTypeRawToEnum[commandType]

            actorCueList = OOTCSMotionActorCueList(commandType, entryTotal)
            actorCueData += getActorCueListCmd(actorCueList, isPlayerActor(obj))

            for i in range(len(actorCueObjects) - 1):
                objElem = actorCueObjects[i]
                actorCue = OOTCSMotionActorCue(
                    objElem.ootCSMotionProperty.actorCueProp.cueStartFrame,
                    objElem.ootCSMotionProperty.actorCueProp.cueEndFrame,
                    objElem.ootCSMotionProperty.actorCueProp.cueActionID,
                    getOoTRotation(objElem),
                    getOoTPosition(objElem.location),
                    getOoTPosition(actorCueObjects[i + 1].location),
                )
                actorCueData += getActorCueCmd(actorCue, isPlayerActor(objElem))

    return actorCueData


def getShotObjectsSort(shotObjects: list[Object]):
    sortedObjects: dict[str, list[Object]] = {
        "splineEyeOrAT": [],
        "splineEyeOrATRelPlayer": [],
        "eyeOrAT": [],
    }

    for obj in shotObjects:
        sortedObjects[obj.data.ootCamShotProp.shotCamMode].append(obj)

    return sortedObjects


def getCameraShotPointData(bones, useAT: bool, useFlagMacro: bool):
    shotPoints: list[OOTCSMotionCamPoint] = []

    if len(bones) < 4:
        raise RuntimeError("Camera Armature needs at least 4 bones!")

    for bone in bones:
        if bone.parent is not None:
            raise RuntimeError("Camera Armature bones are not allowed to have parent bones!")

        posBlend = bone.head if not useAT else bone.tail
        shotPoints.append(
            OOTCSMotionCamPoint(
                ("CS_CAM_CONTINUE" if useFlagMacro else "0")
                if bone != bones[-1]
                else ("CS_CAM_STOP" if useFlagMacro else "-1"),
                bone.ootCamShotPointProp.shotPointRoll,
                bone.ootCamShotPointProp.shotPointFrame,
                bone.ootCamShotPointProp.shotPointViewAngle,
                getOoTPosition([int(posBlend[0]), int(posBlend[2]), int(posBlend[1])]),
            )
        )

    return shotPoints


def getCamCmdFunc(camMode: str, useAT: bool):
    camCmdFuncMap = {
        "splineEyeOrAT": getCamATSplineCmd if useAT else getCamEyeSplineCmd,
        "splineEyeOrATRelPlayer": getCamATSplineRelToPlayerCmd if useAT else getCamEyeSplineRelToPlayerCmd,
        "eyeOrAT": getCamATCmd if useAT else getCamEyeCmd,
    }

    return camCmdFuncMap[camMode]


def getCamClass(camMode: str, useAT: bool):
    camCmdFuncMap = {
        "splineEyeOrAT": OOTCSMotionCamATSpline if useAT else OOTCSMotionCamEyeSpline,
        "splineEyeOrATRelPlayer": OOTCSMotionCamATSplineRelToPlayer if useAT else OOTCSMotionCamEyeSplineRelToPlayer,
        "eyeOrAT": OOTCSMotionCamAT if useAT else OOTCSMotionCamEye,
    }

    return camCmdFuncMap[camMode]


def getCamListData(obj: Object, useAT: bool, useFlagMacro: bool):
    splineData = getCameraShotPointData(obj.data.bones, useAT, useFlagMacro)

    startFrame = obj.data.ootCamShotProp.shotStartFrame
    endFrame = startFrame + max(2, sum(point.frame for point in splineData)) + (splineData[-1].frame if useAT else 1)

    camData = getCamClass(obj.data.ootCamShotProp.shotCamMode, useAT)(startFrame, endFrame)

    return getCamCmdFunc(obj.data.ootCamShotProp.shotCamMode, useAT)(camData) + "".join(
        getCamPointCmd(pointData) for pointData in splineData
    )


def getCameraShotData(shotObjects: list[Object], useFlagMacro: bool):
    cameraShotData = ""

    if len(shotObjects) == 0:
        raise RuntimeError(f"Found no camera commands!")

    shotObjectsSorted = getShotObjectsSort(shotObjects)

    for listName, objList in shotObjectsSorted.items():
        for obj in objList:
            continueFlag = (
                ("CS_CAM_CONTINUE" if useFlagMacro else "0")
                if obj != shotObjectsSorted[obj.data.ootCamShotProp.shotCamMode][-1]
                else ("CS_CAM_STOP" if useFlagMacro else "-1")
            )

            cameraShotData += getCamListData(obj, False, useFlagMacro) + getCamListData(obj, True, useFlagMacro)

    return cameraShotData


def getCutsceneMotionData(useFlagMacro: bool):
    csMotionObjects = getCSMotionObjects()

    return (
        getActorCueListData(csMotionObjects["CS Actor Cue List"], csMotionObjects["CS Actor Cue"])
        + getActorCueListData(csMotionObjects["CS Player Cue List"], csMotionObjects["CS Player Cue"])
        + getCameraShotData(csMotionObjects["camShot"], useFlagMacro)
    )
