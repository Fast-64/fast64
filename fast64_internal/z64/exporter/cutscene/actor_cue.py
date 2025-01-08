from dataclasses import dataclass, field
from ....utility import PluginError, indent
from ....game_data import game_data
from ...cutscene.motion.utility import getRotation, getInteger
from .common import CutsceneCmdBase


@dataclass
class CutsceneCmdActorCue(CutsceneCmdBase):
    """This class contains a single Actor Cue command data"""

    actionID: int
    rot: list[str]
    startPos: list[int]
    endPos: list[int]
    isPlayer: bool

    paramNumber: int = field(init=False, default=15)

    @staticmethod
    def from_params(params: list[str]):
        return CutsceneCmdActorCue(
            getInteger(params[1]),
            getInteger(params[2]),
            getInteger(params[0]),
            [getRotation(params[3]), getRotation(params[4]), getRotation(params[5])],
            [getInteger(params[6]), getInteger(params[7]), getInteger(params[8])],
            [getInteger(params[9]), getInteger(params[10]), getInteger(params[11])],
        )

    def getCmd(self):
        self.validateFrames()

        if len(self.rot) == 0:
            raise PluginError("ERROR: Rotation list is empty!")

        if len(self.startPos) == 0:
            raise PluginError("ERROR: Start Position list is empty!")

        if len(self.endPos) == 0:
            raise PluginError("ERROR: End Position list is empty!")

        return indent * 3 + (
            f"CS_{'PLAYER' if self.isPlayer else 'ACTOR'}_CUE("
            + f"{self.actionID}, {self.startFrame}, {self.endFrame}, "
            + "".join(f"{rot}, " for rot in self.rot)
            + "".join(f"{pos}, " for pos in self.startPos)
            + "".join(f"{pos}, " for pos in self.endPos)
            + "0.0f, 0.0f, 0.0f),\n"
        )


@dataclass
class CutsceneCmdActorCueList(CutsceneCmdBase):
    """This class contains the Actor Cue List command data"""

    isPlayer: bool
    commandType: str
    entryTotal: int

    entries: list[CutsceneCmdActorCue] = field(init=False, default_factory=list)
    paramNumber: int = field(init=False, default=2)
    listName: str = field(init=False, default="actorCueList")

    @staticmethod
    def from_params(params: list[str], isPlayer: bool):
        if isPlayer:
            commandType = "Player"
            entryTotal = getInteger(params[0])
        else:
            commandType = params[0]
            if commandType.startswith("0x"):
                # make it a 4 digit hex
                commandType = commandType.removeprefix("0x")
                commandType = "0x" + "0" * (4 - len(commandType)) + commandType
            else:
                commandType = game_data.z64.enums.enumByKey["csCmd"].item_by_id[commandType].key
            entryTotal = getInteger(params[1].strip())

        return CutsceneCmdActorCueList(None, None, isPlayer, commandType, entryTotal)

    def getCmd(self):
        if len(self.entries) == 0:
            raise PluginError("ERROR: No Actor Cue entry found!")

        return (
            indent * 2
            + (
                f"CS_{'PLAYER' if self.isPlayer else 'ACTOR'}_CUE_LIST("
                + f"{self.commandType + ', ' if not self.isPlayer else ''}"
                + f"{self.entryTotal}),\n"
            )
            + "".join(entry.getCmd() for entry in self.entries)
        )
