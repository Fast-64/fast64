from ....utility import CData
from .actor import ootActorListToC
from .room_commands import ootRoomCommandsToC


# Object List


def ootObjectListToC(room, headerIndex):
    data = CData()
    data.header = "extern s16 " + room.objectListName(headerIndex) + "[" + str(len(room.objectList)) + "];\n"
    data.source = "s16 " + room.objectListName(headerIndex) + "[" + str(len(room.objectList)) + "] = {\n"
    for objectItem in room.objectList:
        data.source += "\t" + objectItem + ",\n"
    data.source += "};\n\n"
    return data


# Room Header


def ootAlternateRoomMainToC(scene, room):
    altHeader = CData()
    altData = CData()

    altHeader.header = "extern SceneCmd* " + room.alternateHeadersName() + "[];\n"
    altHeader.source = "SceneCmd* " + room.alternateHeadersName() + "[] = {\n"

    if room.childNightHeader is not None:
        altHeader.source += "\t" + room.roomName() + "_header" + format(1, "02") + ",\n"
        altData.append(ootRoomMainToC(scene, room.childNightHeader, 1))
    else:
        altHeader.source += "\t0,\n"

    if room.adultDayHeader is not None:
        altHeader.source += "\t" + room.roomName() + "_header" + format(2, "02") + ",\n"
        altData.append(ootRoomMainToC(scene, room.adultDayHeader, 2))
    else:
        altHeader.source += "\t0,\n"

    if room.adultNightHeader is not None:
        altHeader.source += "\t" + room.roomName() + "_header" + format(3, "02") + ",\n"
        altData.append(ootRoomMainToC(scene, room.adultNightHeader, 3))
    else:
        altHeader.source += "\t0,\n"

    for i in range(len(room.cutsceneHeaders)):
        altHeader.source += "\t" + room.roomName() + "_header" + format(i + 4, "02") + ",\n"
        altData.append(ootRoomMainToC(scene, room.cutsceneHeaders[i], i + 4))

    altHeader.source += "};\n\n"

    return altHeader, altData


def ootRoomMainToC(scene, room, headerIndex):
    roomMainC = CData()

    if room.hasAlternateHeaders():
        altHeader, altData = ootAlternateRoomMainToC(scene, room)
    else:
        altHeader = CData()
        altData = CData()

    roomMainC.append(ootRoomCommandsToC(room, headerIndex))
    roomMainC.append(altHeader)
    if len(room.objectList) > 0:
        roomMainC.append(ootObjectListToC(room, headerIndex))
    if len(room.actorList) > 0:
        roomMainC.append(ootActorListToC(room, headerIndex))
    roomMainC.append(altData)

    return roomMainC
