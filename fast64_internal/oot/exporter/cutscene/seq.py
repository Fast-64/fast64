from dataclasses import dataclass, field
from typing import Optional
from ...cutscene.motion.utility import getInteger
from .common import CutsceneCmdBase


@dataclass
class CutsceneCmdStartStopSeq(CutsceneCmdBase):
    """This class contains Start/Stop Seq command data"""

    isLegacy: Optional[bool] = None
    seqId: Optional[str] = None
    paramNumber: int = 11
    type: Optional[str] = None  # "start" or "stop"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.seqId = self.getEnumValue("seqId", 0, self.isLegacy)

    def getCmd(self):
        return self.getGenericSeqCmd(f"CS_{self.type.upper()}_SEQ", self.seqId, self.startFrame, self.endFrame)


@dataclass
class CutsceneCmdFadeSeq(CutsceneCmdBase):
    """This class contains Fade Seq command data"""

    seqPlayer: Optional[str] = None
    paramNumber: int = 11
    enumKey: str = "csFadeOutSeqPlayer"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.seqPlayer = self.getEnumValue(self.enumKey, 0)

    def getCmd(self):
        return self.getGenericSeqCmd("CS_FADE_OUT_SEQ", self.seqPlayer, self.startFrame, self.endFrame)


@dataclass
class CutsceneCmdStartStopSeqList(CutsceneCmdBase):
    """This class contains Start/Stop Seq List command data"""

    entryTotal: Optional[int] = None
    type: Optional[str] = None  # "start" or "stop"
    entries: list[CutsceneCmdStartStopSeq] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "seqList"

    def __post_init__(self):
        if self.params is not None:
            self.entryTotal = getInteger(self.params[0])

    def getCmd(self):
        return self.getGenericListCmd(f"CS_{self.type.upper()}_SEQ_LIST", self.entryTotal) + "".join(
            entry.getCmd() for entry in self.entries
        )


@dataclass
class CutsceneCmdFadeSeqList(CutsceneCmdBase):
    """This class contains Fade Seq List command data"""

    entryTotal: Optional[int] = None
    entries: list[CutsceneCmdFadeSeq] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "fadeSeqList"

    def __post_init__(self):
        if self.params is not None:
            self.entryTotal = getInteger(self.params[0])

    def getCmd(self):
        return self.getGenericListCmd("CS_FADE_OUT_SEQ_LIST", self.entryTotal) + "".join(
            entry.getCmd() for entry in self.entries
        )
