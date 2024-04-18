import os
import enum
import bpy

from dataclasses import dataclass, field
from typing import Optional
from .....utility import PluginError, writeFile
from ....oot_constants import ootEnumSceneID, ootSceneNameToID
from ....oot_utility import getCustomProperty, ExportInfo
from ....oot_level_classes import OOTScene


ADDED_SCENES_COMMENT = "// Added scenes"


class SceneIndexType(enum.IntEnum):
    """Used to figure out the value of ``selectedSceneIndex``"""

    # this is using negative numbers since this is used as a return type if the scene index wasn't found
    CUSTOM = -1  # custom scene
    VANILLA_REMOVED = -2  # vanilla scene that was removed, this is to know if it should insert an entry


@dataclass
class SceneTableEntry:
    """Defines an entry of ``scene_table.h``"""

    index: int
    original: Optional[str]  # the original line from the parsed file
    scene: Optional[OOTScene] = None
    exportName: Optional[str] = None
    prefix: Optional[str] = None  # ifdefs, endifs, comments etc, everything before the current entry
    suffix: Optional[str] = None  # remaining data after the last entry
    parsed: Optional[str] = None

    # macro parameters
    specName: Optional[str] = None  # name of the scene segment in spec
    titleCardName: Optional[str] = None  # name of the title card segment in spec, or `none` for no title card
    enumValue: Optional[str] = None  # enum value for this scene
    drawConfigIdx: Optional[str] = None  # scene draw config index
    unk1: Optional[str] = None
    unk2: Optional[str] = None

    def __post_init__(self):
        # parse the entry parameters from file data or an ``OOTScene``
        macroStart = "DEFINE_SCENE("
        if self.original is not None and macroStart in self.original:
            # remove the index and the macro's name with the parenthesis
            index = self.original.index(macroStart) + len(macroStart)
            self.parsed = self.original[index:].removesuffix(")\n")

            parameters = self.parsed.split(", ")
            assert len(parameters) == 6
            self.setParameters(*parameters)
        elif self.scene is not None:
            self.setParametersFromScene()

    def setParameters(
        self, specName: str, titleCardName: str, enumValue: str, drawConfigIdx: str, unk1: str = "0", unk2: str = "0"
    ):
        """Sets the entry's parameters"""
        self.specName = specName
        self.titleCardName = titleCardName
        self.enumValue = enumValue
        self.drawConfigIdx = drawConfigIdx
        self.unk1 = unk1
        self.unk2 = unk2

    def setParametersFromScene(self, scene: Optional[OOTScene] = None):
        """Use the ``OOTScene`` data to set the entry's parameters"""
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
        """Returns the entry as C code"""
        return (
            (self.prefix if self.prefix is not None else "")
            + f"/* 0x{self.index:02X} */ "
            + f"DEFINE_SCENE({self.specName}, {self.titleCardName}, {self.enumValue}, "
            + f"{self.drawConfigIdx}, {self.unk1}, {self.unk2})\n"
            + (self.suffix if self.suffix is not None else "")
        )


