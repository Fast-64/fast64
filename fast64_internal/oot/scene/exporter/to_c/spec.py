import os
import bpy
import enum

from dataclasses import dataclass, field
from typing import Optional
from .....utility import PluginError, writeFile, indent
from ....oot_utility import ExportInfo, getSceneDirFromLevelName


class CommandType(enum.Enum):
    """This class defines the different spec command types"""

    NAME = 0
    COMPRESS = 1
    AFTER = 2
    FLAGS = 3
    ALIGN = 4
    ADDRESS = 5
    ROMALIGN = 6
    INCLUDE = 7
    INCLUDE_DATA_WITH_RODATA = 8
    NUMBER = 9
    PAD_TEXT = 10

    @staticmethod
    def from_string(value: str):
        """Returns one of the enum values from a string"""

        cmdType = CommandType._member_map_.get(value.upper())
        if cmdType is None:
            raise PluginError(f"ERROR: Can't find value: ``{value}`` in the enum!")
        return cmdType


@dataclass
class SpecEntryCommand:
    """This class defines a single spec command"""

    type: CommandType
    content: str = ""
    prefix: str = ""
    suffix: str = ""

    def to_c(self):
        return self.prefix + indent + f"{self.type.name.lower()} {self.content}".strip() + self.suffix + "\n"


@dataclass
class SpecEntry:
    """Defines an entry of ``spec``"""

    original: Optional[list[str]] = field(default_factory=list)  # the original lines from the parsed file
    commands: list[SpecEntryCommand] = field(default_factory=list)  # list of the different spec commands
    segmentName: str = ""  # the name of the current segment
    prefix: str = ""  # data between two commands
    suffix: str = ""  # remaining data after the entry (used for the last entry)
    contentSuffix: str = ""  # remaining data after the last command in the current entry

    def __post_init__(self):
        if self.original is not None:
            # parse the commands from the existing data
            prefix = ""
            for line in self.original:
                line = line.strip()
                dontHaveComments = (
                    not line.startswith("// ") and not line.startswith("/* ") and not line.startswith(" */")
                )

                if line != "\n":
                    if not line.startswith("#") and dontHaveComments:
                        split = line.split(" ")
                        command = split[0]
                        if len(split) > 2:
                            content = " ".join(elem for i, elem in enumerate(split) if i > 0)
                        elif len(split) > 1:
                            content = split[1]
                        elif command == "name":
                            content = self.segmentName
                        else:
                            content = ""

                        self.commands.append(
                            SpecEntryCommand(
                                CommandType.from_string(command),
                                content,
                                (prefix + ("\n" if len(prefix) > 0 else "")) if prefix != "\n" else "",
                            )
                        )
                        prefix = ""
                    else:
                        prefix += (f"\n{indent}" if not dontHaveComments else "") + line
            # if there's a prefix it's the remaining data after the last entry
            if len(prefix) > 0:
                self.contentSuffix = prefix

        if len(self.segmentName) == 0 and len(self.commands[0].content) > 0:
            self.segmentName = self.commands[0].content
        else:
            raise PluginError("ERROR: The segment name can't be set!")

    def to_c(self):
        return (
            (self.prefix if len(self.prefix) > 0 else "\n")
            + "beginseg\n"
            + "".join(cmd.to_c() for cmd in self.commands)
            + (f"{self.contentSuffix}\n" if len(self.contentSuffix) > 0 else "")
            + "endseg"
            + (self.suffix if self.suffix == "\n" else f"\n{self.suffix}\n" if len(self.suffix) > 0 else "")
        )


