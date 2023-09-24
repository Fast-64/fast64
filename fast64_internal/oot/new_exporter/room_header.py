from dataclasses import dataclass, field
from mathutils import Matrix
from bpy.types import Object
from ...utility import CData, indent
from ..oot_constants import ootData
from .common import Common, Actor


@dataclass
class OOTRoomHeaderInfos:
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
class OOTRoomHeaderObjects:
    name: str
    objectList: list[str]

    def getObjectLengthDefineName(self):
        return f"LENGTH_{self.name.upper()}"

    def getObjectListC(self):
        objectList = CData()

        listName = f"s16 {self.name}"

        # .h
        objectList.header = f"extern {listName}[];\n"

        # .c
        objectList.source = (
            (f"{listName}[{self.getObjectLengthDefineName()}]" + " = {\n")
            + ",\n".join(indent + objectID for objectID in self.objectList)
            + ",\n};\n\n"
        )

        return objectList


@dataclass
class OOTRoomHeaderActors:
    name: str
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
            if not Common.isCurrentHeaderValid(actorProp.headerSettings, self.headerIndex):
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

    def getActorLengthDefineName(self):
        return f"LENGTH_{self.name.upper()}"

    def getActorListC(self):
        """Returns the actor list for the current header"""
        actorList = CData()
        listName = f"ActorEntry {self.name}"

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
class OOTRoomAlternateHeader:
    name: str
    childNight: "OOTRoomHeader" = None
    adultDay: "OOTRoomHeader" = None
    adultNight: "OOTRoomHeader" = None
    cutscenes: list["OOTRoomHeader"] = field(default_factory=list)


@dataclass
class OOTRoomHeader:
    name: str
    infos: OOTRoomHeaderInfos
    objects: OOTRoomHeaderObjects
    actors: OOTRoomHeaderActors

    def getHeaderDefines(self):
        """Returns a string containing defines for actor and object lists lengths"""
        headerDefines = ""

        if len(self.objects.objectList) > 0:
            defineName = self.objects.getObjectLengthDefineName()
            headerDefines += f"#define {defineName} {len(self.objects.objectList)}\n"

        if len(self.actors.actorList) > 0:
            defineName = self.actors.getActorLengthDefineName()
            headerDefines += f"#define {defineName} {len(self.actors.actorList)}\n"

        return headerDefines
