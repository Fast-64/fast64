import os, re
from ...utility import *


class SceneTableEntry:
    def __init__(self, sceneType, name, title, unk10, config, unk12):
        self.sceneType = sceneType
        self.name = name
        self.title = title
        self.unk10 = unk10
        self.config = config
        self.unk12 = unk12

    def toC(self):
        return (
            "\t"
            + self.sceneType
            + "("
            + self.name
            + ", "
            + ((self.title + ", ") if self.title is not None else "")
            + self.unk10
            + ", "
            + self.config
            + ", "
            + self.unk12
            + "),\n"
        )


def getSceneTableEntryBySceneName(sceneTable, sceneName):
    for entry in sceneTable:
        if entry.name[:-6] == sceneName:
            return entry
    return None


def readSceneTable(exportPath):
    fileData = readFile(os.path.join(exportPath, "src/code/z_scene_table.c"))

    matchResult = re.search(
        "SceneTableEntry\s*gSceneTable\[\]\s*=\s*\{([^\}]*)\}", fileData, re.DOTALL
    )
    if matchResult is None:
        raise PluginError("z_scene_table.c does not have gSceneTable in it.")
    sceneTable = parseSceneTableData(matchResult.group(1))

    return sceneTable, fileData, matchResult.start(0), matchResult.end(0)


def parseSceneTableData(data):
    table = []
    for match in re.finditer(
        "([^,]*)\s*\(([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*)(,\s*([^,]*))?\)\s*,", data
    ):
        name = match.group(2)
        sceneType = match.group(1).strip()
        if sceneType == "UNTITLED_SCENE":
            table.append(
                SceneTableEntry(
                    sceneType,
                    name,
                    None,
                    match.group(3),
                    match.group(4),
                    match.group(5),
                )
            )
        elif sceneType == "TITLED_SCENE":
            table.append(
                SceneTableEntry(
                    sceneType,
                    name,
                    match.group(3),
                    match.group(4),
                    match.group(5),
                    match.group(7),
                )
            )
        else:
            raise PluginError("Unhandled scene entry type: " + str(sceneType))
    return table


def sceneTableToString(sceneTable):
    data = "SceneTableEntry gSceneTable[] = {\n"
    for entry in sceneTable:
        data += entry.toC()
    data += "}"
    return data


def writeSceneTable(sceneTable, fileData, start, end, exportPath):
    sceneTableData = sceneTableToString(sceneTable)
    newFileData = fileData[:start] + sceneTableData + fileData[end:]

    if newFileData != fileData:
        writeFile(os.path.join(exportPath, "src/code/z_scene_table.c"), newFileData)


def modifySceneTable(scene, exportInfo):
    exportPath = exportInfo.exportPath
    sceneTable, sceneFileData, start, end = readSceneTable(exportPath)
    entry = getSceneTableEntryBySceneName(
        sceneTable, scene.name if scene is not None else exportInfo.name
    )

    if scene is not None:
        if entry is None:
            sceneTable.append(
                SceneTableEntry(
                    "UNTITLED_SCENE",
                    scene.name + "_scene",
                    None,
                    "0",
                    str(scene.sceneTableEntry.drawConfig),
                    "0",
                )
            )
        else:
            entry.sceneType = entry.sceneType
            entry.config = str(scene.sceneTableEntry.drawConfig)
    else:
        if entry is not None:
            sceneTable.remove(entry)
    writeSceneTable(sceneTable, sceneFileData, start, end, exportPath)
