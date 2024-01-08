from dataclasses import dataclass, field
from typing import Optional
from ....utility import indent
from ...cutscene.motion.utility import getInteger
from .common import CutsceneCmdBase


@dataclass
class CutsceneCmdText(CutsceneCmdBase):
    """This class contains Text command data"""

    textId: Optional[int] = None
    type: Optional[str] = None
    altTextId1: Optional[int] = None
    altTextId2: Optional[int] = None
    paramNumber: int = 6
    id: str = "Text"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.textId = getInteger(self.params[0])
            self.type = self.getEnumValue("csTextType", 3)
            self.altTextId1 = getInteger(self.params[4])
            self.altTextId2 = getInteger(self.params[5])

    def getCmd(self):
        return indent * 3 + (
            f"CS_TEXT("
            + f"{self.textId}, {self.startFrame}, {self.endFrame}, {self.type}, {self.altTextId1}, {self.altTextId2}"
            + "),\n"
        )


@dataclass
class CutsceneCmdTextNone(CutsceneCmdBase):
    """This class contains Text None command data"""

    paramNumber: int = 2
    id: str = "None"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[0])
            self.endFrame = getInteger(self.params[1])

    def getCmd(self):
        return indent * 3 + f"CS_TEXT_NONE({self.startFrame}, {self.endFrame}),\n"


@dataclass
class CutsceneCmdTextOcarinaAction(CutsceneCmdBase):
    """This class contains Text Ocarina Action command data"""

    ocarinaActionId: Optional[str] = None
    messageId: Optional[int] = None
    paramNumber: int = 4
    id: str = "OcarinaAction"

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.ocarinaActionId = self.getEnumValue("ocarinaSongActionId", 0)
            self.messageId = getInteger(self.params[3])

    def getCmd(self):
        return indent * 3 + (
            f"CS_TEXT_OCARINA_ACTION("
            + f"{self.ocarinaActionId}, {self.startFrame}, "
            + f"{self.endFrame}, {self.messageId}"
            + "),\n"
        )


@dataclass
class CutsceneCmdTextList(CutsceneCmdBase):
    """This class contains Text List command data"""

    entryTotal: Optional[int] = None
    entries: list[CutsceneCmdText | CutsceneCmdTextNone | CutsceneCmdTextOcarinaAction] = field(default_factory=list)
    paramNumber: int = 1
    listName: str = "textList"

    def __post_init__(self):
        if self.params is not None:
            self.entryTotal = getInteger(self.params[0])

    def getCmd(self):
        return self.getGenericListCmd("CS_TEXT_LIST", self.entryTotal) + "".join(
            entry.getCmd() for entry in self.entries
        )
