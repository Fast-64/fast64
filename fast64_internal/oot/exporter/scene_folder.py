from os import path, listdir, remove
from re import match as reMatch
from shutil import rmtree
from ..oot_level_classes import OOTScene
from ..oot_utility import ExportInfo, getSceneDirFromLevelName


def getScenePath(exportInfo: ExportInfo, sceneName: str):
    """Returns the scene path"""
    if exportInfo.customSubPath is not None:
        sceneDir = exportInfo.customSubPath + exportInfo.name
    else:
        sceneDir = getSceneDirFromLevelName(sceneName)

    if sceneDir is not None:
        return path.join(exportInfo.exportPath, sceneDir)

    return None


def modifySceneFiles(scene: OOTScene, exportInfo: ExportInfo):
    """Removes extra rooms from the scene folder"""
    scenePath = getScenePath(exportInfo, scene.name)

    if scenePath is not None:
        for filename in listdir(scenePath):
            filepath = path.join(scenePath, filename)
            if path.isfile(filepath):
                match = reMatch(scene.name + "\_room\_(\d+)\.[ch]", filename)
                if match is not None and int(match.group(1)) >= len(scene.rooms):
                    remove(filepath)


def deleteSceneFiles(exportInfo: ExportInfo):
    """Deletes the scene folder"""
    scenePath = getScenePath(exportInfo, exportInfo.name)
    if scenePath is not None and path.exists(scenePath):
        rmtree(scenePath)
