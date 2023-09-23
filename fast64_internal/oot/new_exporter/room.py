from dataclasses import dataclass, field
from mathutils import Matrix
from bpy.types import Object
from ...utility import CData, indent
from ..room.properties import OOTRoomHeaderProperty
from ..oot_constants import ootData
from .commands import OOTRoomCommands
from .common import Common, Actor


@dataclass
class RoomCommon:
    roomName: str


@dataclass
class OOTRoomGeneral:
    ### General ###

    index: int
    roomShape: str

    ### Behavior ###

    roomBehavior: str
    playerIdleType: str
    disableWarpSongs: bool
    showInvisActors: bool

    ### Skybox And Time ###

    disableSky: bool
    disableSunMoon: bool
    hour: int
    minute: int
    timeSpeed: float
    echo: str

    ### Wind ###

    setWind: bool
    direction: tuple[int, int, int]
    strength: int


@dataclass
class OOTRoomObjects(RoomCommon):
    objectList: list[str]

    def objectListName(self, headerIndex: int):
        return f"{self.roomName}_header{headerIndex:02}_objectList"

    def getObjectLengthDefineName(self, headerIndex: int):
        return f"LENGTH_{self.objectListName(headerIndex).upper()}"

    def getObjectList(self, headerIndex: int):
        objectList = CData()

        listName = f"s16 {self.objectListName(headerIndex)}"

        # .h
        objectList.header = f"extern {listName}[];\n"

        # .c
        objectList.source = (
            (f"{listName}[{self.getObjectLengthDefineName(headerIndex)}]" + " = {\n")
            + ",\n".join(indent + objectID for objectID in self.objectList)
            + ",\n};\n\n"
        )

        return objectList


@dataclass
class OOTRoomActors(RoomCommon):
    sceneObj: Object
    roomObj: Object
    transform: Matrix
    headerIndex: int
    actorList: list[Actor] = field(default_factory=list)

    def __post_init__(self):
        actorObjList: list[Object] = [
            obj for obj in self.roomObj.children_recursive if obj.type == "EMPTY" and obj.ootEmptyType == "Actor"
        ]
        for obj in actorObjList:
            actorProp = obj.ootActorProperty
            if not Common.isCurrentHeaderValid(actorProp, self.headerIndex):
                continue

            # The Actor list is filled with ``("None", f"{i} (Deleted from the XML)", "None")`` for
            # the total number of actors defined in the XML. If the user deletes one, this will prevent
            # any data loss as Blender saves the index of the element in the Actor list used for the EnumProperty
            # and not the identifier as defined by the first element of the tuple. Therefore, we need to check if
            # the current Actor has the ID `None` to avoid export issues.
            if actorProp.actorID != "None":
                pos, rot, _, _ = Common.getConvertedTransform(self.transform, self.sceneObj, obj, True)
                actor = Actor()

                if actorProp.actorID == "Custom":
                    actor.id = actorProp.actorIDCustom
                else:
                    actor.id = actorProp.actorID

                if actorProp.rotOverride:
                    actor.rot = ", ".join([actorProp.rotOverrideX, actorProp.rotOverrideY, actorProp.rotOverrideZ])
                else:
                    actor.rot = ", ".join(f"DEG_TO_BINANG({(r * (180 / 0x8000)):.3f})" for r in rot)

                actor.name = (
                    ootData.actorData.actorsByID[actorProp.actorID].name.replace(
                        f" - {actorProp.actorID.removeprefix('ACTOR_')}", ""
                    )
                    if actorProp.actorID != "Custom"
                    else "Custom Actor"
                )

                actor.pos = pos
                actor.params = actorProp.actorParam
                self.actorList.append(actor)

    # Exporter

    def actorListName(self):
        return f"{self.roomName}_header{self.headerIndex:02}_actorList"

    def getActorLengthDefineName(self):
        return f"LENGTH_{self.actorListName().upper()}"

    def getActorListData(self):
        """Returns the actor list for the current header"""
        actorList = CData()
        listName = f"ActorEntry {self.actorListName()}"

        # .h
        actorList.header = f"extern {listName}[];\n"

        # .c
        actorList.source = (
            (f"{listName}[{self.getActorLengthDefineName()}]" + " = {\n")
            + "\n".join(actor.getActorEntry() for actor in self.actorList)
            + "};\n\n"
        )

        return actorList


