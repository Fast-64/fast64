from dataclasses import dataclass, field
from typing import Optional
from bpy.types import Object
from ....utility import PluginError, CData, indent
from ...scene.properties import OOTSceneHeaderProperty
from ..base import Base


@dataclass
class SceneCutscene(Base):
    """This class hosts cutscene data (unfinished)"""

    props: OOTSceneHeaderProperty
    headerIndex: int

    writeType: Optional[str] = None
    writeCutscene: Optional[bool] = None
    csObj: Optional[Object] = None
    csWriteCustom: Optional[str] = None
    extraCutscenes: list[Object] = field(default_factory=list)
    name: Optional[str] = None

    def __post_init__(self):
        self.writeType = self.props.csWriteType
        self.writeCutscene = self.props.writeCutscene
        self.csObj = self.props.csWriteObject
        self.csWriteCustom = self.props.csWriteCustom if self.props.csWriteType == "Custom" else None
        self.extraCutscenes = [csObj for csObj in self.props.extraCutscenes]

        if self.writeCutscene and self.writeType == "Embedded":
            raise PluginError("ERROR: 'Embedded' CS Write Type is not supported!")

        if self.headerIndex > 0 and len(self.extraCutscenes) > 0:
            raise PluginError("ERROR: Extra cutscenes can only belong to the main header!")

        if self.csObj is not None:
            self.name = self.csObj.name.removeprefix("Cutscene.")

            if self.csObj.ootEmptyType != "Cutscene":
                raise PluginError("ERROR: Object selected as cutscene is wrong type, must be empty with Cutscene type")
            elif self.csObj.parent is not None:
                raise PluginError("ERROR: Cutscene empty object should not be parented to anything")
        else:
            raise PluginError("ERROR: No object selected for cutscene reference")

    def getCmd(self):
        csDataName = self.csObj.name if self.writeType == "Object" else self.csWriteCustom
        return indent + f"SCENE_CMD_CUTSCENE_DATA({csDataName}),\n"

    def getC(self):
        # will be implemented when PR #208 is merged
        cutsceneData = CData()
        return cutsceneData
