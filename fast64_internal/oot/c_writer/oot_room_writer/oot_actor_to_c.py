from ....utility import CData, PluginError
from ...oot_level_classes import OOTScene, OOTRoom, OOTActor
from ...oot_utility import indent


def ootGetActorEntry(actor: OOTActor):
    """Returns a single actor entry"""
    # position data
    actorPosData = ", { " + ", ".join([f"{round(pos)}" for pos in actor.position]) + " }, "

    # rotation data
    rotList = actor.rotOverride if actor.rotOverride is not None else actor.rotation
    actorRotData = "{ " + ", ".join([f"{rot}" for rot in rotList]) + " }, "

    # actor entry
    return "{ " + actor.actorID + actorPosData + actorRotData + actor.actorParam + " },\n"


def ootActorListToC(scene: OOTScene, room: OOTRoom, headerIndex: int):
    """Returns the actor list of the current header"""
    actorListData = CData()

    if scene is not None:
        # start position actor list
        actorListName = f"ActorEntry {scene.startPositionsName(headerIndex)}[]"
        actorList = scene.startPositions.values()
    elif room is not None:
        # normal actor list
        actorListName = f"ActorEntry {room.actorListName(headerIndex)}[{len(room.actorList)}]"
        actorList = room.actorList
    else:
        raise PluginError("ERROR: Can't convert the actor list to C!")

    # .h
    actorListData.header = f"extern {actorListName};\n"

    # .c
    actorListData.source = (
        actorListName + " = {\n" + "".join([indent + ootGetActorEntry(actor) for actor in actorList]) + "};\n\n"
    )

    return actorListData
