from ....utility import CData
from ...oot_level_classes import OOTScene, OOTTransitionActor
from ...oot_utility import indent


def ootGetTransActorData(transActor: OOTTransitionActor):
    """Returns the transition actors array's data"""
    sides = [(transActor.frontRoom, transActor.frontCam), (transActor.backRoom, transActor.backCam)]
    return (
        "{ "
        + (", ".join(["{ " + f"{room}, {cam}" + " }" for room, cam in sides]) + ", ")
        + transActor.actorID
        + ", { "
        + ", ".join([f"{round(pos)}" for pos in transActor.position])
        + " }, "
        + f"{round(transActor.rotationY)}, "
        + f"{transActor.actorParam}"
        + " },\n"
    )


def ootTransitionActorListToC(scene: OOTScene, headerIndex: int):
    """Returns the transition actors array"""
    transActorListData = CData()
    transActorName = (
        f"TransitionActorEntry {scene.transitionActorListName(headerIndex)}[{len(scene.transitionActorList)}]"
    )

    # .h
    transActorListData.header = f"extern {transActorName};\n"

    # .c
    transActorListData.source = (
        (transActorName + " = {\n")
        + "".join([indent + ootGetTransActorData(transActor) for transActor in scene.transitionActorList])
        + "};\n\n"
    )

    return transActorListData
