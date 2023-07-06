from dataclasses import dataclass, field


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
    entries: list[OOTCSMotionActorCue] = field(default_factory=list)


@dataclass
class OOTCSMotionCamEyeSpline(OOTCSMotionBase):
    entries: list[OOTCSMotionCamPoint] = field(default_factory=list)


@dataclass
class OOTCSMotionCamATSpline(OOTCSMotionBase):
    entries: list[OOTCSMotionCamPoint] = field(default_factory=list)


@dataclass
class OOTCSMotionCamEyeSplineRelToPlayer(OOTCSMotionBase):
    entries: list[OOTCSMotionCamPoint] = field(default_factory=list)


@dataclass
class OOTCSMotionCamATSplineRelToPlayer(OOTCSMotionBase):
    entries: list[OOTCSMotionCamPoint] = field(default_factory=list)


@dataclass
class OOTCSMotionCamEye(OOTCSMotionBase):
    # This feature is not used in the final game and lacks polish, it is recommended to use splines in all cases.
    entries: list = field(default_factory=list)


@dataclass
class OOTCSMotionCamAT(OOTCSMotionBase):
    # This feature is not used in the final game and lacks polish, it is recommended to use splines in all cases.
    entries: list = field(default_factory=list)


@dataclass
class OOTCSMotionCutscene:
    name: str
    totalEntries: int
    frameCount: int

    actorCueList: list[OOTCSMotionActorCueList] = field(default_factory=list)
    playerCueList: list[OOTCSMotionActorCueList] = field(default_factory=list)
    camEyeSplineList: list[OOTCSMotionCamEyeSpline] = field(default_factory=list)
    camATSplineList: list[OOTCSMotionCamATSpline] = field(default_factory=list)
    camEyeSplineRelPlayerList: list[OOTCSMotionCamEyeSplineRelToPlayer] = field(default_factory=list)
    camATSplineRelPlayerList: list[OOTCSMotionCamATSplineRelToPlayer] = field(default_factory=list)
    camEyeList: list[OOTCSMotionCamEye] = field(default_factory=list)
    camATList: list[OOTCSMotionCamAT] = field(default_factory=list)
