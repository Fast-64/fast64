from ....utility import CData
from ...oot_utility import indent
from ...oot_level_classes import OOTScene


def ootRoomListHeaderToC(scene: OOTScene):
    """Returns the room list array"""
    headerData = CData()
    headerName = f"RomFile {scene.roomListName()}[]"

    # generating segment rom names for every room
    segNames = []
    for room in scene.rooms.values():
        roomName = room.roomName()
        segNames.append((f"_{roomName}SegmentRomStart", f"_{roomName}SegmentRomEnd"))

    # .h
    headerData.header += f"extern {headerName};\n"

    if not scene.write_dummy_room_list:
        # Write externs for rom segments
        headerData.header += "".join(
            [f"extern u8 {startName}[];\n" + f"extern u8 {stopName}[];\n" for startName, stopName in segNames]
        )

    # .c
    headerData.source = headerName + " = {\n"

    if scene.write_dummy_room_list:
        headerData.source = (
            "// Dummy room list\n" + headerData.source + ((indent + "{ NULL, NULL },\n") * len(scene.rooms))
        )
    else:
        headerData.source += " },\n".join(
            [indent + "{ " + f"(u32){startName}, (u32){stopName}" for startName, stopName in segNames]
        ) + " },\n"

    headerData.source += "};\n\n"
    return headerData
