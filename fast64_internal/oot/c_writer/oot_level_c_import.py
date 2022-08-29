import math, os
from ..oot_f3d_writer import *
from ..oot_level_writer import *
from ..oot_collision import *
from ..oot_cutscene import *
from ..oot_level import OOTImportSceneSettingsProperty
from ..oot_scene_room import OOTSceneHeaderProperty
from .oot_scene_table_c import getDrawConfig
from ...utility import yUpToZUp

headerNames = ["childDayHeader", "childNightHeader", "adultDayHeader", "adultNightHeader"]


class SharedActorData:
    def __init__(self):
        self.actorDict = {}  # actor hash : blender object
        self.entranceDict = {}  # actor hash : blender object
        self.transDict = {}  # actor hash : blender object

    def addHeaderIfActorExists(self, actorHash, emptyType: str, headerIndex: int):
        if emptyType == "Actor":
            dictToAdd = self.actorDict
        elif emptyType == "Entrance":
            dictToAdd = self.entranceDict
        elif emptyType == "Transition Actor":
            dictToAdd = self.transDict
        else:
            raise PluginError(f"Invalid empty type for shared actor handling: {emptyType}")

        if actorHash not in dictToAdd:
            return False

        actorObj = dictToAdd[actorHash]
        if emptyType == "Actor":
            actorProp = actorObj.ootActorProperty
        elif emptyType == "Entrance":
            actorProp = actorObj.ootEntranceProperty.actor
        elif emptyType == "Transition Actor":
            actorProp = actorObj.ootTransitionActorProperty.actor

        if headerIndex < 4:
            setattr(actorProp.headerSettings, headerNames[headerIndex], True)
        else:
            cutsceneHeaders = actorProp.headerSettings.cutsceneHeaders
            if len([header for header in cutsceneHeaders if header.headerIndex == headerIndex]) == 0:
                cutsceneHeaders.add().headerIndex = headerIndex

        return True


