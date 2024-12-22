import math
import os
import re
import bpy
import mathutils

from ...utility import PluginError, readFile, parentObject, hexOrDecInt, gammaInverse
from ...f3d.f3d_parser import parseMatrices
from ..model_classes import OOTF3DContext
from ..scene.properties import Z64_SceneHeaderProperty, Z64_LightProperty
from ..utility import (
    getEvalParams,
    setCustomProperty,
    get_game_enum,
    is_game_oot,
    get_cs_index_start,
    get_game_prop_name,
)
from .constants import headerNames
from .utility import getDataMatch, stripName
from .classes import SharedSceneData
from .room_header import parseRoomCommands
from .actor import parseTransActorList, parseSpawnList, parseEntranceList
from .scene_collision import parseCollisionHeader
from .scene_pathways import parsePathList

from ..constants import (
    oot_data,
    mm_data,
    ootEnumAudioSessionPreset,
    ootEnumCameraMode,
    ootEnumMapLocation,
    ootEnumNaviHints,
    ootEnumGlobalObject,
    mm_enum_global_object,
    ootEnumSkybox,
    mm_enum_skybox,
    ootEnumCloudiness,
    ootEnumSkyboxLighting,
)


def parseColor(values: tuple[str, str, str]) -> tuple[float, float, float]:
    return tuple(gammaInverse([hexOrDecInt(value) / 0xFF for value in values]))


def parseDirection(index: int, values: tuple[str, str, str]) -> tuple[float, float, float] | int:
    values = [hexOrDecInt(value) for value in values]

    if tuple(values) == (0, 0, 0):
        return "Zero"
    elif index == 0 and tuple(values) == (0x49, 0x49, 0x49):
        return "Default"
    elif index == 1 and tuple(values) == (0xB7, 0xB7, 0xB7):
        return "Default"
    else:
        direction = mathutils.Vector(
            [int.from_bytes(value.to_bytes(1, "big", signed=value < 127), "big", signed=True) / 127 for value in values]
        )

        return (
            mathutils.Euler((0, 0, math.pi)).to_quaternion()
            @ (mathutils.Euler((math.pi / 2, 0, 0)).to_quaternion() @ direction).rotation_difference(
                mathutils.Vector((0, 0, 1))
            )
        ).to_euler()


def parseLight(
    lightHeader: Z64_LightProperty, index: int, rotation: mathutils.Euler, color: mathutils.Vector
) -> bpy.types.Object | None:
    setattr(lightHeader, f"useCustomDiffuse{index}", rotation != "Zero" and rotation != "Default")

    if rotation == "Zero" or rotation == "Default":
        setattr(lightHeader, f"zeroDiffuse{index}", rotation == "Zero")
        setattr(lightHeader, f"diffuse{index}", color + (1,))
        return None
    else:
        light = bpy.data.lights.new("Light", "SUN")
        lightObj = bpy.data.objects.new("Light", light)
        bpy.context.scene.collection.objects.link(lightObj)
        setattr(lightHeader, f"diffuse{index}Custom", lightObj.data)
        lightObj.rotation_euler = rotation
        lightObj.data.color = color
        lightObj.data.type = "SUN"
        return lightObj


def parseLightList(
    sceneObj: bpy.types.Object,
    sceneHeader: Z64_SceneHeaderProperty,
    sceneData: str,
    lightListName: str,
    headerIndex: int,
):
    lightData = getDataMatch(sceneData, lightListName, ["LightSettings", "EnvLightSettings"], "light list")

    # I currently don't understand the light list format in respect to this lighting flag.
    # So we'll set it to custom instead.
    if sceneHeader.skyboxLighting != "Custom":
        sceneHeader.skyboxLightingCustom = sceneHeader.skyboxLighting
        sceneHeader.skyboxLighting = "Custom"
    sceneHeader.lightList.clear()

    # convert string to ZAPD format if using new Fast64 output
    if "// Ambient Color" in sceneData:
        i = 0
        lightData = lightData.replace("{", "").replace("}", "").replace("\n", "").replace(" ", "").replace(",,", ",")
        data = "{ "
        for part in lightData.split(","):
            if i < 20:
                if i == 18:
                    part = getEvalParams(part)
                data += part + ", "
                if i == 19:
                    data = data[:-2]
            else:
                data += "},\n{ " + part + ", "
                i = 0
            i += 1
        lightData = data[:-4]

    lightList = [
        value.replace("{", "").replace("\n", "").replace(" ", "")
        for value in lightData.split("},")
        if value.strip() != ""
    ]

    index = 0
    for lightEntry in lightList:
        lightParams = [value.strip() for value in lightEntry.split(",")]

        ambientColor = parseColor(lightParams[0:3])
        diffuseDir0 = parseDirection(0, lightParams[3:6])
        diffuseColor0 = parseColor(lightParams[6:9])
        diffuseDir1 = parseDirection(1, lightParams[9:12])
        diffuseColor1 = parseColor(lightParams[12:15])
        fogColor = parseColor(lightParams[15:18])

        blendFogShort = hexOrDecInt(lightParams[18])
        fogNear = blendFogShort & ((1 << 10) - 1)
        transitionSpeed = blendFogShort >> 10
        z_far = hexOrDecInt(lightParams[19])

        lightHeader = sceneHeader.lightList.add()
        lightHeader.ambient = ambientColor + (1,)

        lightObj0 = parseLight(lightHeader, 0, diffuseDir0, diffuseColor0)
        lightObj1 = parseLight(lightHeader, 1, diffuseDir1, diffuseColor1)

        if lightObj0 is not None:
            parentObject(sceneObj, lightObj0)
            lightObj0.location = [4 + headerIndex * 2, 0, -index * 2]
        if lightObj1 is not None:
            parentObject(sceneObj, lightObj1)
            lightObj1.location = [4 + headerIndex * 2, 2, -index * 2]

        lightHeader.fogColor = fogColor + (1,)
        lightHeader.fogNear = fogNear
        lightHeader.z_far = z_far
        lightHeader.transitionSpeed = transitionSpeed

        index += 1


