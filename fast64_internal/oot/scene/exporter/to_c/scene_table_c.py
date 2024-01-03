import os
import enum
import bpy

from dataclasses import dataclass, field
from typing import Optional
from .....utility import PluginError, writeFile
from ....oot_constants import ootEnumSceneID, ootSceneNameToID
from ....oot_utility import getCustomProperty, ExportInfo
from ....oot_level_classes import OOTScene


class SceneIndexType(enum.IntEnum):
    """Used to figure out the value of ``selectedSceneIndex``"""

    # this is using negative numbers since this is used as a return type if the scene index wasn't found
    CUSTOM = -1  # custom scene
    VANILLA_REMOVED = -2  # vanilla scene that was removed, this is to know if it should insert an entry


@dataclass(unsafe_hash=True)
class SceneTableEntry:
    index: int
    original: Optional[str]
    scene: Optional[OOTScene] = None
    exportName: Optional[str] = None
    prefix: Optional[str] = None  # ifdefs, endifs, comments etc, everything before the current entry
    suffix: Optional[str] = None  # remaining data after the last entry
    parsed: Optional[str] = None

    specName: Optional[str] = None
    titleCardName: Optional[str] = None
    enumValue: Optional[str] = None
    drawConfigIdx: Optional[str] = None
    unk1: Optional[str] = None
    unk2: Optional[str] = None

    def __post_init__(self):
        macroStart = "DEFINE_SCENE("
        if self.original is not None and macroStart in self.original:
            self.ogIdx = self.original.index(macroStart)
            self.parsed = self.original[self.ogIdx + len(macroStart) :][:-1]

            parameters = self.parsed.split(", ")
            assert len(parameters) == 6
            self.setParameters(*parameters)
        elif self.scene is not None:
            self.setParametersFromScene()

    def setParameters(
        self, specName: str, titleCardName: str, enumValue: str, drawConfigIdx: str, unk1: str = "0", unk2: str = "0"
    ):
        self.specName = specName
        self.titleCardName = titleCardName
        self.enumValue = enumValue
        self.drawConfigIdx = drawConfigIdx
        self.unk1 = unk1
        self.unk2 = unk2

    def setParametersFromScene(self, scene: Optional[OOTScene] = None):
        scene = self.scene if scene is None else scene
        # TODO: Implement title cards
        name = scene.name if scene is not None else self.exportName
        self.setParameters(
            f"{scene.name.lower()}_scene",
            "none",
            ootSceneNameToID.get(name, f"SCENE_{name.upper()}"),
            getCustomProperty(scene.sceneTableEntry, "drawConfig"),
        )

    def to_c(self):
        return (
            (self.prefix if self.prefix is not None else "")
            + f"/* 0x{self.index:02X} */ "
            + f"DEFINE_SCENE({self.specName}, {self.titleCardName}, {self.enumValue}, "
            + f"{self.drawConfigIdx}, {self.unk1}, {self.unk2})\n"
            + (self.suffix if self.suffix is not None else "")
        )


