from dataclasses import dataclass, field
from typing import Optional
from ....utility import PluginError, indent
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

    paramNumber: int = field(init=False, default=8)

    def __post_init__(self):
        if self.params is not None:
            self.continueFlag = self.params[0]
            self.camRoll = getInteger(self.params[1])
            self.frame = getInteger(self.params[2])
            self.viewAngle = float(self.params[3][:-1])
            self.pos = [getInteger(self.params[4]), getInteger(self.params[5]), getInteger(self.params[6])]

    def getCmd(self):
        if self.continueFlag is None:
            raise PluginError("ERROR: ``continueFlag`` is None!")
        if self.camRoll is None:
            raise PluginError("ERROR: ``camRoll`` is None!")
        if self.frame is None:
            raise PluginError("ERROR: ``frame`` is None!")
        if self.viewAngle is None:
            raise PluginError("ERROR: ``viewAngle`` is None!")
        if len(self.pos) == 0:
            raise PluginError("ERROR: Pos list is empty!")
        return indent * 3 + (
            f"CS_CAM_POINT({self.continueFlag}, {self.camRoll}, {self.frame}, {self.viewAngle}f, "
            + "".join(f"{pos}, " for pos in self.pos)
            + "0),\n"
        )


@dataclass
class CutsceneCmdCamEyeSpline(CutsceneCmdBase):
    """This class contains the Camera Eye Spline data"""

    entries: list[CutsceneCmdCamPoint] = field(init=False, default_factory=list)
    paramNumber: int = field(init=False, default=2)
    listName: str = field(init=False, default="camEyeSplineList")

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[0])
            self.endFrame = getInteger(self.params[1])

    def getCmd(self):
        if len(self.entries) == 0:
            raise PluginError("ERROR: Entry list is empty!")
        return self.getCamListCmd("CS_CAM_EYE_SPLINE", self.startFrame, self.endFrame) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdCamATSpline(CutsceneCmdBase):
    """This class contains the Camera AT (look-at) Spline data"""

    entries: list[CutsceneCmdCamPoint] = field(init=False, default_factory=list)
    paramNumber: int = field(init=False, default=2)
    listName: str = field(init=False, default="camATSplineList")

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[0])
            self.endFrame = getInteger(self.params[1])

    def getCmd(self):
        if len(self.entries) == 0:
            raise PluginError("ERROR: Entry list is empty!")
        return self.getCamListCmd("CS_CAM_AT_SPLINE", self.startFrame, self.endFrame) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdCamEyeSplineRelToPlayer(CutsceneCmdBase):
    """This class contains the Camera Eye Spline Relative to the Player data"""

    entries: list[CutsceneCmdCamPoint] = field(init=False, default_factory=list)
    paramNumber: int = field(init=False, default=2)
    listName: str = field(init=False, default="camEyeSplineRelPlayerList")

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[0])
            self.endFrame = getInteger(self.params[1])

    def getCmd(self):
        if len(self.entries) == 0:
            raise PluginError("ERROR: Entry list is empty!")
        return self.getCamListCmd("CS_CAM_EYE_SPLINE_REL_TO_PLAYER", self.startFrame, self.endFrame) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdCamATSplineRelToPlayer(CutsceneCmdBase):
    """This class contains the Camera AT Spline Relative to the Player data"""

    entries: list[CutsceneCmdCamPoint] = field(init=False, default_factory=list)
    paramNumber: int = field(init=False, default=2)
    listName: str = field(init=False, default="camATSplineRelPlayerList")

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[0])
            self.endFrame = getInteger(self.params[1])

    def getCmd(self):
        if len(self.entries) == 0:
            raise PluginError("ERROR: Entry list is empty!")
        return self.getCamListCmd("CS_CAM_AT_SPLINE_REL_TO_PLAYER", self.startFrame, self.endFrame) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdCamEye(CutsceneCmdBase):
    """This class contains a single Camera Eye point"""

    # This feature is not used in the final game and lacks polish, it is recommended to use splines in all cases.
    entries: list = field(init=False, default_factory=list)
    paramNumber: int = field(init=False, default=2)
    listName: str = field(init=False, default="camEyeList")

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
    entries: list = field(init=False, default_factory=list)
    paramNumber: int = field(init=False, default=2)
    listName: str = field(init=False, default="camATList")

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[0])
            self.endFrame = getInteger(self.params[1])

    def getCmd(self):
        return self.getCamListCmd("CS_CAM_AT", self.startFrame, self.endFrame)
