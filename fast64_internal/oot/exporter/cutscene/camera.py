from dataclasses import dataclass, field
from ....utility import PluginError, indent
from ...cutscene.motion.utility import getInteger
from .common import CutsceneCmdBase


@dataclass
class CutsceneCmdCamPoint(CutsceneCmdBase):
    """This class contains a single Camera Point command data"""

    continueFlag: str
    camRoll: int
    frame: int
    viewAngle: float
    pos: list[int]

    paramNumber: int = field(init=False, default=8)

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdCamPoint(
            None,
            None,
            params[0],
            getInteger(params[1]),
            getInteger(params[2]),
            float(params[3][:-1]),
            [getInteger(params[4]), getInteger(params[5]), getInteger(params[6])],
        )

    def getCmd(self):
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

    entries: list[CutsceneCmdCamPoint]
    paramNumber: int = field(init=False, default=2)
    listName: str = field(init=False, default="camEyeSplineList")

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdCamEyeSpline(getInteger(params[0]), getInteger(params[1]))

    def getCmd(self):
        if len(self.entries) == 0:
            raise PluginError("ERROR: Entry list is empty!")

        return self.getCamListCmd("CS_CAM_EYE_SPLINE", self.startFrame, self.endFrame) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdCamATSpline(CutsceneCmdBase):
    """This class contains the Camera AT (look-at) Spline data"""

    entries: list[CutsceneCmdCamPoint]
    paramNumber: int = field(init=False, default=2)
    listName: str = field(init=False, default="camATSplineList")

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdCamATSpline(getInteger(params[0]), getInteger(params[1]))

    def getCmd(self):
        if len(self.entries) == 0:
            raise PluginError("ERROR: Entry list is empty!")

        return self.getCamListCmd("CS_CAM_AT_SPLINE", self.startFrame, self.endFrame) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdCamEyeSplineRelToPlayer(CutsceneCmdBase):
    """This class contains the Camera Eye Spline Relative to the Player data"""

    entries: list[CutsceneCmdCamPoint]
    paramNumber: int = field(init=False, default=2)
    listName: str = field(init=False, default="camEyeSplineRelPlayerList")

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdCamEyeSplineRelToPlayer(getInteger(params[0]), getInteger(params[1]))

    def getCmd(self):
        if len(self.entries) == 0:
            raise PluginError("ERROR: Entry list is empty!")

        return self.getCamListCmd("CS_CAM_EYE_SPLINE_REL_TO_PLAYER", self.startFrame, self.endFrame) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdCamATSplineRelToPlayer(CutsceneCmdBase):
    """This class contains the Camera AT Spline Relative to the Player data"""

    entries: list[CutsceneCmdCamPoint]
    paramNumber: int = field(init=False, default=2)
    listName: str = field(init=False, default="camATSplineRelPlayerList")

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdCamATSplineRelToPlayer(getInteger(params[0]), getInteger(params[1]))

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
    entries: list
    paramNumber: int = field(init=False, default=2)
    listName: str = field(init=False, default="camEyeList")

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdCamEye(getInteger(params[0]), getInteger(params[1]))

    def getCmd(self):
        return self.getCamListCmd("CS_CAM_EYE", self.startFrame, self.endFrame)


@dataclass
class CutsceneCmdCamAT(CutsceneCmdBase):
    """This class contains a single Camera AT point"""

    # This feature is not used in the final game and lacks polish, it is recommended to use splines in all cases.
    entries: list
    paramNumber: int = field(init=False, default=2)
    listName: str = field(init=False, default="camATList")

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdCamAT(getInteger(params[0]), getInteger(params[1]))

    def getCmd(self):
        return self.getCamListCmd("CS_CAM_AT", self.startFrame, self.endFrame)
