from dataclasses import dataclass, field
from ...utility import indent


@dataclass
class Actor:
    """Defines an Actor"""

    name: str = None
    id: str = None
    pos: list[int] = field(default_factory=list)
    rot: str = None
    params: str = None

    def getActorEntry(self):
        """Returns a single actor entry"""

        posData = "{ " + ", ".join(f"{round(p)}" for p in self.pos) + " }"
        rotData = "{ " + self.rot + " }"

        actorInfos = [self.id, posData, rotData, self.params]
        infoDescs = ["Actor ID", "Position", "Rotation", "Parameters"]

        return (
            indent
            + (f"// {self.name}\n" + indent if self.name != "" else "")
            + "{\n"
            + ",\n".join((indent * 2) + f"/* {desc:10} */ {info}" for desc, info in zip(infoDescs, actorInfos))
            + ("\n" + indent + "},\n")
        )


@dataclass
class TransitionActor(Actor):
    """Defines a Transition Actor"""

    dontTransition: bool = None
    roomFrom: int = None
    roomTo: int = None
    cameraFront: str = None
    cameraBack: str = None

    def getTransitionActorEntry(self):
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
class EntranceActor(Actor):
    """Defines an Entrance Actor"""

    roomIndex: int = None
    spawnIndex: int = None

    def getSpawnEntry(self):
        """Returns a single spawn entry"""

        return indent + "{ " + f"{self.spawnIndex}, {self.roomIndex}" + " },\n"
