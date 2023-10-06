from dataclasses import dataclass, field
from mathutils import Matrix
from bpy.types import Object
from .....utility import PluginError, CData, indent
from ....oot_constants import ootData
from ....scene.properties import OOTSceneHeaderProperty
from ...base import Base, Actor


@dataclass
class TransitionActor(Actor):
    """Defines a Transition Actor"""

    dontTransition: bool = None
    roomFrom: int = None
    roomTo: int = None
    cameraFront: str = None
    cameraBack: str = None

    def getEntryC(self):
        """Returns a single transition actor entry"""

        sides = [(self.roomFrom, self.cameraFront), (self.roomTo, self.cameraBack)]
        roomData = "{ " + ", ".join(f"{room}, {cam}" for room, cam in sides) + " }"
        posData = "{ " + ", ".join(f"{round(pos)}" for pos in self.pos) + " }"

        actorInfos = [roomData, self.id, posData, self.rot, self.params]
        infoDescs = ["Room & Cam Index (Front, Back)", "Actor ID", "Position", "Rotation Y", "Parameters"]

        return (
            (indent + f"// {self.name}\n" + indent if self.name != "" else "")
            + "{\n"
            + ",\n".join((indent * 2) + f"/* {desc:30} */ {info}" for desc, info in zip(infoDescs, actorInfos))
            + ("\n" + indent + "},\n")
        )


@dataclass
class SceneTransitionActors(Base):
    props: OOTSceneHeaderProperty
    name: str
    sceneObj: Object
    transform: Matrix
    headerIndex: int

    entries: list[TransitionActor] = field(default_factory=list)

    def __post_init__(self):
        actorObjList: list[Object] = [
            obj
            for obj in self.sceneObj.children_recursive
            if obj.type == "EMPTY" and obj.ootEmptyType == "Transition Actor"
        ]
        for obj in actorObjList:
            roomObj = self.getRoomObjectFromChild(obj)
            if roomObj is None:
                raise PluginError("ERROR: Room Object not found!")
            self.roomIndex = roomObj.ootRoomHeader.roomIndex

            transActorProp = obj.ootTransitionActorProperty

            if (
                self.isCurrentHeaderValid(transActorProp.actor.headerSettings, self.headerIndex)
                and transActorProp.actor.actorID != "None"
            ):
                pos, rot, _, _ = self.getConvertedTransform(self.transform, self.sceneObj, obj, True)
                transActor = TransitionActor()

                if transActorProp.dontTransition:
                    front = (255, self.getPropValue(transActorProp, "cameraTransitionBack"))
                    back = (self.roomIndex, self.getPropValue(transActorProp, "cameraTransitionFront"))
                else:
                    front = (self.roomIndex, self.getPropValue(transActorProp, "cameraTransitionFront"))
                    back = (transActorProp.roomIndex, self.getPropValue(transActorProp, "cameraTransitionBack"))

                if transActorProp.actor.actorID == "Custom":
                    transActor.id = transActorProp.actor.actorIDCustom
                else:
                    transActor.id = transActorProp.actor.actorID

                transActor.name = (
                    ootData.actorData.actorsByID[transActorProp.actor.actorID].name.replace(
                        f" - {transActorProp.actor.actorID.removeprefix('ACTOR_')}", ""
                    )
                    if transActorProp.actor.actorID != "Custom"
                    else "Custom Actor"
                )

                transActor.pos = pos
                transActor.rot = f"DEG_TO_BINANG({(rot[1] * (180 / 0x8000)):.3f})"  # TODO: Correct axis?
                transActor.params = transActorProp.actor.actorParam
                transActor.roomFrom, transActor.cameraFront = front
                transActor.roomTo, transActor.cameraBack = back
                self.entries.append(transActor)

    def getCmd(self):
        return indent + f"SCENE_CMD_TRANSITION_ACTOR_LIST({len(self.entries)}, {self.name}),\n"

    def getC(self):
        """Returns the transition actor array"""

        transActorList = CData()
        listName = f"TransitionActorEntry {self.name}"

        # .h
        transActorList.header = f"extern {listName}[];\n"

        # .c
        transActorList.source = (
            (f"{listName}[]" + " = {\n") + "\n".join(transActor.getEntryC() for transActor in self.entries) + "};\n\n"
        )

        return transActorList


