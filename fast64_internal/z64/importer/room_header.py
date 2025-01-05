import bpy
import re

from ...utility import hexOrDecInt
from ...constants import game_data
from ..utility import (
    setCustomProperty,
    is_game_oot,
    get_cs_index_start,
    get_game_prop_name,
)
from ..model_classes import OOTF3DContext
from ..room.properties import Z64_RoomHeaderProperty
from ..constants import oot_data, mm_data
from .utility import getDataMatch, stripName
from .classes import SharedSceneData
from .constants import headerNames
from .actor import parseActorList
from .room_shape import parseMeshHeader


def get_object_from_id(object: str):
    if is_game_oot():
        return oot_data.objectData.objects_by_id.get(object)
    else:
        return mm_data.object_data.objects_by_id.get(object)


def parseObjectList(roomHeader: Z64_RoomHeaderProperty, sceneData: str, objectListName: str):
    objectData = getDataMatch(sceneData, objectListName, "s16", "object list")
    objects = [value.strip() for value in objectData.split(",") if value.strip() != ""]

    for object in objects:
        objectProp = roomHeader.objectList.add()
        objByID = get_object_from_id(object)

        if objByID is not None:
            setattr(objectProp, get_game_prop_name("object_key"), objByID.key)
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
    elif is_game_oot() and headerIndex < get_cs_index_start():
        roomHeader = getattr(roomObj.ootAlternateRoomHeaders, headerNames[headerIndex])
        roomHeader.usePreviousHeader = False
    else:
        cutsceneHeaders = roomObj.ootAlternateRoomHeaders.cutsceneHeaders
        while len(cutsceneHeaders) < headerIndex - (get_cs_index_start() - 1):
            cutsceneHeaders.add()
        roomHeader = cutsceneHeaders[headerIndex - get_cs_index_start()]

    commands = getDataMatch(sceneData, roomCommandsName, ["SceneCmd", "SCmdBase"], "scene commands")
    for commandMatch in re.finditer(rf"(SCENE\_CMD\_[a-zA-Z0-9\_]*)\s*\((.*?)\)\s*,", commands, flags=re.DOTALL):
        command = commandMatch.group(1)
        args = [arg.strip() for arg in commandMatch.group(2).split(",")]
        if command == "SCENE_CMD_ALTERNATE_HEADER_LIST":
            altHeadersListName = stripName(args[0])
            parseAlternateRoomHeaders(roomObj, roomIndex, sharedSceneData, sceneData, altHeadersListName, f3dContext)
        elif command == "SCENE_CMD_ECHO_SETTINGS":
            roomHeader.echo = args[0]
        elif command == "SCENE_CMD_ROOM_BEHAVIOR":
            setCustomProperty(
                roomHeader,
                get_game_prop_name("room_type"),
                args[0],
                game_data.z64.ootEnumRoomBehaviour,
                "roomBehaviourCustom",
            )
            setCustomProperty(
                roomHeader,
                get_game_prop_name("environment_type"),
                args[1],
                game_data.z64.ootEnumLinkIdle,
                "linkIdleModeCustom",
            )
            roomHeader.showInvisibleActors = args[2] == "true" or args[2] == "1"

            if is_game_oot():
                roomHeader.disableWarpSongs = args[3] == "true" or args[3] == "1"
            else:
                roomHeader.enable_pos_lights = args[4] == "true" or args[4] == "1"
                roomHeader.enable_storm = args[5] == "true" or args[5] == "1"
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

    for i in range(len(altHeadersList)):
        if not (altHeadersList[i] == "NULL" or altHeadersList[i] == "0"):
            parseRoomCommands(
                roomObj.name, roomObj, sceneData, altHeadersList[i], roomIndex, f3dContext, sharedSceneData, i + 1
            )
