import os
import bpy

from typing import TYPE_CHECKING
from ....utility import PluginError, writeFile
from ...oot_constants import ootEnumSceneID, ootSceneNameToID
from ...oot_utility import ExportInfo

if TYPE_CHECKING:
    from ..main import SceneExporter


class SceneTable:
    """This class hosts different function to edit the scene table"""

    def getSceneNameSettings(self, isExport: bool):
        """Returns the scene name"""

        if isExport:
            return bpy.context.scene.ootSceneExportSettings.option
        else:
            return bpy.context.scene.ootSceneRemoveSettings.option

    def isHackerOoT(self, line: str):
        """Returns ``True`` if HackerOoT-related data has been found on the current line"""

        return (
            line != "\n"
            and '#include "config.h"\n' not in line
            and "#ifdef INCLUDE_TEST_SCENES" not in line
            and "#endif" not in line
            and not line.startswith("// ")
        )

    def getSceneTable(self, exportPath: str):
        """Read and remove unwanted stuff from ``scene_table.h``"""

        dataList = []
        sceneNames = []
        fileHeader = ""

        # read the scene table
        try:
            with open(os.path.join(exportPath, "include/tables/scene_table.h")) as fileData:
                # keep the relevant data and do some formatting
                for i, line in enumerate(fileData):
                    # remove empty lines from the file
                    if not line.strip():
                        continue

                    if not bpy.context.scene.fast64.oot.hackerFeaturesEnabled or self.isHackerOoT(line):
                        if not (
                            # Detects the multiline comment at the top of the file:
                            (line.startswith("/**") or line.startswith(" *"))
                            # Detects single line comments:
                            # (meant to detect the built-in single-line comments
                            #  "// Debug-only scenes" and "// Added scenes")
                            or line.startswith("//")
                        ):
                            dataList.append(line[(line.find("(") + 1) :].rstrip(")\n").replace(" ", "").split(","))
                        else:
                            # Only keep comments before the data (as indicated by dataList being empty).
                            # This prevents duplicating the built-in single-line comments to the header.
                            # It also means other handwritten single-line comments are removed from the file.
                            if not dataList:
                                fileHeader += line
                    if line.startswith("/* 0x"):
                        startIndex = line.find("SCENE_")
                        sceneNames.append(line[startIndex : line.find(",", startIndex)])
        except FileNotFoundError:
            raise PluginError("ERROR: Can't find scene_table.h!")

        # return the parsed data, the header comment and the comment mentionning debug scenes
        return dataList, fileHeader, sceneNames

    def getSceneIndex(self, sceneNameList: list[str], sceneName: str):
        """Returns the index (int) of the chosen scene, returns None if ``Custom`` is chosen"""

        if sceneName == "Custom":
            return None

        if sceneNameList is not None:
            for i in range(len(sceneNameList)):
                if sceneNameList[i] == sceneName:
                    return i

        # intended return value to check if the chosen scene was removed
        return None

    def getOriginalIndex(self, sceneName):
        """
        Returns the index of a specific scene defined by which one the user chose
            or by the ``sceneName`` parameter if it's not set to ``None``
        """

        i = 0

        if sceneName != "Custom":
            for elem in ootEnumSceneID:
                if elem[0] == sceneName:
                    # returns i - 1 because the first entry is the ``Custom`` option
                    return i - 1
                i += 1

        raise PluginError("ERROR: Scene Index not found!")

    def getInsertionIndex(self, isExport: bool, sceneNames: list[str], sceneName: str, index: int, mode: str):
        """Returns the index to know where to insert data"""

        # special case where the scene is "Inside the Great Deku Tree"
        # since it's the first scene simply return 0
        if sceneName == "SCENE_DEKU_TREE":
            return 0

        # if index is None this means this is looking for ``original_scene_index - 1``
        # else, this means the table is shifted
        if index is None:
            currentIndex = self.getOriginalIndex(sceneName)
        else:
            currentIndex = index

        for i in range(len(sceneNames)):
            if sceneNames[i] == ootEnumSceneID[currentIndex][0]:
                # return an index to insert new data
                if mode == "INSERT":
                    return i + 1
                # return an index to insert a comment
                elif mode == "EXPORT":
                    return (
                        i if not sceneName in sceneNames and sceneName != self.getSceneNameSettings(isExport) else i + 1
                    )
                # same but don't check for chosen scene
                elif mode == "REMOVE":
                    return i if not sceneName in sceneNames else i + 1
                else:
                    raise NotImplementedError

        # if the index hasn't been found yet, do it again but decrement the index
        return self.getInsertionIndex(isExport, sceneNames, sceneName, currentIndex - 1, mode)

    def getSceneParams(self, exporter: "SceneExporter", exportInfo: ExportInfo, sceneNames: list[str]):
        """Returns the parameters that needs to be set in ``DEFINE_SCENE()``"""

        # in order to replace the values of ``unk10``, ``unk12`` and basically every parameters from ``DEFINE_SCENE``,
        # you just have to make it return something other than None, not necessarily a string
        sceneIndex = self.getSceneIndex(sceneNames, self.getSceneNameSettings(exporter is not None))
        sceneName = sceneTitle = sceneID = sceneUnk10 = sceneUnk12 = None
        name = exporter.sceneName if exporter is not None else exportInfo.name

        # if the index is None then this is a custom scene
        if sceneIndex is None and exporter is not None:
            sceneName = name.lower() + "_scene"
            sceneTitle = "none"
            sceneID = ootSceneNameToID.get(name, f"SCENE_{name.upper()}")
            sceneUnk10 = sceneUnk12 = 0

        return sceneName, sceneTitle, sceneID, sceneUnk10, sceneUnk12, sceneIndex

    def sceneTableToC(self, data, header: str, sceneNames: list[str], isExport: bool):
        """Converts the Scene Table to C code"""

        # start the data with the header comment explaining the format of the file
        fileData = header

        # determine if this function is called by 'Remove Scene' or 'Export Scene'
        mode = "EXPORT" if isExport else "REMOVE"

        # get the index of the last non-debug scene
        lastNonDebugSceneIdx = self.getInsertionIndex(isExport, sceneNames, "SCENE_OUTSIDE_GANONS_CASTLE", None, mode)
        lastSceneIdx = self.getInsertionIndex(isExport, sceneNames, "SCENE_TESTROOM", None, mode)

        # add the actual lines with the same formatting
        for i in range(len(data)):
            # adds the "// Debug-only scenes"
            # if both lastScene indexes are the same values this means there's no debug scene
            if ((i - 1) == lastNonDebugSceneIdx) and (lastSceneIdx != lastNonDebugSceneIdx):
                fileData += "// Debug-only scenes\n"

            # add a comment to show when it's new scenes
            if (i - 1) == lastSceneIdx:
                fileData += "// Added scenes\n"

            fileData += f"/* 0x{i:02X} */ DEFINE_SCENE("
            fileData += ", ".join(str(d) for d in data[i])

            fileData += ")\n"

        # return the string containing the file data to write
        return fileData

    def getDrawConfig(self, sceneName: str):
        """Read draw config from scene table"""

        fileData, _, _ = self.getSceneTable(bpy.path.abspath(bpy.context.scene.ootDecompPath))

        for sceneEntry in fileData:
            if sceneEntry[0] == f"{sceneName}_scene":
                return sceneEntry[3]

        raise PluginError(f"Scene name {sceneName} not found in scene table.")

    def addHackerOoTData(self, fileData: str):
        """Reads the file and adds HackerOoT's modifications to the scene table file"""

        newFileData = ['#include "config.h"\n\n']

        for line in fileData.splitlines():
            if "// Debug-only scenes" in line:
                newFileData.append("\n#ifdef INCLUDE_TEST_SCENES\n")

            if "// Added scenes" in line:
                newFileData.append("#endif\n\n")

            newFileData.append(f"{line}\n")

        if "// Added scenes" not in fileData:
            newFileData.append("#endif\n")

        return "".join(newFileData)

    def editSceneTable(self, exporter: "SceneExporter", exportInfo: ExportInfo = None):
        """Edit the scene table with the new data"""

        isExport = exporter is not None
        if exportInfo is None:
            exportInfo = exporter.exportInfo

        exportPath = exportInfo.exportPath
        # the list ``sceneNames`` needs to be synced with ``fileData``
        fileData, header, sceneNames = self.getSceneTable(exportPath)
        sceneName, sceneTitle, sceneID, sceneUnk10, sceneUnk12, sceneIndex = self.getSceneParams(
            exporter, exportInfo, sceneNames
        )

        if isExport:
            sceneDrawConfig = exporter.scene.mainHeader.infos.drawConfig
        else:
            sceneDrawConfig = None

        # ``DEFINE_SCENE()`` parameters
        sceneParams = [sceneName, sceneTitle, sceneID, sceneDrawConfig, sceneUnk10, sceneUnk12]

        # check if it's a custom scene name
        # sceneIndex can be None and ootSceneOption not "Custom",
        # that means the selected scene has been removed from the table
        # however if the scene variable is not None
        # set it to "INSERT" because we need to insert the scene in the right place
        if sceneIndex is None and self.getSceneNameSettings(isExport) == "Custom":
            mode = "CUSTOM"
        elif sceneIndex is None and isExport:
            mode = "INSERT"
        elif sceneIndex is not None:
            mode = "NORMAL"
        else:
            mode = None

        if mode is not None:
            # if so, check if the custom scene already exists in the data
            # if it already exists set mode to NORMAL to consider it like a normal scene
            if mode == "CUSTOM":
                exportName = exportInfo.name.lower()
                for i in range(len(fileData)):
                    if fileData[i][0] == exportName + "_scene":
                        sceneIndex = i
                        mode = "NORMAL"
                        break
            else:
                exportName = exportInfo.name

            # edit the current data or append new one if we are in a ``Custom`` context
            if mode == "NORMAL":
                for i in range(6):
                    if sceneParams[i] is not None and fileData[sceneIndex][i] != sceneParams[i]:
                        fileData[sceneIndex][i] = sceneParams[i]
            elif mode == "CUSTOM":
                sceneNames.append(sceneParams[2])
                fileData.append(sceneParams)
                sceneIndex = len(fileData) - 1
            elif mode == "INSERT":
                # if this the user chose a vanilla scene, removed it and want to export
                # insert the data in the normal location
                # shifted index = vanilla index - (vanilla last scene index - new last scene index)
                index = self.getInsertionIndex(isExport, sceneNames, sceneID, None, mode)
                sceneNames.insert(index, sceneParams[2])
                fileData.insert(index, sceneParams)

        # remove the scene data if scene is None (`Remove Scene` button)
        if not isExport:
            if sceneIndex is not None:
                sceneNames.pop(sceneIndex)
                fileData.pop(sceneIndex)
            else:
                raise PluginError("ERROR: Scene not found in ``scene_table.h``!")

        # get the new file data
        newFileData = self.sceneTableToC(fileData, header, sceneNames, isExport)

        # apply HackerOoT changes if needed
        if bpy.context.scene.fast64.oot.hackerFeaturesEnabled:
            newFileData = self.addHackerOoTData(newFileData)

        # write the file with the final data
        writeFile(os.path.join(exportPath, "include/tables/scene_table.h"), newFileData)
