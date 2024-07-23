import os
import re
import shutil

from typing import TYPE_CHECKING
from ...oot_utility import getSceneDirFromLevelName
from .scene_table import SceneTableUtility
from .spec import SpecUtility

if TYPE_CHECKING:
    from ..main import SceneExport, ExportInfo


class Files:  # TODO: find a better name
    """This class handles editing decomp files"""

    @staticmethod
    def remove_old_room_files(exporter: "SceneExport"):
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
    def remove_scene_dir(exportInfo: "ExportInfo"):
        if exportInfo.customSubPath is not None:
            sceneDir = exportInfo.customSubPath + exportInfo.name
        else:
            sceneDir = getSceneDirFromLevelName(exportInfo.name)

        scenePath = os.path.join(exportInfo.exportPath, sceneDir)
        if os.path.exists(scenePath):
            shutil.rmtree(scenePath)

    @staticmethod
    def add_scene_edits(exporter: "SceneExport"):
        """Edits decomp files"""
        exportInfo = exporter.exportInfo

        Files.remove_old_room_files(exporter)
        SpecUtility.add_segments(exporter)
        SceneTableUtility.edit_scene_table(
            exportInfo.exportPath,
            exportInfo.name,
            exporter.scene.mainHeader.infos.drawConfig,
        )

    @staticmethod
    def remove_scene(exportInfo: "ExportInfo"):
        """Removes data from decomp files"""

        Files.remove_scene_dir(exportInfo)
        SpecUtility.remove_segments(exportInfo.exportPath, exportInfo.name, True)
        SceneTableUtility.delete_scene_table_entry(exportInfo.exportPath, exportInfo.name)
