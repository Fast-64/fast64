import math
import os
import re
import bpy
import mathutils

from bpy.types import Object
from ...utility import PluginError, readFile, parentObject, hexOrDecInt, gammaInverse
from ...game_data import game_data
from ...f3d.f3d_parser import parseMatrices
from ..model_classes import OOTF3DContext
from ..scene.properties import Z64_SceneHeaderProperty, Z64_LightProperty
from ..animated_mats.properties import enum_anim_mat_type
from ..actor_cutscene.properties import enum_cs_cam_id, enum_end_cam, enum_end_sfx, enum_hud_visibility
from ..utility import (
    getEvalParams,
    setCustomProperty,
    getObjectList,
    getEnumIndex,
    get_new_empty_object,
    twos_complement,
)
from .constants import headerNames
from .utility import getDataMatch, stripName
from .classes import SharedSceneData
from .room_header import parseRoomCommands
from .actor import parseTransActorList, parseSpawnList, parseEntranceList
from .scene_collision import parseCollisionHeader, parseCamDataList
from .scene_pathways import parsePathList

from ..constants import (
    ootEnumAudioSessionPreset,
    ootEnumCameraMode,
    ootEnumMapLocation,
    ootEnumNaviHints,
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


def parse_mm_map_data(scene_header, scene_data: str, list_name: str):
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


def parse_mm_map_data_chest(
    room_obj_list: list[Object], scene_header, scene_data: str, chest_count: int, list_name: str
):
    data_match = getDataMatch(scene_data, list_name, ["MapDataChest", "MinimapChest"], "minimap chest")
    chest_map_data = data_match.strip().split("\n")

    if len(chest_map_data) != chest_count:
        print(
            f"WARNING: chest count ({chest_count}) is different than parsed chest data length ({len(chest_map_data)})"
        )

    if room_obj_list is None or len(room_obj_list) == 0:
        raise PluginError("ERROR: The room list doesn't exist or is empty!")

    for data in chest_map_data:
        map_data = data.strip().removeprefix("{ ").removesuffix(" },").split(", ")
        chest_room_id, chest_flag, chest_pos_x, chest_pos_y, chest_pos_z = map_data

        # fetch room
        chest_room = None
        for room in room_obj_list:
            if getattr(room.ootRoomHeader, "roomIndex") == int(chest_room_id, base=0):
                chest_room = room
                break

        # fetch chest actor (based on the chest flag and room index, maybe we should check for the coordinates too?)
        chest_actor_obj = None
        if chest_room is not None:
            for child_obj in chest_room.children_recursive:
                if child_obj.type == "EMPTY" and child_obj.ootEmptyType == "Actor":
                    actor_id: str = getattr(child_obj.ootActorProperty, "actor_id")
                    actor_params = int(getEvalParams(child_obj.ootActorProperty.params_custom), base=0)

                    if actor_id in {"ACTOR_EN_BOX"}:
                        actor_chest_flag = actor_params & 0x1F
                        if actor_chest_flag == int(chest_flag, base=0):
                            chest_actor_obj = child_obj
                            break
        else:
            raise PluginError("ERROR: Chest's Room not found!")

        if chest_actor_obj is not None:
            new_prop = scene_header.minimap_chest_list.add()
            new_prop.chest_obj = chest_actor_obj
        else:
            raise PluginError("ERROR: Chest Object not found!")


animated_material_first_list_name = ""


def parse_animated_material(scene_obj: Object, header_index: int, scene_data: str, list_name: str):
    global animated_material_first_list_name

    data_match = getDataMatch(scene_data, list_name, "AnimatedMaterial", "animated material")
    anim_mat_data = data_match.strip().split("\n")

    if header_index == 0:
        animated_material_first_list_name = list_name
        anim_mat_obj = get_new_empty_object("Animated Material")
        anim_mat_obj.ootEmptyType = "Animated Materials"
        parentObject(scene_obj, anim_mat_obj)
    else:
        obj_list = getObjectList(scene_obj.children_recursive, "EMPTY", "Animated Materials")
        anim_mat_obj = obj_list[0]

    # if the alternate header is using the first header's data then don't do anything
    if header_index > 0 and list_name == animated_material_first_list_name:
        return

    anim_mat_props = anim_mat_obj.z64_anim_mats_property
    anim_mat_item = anim_mat_props.items.add()
    anim_mat_item.header_index = header_index

    for data in anim_mat_data:
        data = data.replace("{", "").replace("}", "").removesuffix(",").strip()

        split = data.split(", ")
        segment = int(split[0], base=0)
        type_num = int(split[1], base=0)
        data_ptr = split[2].removeprefix("&")

        is_array = type_num in {0, 1}
        struct_name, data_match = getDataMatch(
            scene_data, data_ptr, r"(AnimatedMat[a-zA-Z]*Params)", "animated params", is_array, False
        )

        if is_array:
            params_data = data_match.replace("{", "").replace("}", "").replace(" ", "").split("\n")
        else:
            params_data = data_match.replace("\n", "").replace(" ", "").split(",")

        entry = anim_mat_item.entries.add()
        entry.segment_num = abs(segment) + 7
        entry.type = enum_anim_mat_type[type_num + 1][0]

        if struct_name == "AnimatedMatTexScrollParams":
            for params in params_data:
                if len(params) > 0:
                    split = params.split(",")
                    scroll_entry = entry.tex_scroll_params.entries.add()
                    scroll_entry.step_x = int(split[0], base=0)
                    scroll_entry.step_y = int(split[1], base=0)
                    scroll_entry.width = int(split[2], base=0)
                    scroll_entry.height = int(split[3], base=0)
        elif struct_name == "AnimatedMatColorParams":
            entry.color_params.frame_count = int(params_data[0], base=0)

            prim_match = getDataMatch(scene_data, params_data[2], "F3DPrimColor", "animated material prim color", True)
            prim_data = prim_match.strip().replace(" ", "").replace("}", "").replace("{", "").split("\n")

            env_match = getDataMatch(scene_data, params_data[3], "F3DEnvColor", "animated material env color", True)
            env_data = env_match.strip().replace(" ", "").replace("}", "").replace("{", "").split("\n")

            frame_match = getDataMatch(scene_data, params_data[4], "u16", "animated material color frame data", True)
            frame_data = frame_match.strip().replace(" ", "").removesuffix(",").replace(",", "\n").split("\n")

            assert len(prim_data) == len(env_data) == len(frame_data)

            for prim_color_raw, env_color_raw, frame in zip(prim_data, env_data, frame_data):
                prim_color = prim_color_raw.split(",")
                env_color = env_color_raw.split(",")

                color_entry = entry.color_params.keyframes.add()
                color_entry.frame_num = int(frame, base=0)
                color_entry.prim_lod_frac = int(prim_color[4].strip(), base=0)
                color_entry.prim_color = parseColor(prim_color[0:3]) + (1,)
                color_entry.env_color = parseColor(env_color[0:3]) + (1,)
        elif struct_name == "AnimatedMatTexCycleParams":
            entry.tex_cycle_params.frame_count = int(params_data[0], base=0)
            textures: list[str] = []
            frames: list[int] = []

            data_match = getDataMatch(scene_data, params_data[1], "TexturePtr", "animated material texture ptr", True)
            for texture_ptr in data_match.replace(",", "\n").strip().split("\n"):
                textures.append(texture_ptr.strip())

            data_match = getDataMatch(scene_data, params_data[2], "u8", "animated material frame data", True)
            for frame_num in data_match.replace(",", "\n").strip().split("\n"):
                frames.append(int(frame_num.strip(), base=0))

            while len(textures) < len(frames):
                textures.append("")

            for texture_ptr, frame_num in zip(textures, frames):
                cycle_entry = entry.tex_cycle_params.keyframes.add()
                cycle_entry.frame_num = frame_num
                cycle_entry.texture = texture_ptr


def set_actor_cs_property(value: str, enum: tuple[str, str, str], data, prop_name: str, is_cam: bool = False):
    enum_index = None

    try:
        if is_cam:
            # since the value is negative it will simply go backwards in the list
            enum_index = int(value, base=0)

            # use camera obj pointer mode if the value is not negative
            if enum_index >= 0:
                enum_index = 1
        else:
            # accounting for custom value
            enum_index = int(value, base=0) + 1
    except:
        enum_index = getEnumIndex(enum, value)

    if enum_index is not None:
        setattr(data, prop_name, enum[enum_index][0])
    else:
        setattr(data, prop_name, "Custom")
        setattr(data, f"{prop_name}_custom", value)


def parse_actor_cs(scene_obj: Object, header_index: int, scene_data: str, list_name: str):
    data_match = getDataMatch(scene_data, list_name, "CutsceneEntry", "actor cs")
    actor_cs_data = data_match.strip().replace(" ", "").replace("{", "").replace("}", "").split("\n")

    # TODO: implement alt headers
    if header_index != 0:
        return

    actor_cs_obj = get_new_empty_object("Actor Cutscene")
    actor_cs_obj.ootEmptyType = "Actor Cutscene"
    parentObject(scene_obj, actor_cs_obj)

    props = actor_cs_obj.z64_actor_cs_property

    for data in actor_cs_data:
        split = data.removesuffix(",").split(",")

        new_entry = props.entries.add()
        new_entry.priority = int(split[0], base=0)
        new_entry.length = int(split[1], base=0)
        set_actor_cs_property(split[2], enum_cs_cam_id, new_entry, "cs_cam_id", True)
        new_entry.script_index = int(split[3], base=0)
        new_entry.additional_cs_id = int(split[4], base=0)
        set_actor_cs_property(split[5], enum_end_sfx, new_entry, "end_sfx")
        new_entry.custom_value = split[6]
        set_actor_cs_property(split[7], enum_hud_visibility, new_entry, "hud_visibility")
        set_actor_cs_property(split[8], enum_end_cam, new_entry, "end_cam")
        new_entry.letterbox_size = int(split[9], base=0)

        if new_entry.cs_cam_id == "Camera":
            for obj in bpy.data.objects:
                cam_props = obj.ootCameraPositionProperty
                if obj.type == "CAMERA" and cam_props.is_actor_cs_cam and cam_props.index == int(split[2], base=0):
                    new_entry.cs_cam_obj = obj
                    break


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
    elif game_data.z64.is_oot() and headerIndex < game_data.z64.cs_index_start:
        sceneHeader = getattr(sceneObj.ootAlternateSceneHeaders, headerNames[headerIndex])
        sceneHeader.usePreviousHeader = False
    else:
        cutsceneHeaders = sceneObj.ootAlternateSceneHeaders.cutsceneHeaders
        while len(cutsceneHeaders) < headerIndex - (game_data.z64.cs_index_start - 1):
            cutsceneHeaders.add()
        sceneHeader = cutsceneHeaders[headerIndex - game_data.z64.cs_index_start]

    commands = getDataMatch(sceneData, sceneCommandsName, ["SceneCmd", "SCmdBase"], "scene commands")
    entranceList = None
    # command to delay: command args
    delayed_commands: dict[str, list[str]] = {}
    command_map: dict[str, list[str]] = {}

    # store the commands to process with the corresponding args
    for commandMatch in re.finditer(rf"(SCENE\_CMD\_[a-zA-Z0-9\_]*)\s*\((.*?)\)\s*,", commands, flags=re.DOTALL):
        command = commandMatch.group(1)
        args = [arg.strip() for arg in commandMatch.group(2).split(",")]
        command_map[command] = args

    command_list = list(command_map.keys())

    for command, args in command_map.items():
        if command == "SCENE_CMD_SOUND_SETTINGS":
            setCustomProperty(sceneHeader, "audioSessionPreset", args[0], ootEnumAudioSessionPreset)
            setCustomProperty(
                sceneHeader,
                "nightSeq",
                args[1],
                game_data.z64.ootEnumNightSeq,
                "nightSeqCustom",
            )

            if args[2].startswith("NA_BGM_"):
                enum_id = args[2]
            else:
                enum_id = game_data.z64.enums.enumByKey["seq_id"].item_by_index[int(args[2])].id

            setCustomProperty(sceneHeader, "musicSeq", enum_id, game_data.z64.get_enum("musicSeq"), "musicSeqCustom")
            command_list.remove(command)
        elif command == "SCENE_CMD_ROOM_LIST":
            # Delay until actor cutscenes are processed
            delayed_commands[command] = args
            command_list.remove(command)
        elif command == "SCENE_CMD_TRANSITION_ACTOR_LIST":
            if sharedSceneData.includeActors:
                # This must be handled after rooms, so that room objs can be referenced
                delayed_commands[command] = args
            command_list.remove(command)
        elif game_data.z64.is_oot() and command == "SCENE_CMD_MISC_SETTINGS":
            setCustomProperty(sceneHeader, "cameraMode", args[0], ootEnumCameraMode)
            setCustomProperty(sceneHeader, "mapLocation", args[1], ootEnumMapLocation)
            command_list.remove(command)
        elif command == "SCENE_CMD_COL_HEADER":
            # Delay until after rooms are processed
            delayed_commands[command] = args
            command_list.remove(command)
        elif command == "SCENE_CMD_ENTRANCE_LIST":
            if sharedSceneData.includeActors:
                # Delay until after rooms are processed
                delayed_commands[command] = args
            command_list.remove(command)
        elif command == "SCENE_CMD_SPECIAL_FILES":
            if game_data.z64.is_oot():
                setCustomProperty(sceneHeader, "naviCup", args[0], ootEnumNaviHints)
            setCustomProperty(
                sceneHeader,
                "globalObject",
                args[1],
                game_data.z64.get_enum("globalObject"),
                "globalObjectCustom",
            )
            command_list.remove(command)
        elif command == "SCENE_CMD_PATH_LIST":
            if sharedSceneData.includePaths:
                pathListName = stripName(args[0])
                parsePathList(sceneObj, sceneData, pathListName, headerIndex, sharedSceneData)
            command_list.remove(command)
        elif command == "SCENE_CMD_SPAWN_LIST":
            if sharedSceneData.includeActors:
                # This must be handled after entrance list, so that entrance list and room list can be referenced
                delayed_commands[command] = args
            command_list.remove(command)
        elif command == "SCENE_CMD_SKYBOX_SETTINGS":
            args_index = 0
            if game_data.z64.is_mm():
                sceneHeader.skybox_texture_id = args[args_index]
                args_index += 1
            setCustomProperty(
                sceneHeader,
                "skyboxID",
                args[args_index],
                game_data.z64.ootEnumSkybox,
                "skyboxIDCustom",
            )
            setCustomProperty(
                sceneHeader,
                "skyboxCloudiness",
                args[args_index + 1],
                game_data.z64.ootEnumCloudiness,
                "skyboxCloudinessCustom",
            )
            setCustomProperty(sceneHeader, "skyboxLighting", args[args_index + 2], ootEnumSkyboxLighting)
            command_list.remove(command)
        elif command == "SCENE_CMD_EXIT_LIST":
            exitListName = stripName(args[0])
            parseExitList(sceneHeader, sceneData, exitListName)
            command_list.remove(command)
        elif command == "SCENE_CMD_ENV_LIGHT_SETTINGS":
            if sharedSceneData.includeLights:
                if not (args[1] == "NULL" or args[1] == "0" or args[1] == "0x00"):
                    lightsListName = stripName(args[1])
                    parseLightList(sceneObj, sceneHeader, sceneData, lightsListName, headerIndex)
            command_list.remove(command)
        elif command == "SCENE_CMD_CUTSCENE_DATA":
            if sharedSceneData.includeCutscenes:
                sceneHeader.writeCutscene = True
                sceneHeader.csWriteType = "Object"
                csObjName = f"Cutscene.{args[0]}"
                try:
                    sceneHeader.csWriteObject = bpy.data.objects[csObjName]
                except:
                    print(f"ERROR: Cutscene ``{csObjName}`` do not exist!")
            command_list.remove(command)
        elif command == "SCENE_CMD_ALTERNATE_HEADER_LIST":
            # Delay until after rooms are processed
            delayed_commands[command] = args
            command_list.remove(command)
        elif command == "SCENE_CMD_END":
            command_list.remove(command)

        # handle Majora's Mask exclusive commands
        elif game_data.z64.is_mm():
            if command == "SCENE_CMD_SET_REGION_VISITED":
                sceneHeader.set_region_visited = True
                command_list.remove(command)
            elif command in {"SCENE_CMD_MINIMAP_INFO", "SCENE_CMD_MAP_DATA"}:
                parse_mm_map_data(sceneHeader, sceneData, stripName(args[0]))
                command_list.remove(command)
            elif command in {"SCENE_CMD_MINIMAP_COMPASS_ICON_INFO", "SCENE_CMD_MAP_DATA_CHESTS"}:
                # Delay until rooms and actors are processed
                delayed_commands[command] = args
                command_list.remove(command)
            elif command == "SCENE_CMD_ANIMATED_MATERIAL_LIST":
                if sharedSceneData.includeAnimatedMats:
                    parse_animated_material(sceneObj, headerIndex, sceneData, stripName(args[0]))
                command_list.remove(command)
            elif command == "SCENE_CMD_ACTOR_CUTSCENE_CAM_LIST":
                if sharedSceneData.includeActorCs:
                    # TODO: implement alt headers
                    if headerIndex == 0:
                        parseCamDataList(sceneObj, stripName(args[1]), sceneData, True)
                command_list.remove(command)
            elif command == "SCENE_CMD_ACTOR_CUTSCENE_LIST":
                if sharedSceneData.includeActorCs:
                    # Delay until cameras are processed, if used
                    delayed_commands[command] = args
                command_list.remove(command)

    # requires `SCENE_CMD_ACTOR_CUTSCENE_CAM_LIST`
    if "SCENE_CMD_ACTOR_CUTSCENE_LIST" in delayed_commands:
        if sharedSceneData.includeActorCs:
            args = delayed_commands["SCENE_CMD_ACTOR_CUTSCENE_LIST"]
            parse_actor_cs(sceneObj, headerIndex, sceneData, stripName(args[1]))
        delayed_commands.pop("SCENE_CMD_ACTOR_CUTSCENE_LIST")

    # requires `SCENE_CMD_ACTOR_CUTSCENE_LIST`
    if "SCENE_CMD_ROOM_LIST" in delayed_commands:
        args = delayed_commands["SCENE_CMD_ROOM_LIST"]
        # Assumption that all scenes use the same room list.
        if headerIndex == 0:
            if roomObjs is not None:
                raise PluginError("Attempting to parse a room list while room objs already loaded.")
            roomListName = stripName(args[1])
            roomObjs = parseRoomList(sceneObj, sceneData, roomListName, f3dContext, sharedSceneData, headerIndex)
        delayed_commands.pop("SCENE_CMD_ROOM_LIST")
    else:
        raise PluginError("ERROR: no room command found for this scene!")

    # any other delayed command requires rooms to be processed
    for command, args in delayed_commands.items():
        if command == "SCENE_CMD_TRANSITION_ACTOR_LIST" and sharedSceneData.includeActors:
            transActorListName = stripName(args[1])
            parseTransActorList(roomObjs, sceneData, transActorListName, sharedSceneData, headerIndex)
        elif command == "SCENE_CMD_COL_HEADER":
            # Assumption that all scenes use the same collision.
            if headerIndex == 0:
                collisionHeaderName = args[0][1:]  # remove '&'
                parseCollisionHeader(sceneObj, roomObjs, sceneData, collisionHeaderName, sharedSceneData)
        elif command == "SCENE_CMD_ENTRANCE_LIST" and sharedSceneData.includeActors:
            if not (args[0] == "NULL" or args[0] == "0" or args[0] == "0x00"):
                entranceListName = stripName(args[0])
                entranceList = parseEntranceList(sceneHeader, roomObjs, sceneData, entranceListName)
        elif command == "SCENE_CMD_SPAWN_LIST" and sharedSceneData.includeActors:
            if not (args[1] == "NULL" or args[1] == "0" or args[1] == "0x00"):
                spawnListName = stripName(args[1])
                parseSpawnList(roomObjs, sceneData, spawnListName, entranceList, sharedSceneData, headerIndex)

                # Clear entrance list
                entranceList = None
        elif command == "SCENE_CMD_ALTERNATE_HEADER_LIST":
            parseAlternateSceneHeaders(sceneObj, roomObjs, sceneData, stripName(args[0]), f3dContext, sharedSceneData)
        elif command in {"SCENE_CMD_MINIMAP_COMPASS_ICON_INFO", "SCENE_CMD_MAP_DATA_CHESTS"}:
            if sharedSceneData.includeActors:
                parse_mm_map_data_chest(roomObjs, sceneHeader, sceneData, int(args[0], base=0), stripName(args[1]))

    if len(command_list) > 0:
        print(f"INFO: The following scene commands weren't processed for header {headerIndex}:")
        for command in command_list:
            print(f"- {repr(command)}")

    return sceneObj
