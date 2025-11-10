import math
import re
import bpy
import mathutils

from pathlib import Path
from typing import Optional

from ...game_data import game_data
from ...utility import PluginError, get_new_object, parentObject, hexOrDecInt, gammaInverse
from ...f3d.f3d_parser import parseMatrices
from ..exporter.scene.general import EnvLightSettings
from ..model_classes import OOTF3DContext
from ..scene.properties import OOTSceneHeaderProperty, OOTLightProperty
from ..utility import setCustomProperty
from .constants import headerNames
from .utility import getDataMatch, stripName, parse_commands_data
from .classes import SharedSceneData
from .room_header import parseRoomCommands
from .actor import parseTransActorList, parseSpawnList, parseEntranceList
from .scene_collision import parseCollisionHeader
from .scene_pathways import parsePathList

from ..constants import (
    ootEnumAudioSessionPreset,
    ootEnumMusicSeq,
    ootEnumCameraMode,
    ootEnumMapLocation,
    ootEnumNaviHints,
    ootEnumGlobalObject,
    ootEnumSkyboxLighting,
)


def parseColor(values: tuple[int, int, int]) -> tuple[float, float, float]:
    return tuple(gammaInverse([value / 0xFF for value in values]))


def parseDirection(index: int, values: tuple[int, int, int]) -> tuple[float, float, float] | int:
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
    lightHeader: OOTLightProperty, index: int, rotation: mathutils.Euler, color: mathutils.Vector, desc: str
) -> bpy.types.Object | None:
    setattr(lightHeader, f"useCustomDiffuse{index}", rotation != "Zero" and rotation != "Default")

    if rotation == "Zero" or rotation == "Default":
        setattr(lightHeader, f"zeroDiffuse{index}", rotation == "Zero")
        setattr(lightHeader, f"diffuse{index}", color + (1,))
        return None
    else:
        light = bpy.data.lights.new(f"{desc} Diffuse {index} Light", "SUN")
        lightObj = bpy.data.objects.new(f"{desc} Diffuse {index}", light)
        bpy.context.scene.collection.objects.link(lightObj)
        setattr(lightHeader, f"diffuse{index}Custom", lightObj.data)
        lightObj.rotation_euler = rotation
        lightObj.data.color = color
        lightObj.data.type = "SUN"
        return lightObj


def set_light_props(
    parent_obj: bpy.types.Object,
    light_props: OOTLightProperty,
    header_index: int,
    index: int,
    light_entry: EnvLightSettings,
    desc: str,
):
    ambient_col = parseColor(light_entry.ambientColor)
    diffuse0_dir = parseDirection(0, light_entry.light1Dir)
    diffuse0_col = parseColor(light_entry.light1Color)
    diffuse1_dir = parseDirection(1, light_entry.light2Dir)
    diffuse1_col = parseColor(light_entry.light2Color)
    fog_col = parseColor(light_entry.fogColor)

    light_props.ambient = ambient_col + (1,)

    lightObj0 = parseLight(light_props, 0, diffuse0_dir, diffuse0_col, desc)
    lightObj1 = parseLight(light_props, 1, diffuse1_dir, diffuse1_col, desc)

    if lightObj0 is not None:
        parentObject(parent_obj, lightObj0)
        lightObj0.location = [4 + header_index * 2, 0, -index * 2]
    if lightObj1 is not None:
        parentObject(parent_obj, lightObj1)
        lightObj1.location = [4 + header_index * 2, 2, -index * 2]

    light_props.fogColor = fog_col + (1,)
    light_props.fogNear = light_entry.fogNear
    light_props.z_far = light_entry.zFar
    light_props.transitionSpeed = light_entry.blendRate


