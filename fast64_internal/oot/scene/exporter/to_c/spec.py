import os, re, bpy
from .....utility import readFile, writeFile, indent
from ....oot_utility import ExportInfo, getSceneDirFromLevelName
from ....oot_level_classes import OOTScene
from .scene import OOTSceneC


def getSceneSpecEntries(segmentDefinition: list[str], sceneName: str):
    """Returns the existing spec entries for the selected scene"""
    entries = []
    matchText = rf'\s*name\s*"{sceneName}\_'

    for entry in segmentDefinition:
        if re.match(matchText + 'scene"', entry) or re.match(matchText + 'room\_\d+"', entry):
            entries.append(entry)

    return entries


def getSpecEntries(fileData: str):
    """Returns the existing spec entries for the whole file"""
    entries = []
    compressFlag = ""

    for match in re.finditer("beginseg(((?!endseg).)*)endseg", fileData, re.DOTALL):
        segData = match.group(1)
        entries.append(segData)

        # avoid deleting compress flag if the user is using it
        # (defined by whether it is present at least once in spec or not)
        if "compress" in segData:
            compressFlag = indent + "compress\n"

    includes = []
    for match in re.finditer("(#include.*)", fileData):
        includes.append(match.group(0))

    return entries, compressFlag, includes


def editSpecFile(scene: OOTScene, exportInfo: ExportInfo, sceneC: OOTSceneC):
    """Adds or removes entries for the selected scene"""
    exportPath = exportInfo.exportPath
    sceneName = scene.name if scene is not None else exportInfo.name
    fileData = readFile(os.path.join(exportPath, "spec"))

    specEntries, compressFlag, includes = getSpecEntries(fileData)
    sceneSpecEntries = getSceneSpecEntries(specEntries, sceneName)

    if exportInfo.customSubPath is not None:
        includeDir = f"build/{exportInfo.customSubPath + sceneName}/{sceneName}"
    else:
        includeDir = f"build/{getSceneDirFromLevelName(sceneName)}/{sceneName}"

    if len(sceneSpecEntries) > 0:
        firstIndex = specEntries.index(sceneSpecEntries[0])

        # remove the entries of the selected scene
        for entry in sceneSpecEntries:
            specEntries.remove(entry)
    else:
        firstIndex = len(specEntries)

    # Add the spec data for the exported scene
    if scene is not None:
        if bpy.context.scene.ootSceneExportSettings.singleFile:
            specEntries.insert(
                firstIndex,
                ("\n" + indent + f'name "{scene.name}_scene"\n')
                + compressFlag
                + (indent + "romalign 0x1000\n")
                + (indent + f'include "{includeDir}_scene.o"\n')
                + (indent + "number 2\n"),
            )

            firstIndex += 1

            for i in range(len(scene.rooms)):
                specEntries.insert(
                    firstIndex,
                    ("\n" + indent + f'name "{scene.name}_room_{i}"\n')
                    + compressFlag
                    + (indent + "romalign 0x1000\n")
                    + (indent + f'include "{includeDir}_room_{i}.o"\n')
                    + (indent + "number 3\n"),
                )

                firstIndex += 1
        else:
            sceneSegInclude = (
                ("\n" + indent + f'name "{scene.name}_scene"\n')
                + compressFlag
                + (indent + "romalign 0x1000\n")
                + (indent + f'include "{includeDir}_scene_main.o"\n')
                + (indent + f'include "{includeDir}_scene_col.o"\n')
            )

            if sceneC is not None:
                if sceneC.sceneTexturesIsUsed():
                    sceneSegInclude += indent + f'include "{includeDir}_scene_tex.o"\n'

                if sceneC.sceneCutscenesIsUsed():
                    for i in range(len(sceneC.sceneCutscenesC)):
                        sceneSegInclude += indent + f'include "{includeDir}_cs_{i}.o"\n'

            sceneSegInclude += indent + "number 2\n"
            specEntries.insert(firstIndex, sceneSegInclude)
            firstIndex += 1

            for i in range(len(scene.rooms)):
                specEntries.insert(
                    firstIndex,
                    ("\n" + indent + f'name "{scene.name}_room_{i}"\n')
                    + compressFlag
                    + (indent + "romalign 0x1000\n")
                    + (indent + f'include "{includeDir}_room_{i}_main.o"\n')
                    + (indent + f'include "{includeDir}_room_{i}_model_info.o"\n')
                    + (indent + f'include "{includeDir}_room_{i}_model.o"\n')
                    + (indent + "number 3\n"),
                )

                firstIndex += 1

    # Write the file data
    newFileData = (
        "/*\n * ROM spec file\n */\n\n"
        + ("\n".join(includes) + "\n\n" if len(includes) > 0 else "")
        + "\n".join("beginseg" + entry + "endseg\n" for entry in specEntries)
    )

    if newFileData != fileData:
        writeFile(os.path.join(exportPath, "spec"), newFileData)
