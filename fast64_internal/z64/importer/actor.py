import re
import bpy

from bpy.types import Object
from ...utility import parentObject, hexOrDecInt
from ...constants import game_data
from ..scene.properties import Z64_SceneHeaderProperty
from ..utility import setCustomProperty, getEvalParams, is_game_oot, get_game_prop_name
from ..constants import (
    ootEnumCamTransition,
    halfday_bits_all_dawns,
    halfday_bits_all_nights,
    halfday_bits_to_enum,
    halfday_bits_values,
)
from .classes import SharedSceneData
from .constants import actorsWithRotAsParam

from .utility import (
    getDataMatch,
    createEmptyWithTransform,
    getDisplayNameFromActorID,
    handleActorWithRotAsParam,
    unsetAllHeadersExceptSpecified,
)


def parseTransActorList(
    roomObjs: list[bpy.types.Object],
    sceneData: str,
    transActorListName: str,
    sharedSceneData: SharedSceneData,
    headerIndex: int,
):
    transitionActorList = getDataMatch(sceneData, transActorListName, "TransitionActorEntry", "transition actor list")

    regex = r"(?:\{(.*?)\}\s*,)|(?:\{([a-zA-Z0-9\-_.,{}\s]*[^{]*)\},)"
    for actorMatch in re.finditer(regex, transitionActorList):
        actorMatch = actorMatch.group(0).replace(" ", "").replace("\n", "").replace("{", "").replace("}", "")

        params = [value.strip() for value in actorMatch.split(",") if value.strip() != ""]

        position = tuple([hexOrDecInt(value) for value in params[5:8]])

        rot_y = getEvalParams(params[8]) if "DEG_TO_BINANG" in params[8] else params[8]
        cutscene_id = "CS_ID_GLOBAL_END"

        if not is_game_oot():
            rotY_int = int(rot_y, base=0)
            rot_y = f"0x{(rotY_int >> 7) & 0x1FF:04X}"
            cutscene_id = f"0x{rotY_int & 0x7F:02X}"

        rotation = tuple([0, hexOrDecInt(rot_y), 0])

        roomIndexFront = hexOrDecInt(params[0])
        camFront = params[1]
        roomIndexBack = hexOrDecInt(params[2])
        camBack = params[3]
        actorID = params[4]
        actorParam = params[9]

        actorHash = (
            roomIndexFront,
            camFront,
            roomIndexBack,
            camBack,
            actorID,
            position,
            rotation,
            actorParam,
            cutscene_id,
        )
        if not sharedSceneData.addHeaderIfItemExists(actorHash, "Transition Actor", headerIndex):
            actorObj = createEmptyWithTransform(position, [0, 0, 0] if actorID in actorsWithRotAsParam else rotation)
            actorObj.ootEmptyType = "Transition Actor"
            actorObj.name = "Transition " + getDisplayNameFromActorID(params[4])
            transActorProp = actorObj.ootTransitionActorProperty

            sharedSceneData.transDict[actorHash] = actorObj

            fromRoom = roomObjs[roomIndexFront]
            toRoom = roomObjs[roomIndexBack]
            if roomIndexFront != roomIndexBack:
                parentObject(fromRoom, actorObj)
                transActorProp.fromRoom = fromRoom
                transActorProp.toRoom = toRoom
                transActorProp.isRoomTransition = True
            else:
                transActorProp.isRoomTransition = False
                parentObject(toRoom, actorObj)

            if not is_game_oot():
                transActorProp.cutscene_id = cutscene_id

            setCustomProperty(transActorProp, "cameraTransitionFront", camFront, ootEnumCamTransition)
            setCustomProperty(transActorProp, "cameraTransitionBack", camBack, ootEnumCamTransition)

            actorProp = transActorProp.actor
            setCustomProperty(
                actorProp, get_game_prop_name("actor_id"), actorID, game_data.z64.actorData.ootEnumActorID, "actorIDCustom"
            )
            if actorProp.actor_id != "Custom":
                actorProp.params = actorParam
            else:
                actorProp.params_custom = actorParam
            handleActorWithRotAsParam(actorProp, actorID, rotation)
            unsetAllHeadersExceptSpecified(actorProp.headerSettings, headerIndex)


