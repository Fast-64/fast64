import math, os, re, bpy, mathutils
from random import random

from .oot_f3d_writer import getColliderMat
from .oot_level import OOTImportSceneSettingsProperty
from .oot_scene_room import OOTSceneHeaderProperty, OOTRoomHeaderProperty, OOTLightProperty
from .oot_actor import OOTActorProperty
from .oot_utility import (
    getHeaderSettings,
    getSceneDirFromLevelName,
    setCustomProperty,
    ootParseRotation,
    sceneNameFromID,
    ootGetPath,
)
from .oot_constants import (
    ootEnumCamTransition,
    ootEnumDrawConfig,
    ootEnumCameraMode,
    ootEnumAudioSessionPreset,
    ootEnumNightSeq,
    ootEnumMusicSeq,
    ootEnumMapLocation,
    ootEnumNaviHints,
    ootEnumGlobalObject,
    ootEnumSkybox,
    ootEnumCloudiness,
    ootEnumSkyboxLighting,
    ootEnumRoomBehaviour,
    ootEnumLinkIdle,
    ootEnumRoomShapeType,
    ootData,
)
from .oot_actor import OOTActorHeaderProperty, setAllActorsVisibility
from .scene.exporter.to_c import getDrawConfig
from ..utility import yUpToZUp, parentObject, hexOrDecInt, gammaInverse
from ..f3d.f3d_parser import parseMatrices, importMeshC
from collections import OrderedDict
from .oot_collision import OOTMaterialCollisionProperty
from .oot_collision_classes import (
    ootEnumCameraCrawlspaceSType,
    ootEnumFloorSetting,
    ootEnumWallSetting,
    ootEnumFloorProperty,
    ootEnumCollisionTerrain,
    ootEnumCollisionSound,
    ootEnumCameraSType,
)
from ..utility import PluginError, raisePluginError, readFile
from .oot_model_classes import OOTF3DContext
from ..f3d.f3d_gbi import F3D
from ..f3d.flipbook import TextureFlipbook


def run_ops_without_view_layer_update(func):
    from bpy.ops import _BPyOpsSubModOp

    view_layer_update = _BPyOpsSubModOp._view_layer_update

    def dummy_view_layer_update(context):
        pass

    try:
        _BPyOpsSubModOp._view_layer_update = dummy_view_layer_update
        func()

    finally:
        _BPyOpsSubModOp._view_layer_update = view_layer_update


def parseSceneFunc():
    context = bpy.context
    settings = context.scene.ootSceneImportSettings
    parseScene(
        context.scene.f3d_type,
        context.scene.isHWv1,
        settings,
        settings.option,
    )


class OOT_ImportScene(bpy.types.Operator):
    """Import an OOT scene from C."""

    bl_idname = "object.oot_import_level"
    bl_label = "Import Scene"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        try:
            if bpy.context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.select_all(action="DESELECT")

            run_ops_without_view_layer_update(parseSceneFunc)

            self.report({"INFO"}, "Success!")
            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}


headerNames = ["childDayHeader", "childNightHeader", "adultDayHeader", "adultNightHeader"]

actorsWithRotAsParam = {
    "ACTOR_EN_BOX": "Z",
    "ACTOR_EN_WOOD02": "Z",
    "ACTOR_DOOR_ANA": "Z",
    "ACTOR_EN_ENCOUNT1": "Z",
    "ACTOR_EN_MA1": "Z",
    "ACTOR_EN_WONDER_ITEM": "Z",
    "ACTOR_EN_WONDER_TALK": "Z",
    "ACTOR_EN_WONDER_TALK2": "Z",
    "ACTOR_OBJ_BEAN": "Z",
    "ACTOR_EN_OKARINA_TAG": "Z",
    "ACTOR_EN_GOROIWA": "Z",
    "ACTOR_EN_DAIKU": "Z",
    "ACTOR_EN_SIOFUKI": "XYZ",
    "ACTOR_ELF_MSG2": "XYZ",
    "ACTOR_OBJ_MAKEOSHIHIKI": "Z",
    "ACTOR_EN_GELDB": "Z",
    "ACTOR_OBJ_KIBAKO2": "XZ",
    "ACTOR_EN_GO2": "Z",
    "ACTOR_EN_KAKASI2": "Z",
    "ACTOR_EN_KAKASI3": "Z",
    "ACTOR_OBJ_TIMEBLOCK": "Z",
}


def checkBit(value: int, index: int) -> bool:
    return (1 & (value >> index)) == 1


def getBits(value: int, index: int, size: int) -> int:
    return ((1 << size) - 1) & (value >> index)


def getDataMatch(
    sceneData: str, name: str, dataType: str | list[str], errorMessageID: str, isArray: bool = True
) -> str:
    arrayText = rf"\[[\s0-9A-Fa-fx]*\]\s*" if isArray else ""

    if isinstance(dataType, list):
        dataTypeRegex = "(?:"
        for i in dataType:
            dataTypeRegex += f"(?:{re.escape(i)})|"
        dataTypeRegex = dataTypeRegex[:-1] + ")"
    else:
        dataTypeRegex = re.escape(dataType)
    regex = rf"{dataTypeRegex}\s*{re.escape(name)}\s*{arrayText}=\s*\{{(.*?)\}}\s*;"
    match = re.search(regex, sceneData, flags=re.DOTALL)
    if not match:
        raise PluginError(f"Could not find {errorMessageID} {name}.")

    return match.group(1)


