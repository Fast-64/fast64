import math, os
from ..oot_f3d_writer import *
from ..oot_level_writer import *
from ..oot_collision import *
from ..oot_cutscene import *
from ..oot_level import OOTImportSceneSettingsProperty
from ..oot_scene_room import OOTSceneHeaderProperty
from .oot_scene_table_c import getDrawConfig
from ...utility import yUpToZUp
from collections import OrderedDict

headerNames = ["childDayHeader", "childNightHeader", "adultDayHeader", "adultNightHeader"]


class SharedSceneData:
    def __init__(self):
        self.actorDict = {}  # actor hash : blender object
        self.entranceDict = {}  # actor hash : blender object
        self.transDict = {}  # actor hash : blender object
        self.pathDict = {}  # path hash : blender object

    def addHeaderIfItemExists(self, hash, itemType: str, headerIndex: int):
        if itemType == "Actor":
            dictToAdd = self.actorDict
        elif itemType == "Entrance":
            dictToAdd = self.entranceDict
        elif itemType == "Transition Actor":
            dictToAdd = self.transDict
        elif itemType == "Curve":
            dictToAdd = self.pathDict
        else:
            raise PluginError(f"Invalid empty type for shared actor handling: {itemType}")

        if hash not in dictToAdd:
            return False

        actorObj = dictToAdd[hash]
        headerSettings = getHeaderSettings(actorObj)

        if headerIndex < 4:
            setattr(headerSettings, headerNames[headerIndex], True)
        else:
            cutsceneHeaders = headerSettings.cutsceneHeaders
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

    bpy.context.space_data.overlay.show_relationship_lines = False
    sceneCommandsName = f"{sceneName}_sceneCommands"
    sharedSceneData = SharedSceneData()
    sceneObj = parseSceneCommands(None, None, sceneCommandsName, sceneData, f3dContext, 0, sharedSceneData)
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
    sharedSceneData: SharedSceneData,
):
    if sceneObj is None:
        location = mathutils.Vector((0, 0, 0))
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
                roomObjs = parseRoomList(sceneObj, sceneData, roomListName, f3dContext, sharedSceneData, headerIndex)

        # This must be handled after rooms, so that room objs can be referenced
        elif command == "SCENE_CMD_TRANSITION_ACTOR_LIST":
            transActorListName = args[1]
            parseTransActorList(roomObjs, sceneData, transActorListName, sharedSceneData, headerIndex)

        elif command == "SCENE_CMD_MISC_SETTINGS":
            setCustomProperty(sceneHeader, "cameraMode", args[0], ootEnumCameraMode)
            setCustomProperty(sceneHeader, "mapLocation", args[1], ootEnumMapLocation)
        elif command == "SCENE_CMD_COL_HEADER":
            # Assumption that all scenes use the same collision.
            if headerIndex == 0:
                collisionHeaderName = args[0][1:]  # remove '&'
                parseCollisionHeader(sceneObj, sceneData, collisionHeaderName)
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
            parsePathList(sceneObj, sceneData, pathListName, headerIndex, sharedSceneData)

        # This must be handled after entrance list, so that entrance list can be referenced
        elif command == "SCENE_CMD_SPAWN_LIST":
            if not (args[1] == "NULL" or args[1] == "0" or args[1] == "0x00"):
                spawnListName = args[1]
                parseSpawnList(roomObjs, sceneData, spawnListName, entranceList, sharedSceneData, headerIndex)

                # Clear entrance list
                entranceList = None

        elif command == "SCENE_CMD_SKYBOX_SETTINGS":
            setCustomProperty(sceneHeader, "skyboxID", args[0], ootEnumSkybox)
            setCustomProperty(sceneHeader, "skyboxCloudiness", args[1], ootEnumCloudiness)
            setCustomProperty(sceneHeader, "skyboxLighting", args[2], ootEnumSkyboxLighting)
        elif command == "SCENE_CMD_EXIT_LIST":
            exitListName = args[0]
            parseExitList(sceneHeader, sceneData, exitListName)
        elif command == "SCENE_CMD_ENV_LIGHT_SETTINGS":
            if not (args[1] == "NULL" or args[1] == "0" or args[1] == "0x00"):
                lightsListName = args[1]
                parseLightList(sceneObj, sceneHeader, sceneData, lightsListName, headerIndex)
        elif command == "SCENE_CMD_CUTSCENE_DATA":
            cutsceneName = args[0]
            print("Command not implemented.")
        elif command == "SCENE_CMD_ALTERNATE_HEADER_LIST":
            # Delay until after rooms are parsed
            altHeadersListName = args[0]

    if altHeadersListName is not None:
        parseAlternateSceneHeaders(sceneObj, roomObjs, sceneData, altHeadersListName, f3dContext, sharedSceneData)

    return sceneObj


