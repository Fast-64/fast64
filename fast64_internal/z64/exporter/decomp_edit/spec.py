import os
import bpy
import re

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from ....utility import PluginError, writeFile, indent
from ...utility import ExportInfo, getSceneDirFromLevelName
from ..file import SceneFile

if TYPE_CHECKING:
    from ..scene import Scene


def get_spec_path(export_path: Path):
    """Returns the path to the scene spec include"""

    version: str = bpy.context.scene.fast64.oot.oot_version

    if "spec" not in str(export_path):
        export_path = export_path / "spec"

    if version == "legacy":
        return export_path
    elif version.startswith("gc-") or version.startswith("ique-"):
        return export_path / f"scenes_gc_ique.inc"
    else:
        return export_path / f"scenes_n64.inc"


@dataclass
class SpecCommand:
    """This class defines a single spec command"""

    type: str
    content: str = ""
    comment: str = ""

    def to_c(self):
        comment = f" //{self.comment}" if self.comment != "" else ""

        # Note: This is a hacky way of handling internal preprocessor directives, which would be parsed as if they were commands.
        # This is fine as long you are not trying to modify this spec entry, and currently there are no internal preprocessor directives
        # in scene segments anyway.

        indent_string = indent if not self.type.startswith("#") else ""
        content = f" {self.content.strip()}" if self.content != "" else ""
        return f"{indent_string}{self.type}{content}{comment}\n"


@dataclass
class SpecEntry:
    """Defines an entry of ``spec``"""

    commands: list[SpecCommand]

    @staticmethod
    def new(original: list[str]):
        commands: list[SpecCommand] = []
        for line in original:
            comment = ""
            if "//" in line:
                comment = line[line.index("//") + len("//") :]
                line = line[: line.index("//")].strip()
            split = line.split(" ")
            commands.append(SpecCommand(split[0], " ".join(split[1:]) if len(split) > 1 else "", comment))

        return SpecEntry(commands)

    def get_name(self) -> Optional[str]:
        """Returns segment name, with quotes removed"""
        for command in self.commands:
            if command.type == "name":
                return command.content.replace('"', "")
        return ""

    def to_c(self):
        return "beginseg\n" + "".join(command.to_c() for command in self.commands) + "endseg"


@dataclass
class SpecSection:
    """Defines an 'section' of ``spec``, which is a list of segment definitions that are optionally surrounded by a preprocessor directive"""

    directive: Optional[str]
    entries: list[SpecEntry] = field(default_factory=list)

    def to_c(self):
        directive = f"{self.directive}\n" if self.directive else ""
        terminator = "\n#endif" if self.directive and self.directive.startswith("#if") else ""
        entry_string = "\n\n".join(entry.to_c() for entry in self.entries)
        return f"{directive}{entry_string}{terminator}\n\n"


@dataclass
class SpecFile:
    """This class defines the spec's file data"""

    header: str  # contents of file before scene segment definitions
    build_directory: Optional[str]
    sections: list[SpecSection] = field(default_factory=list)  # list of the different spec entries

    @staticmethod
    def new(export_path: Path):
        # read the file's data
        spec_path = get_spec_path(export_path)
        try:
            data = spec_path.read_text()
        except FileNotFoundError:
            raise PluginError(f'ERROR: Can\'t find spec file at "{spec_path}"!')

        # Find first instance of "/assets/scenes/", indicating a scene file
        first_scene_include_index = data.index("/assets/scenes/")
        if first_scene_include_index == -1:
            return SpecFile(data, None, [])  # No scene files found - add to end

        # Get build directory, which is text right before /assets/scenes/...
        build_directory = None
        for dir in ["$(BUILD_DIR)", "build"]:
            if data[:first_scene_include_index].endswith(dir):
                build_directory = dir

        # Go backwards up to previous "endseg" definition
        try:
            header_endseg_index = data[:first_scene_include_index].rfind("endseg")
        except ValueError:
            raise PluginError("endseg not found, scene segements cannot be the first segments in spec file")

        # if it's less than zero it means the file already starts with scene entries
        if header_endseg_index < 0:
            header = ""
            header_endseg_index = 0
            lines = data.split("\n")
        else:
            header = data[: header_endseg_index + len("endseg")]

            # This technically includes data after scene segments
            # However, as long as we don't have to modify them, they should be fine
            lines = data[header_endseg_index + len("endseg") :].split("\n")

        lines = list(filter(None, lines))  # removes empty lines
        lines = [line.strip() for line in lines]

        sections: list[SpecSection] = []
        current_section: Optional[SpecSection] = None
        while len(lines) > 0:
            line = lines.pop(0)
            if line.startswith("#if"):
                if current_section:  # handles non-directive section preceding directive section
                    sections.append(current_section)
                current_section = SpecSection(line)
            elif line.startswith("#endif"):
                sections.append(current_section)
                current_section = None  # handles back-to-back directive sections
            elif line.startswith("beginseg"):
                if not current_section:
                    current_section = SpecSection(None)
                segment_lines = []
                while len(lines) > 0 and not lines[0].startswith("endseg"):
                    next_line = lines.pop(0)
                    segment_lines.append(next_line)
                if len(lines) == 0:
                    raise PluginError("In spec file, a beginseg was found unterminated.")
                lines.pop(0)  # remove endseg line
                current_section.entries.append(SpecEntry.new(segment_lines))
            else:
                # This code should ignore any other line, including comments.
                pass

        if current_section:
            sections.append(current_section)  # add last section if non-directive

        return SpecFile(header, build_directory, sections)

    def get_entries_flattened(self) -> list[SpecEntry]:
        """
        Returns all entries as a single array, without sections.
        This is a shallow copy of the data and adding/removing from this list not change the spec file internally.
        """
        return [entry for section in self.sections for entry in section.entries]

    def find(self, segment_name: str) -> SpecEntry:
        """Returns an entry from a segment name, returns ``None`` if nothing was found"""

        for entry in self.get_entries_flattened():
            if entry.get_name() == segment_name:
                return entry
        return None

    def append(self, entry: SpecEntry):
        """Appends an entry to the list"""

        if len(self.sections) > 0 and self.sections[-1].directive is None:
            self.sections[-1].entries.append(entry)
        else:
            section = SpecSection(None, [entry])
            self.sections.append(section)

    def remove(self, segment_name: str):
        """Removes an entry from a segment name"""
        for i in range(len(self.sections)):
            section = self.sections[i]
            for j in range(len(section.entries)):
                entry = section.entries[j]
                if entry.get_name() == segment_name:
                    section.entries.remove(entry)
                    if len(section.entries) == 0:
                        self.sections.remove(section)
                    return

    def to_c(self):
        header = ""

        if len(self.header) > 0:
            header = f"{self.header}\n\n"

        return header + "".join(section.to_c() for section in self.sections)


