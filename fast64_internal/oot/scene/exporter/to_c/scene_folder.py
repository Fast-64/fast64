import os, re, shutil
from ....oot_utility import ExportInfo, getSceneDirFromLevelName
from ....oot_level_classes import OOTScene


def modifySceneFiles(outScene: OOTScene, exportInfo: ExportInfo):
    if exportInfo.customSubPath is not None:
        sceneDir = exportInfo.customSubPath + exportInfo.name
    else:
        sceneDir = getSceneDirFromLevelName(outScene.name)

    scenePath = os.path.join(exportInfo.exportPath, sceneDir)
    for filename in os.listdir(scenePath):
        filepath = os.path.join(scenePath, filename)
        if os.path.isfile(filepath):
            match = re.match(outScene.name + "\_room\_(\d+)\.[ch]", filename)
            if match is not None and int(match.group(1)) >= len(outScene.rooms):
                os.remove(filepath)


def deleteSceneFiles(exportInfo: ExportInfo):
    if exportInfo.customSubPath is not None:
        sceneDir = exportInfo.customSubPath + exportInfo.name
    else:
        sceneDir = getSceneDirFromLevelName(exportInfo.name)

    scenePath = os.path.join(exportInfo.exportPath, sceneDir)
    if os.path.exists(scenePath):
        shutil.rmtree(scenePath)