@dataclass
class SceneTable:
    """Defines a ``scene_table.h`` file data"""

    exportPath: str
    exportName: Optional[str]
    selectedSceneEnumValue: Optional[str]
    entries: list[SceneTableEntry] = field(default_factory=list)
    sceneEnumValues: list[str] = field(default_factory=list)  # existing values in ``scene_table.h``
    isFirstCustom: bool = False  # if true, adds the "Added Scenes" comment to the C data
    selectedSceneIndex: int = 0
    customSceneIndex: Optional[int] = None  # None if the selected custom scene isn't in the table yet

    def __post_init__(self):
        # read the file's data
        try:
            with open(self.exportPath) as fileData:
                data = fileData.read()
                fileData.seek(0)
                lines = fileData.readlines()
        except FileNotFoundError:
            raise PluginError("ERROR: Can't find scene_table.h!")

        # parse the entries and populate the list of entries (``self.entries``)
        prefix = ""
        self.isFirstCustom = ADDED_SCENES_COMMENT not in data
        entryIndex = 0  # we don't use ``enumerate`` since not every line is an actual entry
        assert len(lines) > 0
        for line in lines:
            # skip the lines before an entry, create one from the file's data
            # and add the skipped lines as a prefix of the current entry
            if (
                not line.startswith("#")  # ifdefs or endifs
                and not line.startswith(" *")  # multi-line comments
                and "//" not in line  # single line comments
                and "/**" not in line  # multi-line comments
                and line != "\n"
                and line != ""
            ):
                entry = SceneTableEntry(entryIndex, line, prefix=prefix)
                self.entries.append(entry)
                self.sceneEnumValues.append(entry.enumValue)
                prefix = ""
                entryIndex += 1
            else:
                prefix += line

        # add whatever's after the last entry
        if len(prefix) > 0 and prefix != "\n":
            self.entries[-1].suffix = prefix

        # get the scene index for the scene chosen by the user
        if self.selectedSceneEnumValue is not None:
            self.selectedSceneIndex = self.getIndexFromEnumValue()

        # dictionary of entries from spec names
        self.entryBySpecName = {entry.specName: entry for entry in self.entries}

        # set the custom scene index
        if self.selectedSceneIndex == SceneIndexType.CUSTOM:
            entry = self.entryBySpecName.get(f"{self.exportName}_scene")
            if entry is not None:
                self.customSceneIndex = entry.index

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
        """Updates every entry index so they follow each other"""
        for i, entry in enumerate(self.entries):
            if entry.index != i:
                entry.index = i

    def getIndex(self):
        """Returns the selected scene index if it's a vanilla one, else returns the custom scene index"""
        assert self.selectedSceneIndex != SceneIndexType.VANILLA_REMOVED

        # this function's usage makes ``customSceneIndex is None`` impossible
        if self.selectedSceneIndex < 0 and self.customSceneIndex is None:
            raise PluginError("ERROR: Custom Scene Index is None!")

        return self.selectedSceneIndex if self.selectedSceneIndex >= 0 else self.customSceneIndex

    def append(self, entry: SceneTableEntry):
        """Appends an entry to the scene table, only used by custom scenes"""
        # add the "added scenes" comment if it's not already there
        if self.isFirstCustom:
            entry.prefix = f"\n{ADDED_SCENES_COMMENT}\n"
            self.isFirstCustom = False

        if entry not in self.entries:
            if entry.index >= 0:
                self.customSceneIndex = entry.index
                self.entries.append(entry)
            else:
                raise PluginError(f"ERROR: (Append) The index is not valid! ({entry.index})")
        else:
            raise PluginError("ERROR: (Append) Entry already in the table!")

    def insert(self, entry: SceneTableEntry):
        """Inserts an entry in the scene table, only used by non-custom scenes"""
        if not entry in self.entries:
            if entry.index >= 0:
                if entry.index < len(self.entries):
                    nextEntry = self.entries[entry.index]  # the next entry is at the insertion index

                    # move the next entry's prefix to the one we're going to insert
                    if len(nextEntry.prefix) > 0 and not "INCLUDE_TEST_SCENES" in nextEntry.prefix:
                        entry.prefix = nextEntry.prefix
                        nextEntry.prefix = ""

                self.entries.insert(entry.index, entry)
            else:
                raise PluginError(f"ERROR: (Insert) The index is not valid! ({entry.index})")
        else:
            raise PluginError("ERROR: (Insert) Entry already in the table!")

    def remove(self, index: int):
        """Removes an entry from the scene table"""
        isCustom = index == SceneIndexType.CUSTOM
        if index >= 0 or isCustom:
            entry = self.entries[self.getIndex()]

            # move the prefix of the entry to remove to the next entry
            # if there's no next entry this prefix becomes the suffix of the last entry
            if len(entry.prefix) > 0:
                nextIndex = index + 1
                if not isCustom and nextIndex < len(self.entries):
                    self.entries[nextIndex].prefix = entry.prefix
                else:
                    previousIndex = entry.index - 1
                    if entry.index == len(self.entries) - 1 and ADDED_SCENES_COMMENT in entry.prefix:
                        entry.prefix = entry.prefix.removesuffix(f"\n{ADDED_SCENES_COMMENT}\n")
                    self.entries[previousIndex].suffix = entry.prefix

            self.entries.remove(entry)
        elif index == SceneIndexType.VANILLA_REMOVED:
            raise PluginError("INFO: This scene was already removed.")
        else:
            raise PluginError("ERROR: Unexpected scene index value.")

    def to_c(self):
        """Returns the scene table as C code"""
        return "".join(entry.to_c() for entry in self.entries)


def getDrawConfig(sceneName: str):
    """Read draw config from scene table"""
    sceneTable = SceneTable(
        os.path.join(bpy.path.abspath(bpy.context.scene.ootDecompPath), "include/tables/scene_table.h"), None, None
    )

    entry = sceneTable.entryBySpecName.get(f"{sceneName}_scene")
    if entry is not None:
        return entry.drawConfigIdx

    raise PluginError(f"ERROR: Scene name {sceneName} not found in scene table.")


def modifySceneTable(scene: Optional[OOTScene], exportInfo: ExportInfo):
    """Remove, append, insert or update the scene table entry of the selected scene"""
    sceneTable = SceneTable(
        os.path.join(exportInfo.exportPath, "include/tables/scene_table.h"),
        exportInfo.name if exportInfo.option == "Custom" else None,
        exportInfo.option,
    )

    if scene is None:
        # remove mode
        sceneTable.remove(sceneTable.selectedSceneIndex)
    elif sceneTable.selectedSceneIndex == SceneIndexType.CUSTOM and sceneTable.customSceneIndex is None:
        # custom mode: new custom scene
        sceneTable.append(SceneTableEntry(len(sceneTable.entries) - 1, None, scene, exportInfo.name))
    elif sceneTable.selectedSceneIndex == SceneIndexType.VANILLA_REMOVED:
        # insert mode
        sceneTable.insert(SceneTableEntry(sceneTable.getInsertionIndex(), None, scene, exportInfo.name))
    else:
        # update mode (for both vanilla and custom scenes since they already exist in the table)
        sceneTable.entries[sceneTable.getIndex()].setParametersFromScene(scene)

    # update the indices
    sceneTable.updateEntryIndex()

    # write the file with the final data
    writeFile(sceneTable.exportPath, sceneTable.to_c())
