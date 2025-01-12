from dataclasses import dataclass, field
from typing import Optional
from ....utility import PluginError, indent
from ...cutscene.motion.utility import getInteger
from .common import CutsceneCmdBase


@dataclass
class CutsceneCmdStartStopSeq(CutsceneCmdBase):
    """This class contains Start/Stop Seq command data"""

    isLegacy: bool = field(init=False, default=False)
    seqId: Optional[str] = field(init=False, default=None)
    paramNumber: int = field(init=False, default=11)
    type: Optional[str] = field(init=False, default=None)  # "start" or "stop"

    @staticmethod
    def from_params(params: list[str], isLegacy: bool):
        return CutsceneCmdFadeSeq(
            getInteger(params[1]), getInteger(params[2]), CutsceneCmdBase.getEnumValue("seq_id", params[0], isLegacy)
        )

    def getCmd(self):
        self.validateFrames()
        if self.type is None:
            raise PluginError("ERROR: Type is None!")
        return self.getGenericSeqCmd(f"CS_{self.type.upper()}_SEQ", self.seqId, self.startFrame, self.endFrame)


@dataclass
class CutsceneCmdFadeSeq(CutsceneCmdBase):
    """This class contains Fade Seq command data"""

    seqPlayer: str = field(init=False, default=str())
    paramNumber: int = field(init=False, default=11)
    enumKey: str = field(init=False, default="csFadeOutSeqPlayer")

    @staticmethod
    def from_params(params: list[str], enumKey: str):
        return CutsceneCmdFadeSeq(
            getInteger(params[1]), getInteger(params[2]), CutsceneCmdBase.getEnumValue(enumKey, params[0])
        )

    def getCmd(self):
        self.validateFrames()
        return self.getGenericSeqCmd("CS_FADE_OUT_SEQ", self.seqPlayer, self.startFrame, self.endFrame)


@dataclass
class CutsceneCmdStartStopSeqList(CutsceneCmdBase):
    """This class contains Start/Stop Seq List command data"""

    entryTotal: int = field(init=False, default=0)
    type: str = field(init=False, default=str())  # "start" or "stop"
    entries: list[CutsceneCmdStartStopSeq] = field(init=False, default_factory=list)
    paramNumber: int = field(init=False, default=1)
    listName: str = field(init=False, default="seqList")

    @staticmethod
    def from_params(params: list[str]):
        new = CutsceneCmdStartStopSeqList()
        new.entryTotal = getInteger(params[0])
        return new

    def getCmd(self):
        if len(self.entries) == 0:
            raise PluginError("ERROR: Entry list is empty!")
        return self.getGenericListCmd(f"CS_{self.type.upper()}_SEQ_LIST", self.entryTotal) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdFadeSeqList(CutsceneCmdBase):
    """This class contains Fade Seq List command data"""

    entryTotal: int = field(init=False, default=0)
    entries: list[CutsceneCmdFadeSeq] = field(init=False, default_factory=list)
    paramNumber: int = field(init=False, default=1)
    listName: str = field(init=False, default="fadeSeqList")

    @staticmethod
    def from_params(params: list[str]):
        new = CutsceneCmdFadeSeqList()
        new.entryTotal = getInteger(params[0])
        return new

    def getCmd(self):
        if len(self.entries) == 0:
            raise PluginError("ERROR: Entry list is empty!")
        return self.getGenericListCmd("CS_FADE_OUT_SEQ_LIST", self.entryTotal) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdModifySeq(CutsceneCmdBase):
    """This class contains modify seq command data"""

    type: str
    paramNumber: int = field(init=False, default=3)

    @staticmethod
    def from_params(params: list[str], enumKey: str):
        return CutsceneCmdModifySeq(
            getInteger(params[1]), getInteger(params[2]), CutsceneCmdBase.getEnumValue("cs_modify_seq_type", params[0])
        )

    def to_c(self):
        return indent * 3 + f"CS_MODIFY_SEQ({self.type}, {self.startFrame}, {self.endFrame}),\n"


@dataclass
class CutsceneCmdModifySeqList(CutsceneCmdBase):
    """This class contains modify seq list command data"""

    entryTotal: int = field(init=False, default=0)
    entries: list[CutsceneCmdModifySeq] = field(default_factory=list)
    paramNumber: int = field(init=False, default=1)
    listName: str = field(init=False, default="modify_seq_list")

    @staticmethod
    def from_params(params: list[str]):
        new = CutsceneCmdModifySeqList()
        new.entryTotal = getInteger(params[0])
        return new

    def getCmd(self):
        return (
            indent * 2 + f"CS_MODIFY_SEQ_LIST({len(self.entries)}),\n" + "".join(entry.to_c() for entry in self.entries)
        )


@dataclass
class CutsceneCmdStartAmbience(CutsceneCmdBase):
    """This class contains modify seq command data"""

    paramNumber: int = field(init=False, default=3)

    @staticmethod
    def from_params(params: list[str], enumKey: str):
        return CutsceneCmdStartAmbience(getInteger(params[1]), getInteger(params[2]))

    def to_c(self):
        return indent * 3 + f"CS_START_AMBIENCE(0, {self.startFrame}, {self.endFrame}),\n"


@dataclass
class CutsceneCmdStartAmbienceList(CutsceneCmdBase):
    """This class contains modify seq list command data"""

    entryTotal: int = field(init=False, default=0)
    entries: list[CutsceneCmdStartAmbience] = field(default_factory=list)
    paramNumber: int = field(init=False, default=1)
    listName: str = field(init=False, default="start_ambience_list")

    @staticmethod
    def from_params(params: list[str]):
        new = CutsceneCmdStartAmbienceList()
        new.entryTotal = getInteger(params[0])
        return new

    def getCmd(self):
        return (
            indent * 2
            + f"CS_START_AMBIENCE_LIST({len(self.entries)}),\n"
            + "".join(entry.to_c() for entry in self.entries)
        )


@dataclass
class CutsceneCmdFadeOutAmbience(CutsceneCmdBase):
    """This class contains modify seq command data"""

    paramNumber: int = field(init=False, default=3)

    @staticmethod
    def from_params(params: list[str], enumKey: str):
        return CutsceneCmdFadeOutAmbience(getInteger(params[1]), getInteger(params[2]))

    def to_c(self):
        return indent * 3 + f"CS_FADE_OUT_AMBIENCE(0, {self.startFrame}, {self.endFrame}),\n"


@dataclass
class CutsceneCmdFadeOutAmbienceList(CutsceneCmdBase):
    """This class contains modify seq list command data"""

    entryTotal: int = field(init=False, default=0)
    entries: list[CutsceneCmdFadeOutAmbience] = field(default_factory=list)
    paramNumber: int = field(init=False, default=1)
    listName: str = field(init=False, default="fade_out_ambience_list")

    @staticmethod
    def from_params(params: list[str]):
        new = CutsceneCmdFadeOutAmbienceList()
        new.entryTotal = getInteger(params[0])
        return new

    def getCmd(self):
        return (
            indent * 2
            + f"CS_FADE_OUT_AMBIENCE_LIST({len(self.entries)}),\n"
            + "".join(entry.to_c() for entry in self.entries)
        )
