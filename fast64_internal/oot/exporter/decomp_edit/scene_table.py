import os
import enum
import bpy

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
from ....utility import PluginError, writeFile
from ...oot_utility import ExportInfo
from ...oot_constants import ootEnumSceneID, ootSceneNameToID

if TYPE_CHECKING:
    from ..main import SceneExport


ADDED_SCENES_COMMENT = "// Added scenes"


class SceneIndexType(enum.IntEnum):
    """Used to figure out the value of ``selectedSceneIndex``"""

    # this is using negative numbers since this is used as a return type if the scene index wasn't found
    CUSTOM = -1  # custom scene
    VANILLA_REMOVED = -2  # vanilla scene that was removed, this is to know if it should insert an entry


@dataclass
class SceneTableEntry:
    """Defines an entry of ``scene_table.h``"""

    # macro parameters
    specName: str  # name of the scene segment in spec
    titleCardName: str  # name of the title card segment in spec, or `none` for no title card
    enumValue: str  # enum value for this scene
    drawConfigIdx: str  # scene draw config index
    unk1: str
    unk2: str

    prefix: str = str()  # ifdefs, endifs, comments etc, everything before the current entry
    suffix: str = str()  # remaining data after the last entry

    @staticmethod
    def from_line(original_line: str, prefix: str):
        macro_start = "DEFINE_SCENE("

        if macro_start in original_line:
            # remove the index and the macro's name with the parenthesis
            index = original_line.index(macro_start) + len(macro_start)
            parsed = original_line[index:].removesuffix(")\n")

            params = parsed.split(", ")
            assert len(params) == 6

            return SceneTableEntry(*params, prefix)
        else:
            raise PluginError("ERROR: This line is not a scene table entry!")

    @staticmethod
    def from_scene(exporter: "SceneExport", export_name: str, is_custom_scene: bool):
        # TODO: Implement title cards
        scene_name = exporter.scene.name.lower() if is_custom_scene else export_name
        return SceneTableEntry(
            scene_name if scene_name.endswith("_scene") else f"{scene_name}_scene",
            "none",
            ootSceneNameToID.get(export_name, f"SCENE_{export_name.upper()}"),
            exporter.scene.mainHeader.infos.drawConfig,
            "0",
            "0",
        )

    def to_c(self, index: int):
        """Returns the entry as C code"""
        return (
            self.prefix
            + f"/* 0x{index:02X} */ "
            + f"DEFINE_SCENE({self.specName}, {self.titleCardName}, {self.enumValue}, "
            + f"{self.drawConfigIdx}, {self.unk1}, {self.unk2})\n"
            + self.suffix
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
                and line.strip() != ""
            ):
                entry = SceneTableEntry.from_line(line, prefix)
                self.entries.append(entry)
                self.sceneEnumValues.append(entry.enumValue)
                prefix = ""
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
                self.customSceneIndex = self.entries.index(entry)

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

    def getIndex(self) -> int:
        """Returns the selected scene index if it's a vanilla one, else returns the custom scene index"""
        assert self.selectedSceneIndex != SceneIndexType.VANILLA_REMOVED

        # this function's usage makes ``customSceneIndex is None`` impossible
        if self.selectedSceneIndex < 0 and self.customSceneIndex is None:
            raise PluginError("ERROR: Custom Scene Index is None!")

        return self.selectedSceneIndex if self.selectedSceneIndex >= 0 else self.customSceneIndex

    def append(self, entry: SceneTableEntry, index: int):
        """Appends an entry to the scene table, only used by custom scenes"""
        # add the "added scenes" comment if it's not already there
        if self.isFirstCustom:
            entry.prefix = f"\n{ADDED_SCENES_COMMENT}\n"
            self.isFirstCustom = False

        if entry not in self.entries:
            if index >= 0:
                self.customSceneIndex = index
                self.entries.append(entry)
            else:
                raise PluginError(f"ERROR: (Append) The index is not valid! ({index})")
        else:
            raise PluginError("ERROR: (Append) Entry already in the table!")

    def insert(self, entry: SceneTableEntry, index: int):
        """Inserts an entry in the scene table, only used by non-custom scenes"""
        if not entry in self.entries:
            if index >= 0:
                if index < len(self.entries):
                    nextEntry = self.entries[index]  # the next entry is at the insertion index

                    # move the next entry's prefix to the one we're going to insert
                    if len(nextEntry.prefix) > 0 and not "INCLUDE_TEST_SCENES" in nextEntry.prefix:
                        entry.prefix = nextEntry.prefix
                        nextEntry.prefix = ""

                self.entries.insert(index, entry)
            else:
                raise PluginError(f"ERROR: (Insert) The index is not valid! ({index})")
        else:
            raise PluginError("ERROR: (Insert) Entry already in the table!")

    def remove(self, index: int):
        """Removes an entry from the scene table"""
        isCustom = index == SceneIndexType.CUSTOM
        if index >= 0 or isCustom:
            idx = self.getIndex()
            entry = self.entries[idx]

            # move the prefix of the entry to remove to the next entry
            # if there's no next entry this prefix becomes the suffix of the last entry
            if len(entry.prefix) > 0:
                nextIndex = index + 1
                if not isCustom and nextIndex < len(self.entries):
                    self.entries[nextIndex].prefix = entry.prefix
                else:
                    previousIndex = idx - 1
                    if idx == len(self.entries) - 1 and ADDED_SCENES_COMMENT in entry.prefix:
                        entry.prefix = entry.prefix.removesuffix(f"\n{ADDED_SCENES_COMMENT}\n")
                    self.entries[previousIndex].suffix = entry.prefix

            self.entries.remove(entry)
        elif index == SceneIndexType.VANILLA_REMOVED:
            raise PluginError("INFO: This scene was already removed.")
        else:
            raise PluginError("ERROR: Unexpected scene index value.")

    def to_c(self):
        """Returns the scene table as C code"""
        return "".join(entry.to_c(i) for i, entry in enumerate(self.entries))


