from .....utility import CData
from ....oot_level_classes import OOTScene, OOTEntrance
from ...data import indent


def getSpawnEntry(entrance: OOTEntrance):
    """Returns an entrance list entrance entry"""
    return "{ " + f"{entrance.startPositionIndex}, {entrance.roomIndex}" + " },\n"


def convertSpawnList(scene: OOTScene, headerIndex: int):
    """Returns the entrance list array"""
    entranceListData = CData()
    entranceName = f"EntranceEntry {scene.getSpawnListName(headerIndex)}[]"

    # .h
    entranceListData.header = f"extern {entranceName};\n"

    # .c
    entranceListData.source = (
        (entranceName + " = {\n")
        + "".join([indent + f"{getSpawnEntry(entrance)}" for entrance in scene.entranceList])
        + "};\n\n"
    )

    return entranceListData


def convertExitList(scene: OOTScene, headerIndex: int):
    """Returns the exit list array"""
    exitListData = CData()
    exitListName = f"u16 {scene.getExitListName(headerIndex)}[{len(scene.exitList)}]"

    # .h
    exitListData.header = f"extern {exitListName};\n"

    # .c
    exitListData.source = (
        (exitListName + " = {\n")
        # @TODO: use the enum name instead of the raw index
        + "".join([indent + f"{exitEntry.index}" for exitEntry in scene.exitList])
        + "};\n\n"
    )

    return exitListData