def parseExitList(sceneHeader: Z64_SceneHeaderProperty, sceneData: str, exitListName: str):
    exitData = getDataMatch(sceneData, exitListName, "u16", "exit list")

    # see also start position list
    exitList = [value.strip() for value in exitData.split(",") if value.strip() != ""]
    for exit in exitList:
        exitProp = sceneHeader.exitList.add()
        exitProp.exitIndex = "Custom"
        exitProp.exitIndexCustom = exit


def parseRoomList(
    sceneObj: bpy.types.Object,
    sceneData: str,
    roomListName: str,
    f3dContext: OOTF3DContext,
    sharedSceneData: SharedSceneData,
    headerIndex: int,
):
    roomList = getDataMatch(sceneData, roomListName, "RomFile", "room list")
    index = 0
    roomObjs = []

    # Assumption that alternate scene headers all use the same room list.
    for roomMatch in re.finditer(
        rf"\{{([\(\)\sA-Za-z0-9\_]*),([\(\)\sA-Za-z0-9\_]*)\}}\s*,", roomList, flags=re.DOTALL
    ):
        roomName = roomMatch.group(1).strip().replace("SegmentRomStart", "")
        if "(u32)" in roomName:
            roomName = roomName[5:].strip()[1:]  # includes leading underscore
        elif "(uintptr_t)" in roomName:
            roomName = roomName[11:].strip()[1:]
        else:
            roomName = roomName[1:]

        roomPath = os.path.join(sharedSceneData.scenePath, f"{roomName}.c")
        roomData = readFile(roomPath)
        parseMatrices(roomData, f3dContext, 1 / bpy.context.scene.ootBlenderScale)

        roomCommandsName = f"{roomName}Commands"
        if roomCommandsName not in roomData:
            roomCommandsName = f"{roomName}_header00"  # fast64 naming

        # Assumption that any shared textures are stored after the CollisionHeader.
        # This is done to avoid including large collision data in regex searches.
        try:
            collisionHeaderIndex = sceneData.index("CollisionHeader ")
        except:
            collisionHeaderIndex = 0
        sharedRoomData = sceneData[collisionHeaderIndex:]
        roomObj = parseRoomCommands(
            roomName,
            None,
            sharedRoomData + roomData,
            roomCommandsName,
            index,
            f3dContext,
            sharedSceneData,
            headerIndex,
        )
        parentObject(sceneObj, roomObj)
        index += 1
        roomObjs.append(roomObj)

    return roomObjs


def parseAlternateSceneHeaders(
    sceneObj: bpy.types.Object,
    roomObjs: list[bpy.types.Object],
    sceneData: str,
    altHeadersListName: str,
    f3dContext: OOTF3DContext,
    sharedSceneData: SharedSceneData,
):
    altHeadersData = getDataMatch(sceneData, altHeadersListName, ["SceneCmd*", "SCmdBase*"], "alternate header list")
    altHeadersList = [value.strip() for value in altHeadersData.split(",") if value.strip() != ""]

    for i in range(len(altHeadersList)):
        if not (altHeadersList[i] == "NULL" or altHeadersList[i] == "0"):
            parseSceneCommands(
                sceneObj.name, sceneObj, roomObjs, altHeadersList[i], sceneData, f3dContext, i + 1, sharedSceneData
            )


