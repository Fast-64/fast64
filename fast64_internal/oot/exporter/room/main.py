from dataclasses import dataclass
from typing import Optional
from mathutils import Matrix
from bpy.types import Object
from ....utility import PluginError, CData, indent, readFile, writeFile
from ....f3d.f3d_gbi import ScrollMethod, TextureExportSettings
from ...room.properties import OOTRoomHeaderProperty
from ...oot_object import addMissingObjectsToAllRoomHeaders
from ...oot_level_classes import OOTRoomMesh
from ...oot_model_classes import OOTModel, OOTGfxFormatter
from ...oot_utility import CullGroup
from ..file import RoomFile
from ..utility import Utility, altHeaderList
from .header import RoomAlternateHeader, RoomHeader
from .shape import RoomShape
from .mesh import ootProcessMesh, BoundingBox


@dataclass
class Room:
    """This class defines a room"""

    name: str
    roomIndex: int
    mainHeader: Optional[RoomHeader]
    altHeader: Optional[RoomAlternateHeader]
    mesh: Optional[OOTRoomMesh]
    roomShape: Optional[RoomShape]
    hasAlternateHeaders: bool

    @staticmethod
    def new(
        name: str,
        transform: Matrix,
        sceneObj: Object,
        roomObj: Object,
        roomShapeType: str,
        model: OOTModel,
        roomIndex: int,
        sceneName: str,
        saveTexturesAsPNG: bool,
    ):
        i = 0
        mainHeaderProps = roomObj.ootRoomHeader
        altHeader = RoomAlternateHeader(f"{name}_alternateHeaders")
        altProp = roomObj.ootAlternateRoomHeaders

        if mainHeaderProps.roomShape == "ROOM_SHAPE_TYPE_IMAGE" and len(mainHeaderProps.bgImageList) == 0:
            raise PluginError(f'Room {roomObj.name} uses room shape "Image" but doesn\'t have any BG images.')

        if mainHeaderProps.roomShape == "ROOM_SHAPE_TYPE_IMAGE" and roomIndex >= 1:
            raise PluginError(f'Room shape "Image" can only have one room in the scene.')

        mainHeader = RoomHeader.new(
            f"{name}_header{i:02}",
            mainHeaderProps,
            sceneObj,
            roomObj,
            transform,
            i,
        )
        hasAlternateHeaders = False

        for i, header in enumerate(altHeaderList, 1):
            altP: OOTRoomHeaderProperty = getattr(altProp, f"{header}Header")
            if not altP.usePreviousHeader:
                hasAlternateHeaders = True
                newRoomHeader = RoomHeader.new(
                    f"{name}_header{i:02}",
                    altP,
                    sceneObj,
                    roomObj,
                    transform,
                    i,
                )
                setattr(altHeader, header, newRoomHeader)

        altHeader.cutscenes = [
            RoomHeader.new(
                f"{name}_header{i:02}",
                csHeader,
                sceneObj,
                roomObj,
                transform,
                i,
            )
            for i, csHeader in enumerate(altProp.cutsceneHeaders, 4)
        ]

        hasAlternateHeaders = True if len(altHeader.cutscenes) > 0 else hasAlternateHeaders
        altHeader = altHeader if hasAlternateHeaders else None
        headers: list[RoomHeader] = [mainHeader]
        if altHeader is not None:
            headers.extend([altHeader.childNight, altHeader.adultDay, altHeader.adultNight])
            if len(altHeader.cutscenes) > 0:
                headers.extend(altHeader.cutscenes)
        addMissingObjectsToAllRoomHeaders(roomObj, headers)

        # Mesh stuff
        mesh = OOTRoomMesh(name, roomShapeType, model)
        pos, _, scale, _ = Utility.getConvertedTransform(transform, sceneObj, roomObj, True)
        cullGroup = CullGroup(pos, scale, roomObj.ootRoomHeader.defaultCullDistance)
        DLGroup = mesh.addMeshGroup(cullGroup).DLGroup
        boundingBox = BoundingBox()
        ootProcessMesh(
            mesh,
            DLGroup,
            sceneObj,
            roomObj,
            transform,
            not saveTexturesAsPNG,
            None,
            boundingBox,
        )
        cullGroup.position, cullGroup.cullDepth = boundingBox.getEnclosingSphere()
        mesh.terminateDLs()
        mesh.removeUnusedEntries()
        roomShape = RoomShape.new(roomShapeType, mainHeaderProps, mesh, sceneName, name)
        return Room(name, roomIndex, mainHeader, altHeader, mesh, roomShape, hasAlternateHeaders)

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

    def getCmdList(self, curHeader: RoomHeader, hasAltHeaders: bool):
        """Returns the room commands list"""

        cmdListData = CData()
        listName = f"SceneCmd {curHeader.name}"

        # .h
        cmdListData.header = f"extern {listName}[];\n"

        # .c
        cmdListData.source = (
            (f"{listName}[]" + " = {\n")
            + (Utility.getAltHeaderListCmd(self.altHeader.name) if hasAltHeaders else "")
            + self.roomShape.getCmd()
            + curHeader.infos.getCmds()
            + (curHeader.objects.getCmd() if len(curHeader.objects.objectList) > 0 else "")
            + (curHeader.actors.getCmd() if len(curHeader.actors.actorList) > 0 else "")
            + Utility.getEndCmd()
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
