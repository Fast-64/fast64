import math
import os
import re
import bpy
import mathutils

from typing import Optional

from ...utility import PluginError, readFile, parentObject, hexOrDecInt, gammaInverse
from ...f3d.f3d_parser import parseMatrices
from ..oot_model_classes import OOTF3DContext
from ..scene.properties import OOTSceneHeaderProperty, OOTLightProperty
from ..oot_utility import getEvalParams, setCustomProperty
from .constants import headerNames
from .utility import getDataMatch, stripName, parse_commands_data
from .classes import SharedSceneData
from .room_header import parseRoomCommands
from .actor import parseTransActorList, parseSpawnList, parseEntranceList
from .scene_collision import parseCollisionHeader
from .scene_pathways import parsePathList

from ..oot_constants import (
    ootEnumAudioSessionPreset,
    ootEnumNightSeq,
    ootEnumMusicSeq,
    ootEnumCameraMode,
    ootEnumMapLocation,
    ootEnumNaviHints,
    ootEnumGlobalObject,
    ootEnumSkybox,
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
    lightHeader: OOTLightProperty, index: int, rotation: mathutils.Euler, color: mathutils.Vector
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
    sceneHeader: OOTSceneHeaderProperty,
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


def parseExitList(sceneHeader: OOTSceneHeaderProperty, sceneData: str, exitListName: str):
    exitData = getDataMatch(sceneData, exitListName, ["u16", "s16"], "exit list", strip=True)

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


def parseSceneCommands(
    sceneName: Optional[str],
    sceneObj: Optional[bpy.types.Object],
    roomObjs: Optional[list[bpy.types.Object]],
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
    elif headerIndex < 4:
        sceneHeader = getattr(sceneObj.ootAlternateSceneHeaders, headerNames[headerIndex])
        sceneHeader.usePreviousHeader = False
    else:
        cutsceneHeaders = sceneObj.ootAlternateSceneHeaders.cutsceneHeaders
        while len(cutsceneHeaders) < headerIndex - 3:
            cutsceneHeaders.add()
        sceneHeader = cutsceneHeaders[headerIndex - 4]

    commands = getDataMatch(sceneData, sceneCommandsName, ["SceneCmd", "SCmdBase"], "scene commands")
    cmd_map = parse_commands_data(commands)
    entranceList = None
    altHeadersListName = None
    for command, args in cmd_map.items():
        if command == "SCENE_CMD_SOUND_SETTINGS":
            setCustomProperty(sceneHeader, "audioSessionPreset", args[0], ootEnumAudioSessionPreset)
            setCustomProperty(sceneHeader, "nightSeq", args[1], ootEnumNightSeq)
            setCustomProperty(sceneHeader, "musicSeq", args[2], ootEnumMusicSeq)
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

        elif command == "SCENE_CMD_MISC_SETTINGS":
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
            setCustomProperty(sceneHeader, "naviCup", args[0], ootEnumNaviHints)
            setCustomProperty(sceneHeader, "globalObject", args[1], ootEnumGlobalObject)
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
            setCustomProperty(sceneHeader, "skyboxID", args[0], ootEnumSkybox)
            setCustomProperty(sceneHeader, "skyboxCloudiness", args[1], ootEnumCloudiness)
            setCustomProperty(sceneHeader, "skyboxLighting", args[2], ootEnumSkyboxLighting)
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

    if altHeadersListName is not None:
        parseAlternateSceneHeaders(sceneObj, roomObjs, sceneData, altHeadersListName, f3dContext, sharedSceneData)

    return sceneObj
