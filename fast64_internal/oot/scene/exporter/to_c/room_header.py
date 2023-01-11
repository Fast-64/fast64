from .....utility import CData, indent
from ....oot_level_classes import OOTRoom
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
    roomC = CData()

    roomHeaders = [
        (outRoom.childNightHeader, "Child Night"),
        (outRoom.adultDayHeader, "Adult Day"),
        (outRoom.adultNightHeader, "Adult Night"),
    ]

    for i, csHeader in enumerate(outRoom.cutsceneHeaders):
        roomHeaders.append((csHeader, f"Cutscene No. {i + 1}"))

    altHeaderPtrListName = f"SceneCmd* {outRoom.alternateHeadersName()}"

    # .h
    roomC.header = f"extern {altHeaderPtrListName}[];\n"

    # .c
    altHeaderPtrList = (
        f"{altHeaderPtrListName}[]"
        + " = {\n"
        + "\n".join(
            indent + f"{curHeader.roomName()}_header{i:02}," if curHeader is not None else indent + "NULL,"
            for i, (curHeader, headerDesc) in enumerate(roomHeaders, 1)
        )
        + "\n};\n\n"
    )

    roomHeaders.insert(0, (outRoom, "Child Day (Default)"))
    for i, (curHeader, headerDesc) in enumerate(roomHeaders):
        if curHeader is not None:
            roomC.source += "/**\n * " + f"Header {headerDesc}\n" + "*/\n"
            roomC.source += getHeaderDefines(curHeader, i)
            roomC.append(getRoomCommandList(curHeader, i))

            if i == 0 and outRoom.hasAlternateHeaders():
                roomC.source += altHeaderPtrList

            if len(curHeader.objectIDList) > 0:
                roomC.append(getObjectList(curHeader, i))

            if len(curHeader.actorList) > 0:
                roomC.append(getActorList(curHeader, i))

    return roomC
