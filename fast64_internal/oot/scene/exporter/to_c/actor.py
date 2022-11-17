from .....utility import CData
from ....oot_utility import indent
from ....oot_level_classes import OOTScene, OOTRoom, OOTActor, OOTTransitionActor, OOTEntrance


###################
# Written to Room #
###################

# Actor List


def getActorEntry(actor: OOTActor):
    """Returns a single actor entry"""
    posData = ", { " + ", ".join([f"{round(pos)}" for pos in actor.position]) + " }, "
    rotData = "{ " + "".join(rot for rot in actor.rotation) + " }, "

    return "{ " + actor.actorID + posData + rotData + actor.actorParam + " },\n"


def getActorList(outRoom: OOTRoom, headerIndex: int):
    """Returns the actor list for the current header"""
    actorList = CData()
    listName = f"ActorEntry {outRoom.actorListName(headerIndex)}"

    # .h
    actorList.header = f"extern {listName}[];\n"

    # .c
    actorList.source = (
        (f"{listName}[{outRoom.getActorLengthDefineName(headerIndex)}]" + " = {\n")
        + "".join(indent + getActorEntry(actor) for actor in outRoom.actorList)
        + "};\n\n"
    )

    return actorList


####################
# Written to Scene #
####################

# Transition Actor List


def getTransitionActorEntry(transActor: OOTTransitionActor):
    """Returns a single transition actor entry"""
    sides = [(transActor.frontRoom, transActor.frontCam), (transActor.backRoom, transActor.backCam)]
    roomData = "{ " + ", ".join(f"{room}, {cam}" for room, cam in sides) + " }"
    posData = "{ " + ", ".join(f"{round(pos)}" for pos in transActor.position) + " }"
    rotData = f"DEG_TO_BINANG({(transActor.rotationY * (180 / 0x8000)):.1f})"

    return "{ " + ", ".join([roomData, transActor.actorID, posData, rotData, transActor.actorParam]) + " },\n"


def getTransitionActorList(outScene: OOTScene, headerIndex: int):
    """Returns the transition actor list for the current header"""
    transActorList = CData()
    listName = f"TransitionActorEntry {outScene.transitionActorListName(headerIndex)}"

    # .h
    transActorList.header = f"extern {listName}[];\n"

    # .c
    transActorList.source = (
        (f"{listName}[]" + " = {\n")
        + "".join(indent + getTransitionActorEntry(transActor) for transActor in outScene.transitionActorList)
        + "};\n\n"
    )

    return transActorList


# Entrance List


def getSpawnActorList(outScene: OOTScene, headerIndex: int):
    """Returns the spawn actor list for the current header"""
    spawnActorList = CData()
    listName = f"ActorEntry {outScene.startPositionsName(headerIndex)}"

    # .h
    spawnActorList.header = f"extern {listName}[];\n"

    # .c
    spawnActorList.source = (
        (f"{listName}[]" + " = {\n")
        + "".join(indent + getActorEntry(spawnActor) for spawnActor in outScene.startPositions.values())
        + "};\n\n"
    )

    return spawnActorList


def getSpawnEntry(entrance: OOTEntrance):
    """Returns a single spawn entry"""
    return "{ " + f"{entrance.startPositionIndex}, {entrance.roomIndex}" + " },\n"


def getSpawnList(outScene: OOTScene, headerIndex: int):
    """Returns the spawn list for the current header"""
    spawnList = CData()
    listName = f"Spawn {outScene.entranceListName(headerIndex)}"

    # .h
    spawnList.header = f"extern {listName}[];\n"

    # .c
    spawnList.source = (
        (f"{listName}[]" + " = {\n")
        + "".join(indent + getSpawnEntry(entrance) for entrance in outScene.entranceList)
        + "};\n\n"
    )

    return spawnList
