from dataclasses import dataclass, field
from typing import Optional
from ....utility import PluginError, indent
from ...cutscene.motion.utility import getInteger
from .common import CutsceneCmdBase


@dataclass
class CutsceneCmdMisc(CutsceneCmdBase):
    """This class contains a single misc command entry"""

    type: str  # see ``CutsceneMiscType`` in decomp

    paramNumber: int = field(init=False, default=14)

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdMisc(
            getInteger(params[1]), getInteger(params[2]), CutsceneCmdBase.getEnumValue("csMiscType", params[0])
        )

    def getCmd(self):
        self.validateFrames()
        return indent * 3 + (f"CS_MISC({self.type}, {self.startFrame}, {self.endFrame}" + ", 0" * 11 + "),\n")


@dataclass
class CutsceneCmdLightSetting(CutsceneCmdBase):
    """This class contains Light Setting command data"""

    isLegacy: bool
    lightSetting: int

    paramNumber: int = field(init=False, default=11)

    @staticmethod
    def from_params(params: list[str], isLegacy: bool):
        lightSetting = getInteger(params[0])
        return CutsceneCmdLightSetting(
            getInteger(params[1]),
            getInteger(params[2]),
            isLegacy,
            lightSetting - 1 if isLegacy else lightSetting
        )

    def getCmd(self):
        self.validateFrames(False)
        return indent * 3 + (f"CS_LIGHT_SETTING({self.lightSetting}, {self.startFrame}" + ", 0" * 12 + "),\n")


@dataclass
class CutsceneCmdTime(CutsceneCmdBase):
    """This class contains Time Ocarina Action command data"""

    hour: int
    minute: int

    paramNumber: int = field(init=False, default=5)

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdTime(
            getInteger(params[1]),
            getInteger(params[2]),
            getInteger(params[3]),
            getInteger(params[4]),
        )

    def getCmd(self):
        self.validateFrames(False)
        return indent * 3 + f"CS_TIME(0, {self.startFrame}, 0, {self.hour}, {self.minute}),\n"


@dataclass
class CutsceneCmdRumbleController(CutsceneCmdBase):
    """This class contains Rumble Controller command data"""

    sourceStrength: int
    duration: int
    decreaseRate: int

    paramNumber: int = field(init=False, default=8)

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdRumbleController(
            getInteger(params[1]),
            getInteger(params[2]),
            getInteger(params[3]),
            getInteger(params[4]),
            getInteger(params[5]),
        )

    def getCmd(self):
        self.validateFrames(False)
        return indent * 3 + (
            f"CS_RUMBLE_CONTROLLER("
            + f"0, {self.startFrame}, 0, {self.sourceStrength}, {self.duration}, {self.decreaseRate}, 0, 0),\n"
        )


@dataclass
class CutsceneCmdMiscList(CutsceneCmdBase):
    """This class contains Misc command data"""

    entryTotal: Optional[int] = field(init=False, default=None)
    entries: list[CutsceneCmdMisc] = field(init=False, default_factory=list)
    paramNumber: int = field(init=False, default=1)
    listName: str = field(init=False, default="miscList")

    @staticmethod
    def from_params(params: list[str]):
        new = CutsceneCmdMiscList()
        new.entryTotal = getInteger(params[0])
        return new

    def getCmd(self):
        if len(self.entries) == 0:
            raise PluginError("ERROR: Entry list is empty!")
        return self.getGenericListCmd("CS_MISC_LIST", self.entryTotal) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdLightSettingList(CutsceneCmdBase):
    """This class contains Light Setting List command data"""

    entryTotal: Optional[int] = field(init=False, default=None)
    entries: list[CutsceneCmdLightSetting] = field(init=False, default_factory=list)
    paramNumber: int = field(init=False, default=1)
    listName: str = field(init=False, default="lightSettingsList")

    @staticmethod
    def from_params(params: list[str]):
        new = CutsceneCmdLightSettingList()
        new.entryTotal = getInteger(params[0])
        return new

    def getCmd(self):
        if len(self.entries) == 0:
            raise PluginError("ERROR: Entry list is empty!")
        return self.getGenericListCmd("CS_LIGHT_SETTING_LIST", self.entryTotal) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdTimeList(CutsceneCmdBase):
    """This class contains Time List command data"""

    entryTotal: Optional[int] = field(init=False, default=None)
    entries: list[CutsceneCmdTime] = field(init=False, default_factory=list)
    paramNumber: int = field(init=False, default=1)
    listName: str = field(init=False, default="timeList")

    @staticmethod
    def from_params(params: list[str]):
        new = CutsceneCmdTimeList()
        new.entryTotal = getInteger(params[0])
        return new

    def getCmd(self):
        if len(self.entries) == 0:
            raise PluginError("ERROR: Entry list is empty!")
        return self.getGenericListCmd("CS_TIME_LIST", self.entryTotal) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdRumbleControllerList(CutsceneCmdBase):
    """This class contains Rumble Controller List command data"""

    entryTotal: Optional[int] = field(init=False, default=None)
    entries: list[CutsceneCmdRumbleController] = field(init=False, default_factory=list)
    paramNumber: int = field(init=False, default=1)
    listName: str = field(init=False, default="rumbleList")

    @staticmethod
    def from_params(params: list[str]):
        new = CutsceneCmdRumbleControllerList()
        new.entryTotal = getInteger(params[0])
        return new

    def getCmd(self):
        if len(self.entries) == 0:
            raise PluginError("ERROR: Entry list is empty!")
        return self.getGenericListCmd("CS_RUMBLE_CONTROLLER_LIST", self.entryTotal) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdDestination(CutsceneCmdBase):
    """This class contains Destination command data"""

    id: str

    paramNumber: int = field(init=False, default=3)
    listName: str = field(init=False, default="destination")

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdDestination(
            getInteger(params[1]), None, CutsceneCmdBase.getEnumValue("csDestination", params[0])
        )

    def getCmd(self):
        self.validateFrames(False)
        return indent * 2 + f"CS_DESTINATION({self.id}, {self.startFrame}, 0),\n"


@dataclass
class CutsceneCmdTransition(CutsceneCmdBase):
    """This class contains Transition command data"""

    type: str

    paramNumber: int = field(init=False, default=3)
    listName: str = field(init=False, default="transitionList")

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdTransition(
            getInteger(params[1]), getInteger(params[2]), CutsceneCmdBase.getEnumValue("csTransitionType", params[0])
        )

    def getCmd(self):
        self.validateFrames()
        return indent * 2 + f"CS_TRANSITION({self.type}, {self.startFrame}, {self.endFrame}),\n"
