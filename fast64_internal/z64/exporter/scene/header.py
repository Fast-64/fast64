from dataclasses import dataclass, field
from typing import Optional
from mathutils import Matrix
from bpy.types import Object

from ....utility import CData
from ...utility import is_oot_features
from ...scene.properties import OOTSceneHeaderProperty
from ..cutscene import SceneCutscene
from .general import SceneLighting, SceneInfos, SceneExits
from .actors import SceneTransitionActors, SceneEntranceActors, SceneSpawns
from .pathways import ScenePathways
from .animated_mats import SceneAnimatedMaterial


@dataclass
class SceneHeader:
    """This class defines a scene header"""

    name: str
    infos: Optional[SceneInfos]
    lighting: Optional[SceneLighting]
    cutscene: Optional[SceneCutscene]
    exits: Optional[SceneExits]
    transitionActors: Optional[SceneTransitionActors]
    entranceActors: Optional[SceneEntranceActors]
    spawns: Optional[SceneSpawns]
    path: Optional[ScenePathways]

    # MM (or HackerOoT)
    anim_mat: Optional[SceneAnimatedMaterial]

    @staticmethod
    def new(
        name: str, props: OOTSceneHeaderProperty, sceneObj: Object, transform: Matrix, headerIndex: int, useMacros: bool
    ):
        entranceActors = SceneEntranceActors.new(f"{name}_playerEntryList", sceneObj, transform, headerIndex)
        return SceneHeader(
            name,
            SceneInfos.new(props, sceneObj),
            SceneLighting.new(f"{name}_lightSettings", props),
            SceneCutscene.new(props, headerIndex, useMacros),
            SceneExits.new(f"{name}_exitList", props),
            SceneTransitionActors.new(f"{name}_transitionActors", sceneObj, transform, headerIndex),
            entranceActors,
            SceneSpawns(f"{name}_entranceList", entranceActors.entries),
            ScenePathways.new(f"{name}_pathway", sceneObj, transform, headerIndex),
            SceneAnimatedMaterial.new(f"{name}_AnimatedMaterial", sceneObj, headerIndex)
            if not is_oot_features()
            else None,
        )

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

        # Write the animated material list, if used
        if self.anim_mat is not None and self.anim_mat.is_used():
            headerData.append(self.anim_mat.to_c())

        return headerData


@dataclass
class SceneAlternateHeader:
    """This class stores alternate header data for the scene"""

    name: str

    childNight: Optional[SceneHeader] = field(init=False, default=None)
    adultDay: Optional[SceneHeader] = field(init=False, default=None)
    adultNight: Optional[SceneHeader] = field(init=False, default=None)
    cutscenes: list[SceneHeader] = field(init=False, default_factory=list)
