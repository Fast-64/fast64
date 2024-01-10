import bpy

from dataclasses import dataclass, field
from typing import Optional
from bpy.types import Object
from ....utility import PluginError, CData, indent
from ...oot_utility import getCustomProperty
from ...scene.properties import OOTSceneHeaderProperty
from ..base import Base
from .data import CutsceneData


# NOTE: ``paramNumber`` is the expected number of parameters inside the parsed commands,
# this account for the unused parameters. Every classes are based on the commands arguments from ``z64cutscene_commands.h``

# NOTE: ``params`` is the list of parsed parameters, it can't be ``None`` if we're importing a scene,
# when it's ``None`` it will get the data from the cutscene objects


@dataclass
class Cutscene:
    """This class defines a cutscene, including its data and its informations"""

    csObj: Object
    useMacros: bool
    name: Optional[str] = None
    motionOnly: bool = False
    data: Optional[CutsceneData] = None
    totalEntries: int = 0
    frameCount: int = 0
    paramNumber: int = 2

    def __post_init__(self):
        # when csObj is None it means we're in import context
        if self.csObj is not None and self.data is None:
            if self.name is None:
                self.name = self.csObj.name.removeprefix("Cutscene.").replace(".", "_")
            self.data = CutsceneData(self.csObj, self.useMacros, self.motionOnly)
            self.totalEntries = self.data.totalEntries
            self.frameCount = self.data.frameCount

    def getC(self):
        """Returns the cutscene data"""

        if self.data is not None:
            csData = CData()
            declarationBase = f"CutsceneData {self.name}[]"

            # this list's order defines the order of the commands in the cutscene array
            dataListNames = []

            if not self.motionOnly:
                dataListNames = [
                    "textList",
                    "miscList",
                    "rumbleList",
                    "transitionList",
                    "lightSettingsList",
                    "timeList",
                    "seqList",
                    "fadeSeqList",
                ]

            dataListNames.extend(
                [
                    "playerCueList",
                    "actorCueList",
                    "camEyeSplineList",
                    "camATSplineList",
                    "camEyeSplineRelPlayerList",
                    "camATSplineRelPlayerList",
                    "camEyeList",
                    "camATList",
                ]
            )

            if self.data.motionFrameCount > self.frameCount:
                self.frameCount += self.data.motionFrameCount - self.frameCount

            # .h
            csData.header = f"extern {declarationBase};\n"

            # .c
            csData.source = (
                declarationBase
                + " = {\n"
                + (indent + f"CS_BEGIN_CUTSCENE({self.totalEntries}, {self.frameCount}),\n")
                + (self.data.destination.getCmd() if self.data.destination is not None else "")
                + "".join(entry.getCmd() for curList in dataListNames for entry in getattr(self.data, curList))
                + (indent + "CS_END(),\n")
                + "};\n\n"
            )

            return csData
        else:
            raise PluginError("ERROR: CutsceneData not initialised!")


@dataclass
class SceneCutscene(Base):
    """This class hosts cutscene data"""

    props: OOTSceneHeaderProperty
    headerIndex: int
    useMacros: bool

    entries: list[Cutscene] = field(default_factory=list)
    csObj: Optional[Object] = None
    cutsceneObjects: list[Object] = field(default_factory=list)

    def __post_init__(self):
        self.csObj: Object = self.props.csWriteObject
        self.cutsceneObjects = [csObj for csObj in self.props.extraCutscenes]

        if self.headerIndex > 0 and len(self.cutsceneObjects) > 0:
            raise PluginError("ERROR: Extra cutscenes can only belong to the main header!")

        self.cutsceneObjects.insert(0, self.csObj)
        for csObj in self.cutsceneObjects:
            if csObj is not None:
                if csObj.ootEmptyType != "Cutscene":
                    raise PluginError(
                        "ERROR: Object selected as cutscene is wrong type, must be empty with Cutscene type"
                    )
                elif csObj.parent is not None:
                    raise PluginError("ERROR: Cutscene empty object should not be parented to anything")

                writeType = self.props.csWriteType
                csWriteCustom = None
                if writeType == "Custom":
                    csWriteCustom = getCustomProperty(self.props, "csWriteCustom")

                if self.props.writeCutscene:
                    # if csWriteCustom is None then the name will auto-set from the csObj passed in the class
                    self.entries.append(
                        Cutscene(csObj, self.useMacros, csWriteCustom, bpy.context.scene.exportMotionOnly)
                    )

    def getCmd(self):
        """Returns the cutscene data scene command"""
        if len(self.entries) == 0:
            raise PluginError("ERROR: Cutscene entry list is empty!")

        # entry No. 0 is always self.csObj
        return indent + f"SCENE_CMD_CUTSCENE_DATA({self.entries[0].name}),\n"