def parseEntranceList(
    sceneHeader: Z64_SceneHeaderProperty, roomObjs: list[bpy.types.Object], sceneData: str, entranceListName: str
):
    entranceList = getDataMatch(sceneData, entranceListName, ["EntranceEntry", "Spawn"], "entrance List")

    # see also start position list
    entrances = []
    for entranceMatch in re.finditer(rf"\{{(.*?)\}}\s*,", entranceList, flags=re.DOTALL):
        params = [value.strip() for value in entranceMatch.group(1).split(",") if value.strip() != ""]
        roomIndex = hexOrDecInt(params[1])
        spawnIndex = hexOrDecInt(params[0])

        entrances.append((spawnIndex, roomIndex))

    if len(entrances) > 1 and entrances[-1] == (0, 0):
        entrances.pop()
        sceneHeader.appendNullEntrance = True

    return entrances


def parseActorInfo(
    actorMatch: re.Match, nestedBrackets: bool
) -> tuple[str, str, list[int], tuple[int], tuple[int], str]:
    spawn_flags = [0x0000] * 3
    actor_id_flags = 0x0000

    if nestedBrackets:
        actorID = actorMatch.group(1).strip()
        position = tuple(
            [hexOrDecInt(value.strip()) for value in actorMatch.group(2).split(",") if value.strip() != ""]
        )

        if is_game_oot():
            spawn_rotation = tuple(
                [
                    hexOrDecInt(getEvalParams(value.strip()))
                    for value in actorMatch.group(3).split(",")
                    if value.strip() != ""
                ]
            )
        else:
            if "|" in actorID:
                split = actorID.split(" | ")
                actorID = split[0]
                actor_id_flags = split[1]

            spawn_rotation = []
            spawn_flags = []
            for value in actorMatch.group(3).replace(" ", "").replace("\n", "").split("SPAWN_ROT_FLAGS"):
                if value != "":
                    rot, flags = value.removeprefix("(").removesuffix(",").removesuffix(")").split(",")
                    spawn_rotation.append(hexOrDecInt(getEvalParams(rot)))
                    spawn_flags.append(hexOrDecInt(getEvalParams(flags)))

        actorParam = actorMatch.group(4).strip()
    else:
        params = [getEvalParams(value.strip()) for value in actorMatch.group(1).split(",")]
        actorID = params[0]
        position = tuple([hexOrDecInt(value) for value in params[1:4]])
        spawn_rotation = tuple([hexOrDecInt(value) for value in params[4:7]])
        actorParam = params[7]

    return actorID, actor_id_flags, position, tuple(spawn_rotation), tuple(spawn_flags), actorParam


def parseSpawnList(
    roomObjs: list[bpy.types.Object],
    sceneData: str,
    spawnListName: str,
    entranceList: list[tuple[str, str]],
    sharedSceneData: SharedSceneData,
    headerIndex: int,
):
    # see also start position list
    spawnList = getDataMatch(sceneData, spawnListName, "ActorEntry", "spawn list")
    index = 0
    regex, nestedBrackets = getActorRegex(spawnList)
    for spawnMatch in re.finditer(regex, spawnList, flags=re.DOTALL):
        actorID, actor_id_flags, position, rotation, spawn_flags, actorParam = parseActorInfo(
            spawnMatch, nestedBrackets
        )
        spawnIndex, roomIndex = [value for value in entranceList if value[0] == index][0]
        actorHash = (actorID, position, rotation, actorParam, spawnIndex, roomIndex)

        if not sharedSceneData.addHeaderIfItemExists(actorHash, "Entrance", headerIndex):
            spawnObj = createEmptyWithTransform(position, [0, 0, 0] if actorID in actorsWithRotAsParam else rotation)
            spawnObj.ootEmptyType = "Entrance"
            spawnObj.name = "Entrance"
            spawnProp = spawnObj.ootEntranceProperty
            spawnProp.tiedRoom = roomObjs[roomIndex]
            spawnProp.spawnIndex = spawnIndex
            spawnProp.customActor = actorID != "ACTOR_PLAYER"
            actorProp = spawnProp.actor
            setCustomProperty(
                actorProp, get_game_prop_name("actor_id"), actorID, game_data.z64.actorData.ootEnumActorID, "actor_id_custom"
            )
            if actorProp.actor_id != "Custom":
                actorProp.params = actorParam
            else:
                actorProp.params_custom = actorParam
            handleActorWithRotAsParam(actorProp, actorID, rotation if is_game_oot() else spawn_flags)
            unsetAllHeadersExceptSpecified(actorProp.headerSettings, headerIndex)

            sharedSceneData.entranceDict[actorHash] = spawnObj

            parentObject(roomObjs[roomIndex], spawnObj)
        index += 1


