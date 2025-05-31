import re
import bpy

from ...utility import parentObject, hexOrDecInt
from ..exporter.scene.actors import SceneTransitionActors
from ..scene.properties import OOTSceneHeaderProperty
from ..oot_utility import setCustomProperty, getEvalParams, getEvalParamsInt
from ..oot_constants import ootEnumCamTransition, ootData
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
    transitionActorList = getDataMatch(
        sceneData, transActorListName, "TransitionActorEntry", "transition actor list", strip=True
    )
    scene_trans_actors = SceneTransitionActors.from_data(transitionActorList, sharedSceneData.use_macros)

    for i, actor in enumerate(scene_trans_actors.entries):
        if not sharedSceneData.addHeaderIfItemExists((i, actor), "Transition Actor", headerIndex):
            rotation = tuple([0, hexOrDecInt(actor.rot), 0])

            actorObj = createEmptyWithTransform(actor.pos, [0, 0, 0] if actor.id in actorsWithRotAsParam else rotation)
            actorObj.ootEmptyType = "Transition Actor"
            actorObj.name = "Transition " + getDisplayNameFromActorID(actor.id)
            transActorProp = actorObj.ootTransitionActorProperty

            sharedSceneData.transDict[actor] = actorObj

            fromRoom = roomObjs[actor.roomFrom]
            toRoom = roomObjs[actor.roomTo]
            if actor.roomFrom != actor.roomTo:
                parentObject(fromRoom, actorObj)
                transActorProp.fromRoom = fromRoom
                transActorProp.toRoom = toRoom
                transActorProp.isRoomTransition = True
            else:
                transActorProp.isRoomTransition = False
                parentObject(toRoom, actorObj)

            setCustomProperty(transActorProp, "cameraTransitionFront", actor.cameraFront, ootEnumCamTransition)
            setCustomProperty(transActorProp, "cameraTransitionBack", actor.cameraBack, ootEnumCamTransition)

            actorProp = transActorProp.actor
            setCustomProperty(actorProp, "actor_id", actor.id, ootData.actorData.ootEnumActorID)
            if actorProp.actor_id != "Custom":
                actorProp.params = actor.params
            else:
                actorProp.params_custom = actor.params
            handleActorWithRotAsParam(actorProp, actor.id, rotation)
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


def parseActorInfo(actorMatch: re.Match, nestedBrackets: bool) -> tuple[str, list[int], list[int], str]:
    if nestedBrackets:
        actorID = actorMatch.group(1).strip()
        position = tuple(
            [hexOrDecInt(value.strip()) for value in actorMatch.group(2).split(",") if value.strip() != ""]
        )
        rotation = tuple(
            [
                hexOrDecInt(getEvalParamsInt(value.strip()))
                for value in actorMatch.group(3).split(",")
                if value.strip() != ""
            ]
        )
        actorParam = actorMatch.group(4).strip()
    else:
        params = [getEvalParams(value.strip()) for value in actorMatch.group(1).split(",")]
        actorID = params[0]
        position = tuple([hexOrDecInt(value) for value in params[1:4]])
        rotation = tuple([hexOrDecInt(value) for value in params[4:7]])
        actorParam = params[7]

    return actorID, position, rotation, actorParam.removesuffix(",")


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
        actorID, position, rotation, actorParam = parseActorInfo(spawnMatch, nestedBrackets)
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
            setCustomProperty(actorProp, "actor_id", actorID, ootData.actorData.ootEnumActorID)
            if actorProp.actor_id != "Custom":
                actorProp.params = actorParam
            else:
                actorProp.params_custom = actorParam
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
    actorList = getDataMatch(sceneData, actorListName, "ActorEntry", "actor list", strip=True)
    regex, nestedBrackets = getActorRegex(actorList)

    for actorMatch in re.finditer(regex, actorList, flags=re.DOTALL):
        actorHash = parseActorInfo(actorMatch, nestedBrackets) + (roomObj.ootRoomHeader.roomIndex,)

        if not sharedSceneData.addHeaderIfItemExists(actorHash, "Actor", headerIndex):
            actorID, position, rotation, actorParam, roomIndex = actorHash

            actorObj = createEmptyWithTransform(position, [0, 0, 0] if actorID in actorsWithRotAsParam else rotation)
            actorObj.ootEmptyType = "Actor"
            actorObj.name = getDisplayNameFromActorID(actorID)
            actorProp = actorObj.ootActorProperty

            setCustomProperty(actorProp, "actor_id", actorID, ootData.actorData.ootEnumActorID)
            if actorProp.actor_id != "Custom":
                actorProp.params = actorParam
            else:
                actorProp.params_custom = actorParam
            handleActorWithRotAsParam(actorProp, actorID, rotation)
            unsetAllHeadersExceptSpecified(actorProp.headerSettings, headerIndex)

            sharedSceneData.actorDict[actorHash] = actorObj

            parentObject(roomObj, actorObj)
