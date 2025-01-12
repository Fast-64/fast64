from dataclasses import dataclass, field
from typing import Optional
from ....game_data import game_data
from ....utility import PluginError, indent
from ...utility import is_oot_features
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
            getInteger(params[1]), getInteger(params[2]), CutsceneCmdBase.getEnumValue("cs_misc_type", params[0])
        )

    def getCmd(self):
        self.validateFrames()
        pad_amount = 11 if is_oot_features() else 1
        return indent * 3 + (f"CS_MISC({self.type}, {self.startFrame}, {self.endFrame}" + ", 0" * pad_amount + "),\n")


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
            getInteger(params[1]), getInteger(params[2]), isLegacy, lightSetting - 1 if isLegacy else lightSetting
        )

    def getCmd(self):
        self.validateFrames(False)
        pad_amount = 12 if is_oot_features() else 1
        return indent * 3 + (f"CS_LIGHT_SETTING({self.lightSetting}, {self.startFrame}" + ", 0" * pad_amount + "),\n")


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
    type: Optional[str]
    paramNumber: int = field(init=False, default=8)

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdRumbleController(
            getInteger(params[1]),
            getInteger(params[2]),
            getInteger(params[3]),
            getInteger(params[4]),
            getInteger(params[5]),
            params[0] if not is_oot_features() else None,
        )

    def getCmd(self):
        self.validateFrames(False)
        if is_oot_features():
            return indent * 3 + (
                f"CS_RUMBLE_CONTROLLER("
                + f"0, {self.startFrame}, 0, {self.sourceStrength}, {self.duration}, {self.decreaseRate}, 0, 0),\n"
            )
        else:
            return indent * 3 + (
                f"CS_RUMBLE("
                + f"{self.type}, {self.startFrame}, {self.endFrame}, "
                + f"{self.sourceStrength}, {self.duration}, {self.decreaseRate}),\n"
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
        suffix = "_CONTROLLER" if is_oot_features() else ""
        return self.getGenericListCmd(f"CS_RUMBLE{suffix}_LIST", self.entryTotal) + "".join(
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
            getInteger(params[1]), getInteger(params[2]), CutsceneCmdBase.getEnumValue("cs_destination", params[0])
        )

    def getCmd(self):
        self.validateFrames(False)
        if is_oot_features():
            return indent * 2 + f"CS_DESTINATION({self.id}, {self.startFrame}, {self.endFrame}),\n"
        else:
            return (
                indent * 2
                + f"CS_DESTINATION_LIST(1),\n"
                + indent * 3
                + f"CS_DESTINATION({self.id}, {self.startFrame}, {self.endFrame}),\n"
            )


@dataclass
class CutsceneCmdTransition(CutsceneCmdBase):
    """This class contains Transition command data"""

    type: str
    paramNumber: int = field(init=False, default=3)

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdTransition(
            getInteger(params[1]), getInteger(params[2]), CutsceneCmdBase.getEnumValue("cs_transition_type", params[0])
        )

    def to_c(self):
        self.validateFrames()
        return indent * 3 + f"CS_TRANSITION({self.type}, {self.startFrame}, {self.endFrame}),\n"


@dataclass
class CutsceneCmdTransitionList(CutsceneCmdBase):
    """This class contains Transition list command data"""

    entryTotal: int
    entries: list[CutsceneCmdTransition] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "transitionList"

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdTransitionList(getInteger(params[0]))

    def getCmd(self):
        if game_data.z64.is_oot():
            return "".join(entry.to_c() for entry in self.entries)
        else:
            return (
                indent * 2
                + f"CS_TRANSITION_LIST({len(self.entries)}),\n"
                + "".join(entry.to_c() for entry in self.entries)
            )


@dataclass
class CutsceneCmdMotionBlur(CutsceneCmdBase):
    """This class contains motion blur command data"""

    type: str
    paramNumber: int = 3

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdMotionBlur(
            CutsceneCmdBase.getEnumValue("cs_motion_blur_type", params[0]),
            getInteger(params[1]),
            getInteger(params[2]),
        )

    def to_c(self):
        return indent * 3 + f"CS_MOTION_BLUR({self.type}, {self.startFrame}, {self.endFrame}),\n"


@dataclass
class CutsceneCmdMotionBlurList(CutsceneCmdBase):
    """This class contains motion blur list command data"""

    entryTotal: int
    entries: list[CutsceneCmdMotionBlur] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "motion_blur_list"

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdMotionBlurList(getInteger(params[0]))

    def getCmd(self):
        return (
            indent * 2
            + f"CS_MOTION_BLUR_LIST({len(self.entries)}),\n"
            + "".join(entry.to_c() for entry in self.entries)
        )


@dataclass
class CutsceneCmdChooseCreditsScenes(CutsceneCmdBase):
    """This class contains choose credits scenes command data"""

    type: str
    paramNumber: int = 3

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdChooseCreditsScenes(
            CutsceneCmdBase.getEnumValue("cs_credits_scene_type", params[0]),
            getInteger(params[1]),
            getInteger(params[2]),
        )

    def to_c(self):
        return indent * 3 + f"CS_CHOOSE_CREDITS_SCENES({self.type}, {self.startFrame}, {self.endFrame}),\n"


@dataclass
class CutsceneCmdChooseCreditsScenesList(CutsceneCmdBase):
    """This class contains choose credits scenes list command data"""

    entryTotal: int
    entries: list[CutsceneCmdChooseCreditsScenes] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "credits_scene_list"

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdChooseCreditsScenesList(getInteger(params[0]))

    def getCmd(self):
        return (
            indent * 2
            + f"CS_CHOOSE_CREDITS_SCENES_LIST({len(self.entries)}),\n"
            + "".join(entry.to_c() for entry in self.entries)
        )


@dataclass
class CutsceneCmdTransitionGeneral(CutsceneCmdBase):
    """This class contains transition general command data"""

    type: str
    rgb: list[int]
    paramNumber: int = 6

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdTransitionGeneral(
            getInteger(params[1]),
            getInteger(params[2]),
            CutsceneCmdBase.getEnumValue("cs_transition_general", 0),
            [getInteger(params[3]), getInteger(params[4]), getInteger(params[5])],
        )

    def to_c(self):
        color = ", ".join(f"{c}" for c in self.rgb)
        return indent * 3 + f"CS_TRANSITION_GENERAL({self.type}, {self.startFrame}, {self.endFrame}, {color}),\n"


@dataclass
class CutsceneCmdTransitionGeneralList(CutsceneCmdBase):
    """This class contains transition general list command data"""

    entryTotal: int
    entries: list[CutsceneCmdTransitionGeneral] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "transition_general_list"

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdTransitionGeneralList(getInteger(params[0]))

    def getCmd(self):
        return (
            indent * 2
            + f"CS_TRANSITION_GENERAL_LIST({len(self.entries)}),\n"
            + "".join(entry.to_c() for entry in self.entries)
        )


@dataclass
class CutsceneCmdGiveTatl(CutsceneCmdBase):
    """This class contains give tatl command data"""

    giveTatl: bool
    paramNumber: int = 3

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdGiveTatl(
            getInteger(params[1]),
            getInteger(params[2]),
            params[0] in {"true", "1"},
        )

    def getCmd(self):
        return (
            indent * 2
            + f"CS_GIVE_TATL_LIST(1),\n"
            + indent * 3
            + f"CS_GIVE_TATL({self.giveTatl}, {self.startFrame}, {self.endFrame}),\n"
        )