def parseLightList(
    sceneObj: bpy.types.Object,
    sceneHeader: OOTSceneHeaderProperty,
    sceneData: str,
    lightListName: str,
    headerIndex: int,
    sharedSceneData: SharedSceneData,
):
    lightData = getDataMatch(sceneData, lightListName, ["LightSettings", "EnvLightSettings"], "light list", strip=True)
    lightList = EnvLightSettings.from_data(lightData, sharedSceneData.not_zapd_assets)

    sceneHeader.tod_lights.clear()
    sceneHeader.lightList.clear()

    lights_empty = None
    if len(lightList) > 0:
        lights_empty = get_new_object(f"{sceneObj.name} Lights (header {headerIndex})", None, False, sceneObj)
        lights_empty.ootEmptyType = "None"

    parent_obj = lights_empty if lights_empty is not None else sceneObj

    custom_value = None
    if sceneHeader.skyboxLighting == "Custom":
        # try to convert the custom value to an int
        try:
            custom_value = hexOrDecInt(sceneHeader.skyboxLightingCustom)
        except:
            custom_value = None

        # for older decomps, make sure it's using the right thing for convenience
        if custom_value is not None and custom_value <= 1:
            sceneHeader.skyboxLighting = "LIGHT_MODE_TIME" if custom_value == 0 else "LIGHT_MODE_SETTINGS"

    for i, lightEntry in enumerate(lightList):
        if sceneHeader.skyboxLighting == "LIGHT_MODE_TIME":
            new_tod_light = sceneHeader.tod_lights.add() if i > 0 else None

            settings_name = "Default Settings" if i == 0 else f"Light Settings {i}"
            sub_lights_empty = get_new_object(f"(Header {headerIndex}) {settings_name}", None, False, parent_obj)
            sub_lights_empty.ootEmptyType = "None"

            for tod_type in ["Dawn", "Day", "Dusk", "Night"]:
                desc = f"{settings_name} ({tod_type})"

                if i == 0:
                    set_light_props(
                        sub_lights_empty,
                        getattr(sceneHeader.timeOfDayLights, tod_type.lower()),
                        headerIndex,
                        i,
                        lightEntry,
                        desc,
                    )
                else:
                    assert new_tod_light is not None
                    set_light_props(
                        sub_lights_empty, getattr(new_tod_light, tod_type.lower()), headerIndex, i, lightEntry, desc
                    )
        else:
            settings_name = "Indoor" if sceneHeader.skyboxLighting != "Custom" else "Custom"
            desc = f"{settings_name} {i}"

            # indoor and custom modes shares the same properties
            set_light_props(parent_obj, sceneHeader.lightList.add(), headerIndex, i, lightEntry, desc)


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
    roomList = getDataMatch(sceneData, roomListName, "RomFile", "room list", strip=True)
    index = 0
    roomObjs = []
    use_macros = "ROM_FILE" in roomList

    if use_macros:
        regex = r"ROM_FILE\((.*?)\)"
    else:
        regex = rf"\{{([\(\)\sA-Za-z0-9\_]*),([\(\)\sA-Za-z0-9\_]*)\}}\s*,"

    # Assumption that alternate scene headers all use the same room list.
    for roomMatch in re.finditer(regex, roomList, flags=re.DOTALL):
        if use_macros:
            roomName = roomMatch.group(1)
        else:
            roomName = roomMatch.group(1).strip().replace("SegmentRomStart", "")
            if "(u32)" in roomName:
                roomName = roomName[5:].strip()[1:]  # includes leading underscore
            elif "(uintptr_t)" in roomName:
                roomName = roomName[11:].strip()[1:]
            else:
                roomName = roomName[1:]

        file_path = Path(sharedSceneData.scenePath) / f"{roomName}.c"

        if not file_path.exists():
            file_path = Path(sharedSceneData.scenePath).resolve() / f"{roomName}_main.c"

        if not file_path.exists():
            raise PluginError("ERROR: scene not found!")

        roomData = file_path.read_text()

        if not sharedSceneData.is_single_file:
            # get the other room files for non-single file fast64 exports
            for file in file_path.parent.rglob("*.c"):
                if roomName in str(file) and f"{roomName}_main" not in str(file):
                    roomData += file.read_text()

        parseMatrices(roomData, f3dContext, 1 / bpy.context.scene.ootBlenderScale)

        roomCommandsName = f"{roomName}Commands"

        # fast64 naming
        if roomCommandsName not in roomData:
            roomCommandsName = f"{roomName}_header00"

        # newer assets system naming
        if roomCommandsName not in roomData:
            roomCommandsName = roomName

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
            setCustomProperty(sceneHeader, "nightSeq", args[1], game_data.z64.get_enum("nature_id"))
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
        elif (
            command in {"SCENE_CMD_ENTRANCE_LIST", "SCENE_CMD_SPAWN_LIST"}
            and sharedSceneData.includeActors
            and len(args) == 1
        ):
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
        elif command in {"SCENE_CMD_SPAWN_LIST", "SCENE_CMD_PLAYER_ENTRY_LIST"} and sharedSceneData.includeActors:
            if not (args[1] == "NULL" or args[1] == "0" or args[1] == "0x00"):
                spawnListName = stripName(args[1])
                parseSpawnList(roomObjs, sceneData, spawnListName, entranceList, sharedSceneData, headerIndex)

                # Clear entrance list
                entranceList = None

        elif command == "SCENE_CMD_SKYBOX_SETTINGS":
            setCustomProperty(sceneHeader, "skyboxID", args[0], game_data.z64.get_enum("skybox"))
            setCustomProperty(sceneHeader, "skyboxCloudiness", args[1], game_data.z64.get_enum("skybox_config"))
            setCustomProperty(sceneHeader, "skyboxLighting", args[2], ootEnumSkyboxLighting)
        elif command == "SCENE_CMD_EXIT_LIST":
            exitListName = stripName(args[0])
            parseExitList(sceneHeader, sceneData, exitListName)
        elif command == "SCENE_CMD_ENV_LIGHT_SETTINGS" and sharedSceneData.includeLights:
            if not (args[1] == "NULL" or args[1] == "0" or args[1] == "0x00"):
                lightsListName = stripName(args[1])
                parseLightList(sceneObj, sceneHeader, sceneData, lightsListName, headerIndex, sharedSceneData)
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
