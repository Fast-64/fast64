import math, os
from ..oot_f3d_writer import *
from ..oot_level_writer import *
from ..oot_collision import *
from ..oot_cutscene import *
from ..oot_level import OOTImportSceneSettingsProperty
from ..oot_scene_room import OOTSceneHeaderProperty
from .oot_scene_table_c import getDrawConfig

# TODO: Handle draw config import
def parseScene(
    f3dType: str,
    isHWv1: bool,
    dlFormat: DLFormat,
    saveTexture: bool,
    settings: OOTImportSceneSettingsProperty,
    option: str,
):
    sceneName = settings.name
    if settings.isCustomDest:
        importPath = bpy.path.abspath(settings.destPath)
        subfolder = None
    else:
        if option == "Custom":
            subfolder = "assets/scenes/" + settings.subFolder + "/"
        else:
            sceneName = sceneNameFromID(option)
            subfolder = None
        importPath = bpy.path.abspath(bpy.context.scene.ootDecompPath)

    importSubdir = ""
    if settings.isCustomDest is not None:
        importSubdir = subfolder
    if not settings.isCustomDest and subfolder is None:
        importSubdir = os.path.dirname(getSceneDirFromLevelName(sceneName)) + "/"

    sceneFolderPath = ootGetPath(importPath, settings.isCustomDest, importSubdir, sceneName, False, True)
    sceneData = readFile(os.path.join(sceneFolderPath, f"{sceneName}_scene.c"))

    roomData = ""
    for match in re.finditer(rf"#include\s*\"({re.escape(sceneName)}\_room\_[0-9]+)\.h\"", sceneData, flags=re.DOTALL):
        roomData += readFile(os.path.join(sceneFolderPath, match.group(1) + ".c"))

    sceneData += roomData

    if bpy.context.mode != "OBJECT":
        bpy.context.mode = "OBJECT"

    sceneObj = parseSceneCommands(sceneName, sceneData, settings.isCustomDest)


