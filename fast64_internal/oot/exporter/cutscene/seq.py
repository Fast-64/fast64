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

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.seqId = self.getEnumValue("seqId", 0, self.isLegacy)

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

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.seqPlayer = self.getEnumValue(self.enumKey, 0)

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

    def __post_init__(self):
        if self.params is not None:
            self.entryTotal = getInteger(self.params[0])

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

    def __post_init__(self):
        if self.params is not None:
            self.entryTotal = getInteger(self.params[0])

    def getCmd(self):
        if len(self.entries) == 0:
            raise PluginError("ERROR: Entry list is empty!")
        return self.getGenericListCmd("CS_FADE_OUT_SEQ_LIST", self.entryTotal) + "".join(
            entry.getCmd() for entry in self.entries
        )
