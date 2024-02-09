from dataclasses import dataclass, field
from typing import Optional
from ....utility import PluginError, indent
from ...oot_constants import ootData
from ...cutscene.motion.utility import getRotation, getInteger
from .common import CutsceneCmdBase


@dataclass
class CutsceneCmdActorCue(CutsceneCmdBase):
    """This class contains a single Actor Cue command data"""

    actionID: Optional[int] = None
    rot: list[str] = field(default_factory=list)
    startPos: list[int] = field(default_factory=list)
    endPos: list[int] = field(default_factory=list)
    isPlayer: bool = False

    paramNumber: int = field(init=False, default=15)

    def __post_init__(self):
        if self.params is not None:
            self.startFrame = getInteger(self.params[1])
            self.endFrame = getInteger(self.params[2])
            self.actionID = getInteger(self.params[0])
            self.rot = [getRotation(self.params[3]), getRotation(self.params[4]), getRotation(self.params[5])]
            self.startPos = [getInteger(self.params[6]), getInteger(self.params[7]), getInteger(self.params[8])]
            self.endPos = [getInteger(self.params[9]), getInteger(self.params[10]), getInteger(self.params[11])]

    def getCmd(self):
        self.validateFrames()
        if self.actionID is None:
            raise PluginError("ERROR: Action ID is None!")
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

    isPlayer: bool = False
    commandType: Optional[str] = None
    entryTotal: Optional[int] = None

    entries: list[CutsceneCmdActorCue] = field(init=False, default_factory=list)
    paramNumber: int = field(init=False, default=2)
    listName: str = field(init=False, default="actorCueList")

    def __post_init__(self):
        if self.params is not None:
            if self.isPlayer:
                self.commandType = "Player"
                self.entryTotal = getInteger(self.params[0])
            else:
                self.commandType = self.params[0]
                if self.commandType.startswith("0x"):
                    # make it a 4 digit hex
                    self.commandType = self.commandType.removeprefix("0x")
                    self.commandType = "0x" + "0" * (4 - len(self.commandType)) + self.commandType
                else:
                    self.commandType = ootData.enumData.enumByKey["csCmd"].itemById[self.commandType].key
                self.entryTotal = getInteger(self.params[1].strip())

    def getCmd(self):
        if self.commandType is None:
            raise PluginError("ERROR: ``commandType`` is None!")
        if self.entryTotal is None:
            raise PluginError("ERROR: ``entryTotal`` is None!")
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