@dataclass
class OOTRoomAlternate:
    childNight: "OOTRoomHeader" = None
    adultDay: "OOTRoomHeader" = None
    adultNight: "OOTRoomHeader" = None
    cutscene: list["OOTRoomHeader"] = field(default_factory=list)


@dataclass
class OOTRoomHeader(RoomCommon):
    general: OOTRoomGeneral
    objects: OOTRoomObjects
    actors: OOTRoomActors

    def getHeaderDefines(self, headerIndex: int):
        """Returns a string containing defines for actor and object lists lengths"""
        headerDefines = ""

        if len(self.objects.objectList) > 0:
            name = self.objects.getObjectLengthDefineName(headerIndex)
            headerDefines += f"#define {name} {len(self.objects.objectList)}\n"

        if len(self.actors.actorList) > 0:
            name = self.actors.getActorLengthDefineName(headerIndex)
            headerDefines += f"#define {name} {len(self.actors.actorList)}\n"

        return headerDefines


@dataclass
class OOTRoom(Common, OOTRoomCommands):
    name: str = None
    altName: str = None
    header: OOTRoomHeader = None
    alternate: OOTRoomAlternate = None

    def __post_init__(self):
        self.altHeadersName = f"{self.name}_alternateHeaders"

    def hasAlternateHeaders(self):
        return (
            self.alternate is not None
            and self.alternate.childNight is not None
            and self.alternate.adultDay is not None
            and self.alternate.adultNight is not None
            and len(self.alternate.cutscene) > 0
        )

    def getRoomHeaderFromIndex(self, headerIndex: int) -> OOTRoomHeader | None:
        if headerIndex == 0:
            return self.header

        for i, header in enumerate(self.altHeaderList, 1):
            if headerIndex == i:
                return getattr(self.alternate, header)

        for i, csHeader in enumerate(self.alternate.cutscene, 4):
            if headerIndex == i:
                return csHeader

        return None

    def getNewRoomHeader(self, headerProp: OOTRoomHeaderProperty, headerIndex: int = 0):
        """Returns a new room header with the informations from the scene empty object"""

        objIDList = []
        for objProp in headerProp.objectList:
            if objProp.objectKey == "Custom":
                objIDList.append(objProp.objectIDCustom)
            else:
                objIDList.append(ootData.objectData.objectsByKey[objProp.objectKey].id)

        return OOTRoomHeader(
            self.name,
            OOTRoomGeneral(
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
            OOTRoomObjects(self.name, objIDList),
            OOTRoomActors(
                self.name,
                self.sceneObj,
                self.roomObj,
                self.transform,
                headerIndex,
            ),
        )

    def getRoomMainC(self):
        roomC = CData()

        roomHeaders: list[tuple[OOTRoomHeader, str]] = [
            (self.alternate.childNight, "Child Night"),
            (self.alternate.adultDay, "Adult Day"),
            (self.alternate.adultNight, "Adult Night"),
        ]

        for i, csHeader in enumerate(self.alternate.cutscene):
            roomHeaders.append((csHeader, f"Cutscene No. {i + 1}"))

        altHeaderPtrListName = f"SceneCmd* {self.altHeadersName}"

        # .h
        roomC.header = f"extern {altHeaderPtrListName}[];\n"

        # .c
        altHeaderPtrList = (
            f"{altHeaderPtrListName}[]"
            + " = {\n"
            + "\n".join(
                indent + f"{curHeader.roomName()}_header{i:02}," if curHeader is not None else indent + "NULL,"
                for i, (curHeader, _) in enumerate(roomHeaders, 1)
            )
            + "\n};\n\n"
        )

        roomHeaders.insert(0, (self.header, "Child Day (Default)"))
        for i, (curHeader, headerDesc) in enumerate(roomHeaders):
            if curHeader is not None:
                roomC.source += "/**\n * " + f"Header {headerDesc}\n" + "*/\n"
                roomC.source += curHeader.getHeaderDefines(i)
                roomC.append(self.getRoomCommandList(self, i))

                if i == 0 and self.hasAlternateHeaders():
                    roomC.source += altHeaderPtrList

                if len(curHeader.objects.objectList) > 0:
                    roomC.append(curHeader.objects.getObjectList(i))

                if len(curHeader.actors.actorList) > 0:
                    roomC.append(curHeader.actors.getActorListData())

        return roomC
