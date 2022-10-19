import os, re, bpy
from ...utility import readFile, writeFile
from .data import indent
from .classes import OOTSceneC
from ..oot_level_classes import OOTScene
from ..oot_utility import ExportInfo, getSceneDirFromLevelName


def getSegmentDefinitionEntryBySceneName(segmentDefinition: list[str], sceneName: str):
    entries = []

    for entry in segmentDefinition:
        matchText = '\s*name\s*"' + sceneName + "\_"
        if re.match(matchText + 'scene"', entry) or re.match(matchText + 'room\_\d+"', entry):
            entries.append(entry)

    return entries


def parseSegmentDefinitionData(fileData: str):
    segmentData: list[str] = []
    compressFlag = ""
    for match in re.finditer("beginseg(((?!endseg).)*)endseg", fileData, re.DOTALL):
        segData = f"{match.group(1)}"
        segmentData.append(segData)

        # avoid deleting compress flag if the user is using it
        # (defined by whether it is present at least once in spec or not)
        if "compress" in segData:
            compressFlag = indent + "compress\n"

    return segmentData, compressFlag


def writeSegmentDefinition(segmentDefinition: list[str], fileData: str, exportPath: str):
    newFileData = "/*\n * ROM spec file\n */\n\n" + "\n\n".join(
        ["beginseg" + entry + "endseg" for entry in segmentDefinition]
    )

    if newFileData != fileData:
        writeFile(os.path.join(exportPath, "spec"), newFileData)


def modifySegmentDefinition(scene: OOTScene, exportInfo: ExportInfo, sceneC: OOTSceneC):
    exportPath = exportInfo.exportPath

    # read spec file data
    fileData = readFile(os.path.join(exportPath, "spec"))
    segmentDefinitions, compressFlag = parseSegmentDefinitionData(fileData)

    sceneName = scene.name if scene is not None else exportInfo.name
    entries = getSegmentDefinitionEntryBySceneName(segmentDefinitions, sceneName)

    if exportInfo.customSubPath is not None:
        scenePath = exportInfo.customSubPath + sceneName
    else:
        scenePath = getSceneDirFromLevelName(sceneName)
    includeDir = f"build/{scenePath}/{sceneName}"

    if len(entries) > 0:
        firstIndex = segmentDefinitions.index(entries[0])
        for entry in entries:
            segmentDefinitions.remove(entry)
    else:
        firstIndex = len(segmentDefinitions)

    if scene is not None:
        if bpy.context.scene.ootSceneSingleFile:
            segmentDefinitions.insert(
                firstIndex,
                "\n"
                + (indent + f'name "{scene.sceneName()}"\n')
                + compressFlag
                + (indent + "romalign 0x1000\n")
                + (indent + f'include "{includeDir}_scene.o"\n')
                + (indent + "number 2\n"),
            )
            firstIndex += 1

            for i in range(len(scene.rooms)):
                roomSuffix = f"_room_{i}"
                segmentDefinitions.insert(
                    firstIndex,
                    "\n"
                    + (indent + f'name "{scene.name + roomSuffix}"\n')
                    + compressFlag
                    + (indent + "romalign 0x1000\n")
                    + (indent + f'include "{includeDir + roomSuffix}".o\n')
                    + (indent + "number 3\n"),
                )
                firstIndex += 1
        else:
            sceneSegInclude = (
                "\n"
                + (indent + f'name "{scene.sceneName()}"\n')
                + compressFlag
                + (indent + "romalign 0x1000\n")
                + (indent + f'include "{includeDir}_scene_main.o"\n')
                + (indent + f'include "{includeDir}_scene_col.o"\n')
            )

            if sceneC is not None:
                if sceneC.sceneTexturesIsUsed():
                    sceneSegInclude += indent + f'include "{includeDir}_scene_tex.o"\n'

                if sceneC.sceneCutscenesIsUsed():
                    sceneSegInclude += "".join(
                        [
                            indent + f'include "{includeDir}_scene_cs_{i}.o"\n'
                            for i in range(len(sceneC.sceneCutscenesC))
                        ]
                    )

            sceneSegInclude += indent + "number 2\n"
            segmentDefinitions.insert(firstIndex, sceneSegInclude)
            firstIndex += 1

            for i in range(len(scene.rooms)):
                roomSuffix = "_room_" + str(i)
                roomDir = includeDir + roomSuffix
                segmentDefinitions.insert(
                    firstIndex,
                    "\n"
                    + (indent + f'name "{scene.name + roomSuffix}"\n')
                    + compressFlag
                    + (indent + "romalign 0x1000\n")
                    + (indent + f'include "{roomDir}_main.o"\n')
                    + (indent + f'include "{roomDir}_model_info.o"\n')
                    + (indent + f'include "{roomDir}_model.o"\n')
                    + (indent + "number 3\n"),
                )
                firstIndex += 1

    writeSegmentDefinition(segmentDefinitions, fileData, exportPath)
