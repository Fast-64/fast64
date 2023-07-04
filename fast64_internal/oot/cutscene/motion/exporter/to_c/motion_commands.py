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


def getActorCueListCmd(actorCueList: OOTCSMotionActorCueList, isPlayerActor: bool):
    return indent + (
        f"CS_{'PLAYER' if isPlayerActor else 'ACTOR'}_CUE_LIST("
        + f"{actorCueList.commandType + ', ' if not isPlayerActor else ''}"
        + f"{actorCueList.entryTotal}),\n"
    )


def getActorCueCmd(actorCue: OOTCSMotionActorCue, isPlayerActor: bool):
    return indent * 2 + (
        f"CS_{'PLAYER' if isPlayerActor else 'ACTOR'}_CUE("
        + f"{actorCue.actionID}, {actorCue.startFrame}, {actorCue.endFrame}, "
        + "".join(f"{rot}, " for rot in actorCue.rot)
        + "".join(f"{pos}, " for pos in actorCue.startPos)
        + "".join(f"{pos}, " for pos in actorCue.endPos)
        + "0.0f, 0.0f, 0.0f),\n"
    )


def getCamListCmd(cmdName: str, startFrame: int, endFrame: int):
    return indent + f"{cmdName}({startFrame}, {endFrame}),\n"


def getCamEyeSplineCmd(camEyeSpline: OOTCSMotionCamEyeSpline):
    return getCamListCmd("CS_CAM_EYE_SPLINE", camEyeSpline.startFrame, camEyeSpline.endFrame)


def getCamATSplineCmd(camATSpline: OOTCSMotionCamATSpline):
    return getCamListCmd("CS_CAM_AT_SPLINE", camATSpline.startFrame, camATSpline.endFrame)


def getCamEyeSplineRelToPlayerCmd(camEyeSplinePlayer: OOTCSMotionCamEyeSplineRelToPlayer):
    return getCamListCmd("CS_CAM_EYE_SPLINE_REL_TO_PLAYER", camEyeSplinePlayer.startFrame, camEyeSplinePlayer.endFrame)


def getCamATSplineRelToPlayerCmd(camATSplinePlayer: OOTCSMotionCamATSplineRelToPlayer):
    return getCamListCmd("CS_CAM_AT_SPLINE_REL_TO_PLAYER", camATSplinePlayer.startFrame, camATSplinePlayer.endFrame)


def getCamEyeCmd(camEye: OOTCSMotionCamEye):
    return getCamListCmd("CS_CAM_EYE", camEye.startFrame, camEye.endFrame)


def getCamATCmd(camAT: OOTCSMotionCamAT):
    return getCamListCmd("CS_CAM_AT", camAT.startFrame, camAT.endFrame)


def getCamPointCmd(camPoint: OOTCSMotionCamPoint):
    return indent * 2 + (
        f"CS_CAM_POINT("
        + f"{camPoint.continueFlag}, {camPoint.camRoll}f, {camPoint.frame}, {camPoint.viewAngle}, "
        + "".join(f"{pos}, " for pos in camPoint.pos)
        + "0),\n"
    )
