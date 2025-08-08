import bpy
import re

from pathlib import Path

from ...utility import PluginError, hexOrDecInt
from ..utility import setCustomProperty
from ..model_classes import OOTF3DContext
from ..room.properties import OOTRoomHeaderProperty
from ...game_data import game_data
from .utility import getDataMatch, stripName, parse_commands_data
from .classes import SharedSceneData
from .constants import headerNames
from .actor import parseActorList
from .room_shape import parseMeshHeader


def parseObjectList(roomHeader: OOTRoomHeaderProperty, sceneData: str, objectListName: str):
    objectData = getDataMatch(sceneData, objectListName, "s16", "object list", strip=True)
    objects = [value.strip() for value in objectData.split(",") if value.strip() != ""]

    for object in objects:
        objectProp = roomHeader.objectList.add()
        objByID = game_data.z64.objects.objects_by_id.get(object)

        if objByID is not None:
            objectProp.objectKey = objByID.key
        else:
            objectProp.objectIDCustom = object


def parseRoomCommands(
    roomName: str | None,
    roomObj: bpy.types.Object | None,
    sceneData: str,
    roomCommandsName: str,
    roomIndex: int,
    f3dContext: OOTF3DContext,
    sharedSceneData: SharedSceneData,
    headerIndex: int,
):
    # we need to access the header in `loadMultiBlock()` for the new assets system
    if not sharedSceneData.is_fast64_data and sharedSceneData.not_zapd_assets:
        header_path = Path(sharedSceneData.scenePath).resolve() / f"{sharedSceneData.scene_name}.h"
        if not header_path.exists():
            raise PluginError("ERROR: scene file header not found!")
        sceneData += header_path.read_text()

        header_path = Path(sharedSceneData.scenePath).resolve() / f"{roomName}.h"
        if not header_path.exists():
            raise PluginError("ERROR: room file header not found!")
        sceneData += header_path.read_text()

    if roomObj is None:
        # Name set in parseRoomList()
        roomObj = bpy.data.objects.new(roomCommandsName, None)
        bpy.context.scene.collection.objects.link(roomObj)
        roomObj.empty_display_type = "SPHERE"
        roomObj.location = [0, 0, (roomIndex + 1) * -2]
        roomObj.ootEmptyType = "Room"
        roomObj.ootRoomHeader.roomIndex = roomIndex
        roomObj.name = roomName

    if headerIndex == 0:
        roomHeader = roomObj.ootRoomHeader
    elif headerIndex < 4:
        roomHeader = getattr(roomObj.ootAlternateRoomHeaders, headerNames[headerIndex])
        roomHeader.usePreviousHeader = False
    else:
        cutsceneHeaders = roomObj.ootAlternateRoomHeaders.cutsceneHeaders
        while len(cutsceneHeaders) < headerIndex - 3:
            cutsceneHeaders.add()
        roomHeader = cutsceneHeaders[headerIndex - 4]

    commands = getDataMatch(sceneData, roomCommandsName, ["SceneCmd", "SCmdBase"], "scene commands")
    cmd_map = parse_commands_data(commands)
    for command, args in cmd_map.items():
        if command == "SCENE_CMD_ALTERNATE_HEADER_LIST":
            altHeadersListName = stripName(args[0])
            parseAlternateRoomHeaders(roomObj, roomIndex, sharedSceneData, sceneData, altHeadersListName, f3dContext)
        elif command == "SCENE_CMD_ECHO_SETTINGS":
            roomHeader.echo = args[0]
        elif command == "SCENE_CMD_ROOM_BEHAVIOR":
            setCustomProperty(roomHeader, "roomBehaviour", args[0], game_data.z64.get_enum("room_type"))
            setCustomProperty(roomHeader, "linkIdleMode", args[1], game_data.z64.get_enum("environment_type"))
            roomHeader.showInvisibleActors = args[2] == "true" or args[2] == "1"
            roomHeader.disableWarpSongs = args[3] == "true" or args[3] == "1"
        elif command == "SCENE_CMD_SKYBOX_DISABLES":
            roomHeader.disableSkybox = args[0] == "true" or args[0] == "1"
            roomHeader.disableSunMoon = args[1] == "true" or args[1] == "1"
        elif command == "SCENE_CMD_TIME_SETTINGS":
            hours = hexOrDecInt(args[0])
            minutes = hexOrDecInt(args[1])
            if hours == 255 and minutes == 255:
                roomHeader.leaveTimeUnchanged = True
            else:
                roomHeader.leaveTimeUnchanged = False
                roomHeader.timeHours = hours
                roomHeader.timeMinutes = minutes
            roomHeader.timeSpeed = hexOrDecInt(args[2]) / 10
        elif command == "SCENE_CMD_WIND_SETTINGS":
            windVector = [
                int.from_bytes(
                    hexOrDecInt(value).to_bytes(1, "big", signed=hexOrDecInt(value) < 0x80), "big", signed=True
                )
                for value in args[0:3]
            ]
            windStrength = hexOrDecInt(args[3])

            roomHeader.windVector = windVector
            roomHeader.windStrength = windStrength
            roomHeader.setWind = True
        elif (command == "SCENE_CMD_ROOM_SHAPE" or command == "SCENE_CMD_MESH") and sharedSceneData.includeMesh:
            # Assumption that all rooms use the same mesh.
            if headerIndex == 0:
                meshHeaderName = args[0][1:]  # remove '&'
                parseMeshHeader(roomObj, sceneData, meshHeaderName, f3dContext, sharedSceneData)
        elif command == "SCENE_CMD_OBJECT_LIST":
            objectListName = stripName(args[1])
            parseObjectList(roomHeader, sceneData, objectListName)
        elif command == "SCENE_CMD_ACTOR_LIST" and sharedSceneData.includeActors:
            actorListName = stripName(args[1])
            parseActorList(roomObj, sceneData, actorListName, sharedSceneData, headerIndex)

    return roomObj


def parseAlternateRoomHeaders(
    roomObj: bpy.types.Object,
    roomIndex: int,
    sharedSceneData: SharedSceneData,
    sceneData: str,
    altHeadersListName: str,
    f3dContext: OOTF3DContext,
):
    altHeadersData = getDataMatch(sceneData, altHeadersListName, ["SceneCmd*", "SCmdBase*"], "alternate header list")
    altHeadersList = [value.strip() for value in altHeadersData.split(",") if value.strip() != ""]
    room_name = roomObj.name.split(".")[0]

    for i in range(len(altHeadersList)):
        if not (altHeadersList[i] == "NULL" or altHeadersList[i] == "0"):
            parseRoomCommands(
                room_name, roomObj, sceneData, altHeadersList[i], roomIndex, f3dContext, sharedSceneData, i + 1
            )
