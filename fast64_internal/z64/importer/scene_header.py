import math
import re
import bpy
import mathutils

from bpy.types import Object
from pathlib import Path
from typing import Optional

from ...game_data import game_data
from ...utility import PluginError, get_new_empty_object, parentObject, hexOrDecInt
from ...f3d.f3d_parser import parseMatrices
from ..exporter.scene.general import EnvLightSettings
from ..model_classes import OOTF3DContext
from ..scene.properties import OOTSceneHeaderProperty, OOTLightProperty
from ..utility import getEvalParams, setCustomProperty, is_oot_features, getEnumIndex, twos_complement, parseColor
from .constants import headerNames
from .utility import getDataMatch, stripName
from .classes import SharedSceneData
from .room_header import parseRoomCommands
from .actor import parseTransActorList, parseSpawnList, parseEntranceList
from .scene_collision import parseCollisionHeader, parseCamDataList
from .scene_pathways import parsePathList
from ..animated_mats.properties import Z64_AnimatedMaterial
from ..actor_cutscene.properties import enum_cs_cam_id, enum_end_cam, enum_end_sfx, enum_hud_visibility

from ..constants import (
    ootEnumAudioSessionPreset,
    ootEnumCameraMode,
    ootEnumMapLocation,
    ootEnumNaviHints,
    ootEnumSkyboxLighting,
)


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
        lights_empty = get_new_empty_object(
            f"{sceneObj.name} Lights (header {headerIndex})", do_select=False, parent=sceneObj
        )
        lights_empty.ootEmptyType = "None"

    parent_obj = lights_empty if lights_empty is not None else sceneObj

    custom_value = None
    if sceneHeader.skyboxLighting == "Custom":
        # try to convert the custom value to an int
        try:
            custom_value = hexOrDecInt(sceneHeader.skyboxLightingCustom)
        except Exception:
            custom_value = None

        # for older decomps, make sure it's using the right thing for convenience
        if custom_value is not None and custom_value <= 1:
            sceneHeader.skyboxLighting = "LIGHT_MODE_TIME" if custom_value == 0 else "LIGHT_MODE_SETTINGS"

    for i, lightEntry in enumerate(lightList):
        if sceneHeader.skyboxLighting == "LIGHT_MODE_TIME":
            new_tod_light = sceneHeader.tod_lights.add() if i > 0 else None

            settings_name = "Default Settings" if i == 0 else f"Light Settings {i}"
            sub_lights_empty = get_new_empty_object(
                f"(Header {headerIndex}) {settings_name}", do_select=False, parent=parent_obj
            )
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
    elif game_data.z64.is_oot():
        regex = r"\{{([\(\)\sA-Za-z0-9\_]*),([\(\)\sA-Za-z0-9\_]*)\}}\s*,"
    elif game_data.z64.is_mm():
        regex = r"{([\(\)\sA-Za-z0-9\_]*),\s?([\(\)\sA-Za-z0-9\_]*)\}\s*,"
    else:
        raise PluginError("ERROR: invalid operating mode")

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
        except Exception:
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