def getActorRegex(actorList: list[str]):
    nestedBrackets = re.search(r"\{[^\}]*\{", actorList) is not None
    if nestedBrackets:
        regex = r"\{(.*?),\s*\{(.*?)\}\s*,\s*\{(.*?)\}\s*,(.*?)\}\s*,"
    else:
        regex = r"\{(.*?)\}\s*,"

    return regex, nestedBrackets


def move_actor_cs_entry(global_cs_obj: Object, actor_obj: Object, index: int, default_entry):
    index &= 0x7F
    if index >= 0x78:
        return default_entry

    global_cs_props = global_cs_obj.z64_actor_cs_property
    actor_cs_props = actor_obj.z64_actor_cs_property
    entry = global_cs_props.entries[index]
    additional_cs_id = entry.additional_cs_id

    new_entry = actor_cs_props.entries.add()
    new_entry.priority = entry.priority
    new_entry.length = entry.length
    new_entry.cs_cam_id = entry.cs_cam_id
    new_entry.cs_cam_id_custom = entry.cs_cam_id_custom
    new_entry.cs_cam_obj = entry.cs_cam_obj
    new_entry.script_index = entry.script_index
    new_entry.additional_cs_id = additional_cs_id
    new_entry.end_sfx = entry.end_sfx
    new_entry.end_sfx_custom = entry.end_sfx_custom
    new_entry.custom_value = entry.custom_value
    new_entry.hud_visibility = entry.hud_visibility
    new_entry.hud_visibility_custom = entry.hud_visibility_custom
    new_entry.end_cam = entry.end_cam
    new_entry.end_cam_custom = entry.end_cam_custom
    new_entry.letterbox_size = entry.letterbox_size

    return new_entry


def parseActorList(
    roomObj: bpy.types.Object, sceneData: str, actorListName: str, sharedSceneData: SharedSceneData, headerIndex: int
):
    actorList = getDataMatch(sceneData, actorListName, "ActorEntry", "actor list")
    regex, nestedBrackets = getActorRegex(actorList)

    for actorMatch in re.finditer(regex, actorList, flags=re.DOTALL):
        actorHash = parseActorInfo(actorMatch, nestedBrackets) + (roomObj.ootRoomHeader.roomIndex,)

        if not sharedSceneData.addHeaderIfItemExists(actorHash, "Actor", headerIndex):
            actorID, actor_id_flags, position, rotation, spawn_flags, actorParam, roomIndex = actorHash

            actorObj = createEmptyWithTransform(position, [0, 0, 0] if actorID in actorsWithRotAsParam else rotation)
            actorObj.ootEmptyType = "Actor"
            actorObj.name = getDisplayNameFromActorID(actorID)
            actorProp = actorObj.ootActorProperty
            setCustomProperty(
                actorProp, get_game_prop_name("actor_id"), actorID, game_data.z64.actorData.ootEnumActorID, "actor_id_custom"
            )
            actorProp.actorParam = actorParam
            handleActorWithRotAsParam(actorProp, actorID, rotation)
            unsetAllHeadersExceptSpecified(actorProp.headerSettings, headerIndex)

            actor_cs_obj = None
            for obj in bpy.data.objects:
                if obj.type == "EMPTY" and obj.ootEmptyType == "Actor Cutscene":
                    actor_cs_obj = obj
                    break

            if sharedSceneData.includeActorCs and actor_cs_obj is not None:
                # move any actor cs entry to the actor object embedded list based on the cs index of rot.y
                # also move any other entries as defined by the additional cs id
                new_entry = move_actor_cs_entry(actor_cs_obj, actorObj, spawn_flags[1], None)
                if new_entry is not None:
                    while new_entry.additional_cs_id != -1:
                        new_entry = move_actor_cs_entry(actor_cs_obj, actorObj, new_entry.additional_cs_id, new_entry)

            # see `Actor_SpawnEntry()`
            halfday_bits = ((spawn_flags[0] & 7) << 7) | (spawn_flags[2] & 0x7F)
            actorProp.halfday_all = halfday_bits == halfday_bits_all_dawns | halfday_bits_all_nights

            if not actorProp.halfday_all:
                actorProp.halfday_all_dawns = halfday_bits == halfday_bits_all_dawns
                actorProp.halfday_all_nights = halfday_bits == halfday_bits_all_nights

            if not actorProp.halfday_all and not actorProp.halfday_all_dawns and not actorProp.halfday_all_nights:
                for bits in halfday_bits_values:
                    value = halfday_bits & bits

                    if value > 0:
                        new_entry = actorProp.halfday_bits.add()
                        new_entry.value = halfday_bits_to_enum[value]

            sharedSceneData.actorDict[actorHash] = actorObj

            parentObject(roomObj, actorObj)
