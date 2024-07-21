import os
import re

from typing import TYPE_CHECKING
from ...oot_utility import getSceneDirFromLevelName
from .scene_table import SceneTableUtility
from .spec import SpecUtility

if TYPE_CHECKING:
    from ..main import SceneExport


class Files:  # TODO: find a better name
    """This class handles editing decomp files"""

    @staticmethod
    def modifySceneFiles(exporter: "SceneExport"):
        if exporter.exportInfo.customSubPath is not None:
            sceneDir = exporter.exportInfo.customSubPath + exporter.exportInfo.name
        else:
            sceneDir = getSceneDirFromLevelName(exporter.sceneName)

        scenePath = os.path.join(exporter.exportInfo.exportPath, sceneDir)
        for filename in os.listdir(scenePath):
            filepath = os.path.join(scenePath, filename)
            if os.path.isfile(filepath):
                match = re.match(exporter.scene.name + "\_room\_(\d+)\.[ch]", filename)
                if match is not None and int(match.group(1)) >= len(exporter.scene.rooms.entries):
                    os.remove(filepath)

    @staticmethod
    def editFiles(exporter: "SceneExport"):
        """Edits decomp files"""

        Files.modifySceneFiles(exporter)
        SpecUtility.editSpec(exporter)
        SceneTableUtility.editSceneTable(exporter, exporter.exportInfo)
