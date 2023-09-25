from dataclasses import dataclass
from bpy.types import Object
from ...utility import PluginError, CData, indent
from ..room.properties import OOTRoomHeaderProperty
from ..oot_constants import ootData
from ..oot_level_classes import OOTRoomMesh
from ..oot_model_classes import OOTModel
from .commands import RoomCommands
from .common import Common, altHeaderList

from .room_shape import (
    RoomShape,
    RoomShapeDLists,
    RoomShapeDListsEntry,
    RoomShapeImageBase,
    RoomShapeImageMulti,
    RoomShapeImageMultiBg,
    RoomShapeImageMultiBgEntry,
    RoomShapeImageSingle,
    RoomShapeNormal,
)

from .room_header import (
    OOTRoomHeader,
    OOTRoomAlternateHeader,
    OOTRoomHeaderInfos,
    OOTRoomHeaderObjects,
    OOTRoomHeaderActors,
)


@dataclass
class OOTRoom(Common, RoomCommands):
    name: str = None
    roomObj: Object = None
    roomShapeType: str = None
    model: OOTModel = None
    headerIndex: int = None
    mainHeader: OOTRoomHeader = None
    altHeader: OOTRoomAlternateHeader = None
    mesh: OOTRoomMesh = None
    roomShape: RoomShape = None

    def __post_init__(self):
        self.mesh = OOTRoomMesh(self.name, self.roomShapeType, self.model)

    def hasAlternateHeaders(self):
        return self.altHeader is not None

    def getRoomHeaderFromIndex(self, headerIndex: int) -> OOTRoomHeader | None:
        if headerIndex == 0:
            return self.mainHeader

        for i, header in enumerate(altHeaderList, 1):
            if headerIndex == i:
                return getattr(self.altHeader, header)

        for i, csHeader in enumerate(self.altHeader.cutscenes, 4):
            if headerIndex == i:
                return csHeader

        return None

    def getMultiBgEntries(self):
        entries: list[RoomShapeImageMultiBgEntry] = []

        for i, bgImg in enumerate(self.mesh.bgImages):
            entries.append(
                RoomShapeImageMultiBgEntry(
                    i, bgImg.name, bgImg.image.size[0], bgImg.image.size[1], bgImg.otherModeFlags
                )
            )

        return entries

    def getDListsEntries(self):
        entries: list[RoomShapeDListsEntry] = []

        for meshGrp in self.mesh.meshEntries:
            entries.append(
                RoomShapeDListsEntry(
                    meshGrp.DLGroup.opaque.name if meshGrp.DLGroup.opaque is not None else "NULL",
                    meshGrp.DLGroup.transparent.name if meshGrp.DLGroup.transparent is not None else "NULL",
                )
            )

        return entries

    def getNewRoomHeader(self, headerProp: OOTRoomHeaderProperty, headerIndex: int = 0):
        """Returns a new room header with the informations from the scene empty object"""

        self.headerIndex = headerIndex
        headerName = f"{self.name}_header{self.headerIndex:02}"

        objIDList = []
        for objProp in headerProp.objectList:
            if objProp.objectKey == "Custom":
                objIDList.append(objProp.objectIDCustom)
            else:
                objIDList.append(ootData.objectData.objectsByKey[objProp.objectKey].id)

        return OOTRoomHeader(
            headerName,
            OOTRoomHeaderInfos(
                headerProp.roomIndex,
                headerProp.roomShape,
                self.getPropValue(headerProp, "roomBehaviour"),
                self.getPropValue(headerProp, "linkIdleMode"),
                headerProp.disableWarpSongs,
                headerProp.showInvisibleActors,
                headerProp.disableSkybox,
                headerProp.disableSunMoon,
                0xFF if headerProp.leaveTimeUnchanged else headerProp.timeHours,
                0xFF if headerProp.leaveTimeUnchanged else headerProp.timeMinutes,
                max(-128, min(127, round(headerProp.timeSpeed * 0xA))),
                headerProp.echo,
                headerProp.setWind,
                [d for d in headerProp.windVector] if headerProp.setWind else None,
                headerProp.windStrength if headerProp.setWind else None,
            ),
            OOTRoomHeaderObjects(f"{headerName}_objectList", objIDList),
            OOTRoomHeaderActors(
                f"{headerName}_actorList",
                self.sceneObj,
                self.roomObj,
                self.transform,
                headerIndex,
            ),
        )

    def getNewRoomShape(self):
        normal = None
        single = None
        multiImg = None
        multi = None
        name = f"{self.name}_shapeHeader"
        dlName = f"{self.name}_shapeDListEntry"

        match self.roomShapeType:
            case "ROOM_SHAPE_TYPE_NORMAL":
                normal = RoomShapeNormal(name, self.roomShapeType, dlName)
            case "ROOM_SHAPE_TYPE_IMAGE":
                if len(self.mesh.bgImages) > 1:
                    multiImg = RoomShapeImageMultiBg(f"{self.name}_shapeMultiBg", self.getMultiBgEntries())
                    multi = RoomShapeImageMulti(
                        name, self.roomShapeType, "ROOM_SHAPE_IMAGE_AMOUNT_MULTI", dlName, multiImg.name
                    )
                else:
                    bgImg = self.mesh.bgImages[0]
                    single = RoomShapeImageSingle(
                        name,
                        self.roomShapeType,
                        "ROOM_SHAPE_IMAGE_AMOUNT_SINGLE",
                        dlName,
                        bgImg.name,
                        bgImg.image.size[0],
                        bgImg.image.size[1],
                        bgImg.otherModeFlags,
                    )
            case _:
                raise PluginError(f"ERROR: Room Shape not supported: {self.roomShapeType}")

        return RoomShape(
            RoomShapeDLists(dlName, normal is not None, self.getDListsEntries()), normal, single, multiImg, multi
        )

    def getRoomMainC(self):
        roomC = CData()
        roomHeaders: list[tuple[OOTRoomHeader, str]] = []
        altHeaderPtrList = None

        if self.hasAlternateHeaders():
            roomHeaders: list[tuple[OOTRoomHeader, str]] = [
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
                roomC.append(self.getRoomCommandList(self, i))

                if i == 0 and self.hasAlternateHeaders() and altHeaderPtrList is not None:
                    roomC.source += altHeaderPtrList

                if len(curHeader.objects.objectList) > 0:
                    roomC.append(curHeader.objects.getObjectListC())

                if len(curHeader.actors.actorList) > 0:
                    roomC.append(curHeader.actors.getActorListC())

        return roomC