class SceneTableUtility:
    """This class hosts different function to edit the scene table"""

    @staticmethod
    def getDrawConfig(sceneName: str):
        """Read draw config from scene table"""
        sceneTable = SceneTable(
            os.path.join(bpy.path.abspath(bpy.context.scene.ootDecompPath), "include/tables/scene_table.h"), None, None
        )

        entry = sceneTable.entryBySpecName.get(f"{sceneName}_scene")
        if entry is not None:
            return entry.drawConfigIdx

        raise PluginError(f"ERROR: Scene name {sceneName} not found in scene table.")

    @staticmethod
    def editSceneTable(exporter: Optional["SceneExport"], exportInfo: ExportInfo):
        """Remove, append, insert or update the scene table entry of the selected scene"""
        sceneTable = SceneTable(
            os.path.join(exportInfo.exportPath, "include/tables/scene_table.h"),
            exportInfo.name if exportInfo.option == "Custom" else None,
            exportInfo.option,
        )

        if exporter is None:
            # remove mode
            sceneTable.remove(sceneTable.selectedSceneIndex)
        elif sceneTable.selectedSceneIndex == SceneIndexType.CUSTOM and sceneTable.customSceneIndex is None:
            # custom mode: new custom scene
            sceneTable.append(
                SceneTableEntry.from_scene(exporter, exporter.exportInfo.name, True), len(sceneTable.entries) - 1
            )
        elif sceneTable.selectedSceneIndex == SceneIndexType.VANILLA_REMOVED:
            # insert mode
            sceneTable.insert(
                SceneTableEntry.from_scene(exporter, exporter.exportInfo.name, False), sceneTable.getInsertionIndex()
            )
        else:
            # update mode (for both vanilla and custom scenes since they already exist in the table)
            index = sceneTable.getIndex()
            entry = sceneTable.entries[index]
            new_entry = SceneTableEntry.from_scene(exporter, exporter.scene.name, False)
            new_entry.prefix = entry.prefix
            new_entry.suffix = entry.suffix
            sceneTable.entries[index] = new_entry

        # write the file with the final data
        writeFile(sceneTable.exportPath, sceneTable.to_c())
