from .....utility import CData, indent
from ....oot_level_classes import OOTRoom, OOTScene
from .actor import ootActorListToC
from .room_commands import ootRoomCommandsToC


def ootGetHeaderDefines(room: OOTRoom, headerIndex: int):
    """Returns a string containing defines for actor and object lists lengths"""
    data = CData()

    if len(room.objectIDList) > 0:
        data.header += f"#define {room.getObjectLengthDefineName(headerIndex)} {len(room.objectIDList)}\n"

    if len(room.actorList) > 0:
        data.header += f"#define {room.getActorLengthDefineName(headerIndex)} {len(room.actorList)}\n"

    return data.header


# Object List


def ootObjectListToC(room: OOTRoom, headerIndex: int):
    data = CData()
    data.header = "extern s16 " + room.objectListName(headerIndex) + "[];\n"
    data.source = f"s16 {room.objectListName(headerIndex)}[{room.getObjectLengthDefineName(headerIndex)}]" + " = {\n"
    for objID in room.objectIDList:
        data.source += indent + objID + ",\n"
    data.source += "};\n\n"
    return data


# Room Header


def ootAlternateRoomMainToC(scene: OOTScene, room: OOTRoom):
    altHeader = CData()
    altData = CData()

    altHeader.header = "extern SceneCmd* " + room.alternateHeadersName() + "[];\n"
    altHeader.source = "SceneCmd* " + room.alternateHeadersName() + "[] = {\n"

    for headerIndex, curHeader in enumerate([room.childNightHeader, room.adultDayHeader, room.adultNightHeader], 1):
        if curHeader is not None:
            altHeader.source += indent + f"{room.roomName()}_header{headerIndex:02},\n"
            altData.append(ootRoomMainToC(scene, curHeader, headerIndex))
        else:
            altHeader.source += indent + "NULL,\n"

    for i in range(len(room.cutsceneHeaders)):
        altHeader.source += indent + room.roomName() + "_header" + format(i + 4, "02") + ",\n"
        altData.append(ootRoomMainToC(scene, room.cutsceneHeaders[i], i + 4))

    altHeader.source += "};\n\n"

    return altHeader, altData


def ootRoomMainToC(scene, room, headerIndex):
    roomMainC = CData()

    roomMainC.source += ootGetHeaderDefines(room, headerIndex)

    if room.hasAlternateHeaders():
        altHeader, altData = ootAlternateRoomMainToC(scene, room)
    else:
        altHeader = CData()
        altData = CData()

    roomMainC.append(ootRoomCommandsToC(room, headerIndex))
    roomMainC.append(altHeader)
    if len(room.objectIDList) > 0:
        roomMainC.append(ootObjectListToC(room, headerIndex))
    if len(room.actorList) > 0:
        roomMainC.append(ootActorListToC(room, headerIndex))
    roomMainC.append(altData)

    return roomMainC