def stripName(name: str):
    if "&" in name:
        name = name[name.index("&") + 1 :].strip()
    if name[0] == "(" and name[-1] == ")":
        name = name[1:-1].strip()
    return name


class SharedSceneData:
    def __init__(
        self,
        scenePath: str,
        includeMesh: bool,
        includeCollision: bool,
        includeActors: bool,
        includeCullGroups: bool,
        includeLights: bool,
        includeCameras: bool,
        includePaths: bool,
        includeWaterBoxes: bool,
    ):
        self.actorDict = {}  # actor hash : blender object
        self.entranceDict = {}  # actor hash : blender object
        self.transDict = {}  # actor hash : blender object
        self.pathDict = {}  # path hash : blender object

        self.scenePath = scenePath
        self.includeMesh = includeMesh
        self.includeCollision = includeCollision
        self.includeActors = includeActors
        self.includeCullGroups = includeCullGroups
        self.includeLights = includeLights
        self.includeCameras = includeCameras
        self.includePaths = includePaths
        self.includeWaterBoxes = includeWaterBoxes

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

    # roomData = ""
    # sceneFolderFiles = [f for f in listdir(sceneFolderPath) if isfile(join(sceneFolderPath, f))]
    # for sceneFile in sceneFolderFiles:
    #    if re.search(rf"{sceneName}_room_[0-9]+\.c", sceneFile):
    #        roomPath = os.path.join(sceneFolderPath, sceneFile)
    #        roomData += readFile(roomPath)

    # sceneData += roomData

    if bpy.context.mode != "OBJECT":
        bpy.context.mode = "OBJECT"

    # set scene default registers (see sDefaultDisplayList)
    f3dContext = OOTF3DContext(F3D(f3dType, isHWv1), [], bpy.path.abspath(bpy.context.scene.ootDecompPath))
    f3dContext.mat().prim_color = (0.5, 0.5, 0.5, 0.5)
    f3dContext.mat().env_color = (0.5, 0.5, 0.5, 0.5)

    parseMatrices(sceneData, f3dContext, 1 / bpy.context.scene.ootBlenderScale)
    f3dContext.addMatrix("&gMtxClear", mathutils.Matrix.Scale(1 / bpy.context.scene.ootBlenderScale, 4))

    if not settings.isCustomDest:
        drawConfigName = getDrawConfig(sceneName)
        drawConfigData = readFile(os.path.join(importPath, "src/code/z_scene_table.c"))
        parseDrawConfig(drawConfigName, sceneData, drawConfigData, f3dContext)

    bpy.context.space_data.overlay.show_relationship_lines = False
    bpy.context.space_data.overlay.show_curve_normals = True
    bpy.context.space_data.overlay.normals_length = 2

    sceneCommandsName = f"{sceneName}_sceneCommands"
    if sceneCommandsName not in sceneData:
        sceneCommandsName = f"{sceneName}_scene_header00"  # fast64 naming
    sharedSceneData = SharedSceneData(
        sceneFolderPath,
        settings.includeMesh,
        settings.includeCollision,
        settings.includeActors,
        settings.includeCullGroups,
        settings.includeLights,
        settings.includeCameras,
        settings.includePaths,
        settings.includeWaterBoxes,
    )
    sceneObj = parseSceneCommands(sceneName, None, None, sceneCommandsName, sceneData, f3dContext, 0, sharedSceneData)
    bpy.context.scene.ootSceneExportObj = sceneObj

    if not settings.isCustomDest:
        setCustomProperty(
            sceneObj.ootSceneHeader.sceneTableEntry, "drawConfig", getDrawConfig(sceneName), ootEnumDrawConfig
        )

    if bpy.context.scene.fast64.oot.headerTabAffectsVisibility:
        setAllActorsVisibility(sceneObj, bpy.context)


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
    elif headerIndex < 4:
        sceneHeader = getattr(sceneObj.ootAlternateSceneHeaders, headerNames[headerIndex])
        sceneHeader.usePreviousHeader = False
    else:
        cutsceneHeaders = sceneObj.ootAlternateSceneHeaders.cutsceneHeaders
        while len(cutsceneHeaders) < headerIndex - 3:
            cutsceneHeaders.add()
        sceneHeader = cutsceneHeaders[headerIndex - 4]

    commands = getDataMatch(sceneData, sceneCommandsName, ["SceneCmd", "SCmdBase"], "scene commands")
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
        elif command == "SCENE_CMD_CUTSCENE_DATA":
            cutsceneName = args[0]
            print("Cutscene command parsing not implemented.")
        elif command == "SCENE_CMD_ALTERNATE_HEADER_LIST":
            # Delay until after rooms are parsed
            altHeadersListName = stripName(args[0])

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


