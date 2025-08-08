from dataclasses import dataclass, field
from typing import Optional
from ....utility import PluginError, indent
from ...utility import is_oot_features
from ...cutscene.motion.utility import getInteger
from .common import CutsceneCmdBase

mm_cmd_name_to_type = {
    "CS_TEXT_NONE": "CS_TEXT_TYPE_NONE",
    "CS_TEXT_DEFAULT": "CS_TEXT_TYPE_DEFAULT",
    "CS_TEXT_TYPE_1": "CS_TEXT_TYPE_1",
    "CS_TEXT_OCARINA_ACTION": "CS_TEXT_OCARINA_ACTION",
    "CS_TEXT_TYPE_3": "CS_TEXT_TYPE_3",
    "CS_TEXT_BOSSES_REMAINS": "CS_TEXT_TYPE_BOSSES_REMAINS",
    "CS_TEXT_ALL_NORMAL_MASKS": "CS_TEXT_TYPE_ALL_NORMAL_MASKS",
}


@dataclass
class CutsceneCmdText(CutsceneCmdBase):
    """This class contains Text command data"""

    textId: int
    type: Optional[str]
    altTextId1: int
    altTextId2: int

    paramNumber: int = field(init=False, default=6)
    id: str = field(init=False, default="Text")

    @staticmethod
    def from_params(params: list[str], cmd_name: str):
        if is_oot_features():
            return CutsceneCmdText(
                getInteger(params[1]),
                getInteger(params[2]),
                getInteger(params[0]),
                CutsceneCmdBase.getEnumValue("cs_text_type", params[3]),
                getInteger(params[4]),
                getInteger(params[5]),
            )
        else:
            return CutsceneCmdText(
                getInteger(params[1]),
                getInteger(params[2]),
                getInteger(params[0]),
                CutsceneCmdBase.getEnumValue("cs_text_type", mm_cmd_name_to_type[cmd_name]),
                getInteger(params[3]),
                getInteger(params[4]),
            )

    def getCmd(self):
        self.validateFrames()
        if is_oot_features():
            command = (
                f"CS_TEXT("
                + f"{self.textId}, {self.startFrame}, {self.endFrame}, {self.type}, {self.altTextId1}, {self.altTextId2}"
                + "),\n"
            )
        else:
            command = f"{self.type}("
            if self.type not in {"CS_TEXT_TYPE_1", "CS_TEXT_TYPE_3"}:
                command = command.replace("_TYPE", "")
            match self.type:
                case "CS_TEXT_TYPE_DEFAULT" | "CS_TEXT_TYPE_1" | "CS_TEXT_TYPE_3":
                    command += (
                        f"{self.textId}, {self.startFrame}, {self.endFrame}, {self.altTextId1}, {self.altTextId2}"
                    )
                case "CS_TEXT_TYPE_BOSSES_REMAINS" | "CS_TEXT_TYPE_ALL_NORMAL_MASKS":
                    command += f"{self.textId}, {self.startFrame}, {self.endFrame}, {self.altTextId1}"
            command += "),\n"
        return indent * 3 + command


@dataclass
class CutsceneCmdTextNone(CutsceneCmdBase):
    """This class contains Text None command data"""

    paramNumber: int = field(init=False, default=2)
    id: str = field(init=False, default="None")

    @staticmethod
    def from_params(params: list[str], cmd_name: str):
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
    def from_params(params: list[str], cmd_name: str):
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
        new = CutsceneCmdTextList(None, None)
        new.entryTotal = getInteger(params[0])
        return new

    def getCmd(self):
        if len(self.entries) == 0:
            raise PluginError("ERROR: Entry list is empty!")

        return self.getGenericListCmd("CS_TEXT_LIST", self.entryTotal) + "".join(
            entry.getCmd() for entry in self.entries
        )
