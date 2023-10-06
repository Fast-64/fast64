from dataclasses import dataclass
from mathutils import Matrix
from bpy.types import Object
from ....utility import CData, indent
from ....f3d.f3d_gbi import ScrollMethod, TextureExportSettings
from ...room.properties import OOTRoomHeaderProperty
from ...oot_constants import ootData
from ...oot_level_classes import OOTRoomMesh
from ...oot_model_classes import OOTModel, OOTGfxFormatter
from ..classes import RoomFile
from ..base import Base, altHeaderList
from .header import RoomAlternateHeader, RoomHeader
from .shape import RoomShape


@dataclass
class Room(Base):
    """This class defines a room"""

    name: str
    transform: Matrix
    sceneObj: Object
    roomObj: Object
    roomShapeType: str
    model: OOTModel
    roomIndex: int

    headerIndex: int = None
    mainHeader: RoomHeader = None
    altHeader: RoomAlternateHeader = None
    mesh: OOTRoomMesh = None
    roomShape: RoomShape = None
    hasAlternateHeaders: bool = False

    def __post_init__(self):
        self.mesh = OOTRoomMesh(self.name, self.roomShapeType, self.model)
        self.hasAlternateHeaders = self.altHeader is not None

    def getRoomHeaderFromIndex(self, headerIndex: int) -> RoomHeader | None:
        """Returns the current room header based on the header index"""

        if headerIndex == 0:
            return self.mainHeader

        for i, header in enumerate(altHeaderList, 1):
            if headerIndex == i:
                return getattr(self.altHeader, header)

        for i, csHeader in enumerate(self.altHeader.cutscenes, 4):
            if headerIndex == i:
                return csHeader

        return None

    def getNewRoomHeader(self, headerProp: OOTRoomHeaderProperty, headerIndex: int = 0):
        """Returns a new room header with the informations from the scene empty object"""

        self.headerIndex = headerIndex
        return RoomHeader(
            f"{self.name}_header{self.headerIndex:02}",
            headerProp,
            self.sceneObj,
            self.roomObj,
            self.transform,
            self.headerIndex,
        )

    def getNewRoomShape(self, headerProp: OOTRoomHeaderProperty, sceneName: str):
        """Returns a new room shape"""

        return RoomShape(self.roomShapeType, headerProp, self.mesh, sceneName, self.name)

    def getCmdList(self, curHeader: RoomHeader, hasAltHeaders: bool):
        cmdListData = CData()
        listName = f"SceneCmd {curHeader.name}"

        # .h
        cmdListData.header = f"extern {listName}[];\n"

        # .c
        cmdListData.source = (
            (f"{listName}[]" + " = {\n")
            + (self.getAltHeaderListCmd(self.altHeader.name) if hasAltHeaders else "")
            + self.roomShape.getCmd()
            + curHeader.infos.getCmds()
            + (curHeader.objects.getCmd() if len(curHeader.objects.objectList) > 0 else "")
            + (curHeader.actors.getCmd() if len(curHeader.actors.actorList) > 0 else "")
            + self.getEndCmd()
            + "};\n\n"
        )

        return cmdListData

    def getRoomMainC(self):
        """Returns the C data of the main informations of a room"""

        roomC = CData()
        roomHeaders: list[tuple[RoomHeader, str]] = []
        altHeaderPtrList = None

        if self.hasAlternateHeaders:
            roomHeaders: list[tuple[RoomHeader, str]] = [
                (self.altHeader.childNight, "Child Night"),
                (self.altHeader.adultDay, "Adult Day"),
                (self.altHeader.adultNight, "Adult Night"),
            ]

            for i, csHeader in enumerate(self.altHeader.cutscenes):
                roomHeaders.append((csHeader, f"Cutscene No. {i + 1}"))

            altHeaderPtrListName = f"SceneCmd* {self.altHeader.name}"

            # .h
            roomC.header = f"extern {altHeaderPtrListName}[];\n"

            # .c
            altHeaderPtrList = (
                f"{altHeaderPtrListName}[]"
                + " = {\n"
                + "\n".join(
                    indent + f"{curHeader.name}," if curHeader is not None else indent + "NULL,"
                    for (curHeader, _) in roomHeaders
                )
                + "\n};\n\n"
            )

        roomHeaders.insert(0, (self.mainHeader, "Child Day (Default)"))
        for i, (curHeader, headerDesc) in enumerate(roomHeaders):
            if curHeader is not None:
                roomC.source += "/**\n * " + f"Header {headerDesc}\n" + "*/\n"
                roomC.source += curHeader.getHeaderDefines()
                roomC.append(self.getCmdList(curHeader, i == 0 and self.hasAlternateHeaders))

                if i == 0 and self.hasAlternateHeaders and altHeaderPtrList is not None:
                    roomC.source += altHeaderPtrList

                if len(curHeader.objects.objectList) > 0:
                    roomC.append(curHeader.objects.getC())

                if len(curHeader.actors.actorList) > 0:
                    roomC.append(curHeader.actors.getC())

        return roomC

    def getRoomShapeModelC(self, textureSettings: TextureExportSettings):
        """Returns the C data of the room model"""
        roomModel = CData()

        for i, entry in enumerate(self.mesh.meshEntries):
            if entry.DLGroup.opaque is not None:
                roomModel.append(entry.DLGroup.opaque.to_c(self.mesh.model.f3d))

            if entry.DLGroup.transparent is not None:
                roomModel.append(entry.DLGroup.transparent.to_c(self.mesh.model.f3d))

            # type ``ROOM_SHAPE_TYPE_IMAGE`` only allows 1 room
            if i == 0 and self.mesh.roomShape == "ROOM_SHAPE_TYPE_IMAGE":
                break

        roomModel.append(self.mesh.model.to_c(textureSettings, OOTGfxFormatter(ScrollMethod.Vertex)).all())

        if self.roomShape.multiImg is not None:
            roomModel.append(self.roomShape.multiImg.getC())
            roomModel.append(self.roomShape.getRoomShapeBgImgDataC(self.mesh, textureSettings))

        return roomModel

    def getNewRoomFile(self, path: str, isSingleFile: bool, textureExportSettings: TextureExportSettings):
        """Returns a new ``RoomFile`` element"""

        roomMainData = self.getRoomMainC()
        roomModelData = self.getRoomShapeModelC(textureExportSettings)
        roomModelInfoData = self.roomShape.getRoomShapeC()

        return RoomFile(
            self.name,
            roomMainData.source,
            roomModelData.source,
            roomModelInfoData.source,
            isSingleFile,
            path,
            roomMainData.header + roomModelData.header + roomModelInfoData.header,
        )