def parseRoomCommands(
    roomName: str | None,
    roomObj: bpy.types.Object | None,
    sceneData: str,
    roomCommandsName: str,
    roomIndex: int,
    f3dContext: OOTF3DContext,
    sharedSceneData: SharedSceneData,
    headerIndex: int,
):
    if roomObj is None:
        # Name set in parseRoomList()
        roomObj = bpy.data.objects.new(roomCommandsName, None)
        bpy.context.scene.collection.objects.link(roomObj)
        roomObj.empty_display_type = "SPHERE"
        roomObj.location = [0, 0, (roomIndex + 1) * -2]
        roomObj.ootEmptyType = "Room"
        roomObj.ootRoomHeader.roomIndex = roomIndex
        roomObj.name = roomName

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

    commands = getDataMatch(sceneData, roomCommandsName, ["SceneCmd", "SCmdBase"], "scene commands")
    for commandMatch in re.finditer(rf"(SCENE\_CMD\_[a-zA-Z0-9\_]*)\s*\((.*?)\)\s*,", commands, flags=re.DOTALL):
        command = commandMatch.group(1)
        args = [arg.strip() for arg in commandMatch.group(2).split(",")]
        if command == "SCENE_CMD_ALTERNATE_HEADER_LIST":
            altHeadersListName = stripName(args[0])
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
        elif (command == "SCENE_CMD_ROOM_SHAPE" or command == "SCENE_CMD_MESH") and sharedSceneData.includeMesh:
            # Assumption that all rooms use the same mesh.
            if headerIndex == 0:
                meshHeaderName = args[0][1:]  # remove '&'
                parseMeshHeader(roomObj, sceneData, meshHeaderName, f3dContext, sharedSceneData)
        elif command == "SCENE_CMD_OBJECT_LIST":
            objectListName = stripName(args[1])
            parseObjectList(roomHeader, sceneData, objectListName)
        elif command == "SCENE_CMD_ACTOR_LIST" and sharedSceneData.includeActors:
            actorListName = stripName(args[1])
            parseActorList(roomObj, sceneData, actorListName, sharedSceneData, headerIndex)

    return roomObj


def parseMeshHeader(
    roomObj: bpy.types.Object,
    sceneData: str,
    meshHeaderName: str,
    f3dContext: OOTF3DContext,
    sharedSceneData: SharedSceneData,
):
    roomHeader = roomObj.ootRoomHeader
    meshData = getDataMatch(sceneData, meshHeaderName, "", "mesh header", False)
    meshData = meshData.replace("{", "").replace("}", "")

    meshParams = [value.strip() for value in meshData.split(",") if value.strip() != ""]
    roomShape = meshParams[0]
    if "ROOM_SHAPE_TYPE_" in roomShape:
        roomShapeIndex = [value[0] for value in ootEnumRoomShapeType].index(roomShape)
    else:
        roomShapeIndex = int(roomShape)

    roomHeader.roomShape = ootEnumRoomShapeType[roomShapeIndex][0]
    isType1 = roomShapeIndex == 1
    isMulti = meshParams[1] == "2" or meshParams[1] == "ROOM_SHAPE_IMAGE_AMOUNT_MULTI"

    meshListName = stripName(meshParams[2])
    parseMeshList(roomObj, sceneData, meshListName, roomShapeIndex, f3dContext, sharedSceneData)

    if isType1:
        if not isMulti:
            parseBGImage(roomHeader, meshParams, sharedSceneData)
        else:
            bgListName = stripName(f"{meshParams[4]}")
            parseBGImageList(roomHeader, sceneData, bgListName, sharedSceneData)


def parseBGImage(roomHeader: OOTRoomHeaderProperty, params: list[str], sharedSceneData: SharedSceneData):
    bgImage = roomHeader.bgImageList.add()
    bgImage.otherModeFlags = params[10]
    bgName = f"{params[3]}.jpg"
    image = bpy.data.images.load(os.path.join(bpy.path.abspath(sharedSceneData.scenePath), f"{bgName}"))
    bgImage.image = image


def parseBGImageList(
    roomHeader: OOTRoomHeaderProperty, sceneData: str, bgListName: str, sharedSceneData: SharedSceneData
):
    bgData = getDataMatch(sceneData, bgListName, "", "bg list")
    bgList = [value.replace("{", "").strip() for value in bgData.split("},") if value.strip() != ""]
    for bgDataItem in bgList:
        params = [value.strip() for value in bgDataItem.split(",") if value.strip() != ""]
        bgImage = roomHeader.bgImageList.add()
        # Assuming camera index increments appropriately
        # bgImage.camera = hexOrDecInt(params[1])
        bgImage.otherModeFlags = params[9]

        bgName = params[2]
        image = bpy.data.images.load(os.path.join(bpy.path.abspath(sharedSceneData.scenePath), f"{bgName}.jpg"))
        bgImage.image = image


def parseMeshList(
    roomObj: bpy.types.Object,
    sceneData: str,
    meshListName: str,
    roomShape: int,
    f3dContext: OOTF3DContext,
    sharedSceneData: SharedSceneData,
):
    roomHeader = roomObj.ootRoomHeader
    meshEntryData = getDataMatch(sceneData, meshListName, "", "mesh list", roomShape != 1)

    if roomShape == 2:
        matchPattern = r"\{\s*\{(.*?),(.*?),(.*?)\}\s*,(.*?),(.*?),(.*?)\}\s*,"
        searchItems = re.finditer(matchPattern, meshEntryData, flags=re.DOTALL)
    elif roomShape == 1:
        searchItems = [meshEntryData]
    else:
        matchPattern = r"\{(.*?),(.*?)\}\s*,"
        searchItems = re.finditer(matchPattern, meshEntryData, flags=re.DOTALL)

    for entryMatch in searchItems:
        if roomShape == 2:
            opaqueDL = entryMatch.group(5).strip()
            transparentDL = entryMatch.group(6).strip()
            position = yUpToZUp @ mathutils.Vector(
                [
                    hexOrDecInt(entryMatch.group(value).strip()) / bpy.context.scene.ootBlenderScale
                    for value in range(1, 4)
                ]
            )
            if sharedSceneData.includeCullGroups:
                cullObj = bpy.data.objects.new("Cull Group", None)
                bpy.context.scene.collection.objects.link(cullObj)
                cullObj.location = position
                cullObj.ootEmptyType = "Cull Group"
                cullObj.name = "Cull Group"
                cullProp = cullObj.ootCullGroupProperty
                cullProp.sizeControlsCull = False
                cullProp.manualRadius = hexOrDecInt(entryMatch.group(4).strip())
                cullObj.show_name = True
                # cullObj.empty_display_size = hexOrDecInt(entryMatch.group(4).strip()) / bpy.context.scene.ootBlenderScale
                parentObject(roomObj, cullObj)
                parentObj = cullObj
            else:
                parentObj = roomObj
        elif roomShape == 1:
            dls = [value.strip() for value in entryMatch.split(",")]
            opaqueDL = dls[0]
            transparentDL = dls[1]
            parentObj = roomObj
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
                meshObj.location = [0, 0, 0]
                meshObj.ignore_collision = True
                parentObject(parentObj, meshObj)


