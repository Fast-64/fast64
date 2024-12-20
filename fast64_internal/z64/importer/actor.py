import re
import bpy

from ...utility import parentObject, hexOrDecInt
from ..scene.properties import OOTSceneHeaderProperty
from ..utility import setCustomProperty, getEvalParams, get_game_props, is_game_oot, get_game_enum
from ..constants import ootEnumCamTransition
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

        rotY = getEvalParams(params[8]) if "DEG_TO_BINANG" in params[8] else params[8]
        rotation = tuple([0, hexOrDecInt(rotY), 0])

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
        )
        if not sharedSceneData.addHeaderIfItemExists(actorHash, "Transition Actor", headerIndex):
            actorObj = createEmptyWithTransform(position, [0, 0, 0] if actorID in actorsWithRotAsParam else rotation)
            actorObj.ootEmptyType = "Transition Actor"
            actorObj.name = "Transition " + getDisplayNameFromActorID(params[4])
            transActorProp = get_game_props(actorObj, "transition_actor")

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

            setCustomProperty(transActorProp, "cameraTransitionFront", camFront, ootEnumCamTransition)
            setCustomProperty(transActorProp, "cameraTransitionBack", camBack, ootEnumCamTransition)

            actorProp = transActorProp.actor
            setCustomProperty(actorProp, "actorID", actorID, get_game_enum("enum_actor_id"))
            actorProp.actorParam = actorParam
            handleActorWithRotAsParam(actorProp, actorID, rotation)
            unsetAllHeadersExceptSpecified(actorProp.headerSettings, headerIndex)


def parseEntranceList(
    sceneHeader: OOTSceneHeaderProperty, roomObjs: list[bpy.types.Object], sceneData: str, entranceListName: str
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
    spawn_flags = ["0x0000"] * 3
    actor_id_flags = "0x0000"

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
                    spawn_flags.append(flags)

        actorParam = actorMatch.group(4).strip()
    else:
        params = [getEvalParams(value.strip()) for value in actorMatch.group(1).split(",")]
        actorID = params[0]
        position = tuple([hexOrDecInt(value) for value in params[1:4]])
        spawn_rotation = tuple([hexOrDecInt(value) for value in params[4:7]])
        actorParam = params[7]

    return actorID, actor_id_flags, position, tuple(spawn_rotation), tuple(spawn_flags), actorParam


def set_actor_flags(actor_prop, actor_id_flags: str, spawn_flags: tuple[str, str, str]):
    if not is_game_oot():
        actor_prop.actor_id_flags = actor_id_flags
        actor_prop.rot_flags_x = spawn_flags[0]
        actor_prop.rot_flags_y = spawn_flags[1]
        actor_prop.rot_flags_z = spawn_flags[2]


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
            spawnProp = get_game_props(spawnObj, "entrance_actor")
            spawnProp.tiedRoom = roomObjs[roomIndex]
            spawnProp.spawnIndex = spawnIndex
            spawnProp.customActor = actorID != "ACTOR_PLAYER"
            actorProp = spawnProp.actor
            set_actor_flags(actorProp, actor_id_flags, spawn_flags)
            setCustomProperty(actorProp, "actorID", actorID, get_game_enum("enum_actor_id"))
            actorProp.actorParam = actorParam
            handleActorWithRotAsParam(actorProp, actorID, rotation)
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


def parseActorList(
    roomObj: bpy.types.Object, sceneData: str, actorListName: str, sharedSceneData: SharedSceneData, headerIndex: int
):
    actorList = getDataMatch(sceneData, actorListName, "ActorEntry", "actor list")
    regex, nestedBrackets = getActorRegex(actorList)

    for actorMatch in re.finditer(regex, actorList, flags=re.DOTALL):
        actorHash = parseActorInfo(actorMatch, nestedBrackets) + (get_game_props(roomObj, "room").roomIndex,)

        if not sharedSceneData.addHeaderIfItemExists(actorHash, "Actor", headerIndex):
            actorID, actor_id_flags, position, rotation, spawn_flags, actorParam, roomIndex = actorHash

            actorObj = createEmptyWithTransform(position, [0, 0, 0] if actorID in actorsWithRotAsParam else rotation)
            actorObj.ootEmptyType = "Actor"
            actorObj.name = getDisplayNameFromActorID(actorID)
            actorProp = get_game_props(actorObj, "actor")
            set_actor_flags(actorProp, actor_id_flags, spawn_flags)
            setCustomProperty(actorProp, "actorID", actorID, get_game_enum("enum_actor_id"))
            actorProp.actorParam = actorParam
            handleActorWithRotAsParam(actorProp, actorID, rotation)
            unsetAllHeadersExceptSpecified(actorProp.headerSettings, headerIndex)

            sharedSceneData.actorDict[actorHash] = actorObj

            parentObject(roomObj, actorObj)
