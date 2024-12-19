import os
import bpy

from dataclasses import dataclass, field
from typing import Optional
from ....utility import PluginError, writeFile
from ...constants import ootEnumSceneID, ootSceneNameToID, mm_enum_scene_id, mm_scene_name_to_id

ADDED_SCENES_COMMENT = "// Added scenes"


def get_original_index(enum_value: str) -> Optional[int]:
    """
    Returns the original index of a specific scene
    """
    if bpy.context.scene.gameEditorMode == "OOT":
        enum_scene_id = ootEnumSceneID
    else:
        enum_scene_id = mm_enum_scene_id

    for index, scene_enum in enumerate(
        [elem[0] for elem in enum_scene_id[1:]]
    ):  # ignore first value in array ('Custom')
        if scene_enum == enum_value:
            return index
    return None


def get_scene_enum_from_name(scene_name: str):
    if bpy.context.scene.gameEditorMode == "OOT":
        return ootSceneNameToID.get(scene_name, f"SCENE_{scene_name.upper()}")
    else:
        return mm_scene_name_to_id.get(scene_name, f"SCENE_{scene_name.upper()}")


@dataclass
class SceneTableEntry:
    """Defines an entry of ``scene_table.h``"""

    # macro parameters
    spec_name: str  # name of the scene segment in spec
    title_card_name: str  # name of the title card segment in spec, or `none` for no title card
    enum_value: str  # enum value for this scene
    draw_config: str  # scene draw config index
    unk1: str
    unk2: str

    @staticmethod
    def from_line(original_line: str):
        macro_start = "DEFINE_SCENE("

        if macro_start in original_line:
            # remove the index and the macro's name with the parenthesis
            index = original_line.index(macro_start) + len(macro_start)
            parsed = original_line[index:].removesuffix(")")

            if bpy.context.scene.gameEditorMode == "OOT":
                params = parsed.split(", ")
                assert len(params) == 6
                return SceneTableEntry(*params)
            else:
                split = parsed.split(", ")
                params = []
                for i, elem in enumerate(split):
                    if i == 5:
                        break
                    else:
                        params.append(elem)
                params.append(", ".join(split[i:]))
                assert len(params) == 6
                return SceneTableEntry(params[0], params[2], params[1], params[3], params[4], params[5])

        else:
            raise PluginError("ERROR: This line is not a scene table entry!")

    @staticmethod
    def from_scene(scene_name: str, draw_config: str):
        # TODO: Implement title cards
        return SceneTableEntry(
            scene_name if scene_name.endswith("_scene") else f"{scene_name}_scene",
            "none",
            get_scene_enum_from_name(scene_name),
            draw_config,
            "0",
            "0",
        )

    def to_c(self, index: int):
        """Returns the entry as C code"""
        return (
            f"/* 0x{index:02X} */ "
            f"DEFINE_SCENE({self.spec_name}, {self.title_card_name}, {self.enum_value}, "
            f"{self.draw_config}, {self.unk1}, {self.unk2})"
        )


@dataclass
class SceneTableSection:
    """Defines a section of the scene table, with is a list of entires with an optional preprocessor directive / comment"""

    directive: Optional[str]  # can also be a comment starting with //
    entries: list[SceneTableEntry] = field(default_factory=list)

    def to_c(self, index: int):
        directive = f"{self.directive}\n" if self.directive else ""
        terminator = "\n#endif" if self.directive and self.directive.startswith("#if") else ""
        entry_string = "\n".join(entry.to_c(index + i) for i, entry in enumerate(self.entries))
        return f"{directive}{entry_string}{terminator}\n\n"