def createEmptyWithTransform(positionValues: list[float], rotationValues: list[float]) -> bpy.types.Object:
    position = (
        yUpToZUp
        @ mathutils.Matrix.Scale(1 / bpy.context.scene.ootBlenderScale, 4)
        @ mathutils.Vector([hexOrDecInt(value) for value in positionValues])
    )
    rotation = yUpToZUp @ mathutils.Vector(ootParseRotation(rotationValues))

    obj = bpy.data.objects.new("Empty", None)
    bpy.context.scene.collection.objects.link(obj)
    obj.empty_display_type = "CUBE"
    obj.location = position
    obj.rotation_euler = rotation
    return obj


def getDisplayNameFromActorID(actorID: str):
    return " ".join([word.lower().capitalize() for word in actorID.split("_") if word != "ACTOR"])


def handleActorWithRotAsParam(actorProp: OOTActorProperty, actorID: str, rotation: list[int]):
    if actorID in actorsWithRotAsParam:
        actorProp.rotOverride = True
        actorProp.rotOverrideX = hex(rotation[0])
        actorProp.rotOverrideY = hex(rotation[1])
        actorProp.rotOverrideZ = hex(rotation[2])


def parseTransActorList(
    roomObjs: list[bpy.types.Object],
    sceneData: str,
    transActorListName: str,
    sharedSceneData: SharedSceneData,
    headerIndex: int,
):
    transitionActorList = getDataMatch(sceneData, transActorListName, "TransitionActorEntry", "transition actor list")
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
            actorObj = createEmptyWithTransform(position, [0, 0, 0] if actorID in actorsWithRotAsParam else rotation)
            actorObj.ootEmptyType = "Transition Actor"
            actorObj.name = "Transition " + getDisplayNameFromActorID(params[4])
            transActorProp = actorObj.ootTransitionActorProperty

            sharedSceneData.transDict[actorHash] = actorObj

            if roomIndexFront != 255:
                parentObject(roomObjs[roomIndexFront], actorObj)
                transActorProp.roomIndex = roomIndexBack
            else:
                parentObject(roomObjs[roomIndexBack], actorObj)
                transActorProp.dontTransition = True

            setCustomProperty(transActorProp, "cameraTransitionFront", camFront, ootEnumCamTransition)
            setCustomProperty(transActorProp, "cameraTransitionBack", camBack, ootEnumCamTransition)

            actorProp = transActorProp.actor
            setCustomProperty(actorProp, "actorID", actorID, ootData.actorData.ootEnumActorID)
            actorProp.actorParam = actorParam
            handleActorWithRotAsParam(actorProp, actorID, rotation)
            unsetAllHeadersExceptSpecified(actorProp.headerSettings, headerIndex)


def parseEntranceList(
    sceneHeader: OOTSceneHeaderProperty, roomObjs: list[bpy.types.Object], sceneData: str, entranceListName: str
):
    entranceList = getDataMatch(sceneData, entranceListName, "EntranceEntry", "entrance List")

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
            [hexOrDecInt(value.strip()) for value in actorMatch.group(3).split(",") if value.strip() != ""]
        )
        actorParam = actorMatch.group(4).strip()
    else:
        params = [value.strip() for value in actorMatch.group(1).split(",")]
        actorID = params[0]
        position = tuple([hexOrDecInt(value) for value in params[1:4]])
        rotation = tuple([hexOrDecInt(value) for value in params[4:7]])
        actorParam = params[7]

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
            spawnProp.spawnIndex = spawnIndex
            spawnProp.customActor = actorID != "ACTOR_PLAYER"
            actorProp = spawnProp.actor
            setCustomProperty(actorProp, "actorID", actorID, ootData.actorData.ootEnumActorID)
            actorProp.actorParam = actorParam
            handleActorWithRotAsParam(actorProp, actorID, rotation)
            unsetAllHeadersExceptSpecified(actorProp.headerSettings, headerIndex)

            sharedSceneData.entranceDict[actorHash] = spawnObj

            parentObject(roomObjs[roomIndex], spawnObj)
        index += 1


def parseExitList(sceneHeader: OOTSceneHeaderProperty, sceneData: str, exitListName: str):
    exitData = getDataMatch(sceneData, exitListName, "u16", "exit list")

    # see also start position list
    exitList = [value.strip() for value in exitData.split(",") if value.strip() != ""]
    for exit in exitList:
        exitProp = sceneHeader.exitList.add()
        exitProp.exitIndex = "Custom"
        exitProp.exitIndexCustom = exit


