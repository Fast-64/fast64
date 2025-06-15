from dataclasses import dataclass, field
from ....utility import PluginError, indent
from ...cutscene.motion.utility import getInteger
from .common import CutsceneCmdBase


@dataclass
class CutsceneCmdText(CutsceneCmdBase):
    """This class contains Text command data"""

    textId: int
    type: str
    altTextId1: int
    altTextId2: int

    paramNumber: int = field(init=False, default=6)
    id: str = field(init=False, default="Text")

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdText(
            getInteger(params[1]),
            getInteger(params[2]),
            getInteger(params[0]),
            CutsceneCmdBase.getEnumValue("cs_text_type", params[3]),
            getInteger(params[4]),
            getInteger(params[5]),
        )

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

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdTextNone(getInteger(params[0]), getInteger(params[1]))

    def getCmd(self):
        self.validateFrames()
        return indent * 3 + f"CS_TEXT_NONE({self.startFrame}, {self.endFrame}),\n"


@dataclass
class CutsceneCmdTextOcarinaAction(CutsceneCmdBase):
    """This class contains Text Ocarina Action command data"""

    ocarinaActionId: str
    messageId: int

    paramNumber: int = field(init=False, default=4)
    id: str = field(init=False, default="OcarinaAction")

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdTextOcarinaAction(
            getInteger(params[1]),
            getInteger(params[2]),
            CutsceneCmdBase.getEnumValue("ocarina_song_action_id", params[0]),
            getInteger(params[3]),
        )

    def getCmd(self):
        self.validateFrames()
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

    @staticmethod
    def from_params(params: list[str]):
        new = CutsceneCmdTextList()
        new.entryTotal = getInteger(params[0])
        return new

    def getCmd(self):
        if len(self.entries) == 0:
            raise PluginError("ERROR: Entry list is empty!")

        return self.getGenericListCmd("CS_TEXT_LIST", self.entryTotal) + "".join(
            entry.getCmd() for entry in self.entries
        )
