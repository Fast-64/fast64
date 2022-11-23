from .....utility import CData, indent
from ....oot_level_classes import OOTRoom


###################
# Written to Room #
###################

# Actor List


def ootActorToC(actor):
    return (
        "{ "
        + ", ".join(
            (
                str(actor.actorID),
                str(int(round(actor.position[0]))),
                str(int(round(actor.position[1]))),
                str(int(round(actor.position[2]))),
                *(
                    (
                        actor.rotOverride[0],
                        actor.rotOverride[1],
                        actor.rotOverride[2],
                    )
                    if actor.rotOverride is not None
                    else (
                        str(int(round(actor.rotation[0]))),
                        str(int(round(actor.rotation[1]))),
                        str(int(round(actor.rotation[2]))),
                    )
                ),
                str(actor.actorParam),
            )
        )
        + " },\n"
    )


def ootActorListToC(room: OOTRoom, headerIndex: int):
    data = CData()
    data.header = "extern ActorEntry " + room.actorListName(headerIndex) + "[];\n"
    data.source = (
        f"ActorEntry {room.actorListName(headerIndex)}[{room.getActorLengthDefineName(headerIndex)}]" + " = {\n"
    )
    for actor in room.actorList:
        data.source += indent + ootActorToC(actor)
    data.source += "};\n\n"
    return data


####################
# Written to Scene #
####################

# Transition Actor List


def ootTransitionActorToC(transActor):
    return (
        "{ "
        + ", ".join(
            (
                str(transActor.frontRoom),
                str(transActor.frontCam),
                str(transActor.backRoom),
                str(transActor.backCam),
                str(transActor.actorID),
                str(int(round(transActor.position[0]))),
                str(int(round(transActor.position[1]))),
                str(int(round(transActor.position[2]))),
                str(int(round(transActor.rotationY))),
                str(transActor.actorParam),
            )
        )
        + " },\n"
    )


def ootTransitionActorListToC(scene, headerIndex):
    data = CData()
    data.header = (
        "extern TransitionActorEntry "
        + scene.transitionActorListName(headerIndex)
        + "["
        + str(len(scene.transitionActorList))
        + "];\n"
    )
    data.source = (
        "TransitionActorEntry "
        + scene.transitionActorListName(headerIndex)
        + "["
        + str(len(scene.transitionActorList))
        + "] = {\n"
    )
    for transActor in scene.transitionActorList:
        data.source += indent + ootTransitionActorToC(transActor)
    data.source += "};\n\n"
    return data


# Entrance List


def ootStartPositionListToC(scene, headerIndex):
    data = CData()
    data.header = "extern ActorEntry " + scene.startPositionsName(headerIndex) + "[];\n"
    data.source = "ActorEntry " + scene.startPositionsName(headerIndex) + "[] = {\n"
    for i in range(len(scene.startPositions)):
        data.source += indent + ootActorToC(scene.startPositions[i])
    data.source += "};\n\n"
    return data


def ootEntranceToC(entrance):
    return "{ " + str(entrance.startPositionIndex) + ", " + str(entrance.roomIndex) + " },\n"


def ootEntranceListToC(scene, headerIndex):
    data = CData()
    data.header = "extern EntranceEntry " + scene.entranceListName(headerIndex) + "[];\n"
    data.source = "EntranceEntry " + scene.entranceListName(headerIndex) + "[] = {\n"
    for entrance in scene.entranceList:
        data.source += indent + ootEntranceToC(entrance)
    data.source += "};\n\n"
    return data