def parseObjectList(roomHeader: OOTRoomHeaderProperty, sceneData: str, objectListName: str):
    objectData = getDataMatch(sceneData, objectListName, "s16", "object list")
    objects = [value.strip() for value in objectData.split(",") if value.strip() != ""]

    for object in objects:
        objectProp = roomHeader.objectList.add()
        objByID = ootData.objectData.objectsByID.get(object)

        if objByID is not None:
            objectProp.objectKey = objByID.key
        else:
            objectProp.objectIDCustom = object


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
        actorHash = parseActorInfo(actorMatch, nestedBrackets) + (roomObj.ootRoomHeader.roomIndex,)

        if not sharedSceneData.addHeaderIfItemExists(actorHash, "Actor", headerIndex):
            actorID, position, rotation, actorParam, roomIndex = actorHash

            actorObj = createEmptyWithTransform(position, [0, 0, 0] if actorID in actorsWithRotAsParam else rotation)
            actorObj.ootEmptyType = "Actor"
            actorObj.name = getDisplayNameFromActorID(actorID)
            actorProp = actorObj.ootActorProperty

            setCustomProperty(actorProp, "actorID", actorID, ootData.actorData.ootEnumActorID)
            actorProp.actorParam = actorParam
            handleActorWithRotAsParam(actorProp, actorID, rotation)
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
    altHeadersData = getDataMatch(sceneData, altHeadersListName, ["SceneCmd*", "SCmdBase*"], "alternate header list")
    altHeadersList = [value.strip() for value in altHeadersData.split(",") if value.strip() != ""]

    for i in range(len(altHeadersList)):
        if not (altHeadersList[i] == "NULL" or altHeadersList[i] == "0"):
            parseSceneCommands(
                sceneObj.name, sceneObj, roomObjs, altHeadersList[i], sceneData, f3dContext, i + 1, sharedSceneData
            )


def parseAlternateRoomHeaders(
    roomObj: bpy.types.Object,
    roomIndex: int,
    sharedSceneData: SharedSceneData,
    sceneData: str,
    altHeadersListName: str,
    f3dContext: OOTF3DContext,
):
    altHeadersData = getDataMatch(sceneData, altHeadersListName, ["SceneCmd*", "SCmdBase*"], "alternate header list")
    altHeadersList = [value.strip() for value in altHeadersData.split(",") if value.strip() != ""]

    for i in range(len(altHeadersList)):
        if not (altHeadersList[i] == "NULL" or altHeadersList[i] == "0"):
            parseRoomCommands(
                roomObj.name, roomObj, sceneData, altHeadersList[i], roomIndex, f3dContext, sharedSceneData, i + 1
            )


def parsePathList(
    sceneObj: bpy.types.Object,
    sceneData: str,
    pathListName: str,
    headerIndex: int,
    sharedSceneData: SharedSceneData,
):
    pathData = getDataMatch(sceneData, pathListName, "Path", "path list")
    pathList = [value.replace("{", "").strip() for value in pathData.split("},") if value.strip() != ""]
    for pathEntry in pathList:
        numPoints, pathName = [value.strip() for value in pathEntry.split(",")]
        parsePath(sceneObj, sceneData, pathName, headerIndex, sharedSceneData)


def createCurveFromPoints(points: list[tuple[float, float, float]], name: str):
    curve = bpy.data.curves.new(name=name, type="CURVE")
    curveObj = bpy.data.objects.new(name, curve)
    bpy.context.scene.collection.objects.link(curveObj)

    spline = curve.splines.new("NURBS")
    objLocation = None
    curveObj.show_name = True

    # new spline has 1 point by default
    spline.points.add(len(points) - 1)
    for i in range(len(points)):
        position = yUpToZUp @ mathutils.Vector([value / bpy.context.scene.ootBlenderScale for value in points[i]])

        # Set the origin to the first point so that we can display name next to it.
        if objLocation is None:
            objLocation = position
            curveObj.location = position
        spline.points[i].co = (position - objLocation)[:] + (1,)

    spline.resolution_u = 64
    spline.order_u = 2
    curve.dimensions = "3D"

    return curveObj


def parsePath(
    sceneObj: bpy.types.Object, sceneData: str, pathName: str, headerIndex: int, sharedSceneData: SharedSceneData
):
    pathData = getDataMatch(sceneData, pathName, "Vec3s", "path")
    pathPointsEntries = [value.replace("{", "").strip() for value in pathData.split("},") if value.strip() != ""]
    pathPointsInfo = []
    for pathPoint in pathPointsEntries:
        pathPointsInfo.append(tuple([hexOrDecInt(value.strip()) for value in pathPoint.split(",")]))
    pathPoints = tuple(pathPointsInfo)

    if sharedSceneData.addHeaderIfItemExists(pathPoints, "Curve", headerIndex):
        return

    curveObj = createCurveFromPoints(pathPoints, pathName)
    splineProp = curveObj.ootSplineProperty

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
    lightData = getDataMatch(sceneData, lightListName, "LightSettings", "light list")

    # I currently don't understand the light list format in respect to this lighting flag.
    # So we'll set it to custom instead.
    if sceneHeader.skyboxLighting != "Custom":
        sceneHeader.skyboxLightingCustom = sceneHeader.skyboxLighting
        sceneHeader.skyboxLighting = "Custom"
    sceneHeader.lightList.clear()

    lightList = [value.replace("{", "").strip() for value in lightData.split("},") if value.strip() != ""]
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
        light = bpy.data.lights.new("Light", "SUN")
        lightObj = bpy.data.objects.new("Light", light)
        bpy.context.scene.collection.objects.link(lightObj)
        setattr(lightHeader, f"diffuse{index}Custom", lightObj.data)
        lightObj.rotation_euler = rotation
        lightObj.data.color = color
        lightObj.data.type = "SUN"
        return lightObj