@dataclass
class SceneTable:
    exportPath: str
    exportName: Optional[str]
    selectedSceneEnumValue: Optional[str]
    entries: list[SceneTableEntry] = field(default_factory=list)
    sceneEnumValues: list[str] = field(default_factory=list)  # existing values in ``scene_table.h``
    isNewCustom: bool = False  # true if the custom scene doesn't exist in the table
    firstAppend: bool = False
    selectedSceneIndex: int = 0
    customSceneIndex: int = 0

    def __post_init__(self):
        try:
            with open(self.exportPath) as fileData:
                data = fileData.read()
                lines = data.split("\n")
        except FileNotFoundError:
            raise PluginError("ERROR: Can't find scene_table.h!")

        prefix = ""
        self.isNewCustom = self.exportName is not None and not self.exportName in data
        self.firstAppend = "// Added scenes" in data
        entryIndex = 0
        for line in lines:
            entry = SceneTableEntry(entryIndex, line)

            if (
                not line.startswith("#")  # ifdefs or endifs
                and not line.startswith(" *")  # multi-line comments
                and not "//" in line  # single line comments
                and "/**" not in line  # multi-line comments
                and line != "\n"
                and line != ""
            ):
                entry.prefix = prefix
                self.entries.append(entry)
                self.sceneEnumValues.append(entry.enumValue)
                prefix = ""
                if self.exportName is not None and self.exportName in line:
                    self.customSceneIndex = entryIndex
                entryIndex += 1
            else:
                prefix += line + "\n"

        # add whatever's after the last entry
        if len(prefix) > 0 and prefix != "\n":
            self.entries[-1].suffix = prefix

        if self.selectedSceneEnumValue is not None:
            self.selectedSceneIndex = self.getIndexFromEnumValue()

        self.entryBySpecName = {entry.specName: entry for entry in self.entries}

    def getIndexFromEnumValue(self):
        """Returns the index (int) of the chosen scene if vanilla and found, else return an enum value from ``SceneIndexType``"""
        if self.selectedSceneEnumValue == "Custom":
            return SceneIndexType.CUSTOM
        for i in range(len(self.sceneEnumValues)):
            if self.sceneEnumValues[i] == self.selectedSceneEnumValue:
                return i
        # if the index is not found and it's not a custom export it means it's a vanilla scene that was removed
        return SceneIndexType.VANILLA_REMOVED

    def getOriginalIndex(self):
        """
        Returns the index of a specific scene defined by which one the user chose
            or by the ``sceneName`` parameter if it's not set to ``None``
        """
        i = 0
        if self.selectedSceneEnumValue != "Custom":
            for elem in ootEnumSceneID:
                if elem[0] == self.selectedSceneEnumValue:
                    # returns i - 1 because the first entry is the ``Custom`` option
                    return i - 1
                i += 1
        raise PluginError("ERROR: Scene Index not found!")

    def getInsertionIndex(self, index: Optional[int] = None) -> int:
        """Returns the index to know where to insert data"""
        # special case where the scene is "Inside the Great Deku Tree"
        # since it's the first scene simply return 0
        if self.selectedSceneEnumValue == "SCENE_DEKU_TREE":
            return 0

        # if index is None this means this is looking for ``original_scene_index - 1``
        # else, this means the table is shifted
        if index is None:
            currentIndex = self.getOriginalIndex()
        else:
            currentIndex = index

        for i in range(len(self.sceneEnumValues)):
            if self.sceneEnumValues[i] == ootEnumSceneID[currentIndex][0]:
                return i + 1

        # if the index hasn't been found yet, do it again but decrement the index
        return self.getInsertionIndex(currentIndex - 1)

    def updateEntryIndex(self):
        for i, entry in enumerate(self.entries):
            if entry.index != i:
                entry.index = i

    def append(self, entry: SceneTableEntry):
        if not self.firstAppend:
            entry.prefix = "// Added scenes\n"
            self.firstAppend = True

        if not entry in self.entries:
            if entry.index >= 0:
                self.entries.append(entry)
            else:
                raise PluginError(f"ERROR: (Append) The index is not valid! ({entry.index})")
        else:
            raise PluginError("ERROR: (Append) Entry already in the table!")

    def insert(self, entry: SceneTableEntry):
        if not entry in self.entries:
            if entry.index >= 0:
                if entry.index < len(self.entries):
                    nextEntry = self.entries[entry.index]  # the next entry is at the insertion index
                    if len(nextEntry.prefix) > 0 and not "INCLUDE_TEST_SCENES" in nextEntry.prefix:
                        entry.prefix = nextEntry.prefix
                        nextEntry.prefix = ""

                self.entries.insert(entry.index, entry)
            else:
                raise PluginError(f"ERROR: (Insert) The index is not valid! ({entry.index})")
        else:
            raise PluginError("ERROR: (Insert) Entry already in the table!")

    def remove(self, index: int):
        if index >= 0 or index == SceneIndexType.CUSTOM:
            entry = self.entries[index]

            if len(entry.prefix) > 0:
                nextIndex = index + 1
                if index != SceneIndexType.CUSTOM and nextIndex < len(self.entries):
                    self.entries[nextIndex].prefix = entry.prefix
                else:
                    previousIndex = entry.index - 1
                    if entry.index == len(self.entries) - 1:
                        entry.prefix = entry.prefix.removesuffix("// Added scenes\n")
                    self.entries[previousIndex].suffix = entry.prefix

            self.entries.remove(entry)
        elif index == SceneIndexType.VANILLA_REMOVED:
            PluginError("INFO: This scene was already removed.")
        else:
            raise PluginError("ERROR: Unexpected scene index value.")

    def to_c(self):
        return "".join(entry.to_c() for entry in self.entries)


def getDrawConfig(sceneName: str):
    """Read draw config from scene table"""
    sceneTable = SceneTable(
        os.path.join(bpy.path.abspath(bpy.context.scene.ootDecompPath), "include/tables/scene_table.h"), None, None
    )

    entry = sceneTable.entryBySpecName.get(f"{sceneName}_scene")
    if entry is not None:
        return entry.drawConfigIdx

    raise PluginError(f"Scene name {sceneName} not found in scene table.")


def modifySceneTable(scene: Optional[OOTScene], exportInfo: ExportInfo):
    sceneTable = SceneTable(
        os.path.join(exportInfo.exportPath, "include/tables/scene_table.h"),
        exportInfo.name if exportInfo.option == "Custom" else None,
        exportInfo.option,
    )

    if scene is None:
        # remove mode
        sceneTable.remove(sceneTable.selectedSceneIndex)
    elif sceneTable.selectedSceneIndex == SceneIndexType.CUSTOM and sceneTable.isNewCustom:
        # custom mode: new custom scene
        sceneTable.append(SceneTableEntry(len(sceneTable.entries) - 1, None, scene, exportInfo.name))
    elif sceneTable.selectedSceneIndex == SceneIndexType.VANILLA_REMOVED:
        # insert mode
        sceneTable.insert(SceneTableEntry(sceneTable.getInsertionIndex(), None, scene, exportInfo.name))
    else:
        # update mode, handles existing custom scene update
        index = sceneTable.selectedSceneIndex if sceneTable.selectedSceneIndex >= 0 else sceneTable.customSceneIndex
        entry = sceneTable.entries[index]
        entry.setParametersFromScene(scene)

    # update the indices
    sceneTable.updateEntryIndex()

    # write the file with the final data
    writeFile(sceneTable.exportPath, sceneTable.to_c())
