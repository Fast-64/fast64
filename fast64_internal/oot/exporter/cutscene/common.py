from dataclasses import dataclass
from typing import Optional
from ....utility import PluginError, indent
from ...oot_constants import ootData
from ...cutscene.motion.utility import getInteger


@dataclass
class CutsceneCmdBase:
    """This class contains common Cutscene data"""

    params: Optional[list[str]]

    startFrame: Optional[int] = None
    endFrame: Optional[int] = None

    def validateFrames(self, checkEndFrame: bool = True):
        if self.startFrame is None:
            raise PluginError("ERROR: Start Frame is None!")
        if checkEndFrame and self.endFrame is None:
            raise PluginError("ERROR: End Frame is None!")

    def getEnumValue(self, enumKey: str, index: int, isSeqLegacy: bool = False):
        enum = ootData.enumData.enumByKey[enumKey]
        item = enum.itemById.get(self.params[index])
        if item is None:
            setting = getInteger(self.params[index])
            if isSeqLegacy:
                setting -= 1
            item = enum.itemByIndex.get(setting)
        return item.key if item is not None else self.params[index]

    def getGenericListCmd(self, cmdName: str, entryTotal: int):
        if entryTotal is None:
            raise PluginError(f"ERROR: ``{cmdName}``'s entry total is None!")
        return indent * 2 + f"{cmdName}({entryTotal}),\n"

    def getCamListCmd(self, cmdName: str, startFrame: int, endFrame: int):
        self.validateFrames()
        return indent * 2 + f"{cmdName}({startFrame}, {endFrame}),\n"

    def getGenericSeqCmd(self, cmdName: str, type: str, startFrame: int, endFrame: int):
        self.validateFrames()
        if type is None:
            raise PluginError("ERROR: Seq type is None!")
        return indent * 3 + f"{cmdName}({type}, {startFrame}, {endFrame}" + ", 0" * 8 + "),\n"
