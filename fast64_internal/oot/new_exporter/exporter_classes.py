import os

from dataclasses import dataclass, field
from ...utility import writeFile
from .common import includeData


@dataclass
class RoomFile:
    """This class hosts the C data for every room files"""

    name: str
    roomMain: str = None
    roomModel: str = None
    roomModelInfo: str = None
    singleFileExport: bool = False
    path: str = None

    header: str = ""

    def write(self):
        if self.singleFileExport:
            roomMainPath = f"{self.name}.c"
            self.roomMain += self.roomModelInfo + self.roomModel
        else:
            roomMainPath = f"{self.name}_main.c"
            writeFile(os.path.join(self.path, f"{self.name}_model_info.c"), self.roomModelInfo)
            writeFile(os.path.join(self.path, f"{self.name}_model.c"), self.roomModel)

        writeFile(os.path.join(self.path, roomMainPath), self.roomMain)


@dataclass
class SceneFile:
    """This class hosts the C data for every scene files"""

    name: str
    sceneMain: str = None
    sceneCollision: str = None
    sceneCutscenes: list[str] = field(default_factory=list)
    sceneTextures: str = None
    roomList: dict[int, RoomFile] = field(default_factory=dict)
    singleFileExport: bool = False
    path: str = None
    header: str = ""

    hasCutscenes: bool = False
    hasSceneTextures: bool = False

    def __post_init__(self):
        self.hasCutscenes = len(self.sceneCutscenes) > 0
        self.hasSceneTextures = len(self.sceneTextures) > 0

    def setIncludeData(self):
        """Adds includes at the beginning of each file to write"""

        suffix = "\n\n"
        sceneInclude = f'\n#include "{self.name}.h"\n'
        common = includeData["common"]
        # room = includeData["roomMain"]
        # roomShapeInfo = includeData["roomShapeInfo"]
        # scene = includeData["sceneMain"]
        # collision = includeData["collision"]
        # cutscene = includeData["cutscene"]
        room = ""
        roomShapeInfo = ""
        scene = ""
        collision = ""
        cutscene = ""

        common = (
            '#include "ultra64.h"\n'
            + '#include "z64.h"\n'
            + '#include "macros.h"\n'
            + '#include "segment_symbols.h"\n'
            + '#include "command_macros_base.h"\n'
            + '#include "z64cutscene_commands.h"\n'
            + '#include "variables.h"\n'
        )

        for roomData in self.roomList.values():
            if self.singleFileExport:
                common += room + roomShapeInfo + sceneInclude
                roomData.roomMain = common + suffix + roomData.roomMain
            else:
                roomData.roomMain = common + room + sceneInclude + suffix + roomData.roomMain
                roomData.roomModelInfo = common + roomShapeInfo + sceneInclude + suffix + roomData.roomModelInfo
                roomData.roomModel = common + sceneInclude + suffix + roomData.roomModel

        if self.singleFileExport:
            common += scene + collision + cutscene + sceneInclude
            self.sceneMain = common + suffix + self.sceneMain
        else:
            self.sceneMain = common + scene + sceneInclude + suffix + self.sceneMain
            self.sceneCollision = common + collision + sceneInclude + suffix + self.sceneCollision

            if self.hasCutscenes:
                for cs in self.sceneCutscenes:
                    cs = cutscene + sceneInclude + suffix + cs

    def write(self):
        self.setIncludeData()

        for room in self.roomList.values():
            self.header += room.header
            room.write()

        if self.singleFileExport:
            sceneMainPath = f"{self.name}.c"
            self.sceneMain += self.sceneCollision
            if self.hasCutscenes:
                for i, cs in enumerate(self.sceneCutscenes):
                    self.sceneMain += cs
        else:
            sceneMainPath = f"{self.name}_main.c"
            writeFile(os.path.join(self.path, f"{self.name}_col.c"), self.sceneCollision)
            if self.hasCutscenes:
                for i, cs in enumerate(self.sceneCutscenes):
                    writeFile(os.path.join(self.path, f"{self.name}_cs_{i}.c"), cs)

        if self.hasSceneTextures:
            writeFile(os.path.join(self.path, f"{self.name}_tex.c"), self.sceneTextures)

        writeFile(os.path.join(self.path, sceneMainPath), self.sceneMain)

        self.header += "\n#endif\n"
        writeFile(os.path.join(self.path, f"{self.name}.h"), self.header)
