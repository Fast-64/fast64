from dataclasses import dataclass, field
from typing import Optional
from mathutils import Matrix
from bpy.types import Object
from ....utility import CData
from ...scene.properties import OOTSceneHeaderProperty
from ..base import Base
from .general import SceneLighting, SceneInfos, SceneExits
from .cutscene import SceneCutscene
from .actors import SceneTransitionActors, SceneEntranceActors, SceneSpawns
from .pathways import ScenePathways


@dataclass
class SceneHeader(Base):
    """This class defines a scene header"""

    props: OOTSceneHeaderProperty
    name: str
    sceneObj: Object
    transform: Matrix
    headerIndex: int
    useMacros: bool

    infos: Optional[SceneInfos] = None
    lighting: Optional[SceneLighting] = None
    cutscene: Optional[SceneCutscene] = None
    exits: Optional[SceneExits] = None
    transitionActors: Optional[SceneTransitionActors] = None
    entranceActors: Optional[SceneEntranceActors] = None
    spawns: Optional[SceneSpawns] = None
    path: Optional[ScenePathways] = None

    def __post_init__(self):
        self.infos = SceneInfos(self.props, self.sceneObj)
        self.lighting = SceneLighting(self.props, f"{self.name}_lightSettings")
        self.cutscene = SceneCutscene(self.props, self.headerIndex, self.useMacros)
        self.exits = SceneExits(self.props, f"{self.name}_exitList")

        self.transitionActors = SceneTransitionActors(
            None, f"{self.name}_transitionActors", self.sceneObj, self.transform, self.headerIndex
        )

        self.entranceActors = SceneEntranceActors(
            None, f"{self.name}_playerEntryList", self.sceneObj, self.transform, self.headerIndex
        )

        self.spawns = SceneSpawns(None, f"{self.name}_entranceList", self.entranceActors.entries)
        self.path = ScenePathways(self.props, f"{self.name}_pathway", self.sceneObj, self.transform, self.headerIndex)

    def getC(self):
        """Returns the ``CData`` containing the header's data"""

        headerData = CData()

        # Write the spawn position list data and the entrance list
        if len(self.entranceActors.entries) > 0:
            headerData.append(self.entranceActors.getC())
            headerData.append(self.spawns.getC())

        # Write the transition actor list data
        if len(self.transitionActors.entries) > 0:
            headerData.append(self.transitionActors.getC())

        # Write the exit list
        if len(self.exits.exitList) > 0:
            headerData.append(self.exits.getC())

        # Write the light data
        if len(self.lighting.settings) > 0:
            headerData.append(self.lighting.getC())

        # Write the path data, if used
        if len(self.path.pathList) > 0:
            headerData.append(self.path.getC())

        return headerData


@dataclass
class SceneAlternateHeader:
    """This class stores alternate header data for the scene"""

    name: str
    childNight: Optional[SceneHeader] = None
    adultDay: Optional[SceneHeader] = None
    adultNight: Optional[SceneHeader] = None
    cutscenes: list[SceneHeader] = field(default_factory=list)
