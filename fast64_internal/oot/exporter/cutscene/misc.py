from dataclasses import dataclass, field
from typing import Optional
from ....utility import PluginError, indent
from ...cutscene.motion.utility import getInteger
from .common import CutsceneCmdBase


@dataclass
class CutsceneCmdMisc(CutsceneCmdBase):
    """This class contains a single misc command entry"""

    type: Optional[str] = None  # see ``CutsceneMiscType`` in decomp

    paramNumber: int = field(init=False, default=14)

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.type = self.getEnumValue("csMiscType", 0)

    def getCmd(self):
        self.validateFrames()
        if self.type is None:
            raise PluginError("ERROR: Misc Type is None!")
        return indent * 3 + (f"CS_MISC({self.type}, {self.startFrame}, {self.endFrame}" + ", 0" * 11 + "),\n")


@dataclass
class CutsceneCmdLightSetting(CutsceneCmdBase):
    """This class contains Light Setting command data"""

    isLegacy: bool = False
    lightSetting: int = 0

    paramNumber: int = field(init=False, default=11)

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.lightSetting = getInteger(self.params[0])
            if self.isLegacy:
                self.lightSetting -= 1

    def getCmd(self):
        self.validateFrames(False)
        return indent * 3 + (f"CS_LIGHT_SETTING({self.lightSetting}, {self.startFrame}" + ", 0" * 12 + "),\n")


@dataclass
class CutsceneCmdTime(CutsceneCmdBase):
    """This class contains Time Ocarina Action command data"""

    hour: int = 0
    minute: int = 0

    paramNumber: int = field(init=False, default=5)

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.hour = getInteger(self.params[3])
            self.minute = getInteger(self.params[4])

    def getCmd(self):
        self.validateFrames(False)
        return indent * 3 + f"CS_TIME(0, {self.startFrame}, 0, {self.hour}, {self.minute}),\n"


@dataclass
class CutsceneCmdRumbleController(CutsceneCmdBase):
    """This class contains Rumble Controller command data"""

    sourceStrength: int = 0
    duration: int = 0
    decreaseRate: int = 0

    paramNumber: int = field(init=False, default=8)

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.sourceStrength = getInteger(self.params[3])
            self.duration = getInteger(self.params[4])
            self.decreaseRate = getInteger(self.params[5])

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

    def __post_init__(self):
        if self.params is not None:
            self.entryTotal = getInteger(self.params[0])

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

    def __post_init__(self):
        if self.params is not None:
            self.entryTotal = getInteger(self.params[0])

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

    def __post_init__(self):
        if self.params is not None:
            self.entryTotal = getInteger(self.params[0])

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

    def __post_init__(self):
        if self.params is not None:
            self.entryTotal = getInteger(self.params[0])

    def getCmd(self):
        if len(self.entries) == 0:
            raise PluginError("ERROR: Entry list is empty!")
        return self.getGenericListCmd("CS_RUMBLE_CONTROLLER_LIST", self.entryTotal) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdDestination(CutsceneCmdBase):
    """This class contains Destination command data"""

    id: Optional[str] = None

    paramNumber: int = field(init=False, default=3)
    listName: str = field(init=False, default="destination")

    def __post_init__(self):
        if self.params is not None:
            self.id = self.getEnumValue("csDestination", 0)
            self.startFrame = getInteger(self.params[1])

    def getCmd(self):
        self.validateFrames(False)
        if self.id is None:
            raise PluginError("ERROR: Destination ID is None!")
        return indent * 2 + f"CS_DESTINATION({self.id}, {self.startFrame}, 0),\n"


@dataclass
class CutsceneCmdTransition(CutsceneCmdBase):
    """This class contains Transition command data"""

    type: Optional[str] = None

    paramNumber: int = field(init=False, default=3)
    listName: str = field(init=False, default="transitionList")

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.type = self.getEnumValue("csTransitionType", 0)

    def getCmd(self):
        self.validateFrames()
        if self.type is None:
            raise PluginError("ERROR: Transition type is None!")
        return indent * 2 + f"CS_TRANSITION({self.type}, {self.startFrame}, {self.endFrame}),\n"