def parseCollisionHeader(
    sceneObj: bpy.types.Object,
    roomObjs: list[bpy.types.Object],
    sceneData: str,
    collisionHeaderName: str,
    sharedSceneData: SharedSceneData,
):
    match = re.search(
        rf"CollisionHeader\s*{re.escape(collisionHeaderName)}\s*=\s*\{{\s*\{{(.*?)\}}\s*,\s*\{{(.*?)\}}\s*,(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )

    if not match:
        match = re.search(
            rf"CollisionHeader\s*{re.escape(collisionHeaderName)}\s*=\s*\{{(.*?)\}}\s*;",
            sceneData,
            flags=re.DOTALL,
        )
        if not match:
            raise PluginError(f"Could not find collision header {collisionHeaderName}.")

        params = [value.strip() for value in match.group(1).split(",")]
        minBounds = [hexOrDecInt(value.strip()) for value in params[0:3]]
        maxBounds = [hexOrDecInt(value.strip()) for value in params[3:6]]
        otherParams = [value.strip() for value in params[6:]]

    else:
        minBounds = [hexOrDecInt(value.strip()) for value in match.group(1).split(",")]
        maxBounds = [hexOrDecInt(value.strip()) for value in match.group(2).split(",")]
        otherParams = [value.strip() for value in match.group(3).split(",")]

    vertexListName = stripName(otherParams[1])
    polygonListName = stripName(otherParams[3])
    surfaceTypeListName = stripName(otherParams[4])
    camDataListName = stripName(otherParams[5])
    waterBoxListName = stripName(otherParams[7])

    if sharedSceneData.includeCollision:
        parseCollision(sceneObj, vertexListName, polygonListName, surfaceTypeListName, sceneData)
    if sharedSceneData.includeCameras and camDataListName != "NULL" and camDataListName != "0":
        parseCamDataList(sceneObj, camDataListName, sceneData)
    if sharedSceneData.includeWaterBoxes and waterBoxListName != "NULL" and waterBoxListName != "0":
        parseWaterBoxes(sceneObj, roomObjs, sceneData, waterBoxListName)


def parseCollision(
    sceneObj: bpy.types.Object, vertexListName: str, polygonListName: str, surfaceTypeListName: str, sceneData: str
):
    vertMatchData = getDataMatch(sceneData, vertexListName, "Vec3s", "vertex list")
    polyMatchData = getDataMatch(sceneData, polygonListName, "CollisionPoly", "polygon list")
    surfMatchData = getDataMatch(sceneData, surfaceTypeListName, "SurfaceType", "surface type list")

    vertexList = [value.replace("{", "").strip() for value in vertMatchData.split("},") if value.strip() != ""]
    polygonList = [value.replace("{", "").strip() for value in polyMatchData.split("},") if value.strip() != ""]
    surfaceList = [value.replace("{", "").strip() for value in surfMatchData.split("},") if value.strip() != ""]

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

    collisionName = f"{sceneObj.name}_collision"
    mesh = bpy.data.meshes.new(collisionName)
    obj = bpy.data.objects.new(collisionName, mesh)
    bpy.context.scene.collection.objects.link(obj)

    triData = []
    triMatData = []

    surfaceIndex = 0
    for (surface, polygonParams), triList in collisionDict.items():
        randomColor = mathutils.Color((1, 1, 1))
        randomColor.hsv = (random(), 0.5, 0.5)
        collisionMat = getColliderMat(f"oot_collision_mat_{surfaceIndex}", randomColor[:] + (0.5,))
        collision = collisionMat.ootCollisionProperty
        parseSurfaceParams(surface, polygonParams, collision)

        mesh.materials.append(collisionMat)
        for j in range(len(triList)):
            triData.append(triList[j][0])
            triMatData += [surfaceIndex]
        surfaceIndex += 1

    mesh.from_pydata(vertices=vertices, edges=[], faces=triData)
    for i in range(len(mesh.polygons)):
        mesh.polygons[i].material_index = triMatData[i]

    obj.ignore_render = True

    parentObject(sceneObj, obj)


def parseSurfaceParams(
    surface: tuple[int, int], polygonParams: tuple[bool, bool, bool, bool], collision: OOTMaterialCollisionProperty
):
    params = surface
    ignoreCamera, ignoreActor, ignoreProjectile, enableConveyor = polygonParams

    collision.eponaBlock = checkBit(params[0], 31)
    collision.decreaseHeight = checkBit(params[0], 30)
    setCustomProperty(collision, "floorSetting", str(getBits(params[0], 26, 4)), ootEnumFloorSetting)
    setCustomProperty(collision, "wallSetting", str(getBits(params[0], 21, 5)), ootEnumWallSetting)
    setCustomProperty(collision, "floorProperty", str(getBits(params[0], 13, 8)), ootEnumFloorProperty)
    collision.exitID = getBits(params[0], 8, 5)
    collision.cameraID = getBits(params[0], 0, 8)
    collision.isWallDamage = checkBit(params[1], 27)

    collision.conveyorRotation = (getBits(params[1], 21, 6) / 0x3F) * (2 * math.pi)
    collision.conveyorSpeed = "Custom"
    collision.conveyorSpeedCustom = str(getBits(params[1], 18, 3))

    if collision.conveyorRotation == 0 and collision.conveyorSpeedCustom == "0":
        collision.conveyorOption = "None"
    elif enableConveyor:
        collision.conveyorOption = "Land"
    else:
        collision.conveyorOption = "Water"

    collision.hookshotable = checkBit(params[1], 17)
    collision.echo = str(getBits(params[1], 11, 6))
    collision.lightingSetting = getBits(params[1], 6, 5)
    setCustomProperty(collision, "terrain", str(getBits(params[1], 4, 2)), ootEnumCollisionTerrain)
    setCustomProperty(collision, "sound", str(getBits(params[1], 0, 4)), ootEnumCollisionSound)

    collision.ignoreCameraCollision = ignoreCamera
    collision.ignoreActorCollision = ignoreActor
    collision.ignoreProjectileCollision = ignoreProjectile


def parseSurfaces(surfaceList: list[str]):
    surfaces = []
    for surfaceData in surfaceList:
        params = [hexOrDecInt(value.strip()) for value in surfaceData.split(",")]
        surfaces.append(tuple(params))

    return surfaces


def parseVertices(vertexList: list[str]):
    vertices = []
    for vertexData in vertexList:
        vertex = [hexOrDecInt(value.strip()) / bpy.context.scene.ootBlenderScale for value in vertexData.split(",")]
        position = yUpToZUp @ mathutils.Vector(vertex)
        vertices.append(position)

    return vertices


def parsePolygon(polygonData: str):
    shorts = [
        hexOrDecInt(value.strip()) if "COLPOLY_SNORMAL" not in value else value.strip()
        for value in polygonData.split(",")
    ]
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
    enableConveyor = 1 & (shorts[2] >> 13) == 1

    # 06
    vertIndices[2] = shorts[3] & 0x1FFF

    # 08-0C
    normal = []
    for value in shorts[4:7]:
        if isinstance(value, str) and "COLPOLY_SNORMAL" in value:
            normal.append(float(value[value.index("(") + 1 : value.index(")")]))
        else:
            normal.append(int.from_bytes(value.to_bytes(2, "big", signed=value < 0x8000), "big", signed=True) / 0x7FFF)

    # 0E
    distance = shorts[7]

    return (ignoreCamera, ignoreActor, ignoreProjectile, enableConveyor), surfaceIndex, vertIndices, normal


def parseCamDataList(sceneObj: bpy.types.Object, camDataListName: str, sceneData: str):
    camMatchData = getDataMatch(sceneData, camDataListName, "CamData", "camera data list")
    camDataList = [value.replace("{", "").strip() for value in camMatchData.split("},") if value.strip() != ""]

    # orderIndex used for naming cameras in alphabetical order
    orderIndex = 0
    for camEntry in camDataList:
        setting, count, posDataName = [value.strip() for value in camEntry.split(",")]
        index = None

        objName = f"{sceneObj.name}_camPos_{format(orderIndex, '03')}"

        if posDataName != "NULL" and posDataName != "0":
            index = hexOrDecInt(posDataName[posDataName.index("[") + 1 : -1])
            posDataName = posDataName[1 : posDataName.index("[")]  # remove '&' and '[n]'

        if setting == "CAM_SET_CRAWLSPACE" or setting == "0x001E":
            obj = parseCrawlSpaceData(setting, sceneData, posDataName, index, hexOrDecInt(count), objName, orderIndex)
        else:
            obj = parseCamPosData(setting, sceneData, posDataName, index, objName, orderIndex)

        parentObject(sceneObj, obj)
        orderIndex += 1


def parseCamPosData(setting: str, sceneData: str, posDataName: str, index: int, objName: str, orderIndex: str):
    camera = bpy.data.cameras.new("Camera")
    camObj = bpy.data.objects.new(objName, camera)
    bpy.context.scene.collection.objects.link(camObj)
    camProp = camObj.ootCameraPositionProperty
    setCustomProperty(camProp, "camSType", setting, ootEnumCameraSType)
    camProp.hasPositionData = posDataName != "NULL" and posDataName != "0"
    camProp.index = orderIndex

    # name is important for alphabetical ordering
    camObj.name = objName

    if index is None:
        camObj.location = [0, 0, 0]
        return camObj

    camPosData = getDataMatch(sceneData, posDataName, "Vec3s", "camera position list")
    camPosList = [value.replace("{", "").strip() for value in camPosData.split("},") if value.strip() != ""]

    posData = camPosList[index : index + 3]
    position = yUpToZUp @ mathutils.Vector(
        [hexOrDecInt(value.strip()) / bpy.context.scene.ootBlenderScale for value in posData[0].split(",")]
    )

    # camera faces opposite direction
    rotation = (
        yUpToZUp.to_quaternion()
        @ mathutils.Euler(
            ootParseRotation([hexOrDecInt(value.strip()) for value in posData[1].split(",")])
        ).to_quaternion()
        @ mathutils.Quaternion((0, 1, 0), math.radians(180.0))
    ).to_euler()

    fov, bgImageOverrideIndex, unknown = [value.strip() for value in posData[2].split(",")]

    camObj.location = position
    camObj.rotation_euler = rotation
    camObj.show_name = True

    camProp = camObj.ootCameraPositionProperty
    camProp.bgImageOverrideIndex = hexOrDecInt(bgImageOverrideIndex)

    fovValue = hexOrDecInt(fov)
    fovValue = int.from_bytes(fovValue.to_bytes(2, "big", signed=fovValue < 0x8000), "big", signed=True)
    if fovValue > 360:
        fovValue *= 0.01  # see CAM_DATA_SCALED() macro
    camObj.data.angle = math.radians(fovValue)

    return camObj


def parseCrawlSpaceData(
    setting: str, sceneData: str, posDataName: str, index: int, count: int, objName: str, orderIndex: str
):
    camPosData = getDataMatch(sceneData, posDataName, "Vec3s", "camera position list")
    camPosList = [value.replace("{", "").strip() for value in camPosData.split("},") if value.strip() != ""]
    posData = [camPosList[index : index + count][i] for i in range(0, count, 3)]

    points = []
    for posDataItem in posData:
        points.append([hexOrDecInt(value.strip()) for value in posDataItem.split(",")])

    # name is important for alphabetical ordering
    curveObj = createCurveFromPoints(points, objName)
    curveObj.show_name = True
    crawlProp = curveObj.ootSplineProperty
    crawlProp.splineType = "Crawlspace"
    crawlProp.index = orderIndex
    setCustomProperty(crawlProp, "camSType", "CAM_SET_CRAWLSPACE", ootEnumCameraCrawlspaceSType)

    return curveObj


def parseWaterBoxes(
    sceneObj: bpy.types.Object,
    roomObjs: list[bpy.types.Object],
    sceneData: str,
    waterBoxListName: str,
):
    waterBoxListData = getDataMatch(sceneData, waterBoxListName, "WaterBox", "water box list")
    waterBoxList = [value.replace("{", "").strip() for value in waterBoxListData.split("},") if value.strip() != ""]

    # orderIndex used for naming cameras in alphabetical order
    orderIndex = 0
    for waterBoxData in waterBoxList:
        objName = f"{sceneObj.name}_waterBox_{format(orderIndex, '03')}"
        params = [value.strip() for value in waterBoxData.split(",")]
        topCorner = yUpToZUp @ mathutils.Vector(
            [hexOrDecInt(value) / bpy.context.scene.ootBlenderScale for value in params[0:3]]
        )
        dimensions = [hexOrDecInt(value) / bpy.context.scene.ootBlenderScale for value in params[3:5]]
        properties = hexOrDecInt(params[5])

        height = 1000 / bpy.context.scene.ootBlenderScale  # just to add volume

        location = mathutils.Vector([0, 0, 0])
        scale = [dimensions[0] / 2, dimensions[1] / 2, height / 2]
        location.x = topCorner[0] + scale[0]  # x
        location.y = topCorner[1] - scale[1]  # -z
        location.z = topCorner.z - scale[2]  # y

        waterBoxObj = bpy.data.objects.new(objName, None)
        bpy.context.scene.collection.objects.link(waterBoxObj)
        waterBoxObj.location = location
        waterBoxObj.scale = scale
        waterBoxProp = waterBoxObj.ootWaterBoxProperty

        waterBoxObj.show_name = True
        waterBoxObj.ootEmptyType = "Water Box"
        flag19 = checkBit(properties, 19)
        roomIndex = getBits(properties, 13, 6)
        waterBoxProp.lighting = getBits(properties, 8, 5)
        waterBoxProp.camera = getBits(properties, 0, 8)
        waterBoxProp.flag19 = flag19

        # 0x3F = -1 in 6bit value
        parentObject(roomObjs[roomIndex] if roomIndex != 0x3F else sceneObj, waterBoxObj)
        orderIndex += 1


def parseDrawConfig(drawConfigName: str, sceneData: str, drawConfigData: str, f3dContext: OOTF3DContext):
    drawFunctionName = "Scene_DrawConfig" + "".join(
        [value.strip().lower().capitalize() for value in drawConfigName.replace("SDC_", "").split("_")]
    )

    # get draw function
    match = re.search(rf"void\s*{re.escape(drawFunctionName)}(.*?)CLOSE\_DISPS", drawConfigData, flags=re.DOTALL)
    if match is None:
        print(f"Could not find draw function {drawFunctionName}.")
        return
    functionData = match.group(1)

    # get all flipbook textures
    flipbookDict = {}
    for fbMatch in re.finditer(
        r"void\*\s*([a-zA-Z0-9\_]*)\s*\[.*?\]\s*=\s*\{(.*?)\}\s*;", drawConfigData, flags=re.DOTALL
    ):
        name = fbMatch.group(1)
        textureList = [value.strip() for value in fbMatch.group(2).split(",") if value.strip() != ""]
        flipbookDict[name] = textureList

    # static environment color
    for envMatch in re.finditer(
        rf"gDPSetEnvColor\s*\(\s*POLY_[A-Z]{{3}}_DISP\s*\+\+\s*,([^\)]*)\)\s*;", functionData, flags=re.DOTALL
    ):
        params = [value.strip() for value in envMatch.group(1).split(",")]
        try:
            color = tuple([hexOrDecInt(value) / 0xFF for value in params])
            f3dContext.mat().env_color = color
        except:
            pass

    # dynamic textures
    for flipbookMatch in re.finditer(
        rf"gSPSegment\s*\(\s*POLY_([A-Z]{{3}})_DISP\s*\+\+\s*,\s*([^,]*),\s*SEGMENTED_TO_VIRTUAL(.*?)\)\s*;",
        functionData,
        flags=re.DOTALL,
    ):
        drawLayerID = flipbookMatch.group(1)
        segment = flipbookMatch.group(2).strip()
        textureParam = flipbookMatch.group(3)

        drawLayer = "Transparent" if drawLayerID == "XLU" else "Opaque"
        flipbookKey = (hexOrDecInt(segment), drawLayer)

        for name, textureNames in flipbookDict.items():
            if name in textureParam:
                f3dContext.flipbooks[flipbookKey] = TextureFlipbook(name, "Array", flipbookDict[name])
