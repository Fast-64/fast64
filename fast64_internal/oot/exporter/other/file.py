import os
import re

from dataclasses import dataclass
from typing import TYPE_CHECKING
from ...oot_utility import getSceneDirFromLevelName
from .scene_table import SceneTable
from .spec import Spec

if TYPE_CHECKING:
    from ..main import SceneExporter


@dataclass
class Files:  # TODO: find a better name
    """This class handles editing decomp files"""

    exporter: "SceneExporter"

    def modifySceneFiles(self):
        if self.exporter.exportInfo.customSubPath is not None:
            sceneDir = self.exporter.exportInfo.customSubPath + self.exporter.exportInfo.name
        else:
            sceneDir = getSceneDirFromLevelName(self.exporter.sceneName)

        scenePath = os.path.join(self.exporter.exportInfo.exportPath, sceneDir)
        for filename in os.listdir(scenePath):
            filepath = os.path.join(scenePath, filename)
            if os.path.isfile(filepath):
                match = re.match(self.exporter.scene.name + "\_room\_(\d+)\.[ch]", filename)
                if match is not None and int(match.group(1)) >= len(self.exporter.scene.rooms.entries):
                    os.remove(filepath)

    def editFiles(self):
        """Edits decomp files"""
        self.modifySceneFiles()
        Spec().editSpec(self.exporter)
        SceneTable().editSceneTable(self.exporter)
