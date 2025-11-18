from dataclasses import dataclass
from mathutils import Matrix
from bpy.types import Object
from ....utility import PluginError, CData, indent
from ...utility import ExportInfo, getObjectList
from ...model_classes import OOTModel
from ..room import Room


@dataclass
class RoomEntries:
    name: str
    entries: list[Room]

    @staticmethod
    def new(
        name: str,
        sceneName: str,
        model: OOTModel,
        original_scene_obj: Object,
        sceneObj: Object,
        transform: Matrix,
        exportInfo: ExportInfo,
    ):
        """Returns the room list from empty objects with the type 'Room'"""

        roomDict: dict[int, Room] = {}
        roomObjs = getObjectList(sceneObj.children_recursive, "EMPTY", "Room")
        original_room_list = getObjectList(original_scene_obj.children_recursive, "EMPTY", "Room")
        assert len(original_room_list) == len(roomObjs)

        roomObjs.sort(key=lambda obj: obj.ootRoomHeader.roomIndex)
        original_room_list.sort(key=lambda obj: obj.ootRoomHeader.roomIndex)

        if len(roomObjs) == 0:
            raise PluginError("ERROR: The scene has no child empties with the 'Room' empty type.")

        for original_room_obj, roomObj in zip(original_room_list, roomObjs):
            roomHeader = roomObj.ootRoomHeader
            roomIndex = roomHeader.roomIndex

            if roomIndex in roomDict:
                raise PluginError(f"ERROR: Room index {roomIndex} used more than once!")

            roomName = f"{sceneName}_room_{roomIndex}"
            roomDict[roomIndex] = Room.new(
                roomName,
                transform,
                sceneObj,
                original_room_obj,
                roomObj,
                roomHeader.roomShape,
                model.addSubModel(
                    OOTModel(
                        f"{roomName}_dl",
                        model.DLFormat,
                        None,
                        model.draw_config,
                    )
                ),
                roomIndex,
                sceneName,
                exportInfo,
            )

        for i in range(min(roomDict.keys()), len(roomDict)):
            if i not in roomDict:
                raise PluginError(f"Room indices are not consecutive. Missing room index: {i}")

        return RoomEntries(name, [roomDict[i] for i in range(min(roomDict.keys()), len(roomDict))])

    def getCmd(self):
        """Returns the room list scene command"""

        return indent + f"SCENE_CMD_ROOM_LIST({len(self.entries)}, {self.name}),\n"

    def getC(self, useDummyRoomList: bool):
        """Returns the ``CData`` containing the room list array"""

        roomList = CData()
        listName = f"RomFile {self.name}[]"

        # generating segment rom names for every room
        segNames = []
        for i in range(len(self.entries)):
            roomName = self.entries[i].name
            segNames.append((f"_{roomName}SegmentRomStart", f"_{roomName}SegmentRomEnd"))

        # .h
        roomList.header += f"extern {listName};\n"

        if not useDummyRoomList:
            # Write externs for rom segments
            roomList.header += "".join(
                f"extern u8 {startName}[];\n" + f"extern u8 {stopName}[];\n" for startName, stopName in segNames
            )

        # .c
        roomList.source = listName + " = {\n"

        if useDummyRoomList:
            roomList.source = (
                "// Dummy room list\n" + roomList.source + ((indent + "{ NULL, NULL },\n") * len(self.entries))
            )
        else:
            roomList.source += (
                " },\n".join(
                    indent + "{ " + f"(uintptr_t){startName}, (uintptr_t){stopName}" for startName, stopName in segNames
                )
                + " },\n"
            )

        roomList.source += "};\n\n"
        return roomList