def parseScene(
    f3dType: str,
    isHWv1: bool,
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

    f3dContext = OOTF3DContext(F3D(f3dType, isHWv1), [], bpy.path.abspath(bpy.context.scene.ootDecompPath))
    parseMatrices(sceneData, f3dContext, 1 / bpy.context.scene.ootBlenderScale)
    f3dContext.addMatrix("&gMtxClear", mathutils.Matrix.Scale(1 / bpy.context.scene.ootBlenderScale, 4))

    sceneCommandsName = f"{sceneName}_sceneCommands"
    sharedActorData = SharedActorData()
    sceneObj = parseSceneCommands(None, None, sceneCommandsName, sceneData, f3dContext, 0, sharedActorData)
    bpy.context.scene.ootSceneExportObj = sceneObj

    if not settings.isCustomDest:
        setCustomProperty(
            sceneObj.ootSceneHeader.sceneTableEntry, "drawConfig", getDrawConfig(sceneName), ootEnumDrawConfig
        )


def parseSceneCommands(
    sceneObj: bpy.types.Object | None,
    roomObjs: list[bpy.types.Object] | None,
    sceneCommandsName: str,
    sceneData: str,
    f3dContext: OOTF3DContext,
    headerIndex: int,
    sharedActorData: SharedActorData,
):
    if sceneObj is None:
        location = mathutils.Vector((0, 0, 10))
        bpy.ops.object.empty_add(type="SPHERE", radius=1, align="WORLD", location=location[:])
        sceneObj = bpy.context.view_layer.objects.active
        sceneObj.ootEmptyType = "Scene"
        sceneObj.name = sceneCommandsName

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

    match = re.search(
        rf"SceneCmd\s*{re.escape(sceneCommandsName)}\s*\[[\s0-9A-Fa-fx]*\]\s*=\s*\{{(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if not match:
        raise PluginError(f"Could not find scene commands {sceneCommandsName}.")

    commands = match.group(1)
    entranceList = None
    altHeadersListName = None
    for commandMatch in re.finditer(rf"(SCENE\_CMD\_[a-zA-Z0-9\_]*)\s*\((.*?)\)\s*,", commands, flags=re.DOTALL):
        command = commandMatch.group(1)
        args = [arg.strip() for arg in commandMatch.group(2).split(",")]
        if command == "SCENE_CMD_SOUND_SETTINGS":
            setCustomProperty(sceneHeader, "audioSessionPreset", args[0], ootEnumAudioSessionPreset)
            setCustomProperty(sceneHeader, "nightSeq", args[1], ootEnumNightSeq)
            setCustomProperty(sceneHeader, "musicSeq", args[2], ootEnumMusicSeq)
        elif command == "SCENE_CMD_ROOM_LIST":
            # Assumption that all scenes use the same room list.
            if headerIndex == 0:
                if roomObjs is not None:
                    raise PluginError("Attempting to parse a room list while room objs already loaded.")
                roomListName = args[1]
                roomObjs = parseRoomList(sceneObj, sceneData, roomListName, f3dContext, sharedActorData, headerIndex)

        # This must be handled after rooms, so that room objs can be referenced
        elif command == "SCENE_CMD_TRANSITION_ACTOR_LIST":
            transActorListName = args[1]
            parseTransActorList(roomObjs, sceneData, transActorListName, sharedActorData, headerIndex)

        elif command == "SCENE_CMD_MISC_SETTINGS":
            setCustomProperty(sceneHeader, "cameraMode", args[0], ootEnumCameraMode)
            setCustomProperty(sceneHeader, "mapLocation", args[1], ootEnumMapLocation)
        elif command == "SCENE_CMD_COL_HEADER":
            # Assumption that all scenes use the same collision.
            if headerIndex == 0:
                collisionHeaderName = args[0][1:]  # remove '&'
            print("Command not implemented.")
        elif command == "SCENE_CMD_ENTRANCE_LIST":
            if not (args[0] == "NULL" or args[0] == "0" or args[0] == "0x00"):
                entranceListName = args[0]
                entranceList = parseEntranceList(sceneHeader, roomObjs, sceneData, entranceListName)
        elif command == "SCENE_CMD_SPECIAL_FILES":
            setCustomProperty(sceneHeader, "naviCup", args[0], ootEnumNaviHints)
            setCustomProperty(sceneHeader, "globalObject", args[1], ootEnumGlobalObject)
        elif command == "SCENE_CMD_SPECIAL_FILES":
            setCustomProperty(sceneHeader, "naviCup", args[0], ootEnumNaviHints)
            setCustomProperty(sceneHeader, "globalObject", args[1], ootEnumGlobalObject)
        elif command == "SCENE_CMD_PATH_LIST":
            pathListName = args[0]
            print("Command not implemented.")

        # This must be handled after entrance list, so that entrance list can be referenced
        elif command == "SCENE_CMD_SPAWN_LIST":
            if not (args[1] == "NULL" or args[1] == "0" or args[1] == "0x00"):
                spawnListName = args[1]
                parseSpawnList(roomObjs, sceneData, spawnListName, entranceList, sharedActorData, headerIndex)

        elif command == "SCENE_CMD_SKYBOX_SETTINGS":
            setCustomProperty(sceneHeader, "skyboxID", args[0], ootEnumSkybox)
            setCustomProperty(sceneHeader, "skyboxCloudiness", args[1], ootEnumCloudiness)
            setCustomProperty(sceneHeader, "skyboxLighting", args[2], ootEnumSkyboxLighting)
        elif command == "SCENE_CMD_EXIT_LIST":
            exitListName = args[0]
            parseExitList(sceneHeader, sceneData, exitListName)
        elif command == "SCENE_CMD_ENV_LIGHT_SETTINGS":
            if not (args[1] == "NULL" or args[1] == "0" or args[1] == "0x00"):
                lightListName = args[1]
            print("Command not implemented.")
        elif command == "SCENE_CMD_CUTSCENE_DATA":
            cutsceneName = args[0]
            print("Command not implemented.")
        elif command == "SCENE_CMD_ALTERNATE_HEADER_LIST":
            # Delay until after rooms are parsed
            altHeadersListName = args[0]

    if altHeadersListName is not None:
        parseAlternateSceneHeaders(sceneObj, roomObjs, sceneData, altHeadersListName, f3dContext, sharedActorData)

    return sceneObj


def parseRoomList(
    sceneObj: bpy.types.Object,
    sceneData: str,
    roomListName: str,
    f3dContext: OOTF3DContext,
    sharedActorData: SharedActorData,
    headerIndex: int,
):
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

    # Assumption that alternate scene headers all use the same room list.
    for roomMatch in re.finditer(rf"\{{([\sA-Za-z0-9\_]*),([\sA-Za-z0-9\_]*)\}}\s*,", roomList, flags=re.DOTALL):
        roomName = roomMatch.group(1).strip().replace("SegmentRomStart", "")[1:]
        roomCommandsName = f"{roomName}Commands"
        roomObj = parseRoomCommands(None, sceneData, roomCommandsName, index, f3dContext, sharedActorData, headerIndex)
        parentObject(sceneObj, roomObj)
        index += 1
        roomObjs.append(roomObj)

    return roomObjs


def parseRoomCommands(
    roomObj: bpy.types.Object | None,
    sceneData: str,
    roomCommandsName: str,
    roomIndex: int,
    f3dContext: OOTF3DContext,
    sharedActorData: SharedActorData,
    headerIndex: int,
):
    if roomObj is None:
        bpy.ops.object.empty_add(type="SPHERE", radius=1, align="WORLD", location=[0, 0, 8 - roomIndex * 2])
        roomObj = bpy.context.view_layer.objects.active
        roomObj.ootEmptyType = "Room"
        roomObj.name = roomCommandsName
        roomObj.ootRoomHeader.roomIndex = roomIndex

    if headerIndex == 0:
        roomHeader = roomObj.ootRoomHeader
    elif headerIndex < 4:
        roomHeader = getattr(roomObj.ootAlternateRoomHeaders, headerNames[headerIndex])
        roomHeader.usePreviousHeader = False
    else:
        cutsceneHeaders = roomObj.ootAlternateRoomHeaders.cutsceneHeaders
        while len(cutsceneHeaders) < headerIndex - 3:
            cutsceneHeaders.add()
        roomHeader = cutsceneHeaders[headerIndex - 4]

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
            altHeadersListName = args[0]
            parseAlternateRoomHeaders(roomObj, roomIndex, sharedActorData, sceneData, altHeadersListName, f3dContext)
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
        elif command == "SCENE_CMD_MESH":
            # Assumption that all rooms use the same mesh.
            if headerIndex == 0:
                meshHeaderName = args[0][1:]  # remove '&'
                parseMeshHeader(roomObj, sceneData, meshHeaderName, f3dContext)
        elif command == "SCENE_CMD_OBJECT_LIST":
            objectListName = args[1]
            parseObjectList(roomHeader, sceneData, objectListName)
        elif command == "SCENE_CMD_ACTOR_LIST":
            actorListName = args[1]
            parseActorList(roomObj, sceneData, actorListName, sharedActorData, headerIndex)

    return roomObj


def parseMeshHeader(roomObj: bpy.types.Object, sceneData: str, meshHeaderName: str, f3dContext: OOTF3DContext):
    roomHeader = roomObj.ootRoomHeader
    match = re.search(
        rf"([0-9A-Za-z\_]+)\s*{re.escape(meshHeaderName)}\s*=\s*\{{(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if not match:
        raise PluginError(f"Could not find mesh header {meshHeaderName}.")

    meshStructType = match.group(1)
    meshParams = [value.strip() for value in match.group(2).split(",")]
    roomHeader.meshType = meshParams[0]

    meshListName = meshParams[2]
    parseMeshList(roomObj, sceneData, meshListName, int(meshParams[0]), f3dContext)


def parseMeshList(
    roomObj: bpy.types.Object, sceneData: str, meshListName: str, meshType: int, f3dContext: OOTF3DContext
):
    roomHeader = roomObj.ootRoomHeader
    match = re.search(
        rf"([0-9A-Za-z\_]+)\s*{re.escape(meshListName)}\s*\[[\s0-9A-Fa-fx]*\]\s*=\s*\{{(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if not match:
        raise PluginError(f"Could not find mesh header {meshListName}.")

    meshStructType = match.group(1)
    meshEntryData = match.group(2)
    if meshType == 2:
        matchPattern = r"\{\s*\{(.*?),(.*?),(.*?)\}\s*,(.*?),(.*?),(.*?)\}\s*,"
    elif meshType == 1:
        raise PluginError(f"Mesh type 1 not supported for {meshListName}")
    else:
        matchPattern = r"\{(.*?),(.*?)\}\s*,"

    for entryMatch in re.finditer(matchPattern, meshEntryData, flags=re.DOTALL):
        if meshType == 2:
            opaqueDL = entryMatch.group(5).strip()
            transparentDL = entryMatch.group(6).strip()
            position = yUpToZUp @ mathutils.Vector(
                [
                    hexOrDecInt(entryMatch.group(value).strip()) / bpy.context.scene.ootBlenderScale
                    for value in range(1, 4)
                ]
            )
            bpy.ops.object.empty_add(type="SPHERE", radius=1, align="WORLD", location=position[:])
            cullObj = bpy.context.view_layer.objects.active
            cullObj.ootEmptyType = "Cull Group"
            cullObj.name = "Cull Group"
            cullObj.empty_display_size = hexOrDecInt(entryMatch.group(4).strip()) / bpy.context.scene.ootBlenderScale
            parentObject(roomObj, cullObj)
            parentObj = cullObj

        elif meshType == 1:
            continue
        else:
            opaqueDL = entryMatch.group(1).strip()
            transparentDL = entryMatch.group(2).strip()
            parentObj = roomObj

        # Technically the base path argument will not be used for the f3d context,
        # since all our data should be included already. So it should be okay for custom imports.
        for displayList, drawLayer in [(opaqueDL, "Opaque"), (transparentDL, "Transparent")]:
            if displayList != "0" and displayList != "NULL":
                meshObj = importMeshC(
                    sceneData, displayList, bpy.context.scene.ootBlenderScale, True, True, drawLayer, f3dContext, False
                )
                parentObject(parentObj, meshObj)


def createEmptyWithTransform(positionValues: list[float], rotationValues: list[float]) -> bpy.types.Object:
    position = (
        yUpToZUp
        @ mathutils.Matrix.Scale(1 / bpy.context.scene.ootBlenderScale, 4)
        @ mathutils.Vector([hexOrDecInt(value) for value in positionValues])
    )
    rotation = yUpToZUp @ mathutils.Vector(ootParseRotation(rotationValues))

    bpy.ops.object.empty_add(type="CUBE", radius=1, align="WORLD", location=position[:], rotation=rotation[:])
    obj = bpy.context.view_layer.objects.active
    return obj


def getDisplayNameFromActorID(actorID: str):
    return " ".join([word.lower().capitalize() for word in actorID.split("_") if word != "ACTOR"])


def parseTransActorList(
    roomObjs: list[bpy.types.Object],
    sceneData: str,
    transActorListName: str,
    sharedActorData: SharedActorData,
    headerIndex: int,
):
    match = re.search(
        rf"TransitionActorEntry\s*{re.escape(transActorListName)}\s*\[[\s0-9A-Fa-fx]*\]\s*=\s*\{{(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if not match:
        raise PluginError(f"Could not find transition actor list {transActorListName}.")

    transitionActorList = match.group(1)
    for actorMatch in re.finditer(rf"\{{(.*?)\}}\s*,", transitionActorList, flags=re.DOTALL):
        params = [value.strip() for value in actorMatch.group(1).split(",") if value.strip() != ""]

        position = tuple([hexOrDecInt(value) for value in params[5:8]])
        rotation = tuple([0, hexOrDecInt(params[8]), 0])

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
        if sharedActorData.addHeaderIfActorExists(actorHash, "Transition Actor", headerIndex):
            continue

        actorObj = createEmptyWithTransform(position, rotation)
        actorObj.ootEmptyType = "Transition Actor"
        actorObj.name = "Transition " + getDisplayNameFromActorID(params[4])
        transActorProp = actorObj.ootTransitionActorProperty

        sharedActorData.transDict[actorHash] = actorObj

        parentObject(roomObjs[roomIndexFront], actorObj)
        setCustomProperty(transActorProp, "cameraTransitionFront", camFront, ootEnumCamTransition)
        transActorProp.roomIndex = roomIndexBack
        setCustomProperty(transActorProp, "cameraTransitionBack", camBack, ootEnumCamTransition)

        actorProp = transActorProp.actor
        setCustomProperty(actorProp, "actorID", actorID, ootEnumActorID)
        actorProp.actorParam = actorParam
        unsetAllHeadersExceptSpecified(actorProp, headerIndex)


def parseEntranceList(
    sceneHeader: OOTSceneHeaderProperty, roomObjs: list[bpy.types.Object], sceneData: str, entranceListName: str
):
    match = re.search(
        rf"EntranceEntry\s*{re.escape(entranceListName)}\s*\[[\s0-9A-Fa-fx]*\]\s*=\s*\{{(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if not match:
        raise PluginError(f"Could not find entrance list {entranceListName}.")

    # see also start position list
    entranceList = match.group(1)
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


def parseActorInfo(actorMatch: re.Match) -> tuple[str, list[int], list[int], str]:
    actorID = actorMatch.group(1).strip()
    position = tuple([hexOrDecInt(value.strip()) for value in actorMatch.group(2).split(",") if value.strip() != ""])
    rotation = tuple([hexOrDecInt(value.strip()) for value in actorMatch.group(3).split(",") if value.strip() != ""])
    actorParam = actorMatch.group(4).strip()

    return actorID, position, rotation, actorParam


def unsetAllHeadersExceptSpecified(actorProp: OOTActorProperty, headerIndex: int):
    actorProp.headerSettings.sceneSetupPreset = "Custom"
    for i in range(len(headerNames)):
        setattr(actorProp.headerSettings, headerNames[i], i == headerIndex)

    if headerIndex >= 4:
        actorProp.headerSettings.cutsceneHeaders.add().headerIndex = headerIndex


def parseSpawnList(
    roomObjs: list[bpy.types.Object],
    sceneData: str,
    spawnListName: str,
    entranceList: list[tuple[str, str]],
    sharedActorData: SharedActorData,
    headerIndex: int,
):
    match = re.search(
        rf"ActorEntry\s*{re.escape(spawnListName)}\s*\[[\s0-9A-Fa-fx]*\]\s*=\s*\{{(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if not match:
        raise PluginError(f"Could not find spawn list {spawnListName}.")

    # see also start position list
    spawnList = match.group(1)
    index = 0
    for spawnMatch in re.finditer(r"\{(.*?),\s*\{(.*?)\}\s*,\s*\{(.*?)\}\s*,(.*?)\}\s*,", spawnList, flags=re.DOTALL):
        actorID, position, rotation, actorParam = parseActorInfo(spawnMatch)
        spawnIndex, roomIndex = [value for value in entranceList if value[0] == index][0]
        actorHash = (actorID, position, rotation, actorParam, spawnIndex, roomIndex)

        if sharedActorData.addHeaderIfActorExists(actorHash, "Entrance", headerIndex):
            continue

        spawnObj = createEmptyWithTransform(position, rotation)
        spawnObj.ootEmptyType = "Entrance"
        spawnObj.name = "Entrance"
        spawnProp = spawnObj.ootEntranceProperty
        spawnProp.spawnIndex = spawnIndex
        spawnProp.customActor = actorID != "ACTOR_PLAYER"
        actorProp = spawnProp.actor
        setCustomProperty(actorProp, "actorID", actorID, ootEnumActorID)
        actorProp.actorParam = actorParam
        unsetAllHeadersExceptSpecified(actorProp, headerIndex)

        sharedActorData.entranceDict[actorHash] = spawnObj

        parentObject(roomObjs[roomIndex], spawnObj)
        index += 1


def parseExitList(sceneHeader: OOTSceneHeaderProperty, sceneData: str, exitListName: str):
    match = re.search(
        rf"u16\s*{re.escape(exitListName)}\s*\[[\s0-9A-Fa-fx]*\]\s*=\s*\{{(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if not match:
        raise PluginError(f"Could not find exit list {exitListName}.")

    # see also start position list
    exitList = [value.strip() for value in match.group(1).split(",") if value.strip() != ""]
    for exit in exitList:
        exitProp = sceneHeader.exitList.add()
        exitProp.exitIndex = "Custom"
        exitProp.exitIndexCustom = exit


def parseObjectList(roomHeader: OOTRoomHeaderProperty, sceneData: str, objectListName: str):
    match = re.search(
        rf"s16\s*{re.escape(objectListName)}\s*\[[\s0-9A-Fa-fx]*\]\s*=\s*\{{(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if not match:
        raise PluginError(f"Could not find object list {objectListName}.")

    objects = [value.strip() for value in match.group(1).split(",") if value.strip() != ""]

    for object in objects:
        objectProp = roomHeader.objectList.add()
        setCustomProperty(objectProp, "objectID", object, ootEnumObjectID)


def parseActorList(
    roomObj: bpy.types.Object, sceneData: str, actorListName: str, sharedActorData: SharedActorData, headerIndex: int
):
    match = re.search(
        rf"ActorEntry\s*{re.escape(actorListName)}\s*\[[\s0-9A-Fa-fx]*\]\s*=\s*\{{(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if not match:
        raise PluginError(f"Could not find actor list {actorListName}.")

    actorList = match.group(1)
    for actorMatch in re.finditer(r"\{(.*?),\s*\{(.*?)\}\s*,\s*\{(.*?)\}\s*,(.*?)\}\s*,", actorList, flags=re.DOTALL):
        actorHash = parseActorInfo(actorMatch) + (roomObj.ootRoomHeader.roomIndex,)

        if sharedActorData.addHeaderIfActorExists(actorHash, "Actor", headerIndex):
            continue

        actorID, position, rotation, actorParam, roomIndex = actorHash

        actorObj = createEmptyWithTransform(position, rotation)
        actorObj.ootEmptyType = "Actor"
        actorObj.name = getDisplayNameFromActorID(actorID)
        actorProp = actorObj.ootActorProperty

        setCustomProperty(actorProp, "actorID", actorID, ootEnumActorID)
        actorProp.actorParam = actorParam
        unsetAllHeadersExceptSpecified(actorProp, headerIndex)

        sharedActorData.actorDict[actorHash] = actorObj

        parentObject(roomObj, actorObj)


def parseAlternateSceneHeaders(
    sceneObj: bpy.types.Object,
    roomObjs: list[bpy.types.Object],
    sceneData: str,
    altHeadersListName: str,
    f3dContext: OOTF3DContext,
    sharedActorData: SharedActorData,
):
    match = re.search(
        rf"SceneCmd\*\s*{re.escape(altHeadersListName)}\s*\[[\s0-9A-Fa-fx]*\]\s*=\s*\{{(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if not match:
        raise PluginError(f"Could not find alternate header list {altHeadersListName}.")

    altHeadersList = [value.strip() for value in match.group(1).split(",") if value.strip() != ""]

    for i in range(len(altHeadersList)):
        if not (altHeadersList[i] == "NULL" or altHeadersList[i] == "0"):
            parseSceneCommands(sceneObj, roomObjs, altHeadersList[i], sceneData, f3dContext, i + 1, sharedActorData)


def parseAlternateRoomHeaders(
    roomObj: bpy.types.Object,
    roomIndex: int,
    sharedActorData: SharedActorData,
    sceneData: str,
    altHeadersListName: str,
    f3dContext: OOTF3DContext,
):
    match = re.search(
        rf"SceneCmd\*\s*{re.escape(altHeadersListName)}\s*\[[\s0-9A-Fa-fx]*\]\s*=\s*\{{(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if not match:
        raise PluginError(f"Could not find alternate header list {altHeadersListName}.")

    altHeadersList = [value.strip() for value in match.group(1).split(",") if value.strip() != ""]

    for i in range(len(altHeadersList)):
        if not (altHeadersList[i] == "NULL" or altHeadersList[i] == "0"):
            parseRoomCommands(roomObj, sceneData, altHeadersList[i], roomIndex, f3dContext, sharedActorData, i + 1)
