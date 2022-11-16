import os, re, shutil
from ....oot_utility import getSceneDirFromLevelName


def modifySceneFiles(scene, exportInfo):
    exportPath = exportInfo.exportPath
    if exportInfo.customSubPath is not None:
        sceneDir = exportInfo.customSubPath + exportInfo.name
    else:
        sceneDir = getSceneDirFromLevelName(scene.name)
    scenePath = os.path.join(exportPath, sceneDir)
    for filename in os.listdir(scenePath):
        filepath = os.path.join(scenePath, filename)
        if os.path.isfile(filepath):
            match = re.match(scene.name + "\_room\_(\d+)\.[ch]", filename)
            if match is not None and int(match.group(1)) >= len(scene.rooms):
                os.remove(filepath)


def deleteSceneFiles(exportInfo):
    exportPath = exportInfo.exportPath
    if exportInfo.customSubPath is not None:
        sceneDir = exportInfo.customSubPath + exportInfo.name
    else:
        sceneDir = getSceneDirFromLevelName(exportInfo.name)
    scenePath = os.path.join(exportPath, sceneDir)
    if os.path.exists(scenePath):
        shutil.rmtree(scenePath)
