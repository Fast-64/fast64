from dataclasses import dataclass, field
from typing import Optional
from ....utility import PluginError
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