class SpecUtility:
    """This class hosts different functions to edit the spec file"""

    @staticmethod
    def remove_segments(export_path: Path, scene_name: str):
        spec_file = SpecFile.new(export_path)
        SpecUtility.remove_segments_from_spec(spec_file, scene_name)
        path = get_spec_path(export_path)
        path.write_text(spec_file.to_c())

    @staticmethod
    def remove_segments_from_spec(spec_file: SpecFile, scene_name: str):
        # get the scene and current segment name and remove the scene
        scene_segment_name = f"{scene_name}_scene"
        spec_file.remove(scene_segment_name)

        # mark the other scene elements to remove (like rooms)
        segments_to_remove: list[str] = []
        for entry in spec_file.get_entries_flattened():
            # Note: you cannot do startswith(scene_name), ex. entra vs entra_n
            if entry.get_name() == f"{scene_name}_scene" or re.match(f"^{scene_name}\_room\_[0-9]+$", entry.get_name()):
                segments_to_remove.append(entry.get_name())

        # remove the segments
        for segment_name in segments_to_remove:
            spec_file.remove(segment_name)

    @staticmethod
    def add_segments(exportInfo: "ExportInfo", scene: "Scene", sceneFile: "SceneFile"):
        hasSceneTex = sceneFile.hasSceneTextures()
        hasSceneCS = sceneFile.hasCutscenes()
        roomTotal = len(scene.rooms.entries)
        csTotal = 0

        csTotal += len(scene.mainHeader.cutscene.entries)
        if scene.altHeader is not None:
            for cs in scene.altHeader.cutscenes:
                csTotal += len(cs.cutscene.entries)

        # get the spec's data
        exportPath = exportInfo.exportPath
        specFile = SpecFile.new(exportPath)
        build_directory = specFile.build_directory

        # get the scene and current segment name and remove the scene
        sceneName = exportInfo.name
        sceneSegmentName = f"{sceneName}_scene"
        SpecUtility.remove_segments_from_spec(specFile, exportInfo.name)

        assert build_directory is not None
        isSingleFile = bpy.context.scene.ootSceneExportSettings.singleFile
        includeDir = f"{build_directory}/"
        if exportInfo.customSubPath is not None:
            includeDir += f"{exportInfo.customSubPath + sceneName}"
        else:
            includeDir += f"{getSceneDirFromLevelName(sceneName)}"

        sceneCmds = [
            SpecCommand("name", f'"{sceneSegmentName}"'),
            SpecCommand("compress", ""),
            SpecCommand("romalign", "0x1000"),
        ]

        # scene
        if isSingleFile:
            sceneCmds.append(SpecCommand("include", f'"{includeDir}/{sceneSegmentName}.o"'))
        else:
            sceneCmds.extend(
                [
                    SpecCommand("include", f'"{includeDir}/{sceneSegmentName}_main.o"'),
                    SpecCommand("include", f'"{includeDir}/{sceneSegmentName}_col.o"'),
                ]
            )

            if hasSceneTex:
                sceneCmds.append(SpecCommand("include", f'"{includeDir}/{sceneSegmentName}_tex.o"'))

            if hasSceneCS:
                for i in range(csTotal):
                    sceneCmds.append(SpecCommand("include", f'"{includeDir}/{sceneSegmentName}_cs_{i}.o"'))

        sceneCmds.append(SpecCommand("number", "2"))
        specFile.append(SpecEntry(sceneCmds))

        # rooms
        for i in range(roomTotal):
            roomSegmentName = f"{sceneName}_room_{i}"

            roomCmds = [
                SpecCommand("name", f'"{roomSegmentName}"'),
                SpecCommand("compress"),
                SpecCommand("romalign", "0x1000"),
            ]

            if isSingleFile:
                roomCmds.append(SpecCommand("include", f'"{includeDir}/{roomSegmentName}.o"'))
            else:
                roomCmds.extend(
                    [
                        SpecCommand("include", f'"{includeDir}/{roomSegmentName}_main.o"'),
                        SpecCommand("include", f'"{includeDir}/{roomSegmentName}_model_info.o"'),
                        SpecCommand("include", f'"{includeDir}/{roomSegmentName}_model.o"'),
                    ]
                )

            roomCmds.append(SpecCommand("number", "3"))
            specFile.append(SpecEntry(roomCmds))

        # finally, write the spec file
        get_spec_path(exportPath).write_text(specFile.to_c(), encoding="utf-8", newline="\n")