# from https://stackoverflow.com/a/6727975
def twos_complement(hexstr: str, bits: int):
    value = int(hexstr, 16)
    if value & (1 << (bits - 1)):
        value -= 1 << bits
    return value


def parse_mm_minimap_info(scene_header, scene_data: str, list_name: str):
    data_match = getDataMatch(scene_data, list_name, ["MapDataScene", "MinimapList"], "minimap scene", False)
    scene_map_data = data_match.strip().split(", ")
    scene_header.minimap_scale = int(scene_map_data[1], base=0)

    data_match = getDataMatch(scene_data, scene_map_data[0], ["MapDataRoom", "MinimapEntry"], "minimap room")
    room_map_data = data_match.strip().split("\n")
    for data in room_map_data:
        map_data = data.strip().removeprefix("{ ").removesuffix(" },").split(", ")
        new_prop = scene_header.minimap_room_list.add()
        new_prop.map_id = map_data[0]
        new_prop.center_x = twos_complement(map_data[1], 16)
        new_prop.floor_y = twos_complement(map_data[2], 16)
        new_prop.center_z = twos_complement(map_data[3], 16)
        new_prop.flags = map_data[4]

    # TODO: complete chest map data import when actors are handled
    # data_match = getDataMatch(scene_data, scene_map_data[0], ["MapDataChest", "MinimapChest"], "minimap chest")
    # chest_map_data = data_match.strip().split("\n")
    # for data in chest_map_data:
    #     map_data = data.strip().removeprefix("{ ").removesuffix(" },").split(", ")


def get_enum_id_from_index(enum_key: str, index: int):
    if is_game_oot():
        return oot_data.enumData.enumByKey[enum_key].item_by_index[index].id
    else:
        return mm_data.enum_data.enum_by_key[enum_key].item_by_index[index].id


