import os
import re
import shutil

from typing import TYPE_CHECKING
from ...oot_utility import getSceneDirFromLevelName
from .scene_table import SceneTableUtility
from .spec import SpecUtility

if TYPE_CHECKING:
    from ...exporter import SceneExport, ExportInfo, RemoveInfo, Scene, SceneFile


class Files:  # TODO: find a better name
    """This class handles editing decomp files"""

    @staticmethod
    def remove_old_room_files(exportInfo: "ExportInfo", scene: "Scene"):
        if exportInfo.customSubPath is not None:
            sceneDir = exportInfo.customSubPath + exportInfo.name
        else:
            sceneDir = getSceneDirFromLevelName(exportInfo.name)

        scenePath = os.path.join(exportInfo.exportPath, sceneDir)
        for filename in os.listdir(scenePath):
            filepath = os.path.join(scenePath, filename)
            if os.path.isfile(filepath):
                match = re.match(scene.name + "\_room\_(\d+)\.[ch]", filename)
                if match is not None and int(match.group(1)) >= len(scene.rooms.entries):
                    os.remove(filepath)

    @staticmethod
    def remove_scene_dir(remove_info: "RemoveInfo"):
        if remove_info.customSubPath is not None:
            sceneDir = remove_info.customSubPath + remove_info.name
        else:
            sceneDir = getSceneDirFromLevelName(remove_info.name)

        scenePath = os.path.join(remove_info.exportPath, sceneDir)
        if os.path.exists(scenePath):
            shutil.rmtree(scenePath)

    @staticmethod
    def add_scene_edits(exportInfo: "ExportInfo", scene: "Scene", sceneFile: "SceneFile"):
        """Edits decomp files"""

        Files.remove_old_room_files(exportInfo, scene)
        SpecUtility.add_segments(exportInfo, scene, sceneFile)
        SceneTableUtility.edit_scene_table(
            exportInfo.exportPath,
            exportInfo.name,
            scene.mainHeader.infos.drawConfig,
        )

    @staticmethod
    def remove_scene(remove_info: "RemoveInfo"):
        """Removes data from decomp files"""

        Files.remove_scene_dir(remove_info)
        SpecUtility.remove_segments(remove_info.exportPath, remove_info.name)
        SceneTableUtility.delete_scene_table_entry(remove_info.exportPath, remove_info.name)