@dataclass
class SceneTable:
    """Defines a ``scene_table.h`` file data"""

    header: str
    sections: list[SceneTableSection] = field(default_factory=list)

    @staticmethod
    def new(export_path: str):
        # read the file's data
        try:
            with open(export_path) as file_data:
                data = file_data.read()
                file_data.seek(0)
                lines = file_data.readlines()
        except FileNotFoundError:
            raise PluginError("ERROR: Can't find scene_table.h!")

        # Find first instance of "DEFINE_SCENE(", indicating a scene define macro
        first_macro_index = data.index("DEFINE_SCENE(")
        if first_macro_index == -1:
            return SceneTable(data, [])  # No scene defines found - add to end

        # Go backwards up to previous newline
        try:
            header_end_index = data[:first_macro_index].rfind("\n")
        except ValueError:
            header_end_index = 0

        header = data[: header_end_index + 1]

        lines = data[header_end_index + 1 :].split("\n")
        lines = list(filter(None, lines))  # removes empty lines
        lines = [line.strip() for line in lines]

        sections: list[SceneTableSection] = []
        current_section: Optional[SceneTableSection] = None

        for line in lines:
            if line.startswith("#if"):
                if current_section:  # handles non-directive section preceding directive section
                    sections.append(current_section)
                current_section = SceneTableSection(line)
            elif line.startswith("#endif"):
                sections.append(current_section)
                current_section = None  # handles back-to-back directive sections
            elif line.startswith("//"):
                if current_section:  # handles non-directive section preceding directive section
                    sections.append(current_section)
                current_section = SceneTableSection(line)
            elif "DEFINE_SCENE_UNSET" not in line:
                if not current_section:
                    current_section = SceneTableSection(None)
                current_section.entries.append(SceneTableEntry.from_line(line))

        if current_section:
            sections.append(current_section)  # add last section if non-directive

        return SceneTable(header, sections)

    def get_entries_flattened(self) -> list[SceneTableEntry]:
        """
        Returns all entries as a single array, without sections.
        This is a shallow copy of the data and adding/removing from this list not change the scene table internally.
        """

        return [entry for section in self.sections for entry in section.entries]

    def get_index_from_enum(self, enum_value: str) -> Optional[int]:
        """Returns the index (int) of the chosen scene if found, else return ``None``"""

        for i, entry in enumerate(self.get_entries_flattened()):
            if entry.enum_value == enum_value:
                return i

        return None

    def set_entry_at_enum(self, entry: SceneTableEntry, enum_value: str):
        """Replaces entry in the scene table with the given enum_value"""
        for section in self.sections:
            for entry_index in range(len(section.entries)):
                if section.entries[entry_index].enum_value == enum_value:
                    section.entries[entry_index] = entry

    def append(self, entry: SceneTableEntry):
        """Appends an entry to the scene table, only used by custom scenes"""

        # Find current added scenes comment, or add one if not found
        current_section = None
        for section in self.sections:
            if section.directive == ADDED_SCENES_COMMENT:
                current_section = section
                break
        if current_section is None:
            current_section = SceneTableSection(ADDED_SCENES_COMMENT)
            self.sections.append(current_section)

        if entry not in current_section.entries:
            current_section.entries.append(entry)
        else:
            raise PluginError("ERROR: (Append) Entry already in the table!")

    def insert(self, entry: SceneTableEntry, index: int):
        """Inserts an entry in the scene table, only used by non-custom scenes"""

        if entry in self.get_entries_flattened():
            raise PluginError("ERROR: (Insert) Entry already in the table!")
        if index < 0 or index > len(self.get_entries_flattened()) - 1:
            raise PluginError(f"ERROR: (Insert) The index is not valid! ({index})")

        i = 0
        for section in self.sections:
            for entry_index in range(len(section.entries)):
                if i == index:
                    section.entries.insert(entry_index, entry)
                    return
                else:
                    i += 1

    def update(self, entry: SceneTableEntry, enum_value: str):
        """Updates an entry if the enum_value exists in the scene table, otherwise appends/inserts entry depending on if custom or not"""

        original_index = get_original_index(enum_value)  # index in unmodified scene table
        current_index = self.get_index_from_enum(enum_value)  # index in current scene table

        if current_index is None:  # Not in scene table currently
            if original_index is not None:
                # insert mode - we want to place vanilla scenes into their original locations if previously deleted
                self.insert(entry, original_index)
            else:
                # this is a custom level, append to end
                self.append(entry)
        else:
            # update mode (for both vanilla and custom scenes since they already exist in the table)
            self.set_entry_at_enum(entry, enum_value)

    def remove(self, enum_value: str):
        """Removes an entry from the scene table"""

        for section in self.sections:
            for entry in section.entries:
                if entry.enum_value == enum_value:
                    section.entries.remove(entry)
                    return

    def to_c(self):
        """Returns the scene table as C code"""
        data = f"{self.header}"
        index = 0
        for section in self.sections:
            data += section.to_c(index)
            index += len(section.entries)

        if data[-2:] == "\n\n":  # For consistency with vanilla
            data = data[:-1]
        return data


class SceneTableUtility:
    """This class hosts different function to edit the scene table"""

    @staticmethod
    def get_draw_config(scene_name: str):
        """Read draw config from scene table"""
        if bpy.context.scene.gameEditorMode == "OOT":
            scene_name = f"{scene_name}_scene"

        scene_table = SceneTable.new(
            os.path.join(bpy.path.abspath(bpy.context.scene.ootDecompPath), "include/tables/scene_table.h")
        )

        spec_dict = {entry.spec_name: entry for entry in scene_table.get_entries_flattened()}
        entry = spec_dict.get(f"{scene_name}")
        if entry is not None:
            return entry.draw_config

        raise PluginError(f"ERROR: Scene name {scene_name} not found in scene table.")

    @staticmethod
    def edit_scene_table(export_path: str, export_name: str, draw_config: str):
        """Update the scene table entry of the selected scene"""
        path = os.path.join(export_path, "include/tables/scene_table.h")
        scene_table = SceneTable.new(path)
        export_enum = get_scene_enum_from_name(export_name)

        scene_table.update(SceneTableEntry.from_scene(export_name, draw_config), export_enum)

        # write the file with the final data
        writeFile(path, scene_table.to_c())

    @staticmethod
    def delete_scene_table_entry(export_path: str, export_name: str):
        """Remove the scene table entry of the selected scene"""
        path = os.path.join(export_path, "include/tables/scene_table.h")
        scene_table = SceneTable.new(path)
        export_enum = get_scene_enum_from_name(export_name)

        scene_table.remove(export_enum)

        # write the file with the final data
        writeFile(path, scene_table.to_c())