def parseRoomList(
    sceneObj: bpy.types.Object,
    sceneData: str,
    roomListName: str,
    f3dContext: OOTF3DContext,
    sharedSceneData: SharedSceneData,
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
        roomObj = parseRoomCommands(None, sceneData, roomCommandsName, index, f3dContext, sharedSceneData, headerIndex)
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
    sharedSceneData: SharedSceneData,
    headerIndex: int,
):
    if roomObj is None:
        bpy.ops.object.empty_add(type="SPHERE", radius=1, align="WORLD", location=[0, 0, (roomIndex + 1) * -2])
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
            parseAlternateRoomHeaders(roomObj, roomIndex, sharedSceneData, sceneData, altHeadersListName, f3dContext)
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
            parseActorList(roomObj, sceneData, actorListName, sharedSceneData, headerIndex)

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
    sharedSceneData: SharedSceneData,
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
        if not sharedSceneData.addHeaderIfItemExists(actorHash, "Transition Actor", headerIndex):
            actorObj = createEmptyWithTransform(position, rotation)
            actorObj.ootEmptyType = "Transition Actor"
            actorObj.name = "Transition " + getDisplayNameFromActorID(params[4])
            transActorProp = actorObj.ootTransitionActorProperty

            sharedSceneData.transDict[actorHash] = actorObj

            parentObject(roomObjs[roomIndexFront], actorObj)
            setCustomProperty(transActorProp, "cameraTransitionFront", camFront, ootEnumCamTransition)
            transActorProp.roomIndex = roomIndexBack
            setCustomProperty(transActorProp, "cameraTransitionBack", camBack, ootEnumCamTransition)

            actorProp = transActorProp.actor
            setCustomProperty(actorProp, "actorID", actorID, ootEnumActorID)
            actorProp.actorParam = actorParam
            unsetAllHeadersExceptSpecified(actorProp.headerSettings, headerIndex)


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


def unsetAllHeadersExceptSpecified(headerSettings: OOTActorHeaderProperty, headerIndex: int):
    headerSettings.sceneSetupPreset = "Custom"
    for i in range(len(headerNames)):
        setattr(headerSettings, headerNames[i], i == headerIndex)

    if headerIndex >= 4:
        headerSettings.cutsceneHeaders.add().headerIndex = headerIndex


