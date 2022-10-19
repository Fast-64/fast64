from .....utility import CData
from ....oot_level_classes import OOTScene
from ...data import indent


def convertRoomList(outScene: OOTScene):
    """Returns the room list array"""
    listData = CData()
    listName = f"RomFile {outScene.getRoomListName()}[]"

    # generating segment rom names for every room
    segNames = []
    for i in range(len(outScene.rooms)):
        roomName = outScene.rooms[i].roomName()
        segNames.append((f"_{roomName}SegmentRomStart", f"_{roomName}SegmentRomEnd"))

    # .h
    listData.header += f"extern {listName};\n"

    if not outScene.write_dummy_room_list:
        # Write externs for rom segments
        listData.header += "".join(
            [f"extern u8 {startName}[];\n" + f"extern u8 {stopName}[];\n" for startName, stopName in segNames]
        )

    # .c
    listData.source = listName + " = {\n"

    if outScene.write_dummy_room_list:
        listData.source = (
            "// Dummy room list\n" + listData.source + ((indent + "{ NULL, NULL },\n") * len(outScene.rooms))
        )
    else:
        listData.source += (
            " },\n".join([indent + "{ " + f"(u32){startName}, (u32){stopName}" for startName, stopName in segNames])
            + " },\n"
        )

    listData.source += "};\n\n"
    return listData
