import os
import bpy

from dataclasses import dataclass, field
from typing import Optional
from .....utility import PluginError, writeFile, indent
from ....oot_utility import ExportInfo, getSceneDirFromLevelName
from ....oot_level_classes import OOTScene


@dataclass
class SpecEntry:
    """Defines an entry of ``spec``"""

    original: Optional[list[str]]  # the original lines from the parsed file
    segmentName: str = ""
    isCompressed: bool = False
    romalign: Optional[str] = None
    number: Optional[int] = None
    files: list[tuple[str, str, str]] = field(default_factory=list)  # (prefix, command, file)
    address: Optional[str] = None
    after: Optional[str] = None
    align: Optional[str] = None
    flags: Optional[str] = None
    pad_text: Optional[str] = None
    prefix: str = ""
    suffix: Optional[str] = None
    contentSuffix: Optional[str] = None

    def __post_init__(self):
        if self.prefix == "\n":
            self.prefix = ""

        if self.original is not None:
            prefix = ""
            content = None
            for line in self.original:
                line = line.strip()
                if not line.startswith("#") and not "pad_text" in line and line != "\n":
                    split = line.split(" ")
                    command = split[0]
                    if len(split) > 2:
                        content = " ".join(elem for i, elem in enumerate(split) if i > 0)
                    elif len(split) > 1:
                        content = split[1]
                    match command:
                        case "compress":
                            self.isCompressed = True
                        case "name" | "after" | "flags" | "align" | "address" | "romalign":
                            if content is not None:
                                setattr(self, "segmentName" if command == "name" else command, content)
                        case "include" | "include_data_with_rodata":
                            if content is not None:
                                self.files.append(
                                    (
                                        (prefix + ("\n" if len(prefix) > 0 else "")) if prefix != "\n" else "",
                                        command,
                                        content,
                                    )
                                )
                        case "number":
                            if content is not None:
                                self.number = int(content)
                        case _:
                            raise PluginError(f"ERROR: Unknown spec command: `{command}`")
                    prefix = ""
                else:
                    prefix += (indent if "pad_text" in line else "") + line
            if len(prefix) > 0:
                self.contentSuffix = f"{prefix}\n"

    def to_c(self):
        return (
            self.prefix
            + "beginseg\n"
            + f"".join(
                (
                    (indent + f"name {self.segmentName}\n"),
                    (indent + "compress\n" if self.isCompressed else ""),
                    (indent + f"after {self.after}\n" if self.after is not None else ""),
                    (indent + f"flags {self.flags}\n" if self.flags is not None else ""),
                    (indent + f"align {self.align}\n" if self.align is not None else ""),
                    (indent + f"address {self.address}\n" if self.address is not None else ""),
                    (indent + f"romalign {self.romalign}\n" if self.romalign is not None else ""),
                    "".join(prefix + indent + f"{command} {file}\n" for prefix, command, file in self.files),
                    (indent + f"number {self.number}\n" if self.number is not None else ""),
                )
            )
            + (self.contentSuffix if self.contentSuffix is not None else "")
            + "endseg"
            + ("\n" + self.suffix if self.suffix is not None else "")
        )


@dataclass
class SpecFile:
    exportPath: str
    # exportName: Optional[str]
    exportInfo: ExportInfo
    scene: OOTScene
    cutsceneTotal: int
    isSingleFile: bool
    entries: list[SpecEntry] = field(default_factory=list)

    def __post_init__(self):
        # read the file's data
        try:
            with open(os.path.join(self.exportPath, "spec"), "r") as fileData:
                # data = fileData.read()
                # fileData.seek(0)
                lines = fileData.readlines()
        except FileNotFoundError:
            raise PluginError("ERROR: Can't find spec!")

        # parse the entries and populate the list of entries (``self.entries``)
        prefix = ""
        parsedLines = []
        assert len(lines) > 0
        for line in lines:
            # skip the lines before an entry, create one from the file's data
            # and add the skipped lines as a prefix of the current entry
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
                # else, if between 2 segments and the line is a preprocessor command
                prefix += line
        self.entries[-1].suffix = prefix.removesuffix("\n")

    def find(self, segmentName: str):
        for i, entry in enumerate(self.entries):
            if entry.segmentName == segmentName:
                return self.entries[i]
        return None

    def append(self, entry: SpecEntry):
        self.entries.append(entry)

    def remove(self, segmentName: str):
        entry = self.find(segmentName)
        if entry is not None:
            lastEntry = self.entries[self.entries.index(entry) - 1]
            if len(entry.prefix) > 0 and entry.prefix != "\n":
                lastEntry.suffix = (lastEntry.suffix if lastEntry.suffix is not None else "") + entry.prefix[:-2]
            self.entries.remove(entry)

    def to_c(self):
        return (
            "".join(
                (("\n" * (1 if len(entry.prefix) > 0 else 2)) if i > 0 else "") + entry.to_c()
                for i, entry in enumerate(self.entries)
            )
            + "\n"
        )


def editSpecFile(
    scene: Optional[OOTScene], exportInfo: ExportInfo, hasSceneTextures: bool, hasSceneCutscenes: bool, csTotal: int
):
    specFile = SpecFile(
        exportInfo.exportPath,
        exportInfo,
        scene,
        csTotal,
        bpy.context.scene.ootSceneExportSettings.singleFile,
    )

    sceneName = scene.name if scene is not None else exportInfo.name
    segmentName = f"{sceneName}_scene"
    specFile.remove(f'"{segmentName}"')
    for entry in specFile.entries:
        if entry.segmentName.startswith(f'"{sceneName}'):
            specFile.remove(entry.segmentName)

    if scene is not None:
        includeDir = "$(BUILD_DIR)/"
        if exportInfo.customSubPath is not None:
            includeDir += f"{exportInfo.customSubPath + sceneName}"
        else:
            includeDir += f"{getSceneDirFromLevelName(sceneName)}"

        if specFile.isSingleFile:
            files = [("", "include", f'"{includeDir}/{segmentName}.o"')]
        else:
            files = [
                ("", "include", f'"{includeDir}/{segmentName}_main.o"'),
                ("", "include", f'"{includeDir}/{segmentName}_col.o"'),
            ]

            if hasSceneTextures:
                files.append(("", "include", f'"{includeDir}/{segmentName}_tex.o"'))

            if hasSceneCutscenes:
                for i in range(specFile.cutsceneTotal):
                    files.append(("", "include", f'"{includeDir}/{segmentName}_cs_{i}.o"'))

        specFile.append(SpecEntry(None, f'"{segmentName}"', True, "0x1000", 2, files))

        for i in range(len(scene.rooms)):
            segmentName = f"{sceneName}_room_{i}"

            if specFile.isSingleFile:
                files = [("", "include", f'"{includeDir}/{segmentName}.o"')]
            else:
                files = [
                    ("", "include", f'"{includeDir}/{segmentName}_main.o"'),
                    ("", "include", f'"{includeDir}/{segmentName}_model_info.o"'),
                    ("", "include", f'"{includeDir}/{segmentName}_model.o"'),
                ]

            specFile.append(SpecEntry(None, f'"{segmentName}"', True, "0x1000", 3, files))

    writeFile(os.path.join(exportInfo.exportPath, "spec"), specFile.to_c())
