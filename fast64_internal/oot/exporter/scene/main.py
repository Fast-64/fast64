from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from mathutils import Matrix
from bpy.types import Object
from ....utility import PluginError, CData, indent
from ....f3d.f3d_gbi import TextureExportSettings, ScrollMethod
from ...scene.properties import OOTSceneHeaderProperty
from ...oot_model_classes import OOTModel, OOTGfxFormatter
from ..classes import SceneFile
from ..base import Base, altHeaderList
from ..collision import CollisionHeader
from .header import SceneAlternateHeader, SceneHeader

if TYPE_CHECKING:
    from ..room import Room


@dataclass
class Scene(Base):
    """This class defines a scene"""

    sceneObj: Object
    transform: Matrix
    useMacros: bool
    name: str = None
    model: OOTModel = None
    headerIndex: int = None
    mainHeader: SceneHeader = None
    altHeader: SceneAlternateHeader = None
    roomList: list["Room"] = field(default_factory=list)
    roomListName: str = None
    colHeader: CollisionHeader = None
    hasAlternateHeaders: bool = False

    def __post_init__(self):
        self.roomListName = f"{self.name}_roomList"
        self.hasAlternateHeaders = self.altHeader is not None

    def validateRoomIndices(self):
        """Checks if there are multiple rooms with the same room index"""

        for i, room in enumerate(self.roomList):
            if i != room.roomIndex:
                return False
        return True

    def validateScene(self):
        """Performs safety checks related to the scene data"""

        if not len(self.roomList) > 0:
            raise PluginError("ERROR: This scene does not have any rooms!")

        if not self.validateRoomIndices():
            raise PluginError("ERROR: Room indices do not have a consecutive list of indices.")

    def getSceneHeaderFromIndex(self, headerIndex: int) -> SceneHeader | None:
        """Returns the scene header based on the header index"""

        if headerIndex == 0:
            return self.mainHeader

        for i, header in enumerate(altHeaderList, 1):
            if headerIndex == i:
                return getattr(self.altHeader, header)

        for i, csHeader in enumerate(self.altHeader.cutscenes, 4):
            if headerIndex == i:
                return csHeader

        return None

    def getNewCollisionHeader(self):
        """Returns and creates collision data"""

        return CollisionHeader(
            self.sceneObj,
            self.transform,
            self.useMacros,
            f"{self.name}_collisionHeader",
            self.name,
        )

    def getNewSceneHeader(self, headerProp: OOTSceneHeaderProperty, headerIndex: int = 0):
        """Returns the scene header"""

        self.headerIndex = headerIndex
        return SceneHeader(
            headerProp, f"{self.name}_header{self.headerIndex:02}", self.sceneObj, self.transform, headerIndex
        )

    def getRoomListCmd(self):
        return indent + f"SCENE_CMD_ROOM_LIST({len(self.roomList)}, {self.roomListName}),\n"

    def getCmdList(self, curHeader: SceneHeader, hasAltHeaders: bool):
        cmdListData = CData()
        listName = f"SceneCmd {curHeader.name}"

        # .h
        cmdListData.header = f"extern {listName}[]" + ";\n"

        # .c
        cmdListData.source = (
            (f"{listName}[]" + " = {\n")
            + (self.getAltHeaderListCmd(self.altHeader.name) if hasAltHeaders else "")
            + self.colHeader.getCmd()
            + self.getRoomListCmd()
            + curHeader.infos.getCmds(curHeader.lighting)
            + curHeader.lighting.getCmd()
            + curHeader.path.getCmd()
            + (curHeader.transitionActors.getCmd() if len(curHeader.transitionActors.entries) > 0 else "")
            + curHeader.spawns.getCmd()
            + curHeader.entranceActors.getCmd()
            + (curHeader.exits.getCmd() if len(curHeader.exits.exitList) > 0 else "")
            # + (curHeader.cutscene.getCmd() if curHeader.cutscene.writeCutscene else "")
            + self.getEndCmd()
            + "};\n\n"
        )

        return cmdListData

    def getRoomListC(self):
        """Returns the ``CData`` containing the room list array"""

        roomList = CData()
        listName = f"RomFile {self.roomListName}[]"

        # generating segment rom names for every room
        segNames = []
        for i in range(len(self.roomList)):
            roomName = self.roomList[i].name
            segNames.append((f"_{roomName}SegmentRomStart", f"_{roomName}SegmentRomEnd"))

        # .h
        roomList.header += f"extern {listName};\n"

        if not self.mainHeader.infos.useDummyRoomList:
            # Write externs for rom segments
            roomList.header += "".join(
                f"extern u8 {startName}[];\n" + f"extern u8 {stopName}[];\n" for startName, stopName in segNames
            )

        # .c
        roomList.source = listName + " = {\n"

        if self.mainHeader.infos.useDummyRoomList:
            roomList.source = (
                "// Dummy room list\n" + roomList.source + ((indent + "{ NULL, NULL },\n") * len(self.roomList))
            )
        else:
            roomList.source += (
                " },\n".join(
                    indent + "{ " + f"(uintptr_t){startName}, (uintptr_t){stopName}" for startName, stopName in segNames
                )
                + " },\n"
            )

        roomList.source += "};\n\n"
        return roomList

    def getSceneMainC(self):
        """Returns the main informations of the scene as ``CData``"""

        sceneC = CData()
        headers: list[tuple[SceneHeader, str]] = []
        altHeaderPtrs = None

        if self.hasAlternateHeaders:
            headers = [
                (self.altHeader.childNight, "Child Night"),
                (self.altHeader.adultDay, "Adult Day"),
                (self.altHeader.adultNight, "Adult Night"),
            ]

            for i, csHeader in enumerate(self.altHeader.cutscenes):
                headers.append((csHeader, f"Cutscene No. {i + 1}"))

            altHeaderPtrs = "\n".join(
                indent + curHeader.name + "," if curHeader is not None else indent + "NULL," if i < 4 else ""
                for i, (curHeader, _) in enumerate(headers, 1)
            )

        headers.insert(0, (self.mainHeader, "Child Day (Default)"))
        for i, (curHeader, headerDesc) in enumerate(headers):
            if curHeader is not None:
                sceneC.source += "/**\n * " + f"Header {headerDesc}\n" + "*/\n"
                sceneC.append(self.getCmdList(curHeader, i == 0 and self.hasAlternateHeaders))

                if i == 0:
                    if self.hasAlternateHeaders and altHeaderPtrs is not None:
                        altHeaderListName = f"SceneCmd* {self.altHeader.name}[]"
                        sceneC.header += f"extern {altHeaderListName};\n"
                        sceneC.source += altHeaderListName + " = {\n" + altHeaderPtrs + "\n};\n\n"

                    # Write the room segment list
                    sceneC.append(self.getRoomListC())

                sceneC.append(curHeader.getC())

        return sceneC

    def getSceneCutscenesC(self):
        """Returns the cutscene informations of the scene as ``CData`` (unfinished)"""

        # will be implemented when PR #208 is merged
        csDataList: list[CData] = []
        return csDataList

    def getSceneTexturesC(self, textureExportSettings: TextureExportSettings):
        """
        Writes the textures and material setup displaylists that are shared between multiple rooms
        (is written to the scene)
        """

        return self.model.to_c(textureExportSettings, OOTGfxFormatter(ScrollMethod.Vertex)).all()

    def getNewSceneFile(self, path: str, isSingleFile: bool, textureExportSettings: TextureExportSettings):
        """Gets and sets C data for every scene elements"""

        sceneMainData = self.getSceneMainC()
        sceneCollisionData = self.colHeader.getC()
        sceneCutsceneData = self.getSceneCutscenesC()
        sceneTexturesData = self.getSceneTexturesC(textureExportSettings)

        return SceneFile(
            self.name,
            sceneMainData.source,
            sceneCollisionData.source,
            [cs.source for cs in sceneCutsceneData],
            sceneTexturesData.source,
            {room.roomIndex: room.getNewRoomFile(path, isSingleFile, textureExportSettings) for room in self.roomList},
            isSingleFile,
            path,
            (
                f"#ifndef {self.name.upper()}_H\n"
                + f"#define {self.name.upper()}_H\n\n"
                + sceneMainData.header
                + "".join(cs.header for cs in sceneCutsceneData)
                + sceneCollisionData.header
                + sceneTexturesData.header
            ),
        )