def parseSceneCommands(
    sceneName: str | None,
    sceneObj: bpy.types.Object | None,
    roomObjs: list[bpy.types.Object] | None,
    sceneCommandsName: str,
    sceneData: str,
    f3dContext: OOTF3DContext,
    headerIndex: int,
    sharedSceneData: SharedSceneData,
):
    if sceneObj is None:
        sceneObj = bpy.data.objects.new(sceneCommandsName, None)
        bpy.context.scene.collection.objects.link(sceneObj)
        sceneObj.empty_display_type = "SPHERE"
        sceneObj.ootEmptyType = "Scene"
        sceneObj.name = sceneName

    if headerIndex == 0:
        sceneHeader = sceneObj.ootSceneHeader
    elif is_game_oot() and headerIndex < get_cs_index_start():
        sceneHeader = getattr(sceneObj.ootAlternateSceneHeaders, headerNames[headerIndex])
        sceneHeader.usePreviousHeader = False
    else:
        cutsceneHeaders = sceneObj.ootAlternateSceneHeaders.cutsceneHeaders
        while len(cutsceneHeaders) < headerIndex - (get_cs_index_start() - 1):
            cutsceneHeaders.add()
        sceneHeader = cutsceneHeaders[headerIndex - get_cs_index_start()]

    commands = getDataMatch(sceneData, sceneCommandsName, ["SceneCmd", "SCmdBase"], "scene commands")
    entranceList = None
    altHeadersListName = None
    for commandMatch in re.finditer(rf"(SCENE\_CMD\_[a-zA-Z0-9\_]*)\s*\((.*?)\)\s*,", commands, flags=re.DOTALL):
        command = commandMatch.group(1)
        args = [arg.strip() for arg in commandMatch.group(2).split(",")]
        if command == "SCENE_CMD_SOUND_SETTINGS":
            setCustomProperty(sceneHeader, "audioSessionPreset", args[0], ootEnumAudioSessionPreset)
            setCustomProperty(sceneHeader, get_game_prop_name("ambience_id"), args[1], get_game_enum("enum_ambiance_id"))

            if args[2].startswith("NA_BGM_"):
                enum_id = args[2]
            else:
                if is_game_oot():
                    enum_seq_id = oot_data.enumData.enumByKey["seqId"]
                else:
                    enum_seq_id = mm_data.enum_data.enum_by_key["seqId"]

                enum_id = enum_seq_id.item_by_index[int(args[2])].id

            setCustomProperty(sceneHeader, get_game_prop_name("seq_id"), enum_id, get_game_enum("enum_seq_id"))
        elif command == "SCENE_CMD_ROOM_LIST":
            # Assumption that all scenes use the same room list.
            if headerIndex == 0:
                if roomObjs is not None:
                    raise PluginError("Attempting to parse a room list while room objs already loaded.")
                roomListName = stripName(args[1])
                roomObjs = parseRoomList(sceneObj, sceneData, roomListName, f3dContext, sharedSceneData, headerIndex)

        # This must be handled after rooms, so that room objs can be referenced
        elif command == "SCENE_CMD_TRANSITION_ACTOR_LIST" and sharedSceneData.includeActors:
            transActorListName = stripName(args[1])
            parseTransActorList(roomObjs, sceneData, transActorListName, sharedSceneData, headerIndex)

        elif is_game_oot() and command == "SCENE_CMD_MISC_SETTINGS":
            setCustomProperty(sceneHeader, "cameraMode", args[0], ootEnumCameraMode)
            setCustomProperty(sceneHeader, "mapLocation", args[1], ootEnumMapLocation)
        elif command == "SCENE_CMD_COL_HEADER":
            # Assumption that all scenes use the same collision.
            if headerIndex == 0:
                collisionHeaderName = args[0][1:]  # remove '&'
                parseCollisionHeader(sceneObj, roomObjs, sceneData, collisionHeaderName, sharedSceneData)
        elif command == "SCENE_CMD_ENTRANCE_LIST" and sharedSceneData.includeActors:
            if not (args[0] == "NULL" or args[0] == "0" or args[0] == "0x00"):
                entranceListName = stripName(args[0])
                entranceList = parseEntranceList(sceneHeader, roomObjs, sceneData, entranceListName)
        elif command == "SCENE_CMD_SPECIAL_FILES":
            if is_game_oot():
                setCustomProperty(sceneHeader, "naviCup", args[0], ootEnumNaviHints)
            setCustomProperty(
                sceneHeader, get_game_prop_name("global_obj"), args[1], get_game_enum("enum_global_object")
            )
        elif command == "SCENE_CMD_PATH_LIST" and sharedSceneData.includePaths:
            pathListName = stripName(args[0])
            parsePathList(sceneObj, sceneData, pathListName, headerIndex, sharedSceneData)

        # This must be handled after entrance list, so that entrance list can be referenced
        elif command == "SCENE_CMD_SPAWN_LIST" and sharedSceneData.includeActors:
            if not (args[1] == "NULL" or args[1] == "0" or args[1] == "0x00"):
                spawnListName = stripName(args[1])
                parseSpawnList(roomObjs, sceneData, spawnListName, entranceList, sharedSceneData, headerIndex)

                # Clear entrance list
                entranceList = None

        elif command == "SCENE_CMD_SKYBOX_SETTINGS":
            args_index = 0
            if not is_game_oot():
                sceneHeader.skybox_texture_id = args[args_index]
                args_index += 1
            setCustomProperty(
                sceneHeader, get_game_prop_name("skybox_id"), args[args_index], get_game_enum("enum_skybox")
            )
            setCustomProperty(
                sceneHeader,
                get_game_prop_name("skybox_config"),
                args[args_index + 1],
                get_game_enum("enum_skybox_config"),
            )
            setCustomProperty(sceneHeader, "skyboxLighting", args[args_index + 2], ootEnumSkyboxLighting)
        elif command == "SCENE_CMD_EXIT_LIST":
            exitListName = stripName(args[0])
            parseExitList(sceneHeader, sceneData, exitListName)
        elif command == "SCENE_CMD_ENV_LIGHT_SETTINGS" and sharedSceneData.includeLights:
            if not (args[1] == "NULL" or args[1] == "0" or args[1] == "0x00"):
                lightsListName = stripName(args[1])
                parseLightList(sceneObj, sceneHeader, sceneData, lightsListName, headerIndex)
        elif command == "SCENE_CMD_CUTSCENE_DATA" and sharedSceneData.includeCutscenes:
            sceneHeader.writeCutscene = True
            sceneHeader.csWriteType = "Object"
            csObjName = f"Cutscene.{args[0]}"
            try:
                sceneHeader.csWriteObject = bpy.data.objects[csObjName]
            except:
                print(f"ERROR: Cutscene ``{csObjName}`` do not exist!")
        elif command == "SCENE_CMD_ALTERNATE_HEADER_LIST":
            # Delay until after rooms are parsed
            altHeadersListName = stripName(args[0])

        # handle Majora's Mask exclusive commands
        elif not is_game_oot():
            if command == "SCENE_CMD_SET_REGION_VISITED":
                sceneHeader.set_region_visited = True
            elif command in {"SCENE_CMD_MINIMAP_INFO", "SCENE_CMD_MAP_DATA"}:
                parse_mm_minimap_info(sceneHeader, sceneData, stripName(args[0]))

    if altHeadersListName is not None:
        parseAlternateSceneHeaders(sceneObj, roomObjs, sceneData, altHeadersListName, f3dContext, sharedSceneData)

    return sceneObj
