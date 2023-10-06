from dataclasses import dataclass, field
from mathutils import Matrix
from bpy.types import Object
from ....utility import CData, indent
from ...oot_constants import ootData
from ...room.properties import OOTRoomHeaderProperty
from ..base import Base, Actor


@dataclass
class HeaderBase(Base):
    name: str = None
    props: OOTRoomHeaderProperty = None
    sceneObj: Object = None
    roomObj: Object = None
    transform: Matrix = None
    headerIndex: int = None


@dataclass
class RoomInfos(HeaderBase):
    """This class stores various room header informations"""

    ### General ###

    index: int = None
    roomShape: str = None

    ### Behavior ###

    roomBehavior: str = None
    playerIdleType: str = None
    disableWarpSongs: bool = None
    showInvisActors: bool = None

    ### Skybox And Time ###

    disableSky: bool = None
    disableSunMoon: bool = None
    hour: int = None
    minute: int = None
    timeSpeed: float = None
    echo: str = None

    ### Wind ###

    setWind: bool = None
    direction: tuple[int, int, int] = None
    strength: int = None

    def __post_init__(self):
        self.index = self.props.roomIndex
        self.roomShape = self.props.roomShape
        self.roomBehavior = self.getPropValue(self.props, "roomBehaviour")
        self.playerIdleType = self.getPropValue(self.props, "linkIdleMode")
        self.disableWarpSongs = self.props.disableWarpSongs
        self.showInvisActors = self.props.showInvisibleActors
        self.disableSky = self.props.disableSkybox
        self.disableSunMoon = self.props.disableSunMoon
        self.hour = 0xFF if self.props.leaveTimeUnchanged else self.props.timeHours
        self.minute = 0xFF if self.props.leaveTimeUnchanged else self.props.timeMinutes
        self.timeSpeed = max(-128, min(127, round(self.props.timeSpeed * 0xA)))
        self.echo = self.props.echo
        self.setWind = self.props.setWind
        self.direction = [d for d in self.props.windVector] if self.props.setWind else None
        self.strength = self.props.windStrength if self.props.setWind else None

    def getCmds(self):
        showInvisActors = "true" if self.showInvisActors else "false"
        disableWarpSongs = "true" if self.disableWarpSongs else "false"
        disableSkybox = "true" if self.disableSky else "false"
        disableSunMoon = "true" if self.disableSunMoon else "false"

        roomBehaviorArgs = f"{self.roomBehavior}, {self.playerIdleType}, {showInvisActors}, {disableWarpSongs}"
        cmdList = [
            f"SCENE_CMD_ECHO_SETTINGS({self.echo})",
            f"SCENE_CMD_ROOM_BEHAVIOR({roomBehaviorArgs})",
            f"SCENE_CMD_SKYBOX_DISABLES({disableSkybox}, {disableSunMoon})",
            f"SCENE_CMD_TIME_SETTINGS({self.hour}, {self.minute}, {self.timeSpeed})",
        ]

        if self.setWind:
            cmdList.append(f"SCENE_CMD_WIND_SETTINGS({', '.join(f'{dir}' for dir in self.direction)}, {self.strength})")

        return indent + f",\n{indent}".join(cmdList) + ",\n"


@dataclass
class RoomObjects(HeaderBase):
    """This class defines an OoT object array"""

    objectList: list[str] = field(default_factory=list)

    def __post_init__(self):
        for objProp in self.props.objectList:
            if objProp.objectKey == "Custom":
                self.objectList.append(objProp.objectIDCustom)
            else:
                self.objectList.append(ootData.objectData.objectsByKey[objProp.objectKey].id)

    def getDefineName(self):
        """Returns the name of the define for the total of entries in the object list"""

        return f"LENGTH_{self.name.upper()}"

    def getCmd(self):
        return indent + f"SCENE_CMD_OBJECT_LIST({self.getDefineName()}, {self.name}),\n"

    def getC(self):
        """Returns the array with the objects the room uses"""

        objectList = CData()

        listName = f"s16 {self.name}"

        # .h
        objectList.header = f"extern {listName}[];\n"

        # .c
        objectList.source = (
            (f"{listName}[{self.getDefineName()}]" + " = {\n")
            + ",\n".join(indent + objectID for objectID in self.objectList)
            + ",\n};\n\n"
        )

        return objectList


@dataclass
class RoomActors(HeaderBase):
    """This class defines an OoT actor array"""

    actorList: list[Actor] = field(default_factory=list)

    def __post_init__(self):
        actorObjList: list[Object] = [
            obj for obj in self.roomObj.children_recursive if obj.type == "EMPTY" and obj.ootEmptyType == "Actor"
        ]
        for obj in actorObjList:
            actorProp = obj.ootActorProperty
            if not self.isCurrentHeaderValid(actorProp.headerSettings, self.headerIndex):
                continue

            # The Actor list is filled with ``("None", f"{i} (Deleted from the XML)", "None")`` for
            # the total number of actors defined in the XML. If the user deletes one, this will prevent
            # any data loss as Blender saves the index of the element in the Actor list used for the EnumProperty
            # and not the identifier as defined by the first element of the tuple. Therefore, we need to check if
            # the current Actor has the ID `None` to avoid export issues.
            if actorProp.actorID != "None":
                pos, rot, _, _ = self.getConvertedTransform(self.transform, self.sceneObj, obj, True)
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

    def getDefineName(self):
        """Returns the name of the define for the total of entries in the actor list"""

        return f"LENGTH_{self.name.upper()}"

    def getCmd(self):
        return indent + f"SCENE_CMD_ACTOR_LIST({self.getDefineName()}, {self.name}),\n"

    def getC(self):
        """Returns the array with the actors the room uses"""

        actorList = CData()
        listName = f"ActorEntry {self.name}"

        # .h
        actorList.header = f"extern {listName}[];\n"

        # .c
        actorList.source = (
            (f"{listName}[{self.getDefineName()}]" + " = {\n")
            + "\n".join(actor.getActorEntry() for actor in self.actorList)
            + "};\n\n"
        )

        return actorList


@dataclass
class RoomHeader(HeaderBase):
    """This class defines a room header"""

    infos: RoomInfos = None
    objects: RoomObjects = None
    actors: RoomActors = None

    def __post_init__(self):
        self.infos = RoomInfos(None, self.props)
        self.objects = RoomObjects(f"{self.name}_objectList", self.props)
        self.actors = RoomActors(
            f"{self.name}_actorList", None, self.sceneObj, self.roomObj, self.transform, self.headerIndex
        )

    def getHeaderDefines(self):
        """Returns a string containing defines for actor and object lists lengths"""

        headerDefines = ""

        if len(self.objects.objectList) > 0:
            defineName = self.objects.getDefineName()
            headerDefines += f"#define {defineName} {len(self.objects.objectList)}\n"

        if len(self.actors.actorList) > 0:
            defineName = self.actors.getDefineName()
            headerDefines += f"#define {defineName} {len(self.actors.actorList)}\n"

        return headerDefines


@dataclass
class RoomAlternateHeader:
    """This class stores alternate header data"""

    name: str
    childNight: RoomHeader = None
    adultDay: RoomHeader = None
    adultNight: RoomHeader = None
    cutscenes: list[RoomHeader] = field(default_factory=list)
