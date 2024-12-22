from dataclasses import dataclass
from typing import Optional
from ....utility import PluginError, indent
from ...constants import oot_data
from ...cutscene.motion.utility import getInteger


@dataclass
class CutsceneCmdBase:
    """This class contains common Cutscene data"""

    startFrame: Optional[int]
    endFrame: Optional[int]

    def validateFrames(self, checkEndFrame: bool = True):
        if self.startFrame is None:
            raise PluginError("ERROR: Start Frame is None!")
        if checkEndFrame and self.endFrame is None:
            raise PluginError("ERROR: End Frame is None!")

    @staticmethod
    def getEnumValue(enumKey: str, value: str, isSeqLegacy: bool = False):
        enum = oot_data.enumData.enumByKey[enumKey]
        item = enum.item_by_id.get(value)
        if item is None:
            setting = getInteger(value)
            if isSeqLegacy:
                setting -= 1
            item = enum.item_by_index.get(setting)
        return item.key if item is not None else value

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