def parseSceneCommands(sceneName: str, sceneData: str, isCustomImport: bool):
    sceneCommandsName = f"{sceneName}_sceneCommands"

    location = mathutils.Vector((0, 0, 10))
    bpy.ops.object.empty_add(type="SPHERE", radius=1, align="WORLD", location=location[:])
    sceneObj = bpy.context.view_layer.objects.active
    sceneObj.ootEmptyType = "Scene"
    sceneObj.name = sceneName
    bpy.context.scene.ootSceneExportObj = sceneObj
    sceneHeader = sceneObj.ootSceneHeader

    if not isCustomImport:
        setCustomProperty(sceneHeader.sceneTableEntry, "drawConfig", getDrawConfig(sceneName), ootEnumDrawConfig)

    match = re.search(
        rf"SceneCmd\s*{re.escape(sceneCommandsName)}\s*\[[\s0-9A-Fa-fx]*\]\s*=\s*\{{(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if not match:
        raise PluginError(f"Could not find scene commands {sceneCommandsName}.")

    commands = match.group(1)
    for commandMatch in re.finditer(rf"(SCENE\_CMD\_[a-zA-Z0-9\_]*)\s*\((.*?)\)\s*,", commands, flags=re.DOTALL):
        command = commandMatch.group(1)
        args = [arg.strip() for arg in commandMatch.group(2).split(",")]
        if command == "SCENE_CMD_SOUND_SETTINGS":
            setCustomProperty(sceneHeader, "audioSessionPreset", args[0], ootEnumAudioSessionPreset)
            setCustomProperty(sceneHeader, "nightSeq", args[1], ootEnumNightSeq)
            setCustomProperty(sceneHeader, "musicSeq", args[2], ootEnumMusicSeq)
        elif command == "SCENE_CMD_ROOM_LIST":
            roomListName = args[1]
            parseRoomList(sceneObj, sceneData, roomListName)
        elif command == "SCENE_CMD_TRANSITION_ACTOR_LIST":
            transActorHeaderName = args[1]
            print("Command not implemented.")
        elif command == "SCENE_CMD_MISC_SETTINGS":
            setCustomProperty(sceneHeader, "cameraMode", args[0], ootEnumCameraMode)
            setCustomProperty(sceneHeader, "mapLocation", args[1], ootEnumMapLocation)
        elif command == "SCENE_CMD_COL_HEADER":
            collisionHeaderName = args[0][1:]  # remove '&'
            print("Command not implemented.")
        elif command == "SCENE_CMD_ENTRANCE_LIST":
            if args[0] == "NULL" or args[0] == "0" or args[0] == "0x00":
                pass
            else:
                entranceListName = args[0]
            print("Command not implemented.")
        elif command == "SCENE_CMD_SPECIAL_FILES":
            setCustomProperty(sceneHeader, "naviCup", args[0], ootEnumNaviHints)
            setCustomProperty(sceneHeader, "globalObject", args[1], ootEnumGlobalObject)
        elif command == "SCENE_CMD_SPECIAL_FILES":
            setCustomProperty(sceneHeader, "naviCup", args[0], ootEnumNaviHints)
            setCustomProperty(sceneHeader, "globalObject", args[1], ootEnumGlobalObject)
        elif command == "SCENE_CMD_PATH_LIST":
            pathListName = args[0]
            print("Command not implemented.")
        elif command == "SCENE_CMD_SPAWN_LIST":
            if args[1] == "NULL" or args[1] == "0" or args[1] == "0x00":
                pass
            else:
                pathListName = args[1]
            print("Command not implemented.")
        elif command == "SCENE_CMD_SKYBOX_SETTINGS":
            setCustomProperty(sceneHeader, "skyboxID", args[0], ootEnumSkybox)
            setCustomProperty(sceneHeader, "skyboxCloudiness", args[1], ootEnumCloudiness)
            setCustomProperty(sceneHeader, "skyboxLighting", args[2], ootEnumSkyboxLighting)
        elif command == "SCENE_CMD_EXIT_LIST":
            exitListName = args[0]
            print("Command not implemented.")
        elif command == "SCENE_CMD_ENV_LIGHT_SETTINGS":
            if args[1] == "NULL" or args[1] == "0" or args[1] == "0x00":
                pass
            else:
                lightListName = args[1]
            print("Command not implemented.")
        elif command == "SCENE_CMD_CUTSCENE_DATA":
            cutsceneName = args[0]
            print("Command not implemented.")

    return sceneObj


def parseRoomList(sceneObj: bpy.types.Object, sceneData: str, roomListName: str):
    match = re.search(
        rf"RomFile\s*{re.escape(roomListName)}\s*\[[\s0-9A-Fa-fx]*\]\s*=\s*\{{(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if not match:
        raise PluginError(f"Could not find scene commands {roomListName}.")

    roomList = match.group(1)
    index = 0
    roomObjs = []
    for roomMatch in re.finditer(rf"\{{([\sA-Za-z0-9\_]*),([\sA-Za-z0-9\_]*)\}}\s*,", roomList, flags=re.DOTALL):
        roomName = roomMatch.group(1).strip().replace("SegmentRomStart", "")[1:]
        roomObj = parseRoomCommands(sceneData, roomName, index)
        parentObject(sceneObj, roomObj)
        index += 1

    return roomObjs


def parseRoomCommands(sceneData: str, roomName: str, roomIndex: int):
    roomCommandsName = f"{roomName}Commands"

    bpy.ops.object.empty_add(type="SPHERE", radius=1, align="WORLD", location=[0, 0, 8 - roomIndex * 2])
    roomObj = bpy.context.view_layer.objects.active
    roomObj.ootEmptyType = "Room"
    roomObj.name = roomName
    roomHeader = roomObj.ootRoomHeader
    roomHeader.roomIndex = roomIndex

    match = re.search(
        rf"SceneCmd\s*{re.escape(roomCommandsName)}\s*\[[\s0-9A-Fa-fx]*\]\s*=\s*\{{(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if not match:
        raise PluginError(f"Could not find scene commands {roomCommandsName}.")

    commands = match.group(1)
    for commandMatch in re.finditer(rf"(SCENE\_CMD\_[a-zA-Z0-9\_]*)\s*\((.*?)\)\s*,", commands, flags=re.DOTALL):
        command = commandMatch.group(1)
        args = [arg.strip() for arg in commandMatch.group(2).split(",")]
        if command == "SCENE_CMD_ALTERNATE_HEADER_LIST":
            altHeadersList = args[0]
            print("Command not implemented.")
        elif command == "SCENE_CMD_ECHO_SETTINGS":
            roomHeader.echo = args[0]
        elif command == "SCENE_CMD_ROOM_BEHAVIOR":
            setCustomProperty(roomHeader, "roomBehaviour", args[0], ootEnumRoomBehaviour)
            setCustomProperty(roomHeader, "linkIdleMode", args[1], ootEnumLinkIdle)
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
            print("Command not implemented.")
        elif command == "SCENE_CMD_MESH":
            meshHeaderName = args[0]
            print("Command not implemented.")
        elif command == "SCENE_CMD_OBJECT_LIST":
            objectListName = args[1]
            print("Command not implemented.")
        elif command == "SCENE_CMD_ACTOR_LIST":
            actorListName = args[1]
            print("Command not implemented.")

    return roomObj
