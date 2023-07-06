from dataclasses import dataclass


@dataclass
class OOTCSMotionBase:
    startFrame: int
    endFrame: int


@dataclass
class OOTCSMotionCamPoint:
    continueFlag: str
    camRoll: int
    frame: int
    viewAngle: float
    pos: list[int, int, int]


@dataclass
class OOTCSMotionActorCue(OOTCSMotionBase):
    actionID: str
    rot: list[str, str, str]
    startPos: list[int, int, int]
    endPos: list[int, int, int]


@dataclass
class OOTCSMotionActorCueList:
    commandType: str
    entryTotal: int
    entries: list[OOTCSMotionActorCue]


@dataclass
class OOTCSMotionCamEyeSpline(OOTCSMotionBase):
    entries: list[OOTCSMotionCamPoint]


@dataclass
class OOTCSMotionCamATSpline(OOTCSMotionBase):
    entries: list[OOTCSMotionCamPoint]


@dataclass
class OOTCSMotionCamEyeSplineRelToPlayer(OOTCSMotionBase):
    entries: list[OOTCSMotionCamPoint]


@dataclass
class OOTCSMotionCamATSplineRelToPlayer(OOTCSMotionBase):
    entries: list[OOTCSMotionCamPoint]


@dataclass
class OOTCSMotionCamEye(OOTCSMotionBase):
    # This feature is not used in the final game and lacks polish, it is recommended to use splines in all cases.
    entries: list


@dataclass
class OOTCSMotionCamAT(OOTCSMotionBase):
    # This feature is not used in the final game and lacks polish, it is recommended to use splines in all cases.
    entries: list


@dataclass
class OOTCSMotionCutscene:
    name: str
    totalEntries: int
    frameCount: int

    actorCueList: list[OOTCSMotionActorCueList]
    playerCueList: list[OOTCSMotionActorCueList]
    camEyeSplineList: list[OOTCSMotionCamEyeSpline]
    camATSplineList: list[OOTCSMotionCamATSpline]
    camEyeSplineRelPlayerList: list[OOTCSMotionCamEyeSplineRelToPlayer]
    camATSplineRelPlayerList: list[OOTCSMotionCamATSplineRelToPlayer]
    camEyeList: list[OOTCSMotionCamEye]
    camATList: list[OOTCSMotionCamAT]
