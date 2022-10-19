from .....utility import CData, PluginError
from ....oot_level_classes import OOTScene, OOTRoom, OOTActor
from ...data import indent


def getActorEntry(actor: OOTActor):
    """Returns a single actor entry"""
    # position data
    actorPosData = ", { " + ", ".join([f"{round(pos)}" for pos in actor.position]) + " }, "

    # rotation data
    actorRotData = "{ " + ", ".join([f"{rot}" for rot in actor.rotation]) + " }, "

    # actor entry
    return "{ " + actor.actorID + actorPosData + actorRotData + actor.actorParam + " },\n"


def convertActorList(outScene: OOTScene, outRoom: OOTRoom, layerIndex: int):
    """Returns the actor list of the current header"""
    actorListData = CData()

    if outScene is not None:
        # start position actor list
        actorListName = f"ActorEntry {outScene.getPlayerEntryListName(layerIndex)}[]"
        actorList = outScene.startPositions.values()
    elif outRoom is not None:
        # normal actor list
        actorListName = f"ActorEntry {outRoom.getActorListName(layerIndex)}[{len(outRoom.actorList)}]"
        actorList = outRoom.actorList
    else:
        raise PluginError("ERROR: Can't convert the actor list to C!")

    # .h
    actorListData.header = f"extern {actorListName};\n"

    # .c
    actorListData.source = (
        actorListName + " = {\n" + "".join([indent + getActorEntry(actor) for actor in actorList]) + "};\n\n"
    )

    return actorListData
