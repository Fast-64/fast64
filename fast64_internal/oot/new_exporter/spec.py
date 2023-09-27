import os
import re

from typing import TYPE_CHECKING
from ...utility import readFile, writeFile, indent
from ..oot_utility import ExportInfo, getSceneDirFromLevelName

if TYPE_CHECKING:
    from .exporter import OOTSceneExport


class Spec:
    """This class hosts different functions to edit the spec file"""

    def getSceneSpecEntries(self, segmentDefinition: list[str], sceneName: str):
        """Returns the existing spec entries for the selected scene"""

        entries = []
        matchText = rf'\s*name\s*"{sceneName}\_'

        for entry in segmentDefinition:
            if re.match(matchText + 'scene"', entry) or re.match(matchText + 'room\_\d+"', entry):
                entries.append(entry)

        return entries

    def getSpecEntries(self, fileData: str):
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

    def editSpec(self, exporter: "OOTSceneExport", exportInfo: ExportInfo = None):
        """Adds or removes entries for the selected scene in the spec file"""

        isExport = exporter is not None
        if exportInfo is None:
            exportInfo = exporter.exportInfo

        exportPath = exportInfo.exportPath
        sceneName = exporter.sceneName if isExport else exportInfo.name
        fileData = readFile(os.path.join(exportPath, "spec"))

        specEntries, compressFlag, includes = self.getSpecEntries(fileData)
        sceneSpecEntries = self.getSceneSpecEntries(specEntries, sceneName)

        if len(sceneSpecEntries) > 0:
            firstIndex = specEntries.index(sceneSpecEntries[0])

            # remove the entries of the selected scene
            for entry in sceneSpecEntries:
                specEntries.remove(entry)
        else:
            firstIndex = len(specEntries)

        # Add the spec data for the exported scene
        if isExport:
            if exportInfo.customSubPath is not None:
                includeDir = f"build/{exportInfo.customSubPath + sceneName}"
            else:
                includeDir = f"build/{getSceneDirFromLevelName(sceneName)}"

            sceneName = exporter.scene.name
            if exporter.singleFileExport:
                specEntries.insert(
                    firstIndex,
                    ("\n" + indent + f'name "{sceneName}"\n')
                    + compressFlag
                    + (indent + "romalign 0x1000\n")
                    + (indent + f'include "{includeDir}/{sceneName}.o"\n')
                    + (indent + "number 2\n"),
                )

                firstIndex += 1

                for room in exporter.roomList.values():
                    specEntries.insert(
                        firstIndex,
                        ("\n" + indent + f'name "{room.name}"\n')
                        + compressFlag
                        + (indent + "romalign 0x1000\n")
                        + (indent + f'include "{includeDir}/{room.name}.o"\n')
                        + (indent + "number 3\n"),
                    )

                    firstIndex += 1
            else:
                sceneSegInclude = (
                    ("\n" + indent + f'name "{sceneName}"\n')
                    + compressFlag
                    + (indent + "romalign 0x1000\n")
                    + (indent + f'include "{includeDir}/{sceneName}_main.o"\n')
                    + (indent + f'include "{includeDir}/{sceneName}_col.o"\n')
                )

                if exporter.hasSceneTextures:
                    sceneSegInclude += indent + f'include "{includeDir}/{sceneName}_tex.o"\n'

                if exporter.hasCutscenes:
                    for i in range(len(exporter.sceneData.sceneCutscenes)):
                        sceneSegInclude += indent + f'include "{includeDir}/{sceneName}_cs_{i}.o"\n'

                sceneSegInclude += indent + "number 2\n"
                specEntries.insert(firstIndex, sceneSegInclude)
                firstIndex += 1

                for room in exporter.roomList.values():
                    specEntries.insert(
                        firstIndex,
                        ("\n" + indent + f'name "{room.name}"\n')
                        + compressFlag
                        + (indent + "romalign 0x1000\n")
                        + (indent + f'include "{includeDir}/{room.name}_main.o"\n')
                        + (indent + f'include "{includeDir}/{room.name}_model_info.o"\n')
                        + (indent + f'include "{includeDir}/{room.name}_model.o"\n')
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
