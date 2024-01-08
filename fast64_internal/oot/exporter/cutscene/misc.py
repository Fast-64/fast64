from dataclasses import dataclass, field
from typing import Optional
from ....utility import indent
from ...cutscene.motion.utility import getInteger
from .common import CutsceneCmdBase


@dataclass
class CutsceneCmdMisc(CutsceneCmdBase):
    """This class contains a single misc command entry"""

    type: Optional[str] = None  # see ``CutsceneMiscType`` in decomp
    paramNumber: int = 14

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.type = self.getEnumValue("csMiscType", 0)

    def getCmd(self):
        return indent * 3 + (f"CS_MISC({self.type}, {self.startFrame}, {self.endFrame}" + ", 0" * 11 + "),\n")


@dataclass
class CutsceneCmdLightSetting(CutsceneCmdBase):
    """This class contains Light Setting command data"""

    isLegacy: Optional[bool] = None
    lightSetting: Optional[int] = None
    paramNumber: int = 11

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.lightSetting = getInteger(self.params[0])
            if self.isLegacy:
                self.lightSetting -= 1

    def getCmd(self):
        return indent * 3 + (f"CS_LIGHT_SETTING({self.lightSetting}, {self.startFrame}" + ", 0" * 9 + "),\n")


@dataclass
class CutsceneCmdTime(CutsceneCmdBase):
    """This class contains Time Ocarina Action command data"""

    hour: Optional[int] = None
    minute: Optional[int] = None
    paramNumber: int = 5

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.hour = getInteger(self.params[3])
            self.minute = getInteger(self.params[4])

    def getCmd(self):
        return indent * 3 + f"CS_TIME(0, {self.startFrame}, 0, {self.hour}, {self.minute}),\n"


@dataclass
class CutsceneCmdRumbleController(CutsceneCmdBase):
    """This class contains Rumble Controller command data"""

    sourceStrength: Optional[int] = None
    duration: Optional[int] = None
    decreaseRate: Optional[int] = None
    paramNumber: int = 8

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.sourceStrength = getInteger(self.params[3])
            self.duration = getInteger(self.params[4])
            self.decreaseRate = getInteger(self.params[5])

    def getCmd(self):
        return indent * 3 + (
            f"CS_RUMBLE_CONTROLLER("
            + f"0, {self.startFrame}, 0, "
            + f"{self.sourceStrength}, {self.duration}, {self.decreaseRate}, 0, 0),\n"
        )


@dataclass
class CutsceneCmdMiscList(CutsceneCmdBase):
    """This class contains Misc command data"""

    entryTotal: Optional[int] = None
    entries: list[CutsceneCmdMisc] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "miscList"

    def __post_init__(self):
        if self.params is not None:
            self.entryTotal = getInteger(self.params[0])

    def getCmd(self):
        return self.getGenericListCmd("CS_MISC_LIST", self.entryTotal) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdLightSettingList(CutsceneCmdBase):
    """This class contains Light Setting List command data"""

    entryTotal: Optional[int] = None
    entries: list[CutsceneCmdLightSetting] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "lightSettingsList"

    def __post_init__(self):
        if self.params is not None:
            self.entryTotal = getInteger(self.params[0])

    def getCmd(self):
        return self.getGenericListCmd("CS_LIGHT_SETTING_LIST", self.entryTotal) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdTimeList(CutsceneCmdBase):
    """This class contains Time List command data"""

    entryTotal: Optional[int] = None
    entries: list[CutsceneCmdTime] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "timeList"

    def __post_init__(self):
        if self.params is not None:
            self.entryTotal = getInteger(self.params[0])

    def getCmd(self):
        return self.getGenericListCmd("CS_TIME_LIST", self.entryTotal) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdRumbleControllerList(CutsceneCmdBase):
    """This class contains Rumble Controller List command data"""

    entryTotal: Optional[int] = None
    entries: list[CutsceneCmdRumbleController] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "rumbleList"

    def __post_init__(self):
        if self.params is not None:
            self.entryTotal = getInteger(self.params[0])

    def getCmd(self):
        return self.getGenericListCmd("CS_RUMBLE_CONTROLLER_LIST", self.entryTotal) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdDestination(CutsceneCmdBase):
    """This class contains Destination command data"""

    id: Optional[str] = None
    paramNumber: int = 3
    listName: str = "destination"

    def __post_init__(self):
        if self.params is not None:
            self.id = self.getEnumValue("csDestination", 0)
            self.startFrame = getInteger(self.params[1])

    def getCmd(self):
        return indent * 2 + f"CS_DESTINATION({self.id}, {self.startFrame}, 0),\n"


@dataclass
class CutsceneCmdTransition(CutsceneCmdBase):
    """This class contains Transition command data"""

    type: Optional[str] = None
    paramNumber: int = 3
    listName: str = "transitionList"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.type = self.getEnumValue("csTransitionType", 0)

    def getCmd(self):
        return indent * 2 + f"CS_TRANSITION({self.type}, {self.startFrame}, {self.endFrame}),\n"
