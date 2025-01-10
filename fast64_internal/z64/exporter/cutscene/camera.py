from dataclasses import dataclass, field
from typing import Optional
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


# MM's new camera commands


@dataclass
class CutsceneCmdNewCamPoint:
    """This class contains a single Camera Point command data (the newer version)"""

    interp_type: str
    weight: int
    duration: int
    pos: list[int]
    relative_to: str

    paramNumber: int = field(init=False, default=7)
    size: int = field(init=False, default=0xC)

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdNewCamPoint(
            params[0],
            getInteger(params[1]),
            getInteger(params[2]),
            [getInteger(params[3]), getInteger(params[4]), getInteger(params[5])],
            params[6],
        )

    def to_c(self):
        return (
            indent * 4
            + "CS_CAM_POINT("
            + f"{self.interp_type}, "
            + f"{self.weight}, "
            + f"{self.duration}, "
            + f"{self.pos[0]}, {self.pos[1]}, {self.pos[2]}, "
            + f"{self.relative_to}"
            + "),\n"
        )


@dataclass
class CutsceneCmdCamMisc:
    """This class contains the Camera Misc data"""

    camRoll: int
    viewAngle: float

    paramNumber: int = field(init=False, default=4)
    size: int = field(init=False, default=0x8)

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdCamMisc(getInteger(params[1]), getInteger(params[2]))

    def to_c(self):
        return indent * 4 + f"CS_CAM_MISC(0, {self.camRoll}, {self.viewAngle}, 0),\n"


@dataclass
class CutsceneSplinePoint:
    # this is not a real command but it helps as each camera point is made of one at, one eye and one misc
    at: CutsceneCmdNewCamPoint
    eye: CutsceneCmdNewCamPoint
    misc: CutsceneCmdCamMisc
    size = 0x20


@dataclass
class CutsceneCmdCamSpline:
    """This class contains the Camera Spline data"""

    num_entries: int
    duration: int
    entries: list[CutsceneSplinePoint] = field(init=False, default_factory=list)

    paramNumber: int = field(init=False, default=4)
    size: int = field(init=False, default=0x8)

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdCamSpline(getInteger(params[0]), getInteger(params[3]))

    def to_c(self):
        at_list: list[str] = []
        eye_list: list[str] = []
        misc_list: list[str] = []

        for entry in self.entries:
            at_list.append(entry.at.to_c())
            eye_list.append(entry.eye.to_c())
            misc_list.append(entry.misc.to_c())

        return (
            (indent * 3 + f"CS_CAM_SPLINE({len(self.entries)}, 0, 0, {self.duration}),\n")
            + "".join(at for at in at_list)
            + "".join(eye for eye in eye_list)
            + "".join(misc for misc in misc_list)
        )


@dataclass
class CutsceneCmdCamSplineList:
    """This class contains the Camera Spline list data"""

    num_bytes: int
    entries: list[CutsceneCmdCamSpline] = field(init=False, default_factory=list)

    paramNumber: int = 1
    listName: str = "camSplineListNew"
    size: int = 0x8

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdCamSplineList(getInteger(params[0]))

    def getCmd(self):
        data = ""
        num_bytes = 0

        for entry in self.entries:
            data += entry.to_c()
            num_bytes += entry.size

            for item in entry.entries:
                num_bytes += item.size

        return (
            (indent * 2 + f"CS_CAM_SPLINE_LIST({num_bytes}),\n")
            + "".join(entry.to_c() for entry in self.entries)
            + (indent * 2 + "CS_CAM_END(),\n")
        )