def parse_animated_material(anim_mat: Z64_AnimatedMaterial, scene_data: str, list_name: str):
    anim_mat_type_to_struct = {
        0: "AnimatedMatTexScrollParams",
        1: "AnimatedMatTexScrollParams",
        2: "AnimatedMatColorParams",
        3: "AnimatedMatColorParams",
        4: "AnimatedMatColorParams",
        5: "AnimatedMatTexCycleParams",
    }

    struct_to_regex = {
        "AnimatedMatTexScrollParams": r"\{\s?(0?x?\-?\d+),\s?(0?x?\-?\d+),\s?(0?x?\-?\d+),\s?(0?x?\-?\d+)\s?\}",
        "AnimatedMatColorParams": r"(\d+)(\,\n?\s*)?(\d+)(\,\n?\s*)?([a-zA-Z0-9_]*)(\,\n?\s*)?([a-zA-Z0-9_]*)(\,\n?\s*)?([a-zA-Z0-9_]*)",
        "AnimatedMatTexCycleParams": r"(\d+)(\,\n?\s*)?([a-zA-Z0-9_]*)(\,\n?\s*)?([a-zA-Z0-9_]*)",
    }

    data_match = getDataMatch(scene_data, list_name, "AnimatedMaterial", "animated material")
    anim_mat_data = data_match.strip().split("\n")

    for data in anim_mat_data:
        data = data.replace("{", "").replace("}", "").removesuffix(",").strip()

        split = data.split(", ")

        type_num = int(split[1], base=0)

        if type_num == 6:
            continue

        raw_segment = split[0]

        if "MATERIAL_SEGMENT_NUM" in raw_segment:
            raw_segment = raw_segment.removesuffix(")").split("(")[1]

        segment = int(raw_segment, base=0)
        data_ptr = split[2].removeprefix("&")

        is_array = type_num in {0, 1}
        struct_name = anim_mat_type_to_struct[type_num]
        regex = struct_to_regex[struct_name]
        data_match = getDataMatch(scene_data, data_ptr, struct_name, "animated params", is_array, False)
        params_data: list[list[str]] | list[str] = []

        if is_array:
            params_data = [
                [match.group(1), match.group(2), match.group(3), match.group(4)]
                for match in re.finditer(regex, data_match, re.DOTALL)
            ]
        else:
            match = re.search(regex, data_match, re.DOTALL)
            assert match is not None

            params_data = [match.group(1), match.group(3), match.group(5)]
            if struct_name == "AnimatedMatColorParams":
                params_data.extend([match.group(7), match.group(9)])

        entry = anim_mat.entries.add()
        entry.segment_num = segment
        enum_type = entry.user_type = game_data.z64.enums.enum_anim_mats_type[type_num + 1][0]
        entry.on_type_set(getEnumIndex(game_data.z64.get_enum("anim_mats_type"), enum_type))

        if struct_name == "AnimatedMatTexScrollParams":
            entry.tex_scroll_params.texture_1.set_from_data(params_data[0])

            if len(params_data) > 1:
                entry.tex_scroll_params.texture_2.set_from_data(params_data[1])
        elif struct_name == "AnimatedMatColorParams":
            entry.color_params.keyframe_length = int(params_data[0], base=0)

            prim_match = getDataMatch(scene_data, params_data[2], "F3DPrimColor", "animated material prim color", True)
            prim_data = prim_match.strip().replace(" ", "").replace("}", "").replace("{", "").split("\n")

            use_env_color = params_data[3] != "NULL"
            use_frame_indices = params_data[4] != "NULL"

            env_data = [None] * len(prim_data)
            if use_env_color:
                env_match = getDataMatch(scene_data, params_data[3], "F3DEnvColor", "animated material env color", True)
                env_data = env_match.strip().replace(" ", "").replace("}", "").replace("{", "").split("\n")

            frame_data = [None] * len(prim_data)
            if use_frame_indices:
                frame_match = getDataMatch(
                    scene_data, params_data[4], "u16", "animated material color frame data", True
                )
                frame_data = (
                    frame_match.strip()
                    .replace(" ", "")
                    .replace(",\n", ",")
                    .replace(",", "\n")
                    .removesuffix("\n")
                    .split("\n")
                )

            assert len(prim_data) == len(env_data) == len(frame_data)

            for prim_color_raw, env_color_raw, frame in zip(prim_data, env_data, frame_data):
                prim_color = [hexOrDecInt(elem) for elem in prim_color_raw.split(",") if len(elem) > 0]

                color_entry = entry.color_params.keyframes.add()

                if use_frame_indices:
                    assert frame is not None
                    color_entry.validate_frame_num()
                    color_entry.frame_num = int(frame, base=0)

                color_entry.prim_lod_frac = prim_color[4]
                color_entry.prim_color = parseColor(prim_color[0:3]) + (1,)

                if use_env_color:
                    assert env_color_raw is not None
                    env_color = [hexOrDecInt(elem) for elem in env_color_raw.split(",") if len(elem) > 0]
                    color_entry.env_color = parseColor(env_color[0:3]) + (1,)
        elif struct_name == "AnimatedMatTexCycleParams":
            entry.tex_cycle_params.keyframe_length = int(params_data[0], base=0)
            textures: list[str] = []
            frames: list[int] = []

            data_match = getDataMatch(scene_data, params_data[1], "TexturePtr", "animated material texture ptr", True)
            for texture_ptr in data_match.replace(" ", "").replace("\n", "").split(","):
                if len(texture_ptr) > 0:
                    textures.append(texture_ptr.strip())

            data_match = getDataMatch(scene_data, params_data[2], "u8", "animated material frame data", True)
            for frame_num in data_match.replace(",", "\n").strip().split("\n"):
                frames.append(int(frame_num.strip(), base=0))

            for symbol in textures:
                cycle_entry = entry.tex_cycle_params.textures.add()
                cycle_entry.symbol = symbol

            for frame_num in frames:
                cycle_entry = entry.tex_cycle_params.keyframes.add()
                cycle_entry.texture_index = frame_num


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
    except Exception:
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

    bpy.context.scene.fast64.oot.global_actor_cs_count = len(props.entries)


