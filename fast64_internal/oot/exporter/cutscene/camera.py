from dataclasses import dataclass, field
from typing import Optional
from ....utility import indent
from ...cutscene.motion.utility import getInteger
from .common import CutsceneCmdBase


@dataclass
class CutsceneCmdCamPoint(CutsceneCmdBase):
    """This class contains a single Camera Point command data"""

    continueFlag: Optional[str] = None
    camRoll: Optional[int] = None
    frame: Optional[int] = None
    viewAngle: Optional[float] = None
    pos: list[int] = field(default_factory=list)
    paramNumber: int = 8

    def __post_init__(self):
        if self.params is not None:
            self.continueFlag = self.params[0]
            self.camRoll = getInteger(self.params[1])
            self.frame = getInteger(self.params[2])
            self.viewAngle = float(self.params[3][:-1])
            self.pos = [getInteger(self.params[4]), getInteger(self.params[5]), getInteger(self.params[6])]

    def getCmd(self):
        return indent * 3 + (
            f"CS_CAM_POINT("
            + f"{self.continueFlag}, {self.camRoll}, {self.frame}, {self.viewAngle}f, "
            + "".join(f"{pos}, " for pos in self.pos)
            + "0),\n"
        )


@dataclass
class CutsceneCmdCamEyeSpline(CutsceneCmdBase):
    """This class contains the Camera Eye Spline data"""

    entries: list[CutsceneCmdCamPoint] = field(default_factory=list)
    paramNumber: int = 2
    listName: str = "camEyeSplineList"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[0])
            self.endFrame = getInteger(self.params[1])

    def getCmd(self):
        return self.getCamListCmd("CS_CAM_EYE_SPLINE", self.startFrame, self.endFrame) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdCamATSpline(CutsceneCmdBase):
    """This class contains the Camera AT (look-at) Spline data"""

    entries: list[CutsceneCmdCamPoint] = field(default_factory=list)
    paramNumber: int = 2
    listName: str = "camATSplineList"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[0])
            self.endFrame = getInteger(self.params[1])

    def getCmd(self):
        return self.getCamListCmd("CS_CAM_AT_SPLINE", self.startFrame, self.endFrame) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdCamEyeSplineRelToPlayer(CutsceneCmdBase):
    """This class contains the Camera Eye Spline Relative to the Player data"""

    entries: list[CutsceneCmdCamPoint] = field(default_factory=list)
    paramNumber: int = 2
    listName: str = "camEyeSplineRelPlayerList"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[0])
            self.endFrame = getInteger(self.params[1])

    def getCmd(self):
        return self.getCamListCmd("CS_CAM_EYE_SPLINE_REL_TO_PLAYER", self.startFrame, self.endFrame) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdCamATSplineRelToPlayer(CutsceneCmdBase):
    """This class contains the Camera AT Spline Relative to the Player data"""

    entries: list[CutsceneCmdCamPoint] = field(default_factory=list)
    paramNumber: int = 2
    listName: str = "camATSplineRelPlayerList"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[0])
            self.endFrame = getInteger(self.params[1])

    def getCmd(self):
        return self.getCamListCmd("CS_CAM_AT_SPLINE_REL_TO_PLAYER", self.startFrame, self.endFrame) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdCamEye(CutsceneCmdBase):
    """This class contains a single Camera Eye point"""

    # This feature is not used in the final game and lacks polish, it is recommended to use splines in all cases.
    entries: list = field(default_factory=list)
    paramNumber: int = 2
    listName: str = "camEyeList"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[0])
            self.endFrame = getInteger(self.params[1])

    def getCmd(self):
        return self.getCamListCmd("CS_CAM_EYE", self.startFrame, self.endFrame)


@dataclass
class CutsceneCmdCamAT(CutsceneCmdBase):
    """This class contains a single Camera AT point"""

    # This feature is not used in the final game and lacks polish, it is recommended to use splines in all cases.
    entries: list = field(default_factory=list)
    paramNumber: int = 2
    listName: str = "camATList"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[0])
            self.endFrame = getInteger(self.params[1])

    def getCmd(self):
        return self.getCamListCmd("CS_CAM_AT", self.startFrame, self.endFrame)
