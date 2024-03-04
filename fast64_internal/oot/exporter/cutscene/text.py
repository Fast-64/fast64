from dataclasses import dataclass, field
from typing import Optional
from ....utility import PluginError, indent
from ...cutscene.motion.utility import getInteger
from .common import CutsceneCmdBase


@dataclass
class CutsceneCmdText(CutsceneCmdBase):
    """This class contains Text command data"""

    textId: int = 0
    type: str = str()
    altTextId1: int = 0
    altTextId2: int = 0

    paramNumber: int = field(init=False, default=6)
    id: str = field(init=False, default="Text")

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.textId = getInteger(self.params[0])
            self.type = self.getEnumValue("csTextType", 3)
            self.altTextId1 = getInteger(self.params[4])
            self.altTextId2 = getInteger(self.params[5])

    def getCmd(self):
        self.validateFrames()
        return indent * 3 + (
            f"CS_TEXT("
            + f"{self.textId}, {self.startFrame}, {self.endFrame}, {self.type}, {self.altTextId1}, {self.altTextId2}"
            + "),\n"
        )


@dataclass
class CutsceneCmdTextNone(CutsceneCmdBase):
    """This class contains Text None command data"""

    paramNumber: int = field(init=False, default=2)
    id: str = field(init=False, default="None")

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[0])
            self.endFrame = getInteger(self.params[1])

    def getCmd(self):
        self.validateFrames()
        return indent * 3 + f"CS_TEXT_NONE({self.startFrame}, {self.endFrame}),\n"


@dataclass
class CutsceneCmdTextOcarinaAction(CutsceneCmdBase):
    """This class contains Text Ocarina Action command data"""

    ocarinaActionId: str = str()
    messageId: int = 0

    paramNumber: int = field(init=False, default=4)
    id: str = field(init=False, default="OcarinaAction")

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.ocarinaActionId = self.getEnumValue("ocarinaSongActionId", 0)
            self.messageId = getInteger(self.params[3])

    def getCmd(self):
        self.validateFrames()
        if self.ocarinaActionId is None:
            raise PluginError("ERROR: ``ocarinaActionId`` is None!")
        if self.messageId is None:
            raise PluginError("ERROR: ``messageId`` is None!")
        return indent * 3 + (
            f"CS_TEXT_OCARINA_ACTION("
            + f"{self.ocarinaActionId}, {self.startFrame}, {self.endFrame}, {self.messageId}"
            + "),\n"
        )


@dataclass
class CutsceneCmdTextList(CutsceneCmdBase):
    """This class contains Text List command data"""

    entryTotal: int = field(init=False, default=0)
    entries: list[CutsceneCmdText | CutsceneCmdTextNone | CutsceneCmdTextOcarinaAction] = field(
        init=False, default_factory=list
    )
    paramNumber: int = field(init=False, default=1)
    listName: str = field(init=False, default="textList")

    def __post_init__(self):
        if self.params is not None:
            self.entryTotal = getInteger(self.params[0])

    def getCmd(self):
        if len(self.entries) == 0:
            raise PluginError("ERROR: Entry list is empty!")
        return self.getGenericListCmd("CS_TEXT_LIST", self.entryTotal) + "".join(
            entry.getCmd() for entry in self.entries
        )