def parse_cs_script_list(scene_obj: Object, header_index: int, scene_data: str, list_name: str, expected_count: int):
    data_match = getDataMatch(scene_data, list_name, "CutsceneScriptEntry", "scripted cs list")
    cs_data = data_match.strip().replace(" ", "").replace("{", "").replace("}", "").split("\n")

    # note: if we want to import cutscenes all the scripts are gonna be processed before the scene is
    cs_map: dict[str, Object] = {
        cs_obj.name.removeprefix("Cutscene."): cs_obj
        for cs_obj in bpy.data.objects
        if cs_obj.type == "EMPTY" and cs_obj.ootEmptyType == "Cutscene"
    }

    assert len(cs_data) == expected_count
    for data in cs_data:
        split = data.removesuffix(",").split(",")
        cs_obj = cs_map[split[0]]
        props = cs_obj.ootCutsceneProperty

        props.next_entrance = split[1]
        props.play_on_spawn = int(split[2], base=16)

        if split[3].startswith("0x"):
            props.spawn_flag_type = "CS_SPAWN_FLAG_ONCE"
            props.spawn_flag = split[3]
        else:
            assert split[3].startswith("CS_SPAWN_FLAG_")
            props.spawn_flag_type = split[3]

        main_scene_props = scene_obj.ootSceneHeader
        if header_index == 0:
            extracs_props = main_scene_props.extraCutscenes
        else:
            extracs_props = scene_obj.ootAlternateSceneHeaders.cutsceneHeaders[header_index - 1].extraCutscenes

        new_entry = extracs_props.add()
        new_entry.csObject = cs_obj


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
    raw_cmds = commands.strip().replace(" ", "").split("\n")
    for raw_cmd in raw_cmds:
        cmd_match = re.search(r"(SCENE\_CMD\_[a-zA-Z0-9\_]*)", raw_cmd, re.DOTALL)
        assert cmd_match is not None
        command = cmd_match.group(1)
        args = raw_cmd.removeprefix(f"{command}(").removesuffix("),").split(",")
        command_map[command] = args

    command_list = list(command_map.keys())

    for command, args in command_map.items():
        if command == "SCENE_CMD_SOUND_SETTINGS":
            setCustomProperty(sceneHeader, "audioSessionPreset", args[0], ootEnumAudioSessionPreset)
            setCustomProperty(sceneHeader, "nightSeq", args[1], game_data.z64.get_enum("nature_id"))

            if args[2].startswith("NA_BGM_"):
                enum_id = args[2]
            else:
                enum_id = game_data.z64.enums.enumByKey["seq_id"].item_by_index[int(args[2])].id

            setCustomProperty(sceneHeader, "musicSeq", enum_id, game_data.z64.get_enum("musicSeq"))
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
        elif command in {"SCENE_CMD_ENTRANCE_LIST", "SCENE_CMD_SPAWN_LIST"}:
            if sharedSceneData.includeActors:
                # Delay until after rooms are processed
                delayed_commands["SCENE_CMD_SPAWN_LIST"] = args
            command_list.remove(command)
        elif command == "SCENE_CMD_SPECIAL_FILES":
            if game_data.z64.is_oot():
                setCustomProperty(sceneHeader, "naviCup", args[0], ootEnumNaviHints)
            setCustomProperty(sceneHeader, "globalObject", args[1], game_data.z64.get_enum("globalObject"))
            command_list.remove(command)
        elif command == "SCENE_CMD_PATH_LIST":
            if sharedSceneData.includePaths:
                pathListName = stripName(args[0])
                parsePathList(sceneObj, sceneData, pathListName, headerIndex, sharedSceneData)
            command_list.remove(command)
        elif command in {"SCENE_CMD_SPAWN_LIST", "SCENE_CMD_PLAYER_ENTRY_LIST"}:
            if sharedSceneData.includeActors:
                # This must be handled after entrance list, so that entrance list and room list can be referenced
                delayed_commands["SCENE_CMD_PLAYER_ENTRY_LIST"] = args
            command_list.remove(command)
        elif command == "SCENE_CMD_SKYBOX_SETTINGS":
            args_index = 0
            if game_data.z64.is_mm():
                sceneHeader.skybox_texture_id = args[args_index]
                args_index += 1
            setCustomProperty(sceneHeader, "skyboxID", args[args_index], game_data.z64.get_enum("skybox"))
            setCustomProperty(
                sceneHeader, "skyboxCloudiness", args[args_index + 1], game_data.z64.get_enum("skybox_config")
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
                    parseLightList(sceneObj, sceneHeader, sceneData, lightsListName, headerIndex, sharedSceneData)
            command_list.remove(command)
        elif command == "SCENE_CMD_CUTSCENE_DATA":
            if sharedSceneData.includeCutscenes:
                sceneHeader.writeCutscene = True
                sceneHeader.csWriteType = "Object"
                csObjName = f"Cutscene.{args[0]}"
                try:
                    sceneHeader.csWriteObject = bpy.data.objects[csObjName]
                except Exception:
                    print(f"ERROR: Cutscene ``{csObjName}`` do not exist!")
            command_list.remove(command)
        elif command == "SCENE_CMD_ALTERNATE_HEADER_LIST":
            # Delay until after rooms are processed
            delayed_commands[command] = args
            command_list.remove(command)
        elif command == "SCENE_CMD_END":
            command_list.remove(command)

        # handle Majora's Mask (or modded OoT) exclusive commands
        elif not is_oot_features():
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
                    parse_animated_material(sceneHeader.animated_material, sceneData, stripName(args[0]))
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
            elif command == "SCENE_CMD_CUTSCENE_SCRIPT_LIST":
                if sharedSceneData.includeCutscenes:
                    parse_cs_script_list(sceneObj, headerIndex, sceneData, stripName(args[1]), hexOrDecInt(args[0]))
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
        elif command == "SCENE_CMD_SPAWN_LIST" and sharedSceneData.includeActors and len(args) == 1:
            if not (args[0] == "NULL" or args[0] == "0" or args[0] == "0x00"):
                entranceListName = stripName(args[0])
                entranceList = parseEntranceList(sceneHeader, roomObjs, sceneData, entranceListName)
        elif command == "SCENE_CMD_PLAYER_ENTRY_LIST" and sharedSceneData.includeActors:
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