@dataclass
class SpecFile:
    """This class defines the spec's file data"""

    exportPath: str  # path to the spec file
    entries: list[SpecEntry] = field(default_factory=list)  # list of the different spec entries

    def __post_init__(self):
        # read the file's data
        try:
            with open(self.exportPath, "r") as fileData:
                lines = fileData.readlines()
        except FileNotFoundError:
            raise PluginError("ERROR: Can't find spec!")

        prefix = ""
        parsedLines = []
        assert len(lines) > 0
        for line in lines:
            # if we're inside a spec entry or if the lines between two entries do not contains these characters
            # fill the ``parsedLine`` list if it's inside a segment
            # when we reach the end of the current segment add a new ``SpecEntry`` to ``self.entries``
            isNotEmptyOrNewline = len(line) > 0 and line != "\n"
            if (
                len(parsedLines) > 0
                or not line.startswith(" *")
                and "/*\n" not in line
                and not line.startswith("#")
                and isNotEmptyOrNewline
            ):
                if "beginseg" not in line and "endseg" not in line:
                    # if inside a segment, between beginseg and endseg
                    parsedLines.append(line)
                elif "endseg" in line:
                    # else, if the line has endseg in it (> if we reached the end of the current segment)
                    entry = SpecEntry(parsedLines, prefix=prefix)
                    self.entries.append(entry)
                    prefix = ""
                    parsedLines = []
            else:
                # else, if between 2 segments and the line is something we don't need
                prefix += line
        # set the last's entry's suffix to the remaining prefix
        self.entries[-1].suffix = prefix.removesuffix("\n")

    def find(self, segmentName: str):
        """Returns an entry from a segment name, returns ``None`` if nothing was found"""

        for i, entry in enumerate(self.entries):
            if entry.segmentName == segmentName:
                return self.entries[i]
        return None

    def append(self, entry: SpecEntry):
        """Appends an entry to the list"""

        # prefix/suffix shenanigans
        lastEntry = self.entries[-1]
        if len(lastEntry.suffix) > 0:
            entry.prefix = f"{lastEntry.suffix}\n\n"
            lastEntry.suffix = ""
        self.entries.append(entry)

    def remove(self, segmentName: str):
        """Removes an entry from a segment name"""

        # prefix/suffix shenanigans
        entry = self.find(segmentName)
        if entry is not None:
            if len(entry.prefix) > 0 and entry.prefix != "\n":
                lastEntry = self.entries[self.entries.index(entry) - 1]
                lastEntry.suffix = (lastEntry.suffix if lastEntry.suffix is not None else "") + entry.prefix[:-2]
            self.entries.remove(entry)

    def to_c(self):
        return "\n".join(entry.to_c() for entry in self.entries)


def editSpecFile(
    isScene: bool, exportInfo: ExportInfo, hasSceneTex: bool, hasSceneCS: bool, roomTotal: int, csTotal: int
):
    # get the spec's data
    specFile = SpecFile(os.path.join(exportInfo.exportPath, "spec"))

    # get the scene and current segment name and remove the scene
    sceneName = exportInfo.name
    segmentName = f"{sceneName}_scene"
    specFile.remove(f'"{segmentName}"')
    for entry in specFile.entries:
        if entry.segmentName.startswith(f'"{sceneName}_'):
            specFile.remove(entry.segmentName)

    if isScene:
        isSingleFile = bpy.context.scene.ootSceneExportSettings.singleFile
        includeDir = "$(BUILD_DIR)/"
        if exportInfo.customSubPath is not None:
            includeDir += f"{exportInfo.customSubPath + sceneName}"
        else:
            includeDir += f"{getSceneDirFromLevelName(sceneName)}"

        sceneCmds = [
            SpecEntryCommand(CommandType.NAME, f'"{segmentName}"'),
            SpecEntryCommand(CommandType.COMPRESS),
            SpecEntryCommand(CommandType.ROMALIGN, "0x1000"),
        ]

        # scene
        if isSingleFile:
            sceneCmds.append(SpecEntryCommand(CommandType.INCLUDE, f'"{includeDir}/{segmentName}.o"'))
        else:
            sceneCmds.extend(
                [
                    SpecEntryCommand(CommandType.INCLUDE, f'"{includeDir}/{segmentName}_main.o"'),
                    SpecEntryCommand(CommandType.INCLUDE, f'"{includeDir}/{segmentName}_col.o"'),
                ]
            )

            if hasSceneTex:
                sceneCmds.append(SpecEntryCommand(CommandType.INCLUDE, f'"{includeDir}/{segmentName}_tex.o"'))

            if hasSceneCS:
                for i in range(csTotal):
                    sceneCmds.append(SpecEntryCommand(CommandType.INCLUDE, f'"{includeDir}/{segmentName}_cs_{i}.o"'))

        sceneCmds.append(SpecEntryCommand(CommandType.NUMBER, "2"))
        specFile.append(SpecEntry(None, sceneCmds))

        # rooms
        for i in range(roomTotal):
            segmentName = f"{sceneName}_room_{i}"

            roomCmds = [
                SpecEntryCommand(CommandType.NAME, f'"{segmentName}"'),
                SpecEntryCommand(CommandType.COMPRESS),
                SpecEntryCommand(CommandType.ROMALIGN, "0x1000"),
            ]

            if isSingleFile:
                roomCmds.append(SpecEntryCommand(CommandType.INCLUDE, f'"{includeDir}/{segmentName}.o"'))
            else:
                roomCmds.extend(
                    [
                        SpecEntryCommand(CommandType.INCLUDE, f'"{includeDir}/{segmentName}_main.o"'),
                        SpecEntryCommand(CommandType.INCLUDE, f'"{includeDir}/{segmentName}_model_info.o"'),
                        SpecEntryCommand(CommandType.INCLUDE, f'"{includeDir}/{segmentName}_model.o"'),
                    ]
                )

            roomCmds.append(SpecEntryCommand(CommandType.NUMBER, "3"))
            specFile.append(SpecEntry(None, roomCmds))
        specFile.entries[-1].suffix = "\n"

    # finally, write the spec file
    writeFile(specFile.exportPath, specFile.to_c())