def parseSpawnList(
    roomObjs: list[bpy.types.Object],
    sceneData: str,
    spawnListName: str,
    entranceList: list[tuple[str, str]],
    sharedSceneData: SharedSceneData,
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

        if not sharedSceneData.addHeaderIfItemExists(actorHash, "Entrance", headerIndex):
            spawnObj = createEmptyWithTransform(position, rotation)
            spawnObj.ootEmptyType = "Entrance"
            spawnObj.name = "Entrance"
            spawnProp = spawnObj.ootEntranceProperty
            spawnProp.spawnIndex = spawnIndex
            spawnProp.customActor = actorID != "ACTOR_PLAYER"
            actorProp = spawnProp.actor
            setCustomProperty(actorProp, "actorID", actorID, ootEnumActorID)
            actorProp.actorParam = actorParam
            unsetAllHeadersExceptSpecified(actorProp.headerSettings, headerIndex)

            sharedSceneData.entranceDict[actorHash] = spawnObj

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
    roomObj: bpy.types.Object, sceneData: str, actorListName: str, sharedSceneData: SharedSceneData, headerIndex: int
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

        if not sharedSceneData.addHeaderIfItemExists(actorHash, "Actor", headerIndex):
            actorID, position, rotation, actorParam, roomIndex = actorHash

            actorObj = createEmptyWithTransform(position, rotation)
            actorObj.ootEmptyType = "Actor"
            actorObj.name = getDisplayNameFromActorID(actorID)
            actorProp = actorObj.ootActorProperty

            setCustomProperty(actorProp, "actorID", actorID, ootEnumActorID)
            actorProp.actorParam = actorParam
            unsetAllHeadersExceptSpecified(actorProp.headerSettings, headerIndex)

            sharedSceneData.actorDict[actorHash] = actorObj

            parentObject(roomObj, actorObj)


def parseAlternateSceneHeaders(
    sceneObj: bpy.types.Object,
    roomObjs: list[bpy.types.Object],
    sceneData: str,
    altHeadersListName: str,
    f3dContext: OOTF3DContext,
    sharedSceneData: SharedSceneData,
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
            parseSceneCommands(sceneObj, roomObjs, altHeadersList[i], sceneData, f3dContext, i + 1, sharedSceneData)


def parseAlternateRoomHeaders(
    roomObj: bpy.types.Object,
    roomIndex: int,
    sharedSceneData: SharedSceneData,
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
            parseRoomCommands(roomObj, sceneData, altHeadersList[i], roomIndex, f3dContext, sharedSceneData, i + 1)


def parsePathList(
    sceneObj: bpy.types.Object,
    sceneData: str,
    pathListName: str,
    headerIndex: int,
    sharedSceneData: SharedSceneData,
):
    match = re.search(
        rf"Path\s*{re.escape(pathListName)}\s*\[[\s0-9A-Fa-fx]*\]\s*=\s*\{{(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if not match:
        raise PluginError(f"Could not find path list {pathListName}.")

    pathList = [value.replace("{", "").strip() for value in match.group(1).split("},") if value.strip() != ""]
    for pathEntry in pathList:
        numPoints, pathName = [value.strip() for value in pathEntry.split(",")]
        parsePath(sceneObj, sceneData, pathName, headerIndex, sharedSceneData)


def parsePath(
    sceneObj: bpy.types.Object, sceneData: str, pathName: str, headerIndex: int, sharedSceneData: SharedSceneData
):
    match = re.search(
        rf"Vec3s\s*{re.escape(pathName)}\s*\[[\s0-9A-Fa-fx]*\]\s*=\s*\{{(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if not match:
        raise PluginError(f"Could not find path  {pathName}.")

    pathPointsEntries = [value.replace("{", "").strip() for value in match.group(1).split("},") if value.strip() != ""]
    pathPointsInfo = []
    for pathPoint in pathPointsEntries:
        pathPointsInfo.append(tuple([hexOrDecInt(value.strip()) for value in pathPoint.split(",")]))
    pathPoints = tuple(pathPointsInfo)

    if sharedSceneData.addHeaderIfItemExists(pathPoints, "Curve", headerIndex):
        return

    curve = bpy.data.curves.new(name=pathName, type="CURVE")
    curveObj = bpy.data.objects.new(pathName, curve)
    bpy.context.scene.collection.objects.link(curveObj)

    # Note that paths are currently processed in alphabetical order by name.
    # Most curves in decomp are named by address, so this should be okay.
    # However name convention might change over time, so keep an eye on this.
    curveObj.name = pathName
    splineProp = curveObj.ootSplineProperty
    curve = curveObj.data
    spline = curve.splines.new("NURBS")
    objLocation = None
    curveObj.show_name = True

    # new spline has 1 point by default
    spline.points.add(len(pathPoints) - 1)
    for i in range(len(pathPoints)):
        position = yUpToZUp @ mathutils.Vector([value / bpy.context.scene.ootBlenderScale for value in pathPoints[i]])

        # Set the origin to the first point so that we can display name next to it.
        if objLocation is None:
            objLocation = position
            curveObj.location = position
        spline.points[i].co = (position - objLocation)[:] + (1,)

    spline.resolution_u = 64
    spline.order_u = 2
    curve.dimensions = "3D"

    unsetAllHeadersExceptSpecified(splineProp.headerSettings, headerIndex)
    sharedSceneData.pathDict[pathPoints] = curveObj

    parentObject(sceneObj, curveObj)


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


def parseLightList(
    sceneObj: bpy.types.Object,
    sceneHeader: OOTSceneHeaderProperty,
    sceneData: str,
    lightListName: str,
    headerIndex: int,
):
    match = re.search(
        rf"LightSettings\s*{re.escape(lightListName)}\s*\[[\s0-9A-Fa-fx]*\]\s*=\s*\{{(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if not match:
        raise PluginError(f"Could not find light list {lightListName}.")

    # I currently don't understand the light list format in respect to this lighting flag.
    # So we'll set it to custom instead.
    if sceneHeader.skyboxLighting != "Custom":
        sceneHeader.skyboxLightingCustom = sceneHeader.skyboxLighting
        sceneHeader.skyboxLighting = "Custom"
    sceneHeader.lightList.clear()

    lightList = [value.replace("{", "").strip() for value in match.group(1).split("},") if value.strip() != ""]
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
        fogFar = hexOrDecInt(lightParams[19])

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
        lightHeader.fogFar = fogFar
        lightHeader.transitionSpeed = transitionSpeed

        index += 1


def parseLight(
    lightHeader: OOTLightProperty, index: int, rotation: mathutils.Euler, color: mathutils.Vector
) -> bpy.types.Object | None:
    setattr(lightHeader, f"useCustomDiffuse{index}", rotation != "Zero" and rotation != "Default")

    if rotation == "Zero" or rotation == "Default":
        setattr(lightHeader, f"zeroDiffuse{index}", rotation == "Zero")
        setattr(lightHeader, f"diffuse{index}", color + (1,))
        return None
    else:
        bpy.ops.object.add(type="LIGHT")
        lightObj = bpy.context.view_layer.objects.active
        setattr(lightHeader, f"diffuse{index}Custom", lightObj.data)
        lightObj.rotation_euler = rotation
        lightObj.data.color = color
        lightObj.data.type = "SUN"
        return lightObj


def parseCollisionHeader(sceneObj: bpy.types.Object, sceneData: str, collisionHeaderName: str):
    match = re.search(
        rf"CollisionHeader\s*{re.escape(collisionHeaderName)}\s*=\s*\{{\s*\{{(.*?)\}}\s*,\s*\{{(.*?)\}}\s*,(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if not match:
        raise PluginError(f"Could not find collision header {collisionHeaderName}.")

    minBounds = [hexOrDecInt(value.strip()) for value in match.group(1).split(",")]
    maxBounds = [hexOrDecInt(value.strip()) for value in match.group(2).split(",")]
    otherParams = [value.strip() for value in match.group(3).split(",")]

    vertexListName = otherParams[1]
    polygonListName = otherParams[3]
    surfaceTypeListName = otherParams[4]
    camDataListName = otherParams[5]
    waterBoxListName = otherParams[7]

    parseCollision(sceneObj, vertexListName, polygonListName, surfaceTypeListName, sceneData)


def parseCollision(
    sceneObj: bpy.types.Object, vertexListName: str, polygonListName: str, surfaceTypeListName: str, sceneData: str
):
    vertMatch = re.search(
        rf"Vec3s\s*{re.escape(vertexListName)}\s*\[[\s0-9A-Fa-fx]*\]\s*=\s*\{{(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if not vertMatch:
        raise PluginError(f"Could not find vertex list {vertexListName}.")

    polyMatch = re.search(
        rf"CollisionPoly\s*{re.escape(polygonListName)}\s*\[[\s0-9A-Fa-fx]*\]\s*=\s*\{{(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if not polyMatch:
        raise PluginError(f"Could not find polygon list {polygonListName}.")

    surfMatch = re.search(
        rf"SurfaceType\s*{re.escape(surfaceTypeListName)}\s*\[[\s0-9A-Fa-fx]*\]\s*=\s*\{{(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )
    if not surfMatch:
        raise PluginError(f"Could not find surface type list {surfaceTypeListName}.")

    vertexList = [value.replace("{", "").strip() for value in vertMatch.group(1).split("},") if value.strip() != ""]
    polygonList = [value.replace("{", "").strip() for value in polyMatch.group(1).split("},") if value.strip() != ""]
    surfaceList = [value.replace("{", "").strip() for value in surfMatch.group(1).split("},") if value.strip() != ""]

    # Although polygon params are geometry based, we will group them with surface.
    collisionDict = OrderedDict()  # (surface, polygonParams) : list[triangles]

    surfaces = parseSurfaces(surfaceList)
    vertices = parseVertices(vertexList)

    for polygonData in polygonList:
        polygonParams, surfaceIndex, vertIndices, normal = parsePolygon(polygonData)
        key = (surfaces[surfaceIndex], polygonParams)
        if key not in collisionDict:
            collisionDict[key] = []

        collisionDict[key].append((vertIndices, normal))

    mesh = bpy.data.meshes.new(polygonListName)
    obj = bpy.data.objects.new(polygonListName, mesh)
    bpy.context.scene.collection.objects.link(obj)

    triData = []
    triMatData = []
    triNormalData = []

    surfaceIndex = 0
    for (surface, polygonParams), triList in collisionDict.items():
        collisionMat = bpy.data.materials.new("oot_collision_mat")
        mesh.materials.append(collisionMat)
        for j in range(len(triList)):
            triData.append(triList[j][0])
            triMatData += [surfaceIndex]
            triNormalData.append(tuple(triList[j][1]))
        surfaceIndex += 1

    mesh.from_pydata(vertices=vertices, edges=[], faces=triData)
    for i in range(len(mesh.polygons)):
        mesh.polygons[i].material_index = triMatData[i]

    parentObject(sceneObj, obj)


def parseSurfaces(surfaceList: list[str]):
    surfaces = []
    for surfaceData in surfaceList:
        params = [hexOrDecInt(value.strip()) for value in surfaceData.split(",")]
        surfaces.append(params[0])

    return surfaces


def parseVertices(vertexList: list[str]):
    vertices = []
    for vertexData in vertexList:
        vertex = [hexOrDecInt(value.strip()) / bpy.context.scene.ootBlenderScale for value in vertexData.split(",")]
        position = yUpToZUp @ mathutils.Vector(vertex)
        vertices.append(position)

    return vertices


def parsePolygon(polygonData: str):
    shorts = [hexOrDecInt(value.strip()) for value in polygonData.split(",")]
    vertIndices = [0, 0, 0]

    # 00
    surfaceIndex = shorts[0]

    # 02
    vertIndices[0] = shorts[1] & 0x1FFF
    ignoreCamera = 1 & (shorts[1] >> 13) == 1
    ignoreActor = 1 & (shorts[1] >> 14) == 1
    ignoreProjectile = 1 & (shorts[1] >> 15) == 1

    # 04
    vertIndices[1] = shorts[2] & 0x1FFF
    enableConveyer = 1 & (shorts[2] >> 13) == 1

    # 06
    vertIndices[2] = shorts[3] & 0x1FFF

    # 08-0C
    normal = [
        int.from_bytes(value.to_bytes(2, "big", signed=value < 0x8000), "big", signed=True) / 0x7FFF
        for value in shorts[4:7]
    ]

    # 0E
    distance = shorts[7]

    return (ignoreCamera, ignoreActor, ignoreProjectile, enableConveyer), surfaceIndex, vertIndices, normal