@dataclass
class EntranceActor(Actor):
    """Defines an Entrance Actor"""

    roomIndex: int = None
    spawnIndex: int = None

    def getEntryC(self):
        """Returns a single spawn entry"""

        return indent + "{ " + f"{self.spawnIndex}, {self.roomIndex}" + " },\n"


@dataclass
class SceneEntranceActors(Base):
    props: OOTSceneHeaderProperty
    name: str
    sceneObj: Object
    transform: Matrix
    headerIndex: int

    entries: list[EntranceActor] = field(default_factory=list)

    def __post_init__(self):
        """Returns the entrance actor list based on empty objects with the type 'Entrance'"""

        entranceActorFromIndex: dict[int, EntranceActor] = {}
        actorObjList: list[Object] = [
            obj for obj in self.sceneObj.children_recursive if obj.type == "EMPTY" and obj.ootEmptyType == "Entrance"
        ]
        for obj in actorObjList:
            roomObj = self.getRoomObjectFromChild(obj)
            if roomObj is None:
                raise PluginError("ERROR: Room Object not found!")

            entranceProp = obj.ootEntranceProperty
            if (
                self.isCurrentHeaderValid(entranceProp.actor.headerSettings, self.headerIndex)
                and entranceProp.actor.actorID != "None"
            ):
                pos, rot, _, _ = self.getConvertedTransform(self.transform, self.sceneObj, obj, True)
                entranceActor = EntranceActor()

                entranceActor.name = (
                    ootData.actorData.actorsByID[entranceProp.actor.actorID].name.replace(
                        f" - {entranceProp.actor.actorID.removeprefix('ACTOR_')}", ""
                    )
                    if entranceProp.actor.actorID != "Custom"
                    else "Custom Actor"
                )

                entranceActor.id = "ACTOR_PLAYER" if not entranceProp.customActor else entranceProp.actor.actorIDCustom
                entranceActor.pos = pos
                entranceActor.rot = ", ".join(f"DEG_TO_BINANG({(r * (180 / 0x8000)):.3f})" for r in rot)
                entranceActor.params = entranceProp.actor.actorParam
                entranceActor.roomIndex = roomObj.ootRoomHeader.roomIndex
                entranceActor.spawnIndex = entranceProp.spawnIndex

                if not entranceProp.spawnIndex in entranceActorFromIndex:
                    entranceActorFromIndex[entranceProp.spawnIndex] = entranceActor
                else:
                    raise PluginError(f"ERROR: Repeated Spawn Index: {entranceProp.spawnIndex}")

        entranceActorFromIndex = dict(sorted(entranceActorFromIndex.items()))
        if list(entranceActorFromIndex.keys()) != list(range(len(entranceActorFromIndex))):
            raise PluginError("ERROR: The spawn indices are not consecutive!")

        self.entries = list(entranceActorFromIndex.values())

    def getCmd(self):
        name = self.name if len(self.entries) > 0 else "NULL"
        return indent + f"SCENE_CMD_SPAWN_LIST({len(self.entries)}, {name}),\n"

    def getC(self):
        """Returns the spawn actor array"""

        spawnActorList = CData()
        listName = f"ActorEntry {self.name}"

        # .h
        spawnActorList.header = f"extern {listName}[];\n"

        # .c
        spawnActorList.source = (
            (f"{listName}[]" + " = {\n") + "".join(entrance.getActorEntry() for entrance in self.entries) + "};\n\n"
        )

        return spawnActorList


@dataclass
class SceneSpawns(Base):
    """This class handles scene actors (transition actors and entrance actors)"""

    props: OOTSceneHeaderProperty
    name: str
    entries: list[EntranceActor]

    def getCmd(self):
        return indent + f"SCENE_CMD_ENTRANCE_LIST({self.name if len(self.entries) > 0 else 'NULL'}),\n"

    def getC(self):
        """Returns the spawn array"""

        spawnList = CData()
        listName = f"Spawn {self.name}"

        # .h
        spawnList.header = f"extern {listName}[];\n"

        # .c
        spawnList.source = (
            (f"{listName}[]" + " = {\n")
            + (indent + "// { Spawn Actor List Index, Room Index }\n")
            + "".join(entrance.getEntryC() for entrance in self.entries)
            + "};\n\n"
        )

        return spawnList
