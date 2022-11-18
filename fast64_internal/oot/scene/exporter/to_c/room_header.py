from .....utility import CData, indent
from ....oot_level_classes import OOTRoom, OOTScene
from .actor import getActorList
from .room_commands import getRoomCommandList


def getHeaderDefines(outRoom: OOTRoom, headerIndex: int):
    """Returns a string containing defines for actor and object lists lengths"""
    headerDefines = ""

    if len(outRoom.objectIDList) > 0:
        headerDefines += f"#define {outRoom.getObjectLengthDefineName(headerIndex)} {len(outRoom.objectIDList)}\n"

    if len(outRoom.actorList) > 0:
        headerDefines += f"#define {outRoom.getActorLengthDefineName(headerIndex)} {len(outRoom.actorList)}\n"

    return headerDefines


# Object List
def getObjectList(outRoom: OOTRoom, headerIndex: int):
    objectList = CData()
    listName = f"s16 {outRoom.objectListName(headerIndex)}"

    # .h
    objectList.header = f"extern {listName}[];\n"

    # .c
    objectList.source = (
        (f"{listName}[{outRoom.getObjectLengthDefineName(headerIndex)}]" + " = {\n")
        + ",\n".join(indent + objectID for objectID in outRoom.objectIDList)
        + ",\n};\n\n"
    )

    return objectList


# Room Header
def getRoomData(outRoom: OOTRoom):
    roomData = CData()
    roomHeaders = [outRoom.childNightHeader, outRoom.adultDayHeader, outRoom.adultNightHeader]
    roomHeaders.extend(outRoom.cutsceneHeaders)
    altHeaderPtrListName = f"SceneCmd* {outRoom.alternateHeadersName()}"

    # .h
    roomData.header = f"extern {altHeaderPtrListName}[];\n"

    # .c
    altHeaderPtrList = f"{altHeaderPtrListName}[]" + " = {\n"
    for i, curHeader in enumerate(roomHeaders, 1):
        if curHeader is not None:
            altHeaderPtrList += indent + f"{curHeader.roomName()}_header{i:02},\n"
        elif i < 4:
            altHeaderPtrList += indent + "NULL,\n"
    altHeaderPtrList += "};\n\n"

    roomHeaders.insert(0, outRoom)
    for i, curHeader in enumerate(roomHeaders):
        if curHeader is not None:
            roomData.source += getHeaderDefines(curHeader, i)
            roomData.append(getRoomCommandList(curHeader, i))

            if outRoom.hasAlternateHeaders():
                roomData.source += altHeaderPtrList

            if len(curHeader.objectIDList) > 0:
                roomData.append(getObjectList(curHeader, i))

            if len(curHeader.actorList) > 0:
                roomData.append(getActorList(curHeader, i))

    return roomData
