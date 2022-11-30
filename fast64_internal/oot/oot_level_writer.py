import bpy, os, math, mathutils
from bpy.utils import register_class, unregister_class
from ..panels import OOT_Panel
from ..f3d.f3d_gbi import TextureExportSettings, DLFormat
from ..f3d.f3d_writer import TriangleConverterInfo, saveStaticModel, getInfoDict
from .oot_object import addMissingObjectsToAllRoomHeaders
from .oot_level import OOTExportSceneSettingsProperty, OOTImportSceneSettingsProperty, OOTRemoveSceneSettingsProperty
from .oot_f3d_writer import writeTextureArraysNew, writeTextureArraysExisting1D
from .oot_constants import ootSceneIDToName, ootEnumSceneID, ootData
from .oot_scene_room import OOT_SearchSceneEnumOperator, OOTRoomHeaderProperty, OOTAlternateRoomHeaderProperty
from .oot_cutscene import convertCutsceneObject, readCutsceneData
from .oot_spline import assertCurveValid, ootConvertPath
from .oot_model_classes import OOTModel
from .oot_collision import OOTCameraData, exportCollisionCommon
from .oot_collision_classes import OOTCameraPosData, OOTWaterBox, OOTCrawlspaceData, decomp_compat_map_CameraSType
from .oot_level_parser import OOT_ImportScene

from ..utility import (
    PluginError,
    CData,
    customExportWarning,
    checkIdentityRotation,
    hideObjsInList,
    unhideAllAndGetHiddenList,
    raisePluginError,
    ootGetBaseOrCustomLight,
    exportColor,
    prop_split,
    toAlnum,
    checkObjectReference,
    writeCDataSourceOnly,
    writeCDataHeaderOnly,
    readFile,
    writeFile,
)

from .scene.exporter.to_c import (
    OOT_ClearBootupScene,
    setBootupScene,
    ootSceneBootupRegister,
    ootSceneBootupUnregister,
    getIncludes,
    getSceneC,
    modifySceneTable,
    editSpecFile,
    modifySceneFiles,
    deleteSceneFiles,
)

from .oot_utility import (
    ExportInfo,
    OOTObjectCategorizer,
    CullGroup,
    checkUniformScale,
    ootDuplicateHierarchy,
    ootCleanupScene,
    ootGetPath,
    getCustomProperty,
    ootConvertTranslation,
    ootConvertRotation,
    getSceneDirFromLevelName,
    isPathObject,
    sceneNameFromID,
    getEnumName,
)

from .oot_level_classes import (
    OOTLight,
    OOTExit,
    OOTScene,
    OOTRoom,
    OOTActor,
    OOTTransitionActor,
    OOTEntrance,
    OOTDLGroup,
    OOTBGImage,
    addActor,
    addStartPosition,
)


def sceneNameFromID(sceneID):
    if sceneID in ootSceneIDToName:
        return ootSceneIDToName[sceneID]
    else:
        raise PluginError("Cannot find scene ID " + str(sceneID))


def ootPreprendSceneIncludes(scene, file):
    exportFile = getIncludes(scene)
    exportFile.append(file)
    return exportFile


def ootCreateSceneHeader(levelC):
    sceneHeader = CData()

    sceneHeader.append(levelC.sceneMainC)
    if levelC.sceneTexturesIsUsed():
        sceneHeader.append(levelC.sceneTexturesC)
    sceneHeader.append(levelC.sceneCollisionC)
    if levelC.sceneCutscenesIsUsed():
        for i in range(len(levelC.sceneCutscenesC)):
            sceneHeader.append(levelC.sceneCutscenesC[i])
    for roomName, roomMainC in levelC.roomMainC.items():
        sceneHeader.append(roomMainC)
    for roomName, roomShapeInfoC in levelC.roomShapeInfoC.items():
        sceneHeader.append(roomShapeInfoC)
    for roomName, roomModelC in levelC.roomModelC.items():
        sceneHeader.append(roomModelC)

    return sceneHeader


def ootCombineSceneFiles(levelC):
    sceneC = CData()

    sceneC.append(levelC.sceneMainC)
    if levelC.sceneTexturesIsUsed():
        sceneC.append(levelC.sceneTexturesC)
    sceneC.append(levelC.sceneCollisionC)
    if levelC.sceneCutscenesIsUsed():
        for i in range(len(levelC.sceneCutscenesC)):
            sceneC.append(levelC.sceneCutscenesC[i])
    return sceneC


def ootExportSceneToC(
    originalSceneObj, transformMatrix, f3dType, isHWv1, sceneName, DLFormat, savePNG, exportInfo, bootToSceneOptions
):

    checkObjectReference(originalSceneObj, "Scene object")
    isCustomExport = exportInfo.isCustomExportPath
    exportPath = exportInfo.exportPath

    scene = ootConvertScene(originalSceneObj, transformMatrix, f3dType, isHWv1, sceneName, DLFormat, not savePNG)

    exportSubdir = ""
    if exportInfo.customSubPath is not None:
        exportSubdir = exportInfo.customSubPath
    if not isCustomExport and exportInfo.customSubPath is None:
        exportSubdir = os.path.dirname(getSceneDirFromLevelName(sceneName))

    roomObjList = [
        obj for obj in originalSceneObj.children_recursive if obj.data is None and obj.ootEmptyType == "Room"
    ]
    for roomObj in roomObjList:
        room = scene.rooms[roomObj.ootRoomHeader.roomIndex]
        addMissingObjectsToAllRoomHeaders(roomObj, room, ootData)

    sceneInclude = exportSubdir + "/" + sceneName + "/"
    levelPath = ootGetPath(exportPath, isCustomExport, exportSubdir, sceneName, True, True)
    levelC = getSceneC(scene, TextureExportSettings(False, savePNG, sceneInclude, levelPath))

    if not isCustomExport:
        writeTextureArraysExistingScene(scene.model, exportPath, sceneInclude + sceneName + "_scene.h")
    else:
        textureArrayData = writeTextureArraysNew(scene.model, None)
        levelC.sceneTexturesC.append(textureArrayData)

    if bpy.context.scene.ootSceneExportSettings.singleFile:
        writeCDataSourceOnly(
            ootPreprendSceneIncludes(scene, ootCombineSceneFiles(levelC)),
            os.path.join(levelPath, scene.sceneName() + ".c"),
        )
        for i in range(len(scene.rooms)):
            roomC = CData()
            roomC.append(levelC.roomMainC[scene.rooms[i].roomName()])
            roomC.append(levelC.roomShapeInfoC[scene.rooms[i].roomName()])
            roomC.append(levelC.roomModelC[scene.rooms[i].roomName()])
            writeCDataSourceOnly(
                ootPreprendSceneIncludes(scene, roomC), os.path.join(levelPath, scene.rooms[i].roomName() + ".c")
            )
    else:
        # Export the scene segment .c files
        writeCDataSourceOnly(
            ootPreprendSceneIncludes(scene, levelC.sceneMainC), os.path.join(levelPath, scene.sceneName() + "_main.c")
        )
        if levelC.sceneTexturesIsUsed():
            writeCDataSourceOnly(
                ootPreprendSceneIncludes(scene, levelC.sceneTexturesC),
                os.path.join(levelPath, scene.sceneName() + "_tex.c"),
            )
        writeCDataSourceOnly(
            ootPreprendSceneIncludes(scene, levelC.sceneCollisionC),
            os.path.join(levelPath, scene.sceneName() + "_col.c"),
        )
        if levelC.sceneCutscenesIsUsed():
            for i in range(len(levelC.sceneCutscenesC)):
                writeCDataSourceOnly(
                    ootPreprendSceneIncludes(scene, levelC.sceneCutscenesC[i]),
                    os.path.join(levelPath, scene.sceneName() + "_cs_" + str(i) + ".c"),
                )

        # Export the room segment .c files
        for roomName, roomMainC in levelC.roomMainC.items():
            writeCDataSourceOnly(
                ootPreprendSceneIncludes(scene, roomMainC), os.path.join(levelPath, roomName + "_main.c")
            )
        for roomName, roomShapeInfoC in levelC.roomShapeInfoC.items():
            writeCDataSourceOnly(
                ootPreprendSceneIncludes(scene, roomShapeInfoC), os.path.join(levelPath, roomName + "_model_info.c")
            )
        for roomName, roomModelC in levelC.roomModelC.items():
            writeCDataSourceOnly(
                ootPreprendSceneIncludes(scene, roomModelC), os.path.join(levelPath, roomName + "_model.c")
            )

    # Export the scene .h file
    writeCDataHeaderOnly(ootCreateSceneHeader(levelC), os.path.join(levelPath, scene.sceneName() + ".h"))

    # Copy bg images
    scene.copyBgImages(levelPath)

    if not isCustomExport:
        writeOtherSceneProperties(scene, exportInfo, levelC)

    if bootToSceneOptions is not None and bootToSceneOptions.bootToScene:
        setBootupScene(
            os.path.join(exportPath, "include/config/config_debug.h")
            if not isCustomExport
            else os.path.join(levelPath, "config_bootup.h"),
            "ENTR_" + sceneName.upper() + "_" + str(bootToSceneOptions.spawnIndex),
            bootToSceneOptions,
        )


def writeTextureArraysExistingScene(fModel: OOTModel, exportPath: str, sceneInclude: str):
    drawConfigPath = os.path.join(exportPath, "src/code/z_scene_table.c")
    drawConfigData = readFile(drawConfigPath)
    newData = drawConfigData

    if f'#include "{sceneInclude}"' not in newData:
        additionalIncludes = f'#include "{sceneInclude}"\n'
    else:
        additionalIncludes = ""

    for flipbook in fModel.flipbooks:
        if flipbook.exportMode == "Array":
            newData = writeTextureArraysExisting1D(newData, flipbook, additionalIncludes)
        else:
            raise PluginError("Scenes can only use array flipbooks.")

    if newData != drawConfigData:
        writeFile(drawConfigPath, newData)


def writeOtherSceneProperties(scene, exportInfo, levelC):
    modifySceneTable(scene, exportInfo)
    editSpecFile(scene, exportInfo, levelC)
    modifySceneFiles(scene, exportInfo)


def readSceneData(scene, scene_properties, sceneHeader, alternateSceneHeaders):
    scene.write_dummy_room_list = scene_properties.write_dummy_room_list
    scene.sceneTableEntry.drawConfig = getCustomProperty(sceneHeader.sceneTableEntry, "drawConfig")
    scene.globalObject = getCustomProperty(sceneHeader, "globalObject")
    scene.naviCup = getCustomProperty(sceneHeader, "naviCup")
    scene.skyboxID = getCustomProperty(sceneHeader, "skyboxID")
    scene.skyboxCloudiness = getCustomProperty(sceneHeader, "skyboxCloudiness")
    scene.skyboxLighting = getCustomProperty(sceneHeader, "skyboxLighting")
    scene.isSkyboxLightingCustom = sceneHeader.skyboxLighting == "Custom"
    scene.mapLocation = getCustomProperty(sceneHeader, "mapLocation")
    scene.cameraMode = getCustomProperty(sceneHeader, "cameraMode")
    scene.musicSeq = getCustomProperty(sceneHeader, "musicSeq")
    scene.nightSeq = getCustomProperty(sceneHeader, "nightSeq")
    scene.audioSessionPreset = getCustomProperty(sceneHeader, "audioSessionPreset")
    scene.appendNullEntrance = sceneHeader.appendNullEntrance

    if (
        sceneHeader.skyboxLighting == "0x00"
        or sceneHeader.skyboxLighting == "0"
        or sceneHeader.skyboxLighting == "LIGHT_MODE_TIME"
    ):  # Time of Day
        scene.lights.append(getLightData(sceneHeader.timeOfDayLights.dawn))
        scene.lights.append(getLightData(sceneHeader.timeOfDayLights.day))
        scene.lights.append(getLightData(sceneHeader.timeOfDayLights.dusk))
        scene.lights.append(getLightData(sceneHeader.timeOfDayLights.night))
    else:
        for lightProp in sceneHeader.lightList:
            scene.lights.append(getLightData(lightProp))

    for exitProp in sceneHeader.exitList:
        scene.exitList.append(getExitData(exitProp))

    scene.writeCutscene = getCustomProperty(sceneHeader, "writeCutscene")
    if scene.writeCutscene:
        scene.csWriteType = getattr(sceneHeader, "csWriteType")
        if scene.csWriteType == "Embedded":
            scene.csEndFrame = getCustomProperty(sceneHeader, "csEndFrame")
            scene.csWriteTerminator = getCustomProperty(sceneHeader, "csWriteTerminator")
            scene.csTermIdx = getCustomProperty(sceneHeader, "csTermIdx")
            scene.csTermStart = getCustomProperty(sceneHeader, "csTermStart")
            scene.csTermEnd = getCustomProperty(sceneHeader, "csTermEnd")
            readCutsceneData(scene, sceneHeader)
        elif scene.csWriteType == "Custom":
            scene.csWriteCustom = getCustomProperty(sceneHeader, "csWriteCustom")
        elif scene.csWriteType == "Object":
            if sceneHeader.csWriteObject is None:
                raise PluginError("No object selected for cutscene reference")
            elif sceneHeader.csWriteObject.ootEmptyType != "Cutscene":
                raise PluginError("Object selected as cutscene is wrong type, must be empty with Cutscene type")
            elif sceneHeader.csWriteObject.parent is not None:
                raise PluginError("Cutscene empty object should not be parented to anything")
            else:
                scene.csWriteObject = convertCutsceneObject(sceneHeader.csWriteObject)

    if alternateSceneHeaders is not None:
        for ec in sceneHeader.extraCutscenes:
            scene.extraCutscenes.append(convertCutsceneObject(ec.csObject))

        scene.collision.cameraData = OOTCameraData(scene.name)

        if not alternateSceneHeaders.childNightHeader.usePreviousHeader:
            scene.childNightHeader = scene.getAlternateHeaderScene(scene.name)
            readSceneData(scene.childNightHeader, scene_properties, alternateSceneHeaders.childNightHeader, None)

        if not alternateSceneHeaders.adultDayHeader.usePreviousHeader:
            scene.adultDayHeader = scene.getAlternateHeaderScene(scene.name)
            readSceneData(scene.adultDayHeader, scene_properties, alternateSceneHeaders.adultDayHeader, None)

        if not alternateSceneHeaders.adultNightHeader.usePreviousHeader:
            scene.adultNightHeader = scene.getAlternateHeaderScene(scene.name)
            readSceneData(scene.adultNightHeader, scene_properties, alternateSceneHeaders.adultNightHeader, None)

        for i in range(len(alternateSceneHeaders.cutsceneHeaders)):
            cutsceneHeaderProp = alternateSceneHeaders.cutsceneHeaders[i]
            cutsceneHeader = scene.getAlternateHeaderScene(scene.name)
            readSceneData(cutsceneHeader, scene_properties, cutsceneHeaderProp, None)
            scene.cutsceneHeaders.append(cutsceneHeader)
    else:
        if len(sceneHeader.extraCutscenes) > 0:
            raise PluginError(
                "Extra cutscenes (not in any header) only belong in the main scene, not alternate headers"
            )


def getConvertedTransform(transformMatrix, sceneObj, obj, handleOrientation):

    # Hacky solution to handle Z-up to Y-up conversion
    # We cannot apply rotation to empty, as that modifies scale
    if handleOrientation:
        orientation = mathutils.Quaternion((1, 0, 0), math.radians(90.0))
    else:
        orientation = mathutils.Matrix.Identity(4)
    return getConvertedTransformWithOrientation(transformMatrix, sceneObj, obj, orientation)


def getConvertedTransformWithOrientation(transformMatrix, sceneObj, obj, orientation):
    relativeTransform = transformMatrix @ sceneObj.matrix_world.inverted() @ obj.matrix_world
    blenderTranslation, blenderRotation, scale = relativeTransform.decompose()
    rotation = blenderRotation @ orientation
    convertedTranslation = ootConvertTranslation(blenderTranslation)
    convertedRotation = ootConvertRotation(rotation)

    return convertedTranslation, convertedRotation, scale, rotation


def getExitData(exitProp):
    if exitProp.exitIndex != "Custom":
        raise PluginError("Exit index enums not implemented yet.")
    return OOTExit(exitProp.exitIndexCustom)


def getLightData(lightProp):
    light = OOTLight()
    light.ambient = exportColor(lightProp.ambient)
    light.diffuse0, light.diffuseDir0 = ootGetBaseOrCustomLight(lightProp, 0, True, True)
    light.diffuse1, light.diffuseDir1 = ootGetBaseOrCustomLight(lightProp, 1, True, True)
    light.fogColor = exportColor(lightProp.fogColor)
    light.fogNear = lightProp.fogNear
    light.transitionSpeed = lightProp.transitionSpeed
    light.fogFar = lightProp.fogFar
    return light


def readRoomData(
    sceneName: str,
    room: OOTRoom,
    roomHeader: OOTRoomHeaderProperty,
    alternateRoomHeaders: OOTAlternateRoomHeaderProperty,
):
    room.roomIndex = roomHeader.roomIndex
    room.roomBehaviour = getCustomProperty(roomHeader, "roomBehaviour")
    room.disableWarpSongs = roomHeader.disableWarpSongs
    room.showInvisibleActors = roomHeader.showInvisibleActors

    # room heat behavior is active if the idle mode is 0x03
    room.linkIdleMode = getCustomProperty(roomHeader, "linkIdleMode") if not roomHeader.roomIsHot else "0x03"

    room.linkIdleModeCustom = roomHeader.linkIdleModeCustom
    room.setWind = roomHeader.setWind
    room.windVector = roomHeader.windVector[:]
    room.windStrength = roomHeader.windStrength
    if roomHeader.leaveTimeUnchanged:
        room.timeHours = "0xFF"
        room.timeMinutes = "0xFF"
    else:
        room.timeHours = roomHeader.timeHours
        room.timeMinutes = roomHeader.timeMinutes
    room.timeSpeed = max(-128, min(127, int(round(roomHeader.timeSpeed * 0xA))))
    room.disableSkybox = roomHeader.disableSkybox
    room.disableSunMoon = roomHeader.disableSunMoon
    room.echo = roomHeader.echo

    for obj in roomHeader.objectList:
        # export using the key if the legacy prop isn't present
        if "objectID" not in obj:
            if obj.objectKey != "Custom":
                objectID = ootData.objectData.objectsByKey[obj.objectKey].id
            else:
                objectID = obj.objectIDCustom
        else:
            objectID = ootData.objectData.ootEnumObjectIDLegacy[obj["objectID"]][0]
            if objectID == "Custom":
                objectID = obj.objectIDCustom

        room.objectIDList.append(objectID)

    if len(room.objectIDList) > 16:
        print(
            "Warning: A room can only have a maximum of 16 objects in its object list, unless more memory is allocated in code.",
        )

    if alternateRoomHeaders is not None:
        if not alternateRoomHeaders.childNightHeader.usePreviousHeader:
            room.childNightHeader = room.getAlternateHeaderRoom(room.ownerName)
            readRoomData(sceneName, room.childNightHeader, alternateRoomHeaders.childNightHeader, None)

        if not alternateRoomHeaders.adultDayHeader.usePreviousHeader:
            room.adultDayHeader = room.getAlternateHeaderRoom(room.ownerName)
            readRoomData(sceneName, room.adultDayHeader, alternateRoomHeaders.adultDayHeader, None)

        if not alternateRoomHeaders.adultNightHeader.usePreviousHeader:
            room.adultNightHeader = room.getAlternateHeaderRoom(room.ownerName)
            readRoomData(sceneName, room.adultNightHeader, alternateRoomHeaders.adultNightHeader, None)

        for i in range(len(alternateRoomHeaders.cutsceneHeaders)):
            cutsceneHeaderProp = alternateRoomHeaders.cutsceneHeaders[i]
            cutsceneHeader = room.getAlternateHeaderRoom(room.ownerName)
            readRoomData(sceneName, cutsceneHeader, cutsceneHeaderProp, None)
            room.cutsceneHeaders.append(cutsceneHeader)

    if roomHeader.roomShape == "ROOM_SHAPE_TYPE_IMAGE":
        for bgImage in roomHeader.bgImageList:
            if bgImage.image is None:
                raise PluginError(
                    'A room is has room shape "Image" but does not have an image set in one of its BG images.'
                )
            room.mesh.bgImages.append(
                OOTBGImage(
                    toAlnum(sceneName + "_bg_" + bgImage.image.name),
                    bgImage.image,
                    bgImage.otherModeFlags,
                )
            )


def readCamPos(camPosProp, obj, scene, sceneObj, transformMatrix):
    # Camera faces opposite direction
    orientation = mathutils.Quaternion((0, 1, 0), math.radians(180.0))
    translation, rotation, scale, orientedRotation = getConvertedTransformWithOrientation(
        transformMatrix, sceneObj, obj, orientation
    )
    camPosProp = obj.ootCameraPositionProperty
    index = camPosProp.index
    # TODO: FOV conversion?
    if index in scene.collision.cameraData.camPosDict:
        raise PluginError(f"Error: Repeated camera position index: {index} for {obj.name}")
    if camPosProp.camSType == "Custom":
        camSType = camPosProp.camSTypeCustom
    else:
        camSType = decomp_compat_map_CameraSType.get(camPosProp.camSType, camPosProp.camSType)

    fov = math.degrees(obj.data.angle)
    if fov > 3.6:
        fov *= 100  # see CAM_DATA_SCALED() macro

    scene.collision.cameraData.camPosDict[index] = OOTCameraPosData(
        camSType,
        camPosProp.hasPositionData,
        translation,
        rotation,
        round(fov),
        camPosProp.bgImageOverrideIndex,
    )


def readCrawlspace(obj, scene, transformMatrix):

    splineProp = obj.ootSplineProperty
    index = splineProp.index

    if index in scene.collision.cameraData.camPosDict:
        raise PluginError(f"Error: Repeated camera position index: {index} for {obj.name}")

    if splineProp.camSType == "Custom":
        camSType = splineProp.camSTypeCustom
    else:
        camSType = decomp_compat_map_CameraSType.get(splineProp.camSType, splineProp.camSType)

    crawlspace = OOTCrawlspaceData(camSType)
    spline = obj.data.splines[0]
    for point in spline.points:
        position = [round(value) for value in transformMatrix @ obj.matrix_world @ point.co]
        crawlspace.points.append(position)

    scene.collision.cameraData.camPosDict[index] = crawlspace


def readPathProp(pathProp, obj, scene, sceneObj, sceneName, transformMatrix):
    relativeTransform = transformMatrix @ sceneObj.matrix_world.inverted() @ obj.matrix_world
    # scene.pathList[obj.name] = ootConvertPath(sceneName, obj, relativeTransform)

    # actorProp should be an actor, but its purpose is to access headerSettings so this also works.
    addActor(scene, ootConvertPath(sceneName, obj, relativeTransform), obj.ootSplineProperty, "pathList", obj.name)


def ootConvertScene(originalSceneObj, transformMatrix, f3dType, isHWv1, sceneName, DLFormat, convertTextureData):

    if originalSceneObj.data is not None or originalSceneObj.ootEmptyType != "Scene":
        raise PluginError(originalSceneObj.name + ' is not an empty with the "Scene" empty type.')

    if bpy.context.scene.exportHiddenGeometry:
        hiddenObjs = unhideAllAndGetHiddenList(bpy.context.scene)

    # Don't remove ignore_render, as we want to reuse this for collision
    sceneObj, allObjs = ootDuplicateHierarchy(originalSceneObj, None, True, OOTObjectCategorizer())

    if bpy.context.scene.exportHiddenGeometry:
        hideObjsInList(hiddenObjs)

    roomObjs = [child for child in sceneObj.children_recursive if child.data is None and child.ootEmptyType == "Room"]
    if len(roomObjs) == 0:
        raise PluginError("The scene has no child empties with the 'Room' empty type.")

    try:
        scene = OOTScene(sceneName, OOTModel(f3dType, isHWv1, sceneName + "_dl", DLFormat, None))
        readSceneData(scene, sceneObj.fast64.oot.scene, sceneObj.ootSceneHeader, sceneObj.ootAlternateSceneHeaders)
        processedRooms = set()

        for obj in sceneObj.children_recursive:
            translation, rotation, scale, orientedRotation = getConvertedTransform(transformMatrix, sceneObj, obj, True)

            if obj.data is None and obj.ootEmptyType == "Room":
                roomObj = obj
                roomHeader = roomObj.ootRoomHeader
                roomIndex = roomHeader.roomIndex
                if roomIndex in processedRooms:
                    raise PluginError("Error: room index " + str(roomIndex) + " is used more than once.")
                processedRooms.add(roomIndex)
                room = scene.addRoom(roomIndex, sceneName, roomHeader.roomShape)
                readRoomData(sceneName, room, roomHeader, roomObj.ootAlternateRoomHeaders)

                if roomHeader.roomShape == "ROOM_SHAPE_TYPE_IMAGE" and len(roomHeader.bgImageList) < 1:
                    raise PluginError(f'Room {roomObj.name} uses room shape "Image" but doesn\'t have any BG images.')
                if roomHeader.roomShape == "ROOM_SHAPE_TYPE_IMAGE" and len(processedRooms) > 1:
                    raise PluginError(f'Room shape "Image" can only have one room in the scene.')

                cullGroup = CullGroup(translation, scale, obj.ootRoomHeader.defaultCullDistance)
                DLGroup = room.mesh.addMeshGroup(cullGroup).DLGroup
                boundingBox = BoundingBox()
                ootProcessMesh(
                    room.mesh, DLGroup, sceneObj, roomObj, transformMatrix, convertTextureData, None, boundingBox
                )
                centroid, radius = boundingBox.getEnclosingSphere()
                cullGroup.position = centroid
                cullGroup.cullDepth = radius

                room.mesh.terminateDLs()
                room.mesh.removeUnusedEntries()
                ootProcessEmpties(scene, room, sceneObj, roomObj, transformMatrix)
            elif obj.data is None and obj.ootEmptyType == "Water Box":
                # 0x3F = -1 in 6bit value
                ootProcessWaterBox(sceneObj, obj, transformMatrix, scene, 0x3F)
            elif isinstance(obj.data, bpy.types.Camera):
                camPosProp = obj.ootCameraPositionProperty
                readCamPos(camPosProp, obj, scene, sceneObj, transformMatrix)
            elif isinstance(obj.data, bpy.types.Curve) and assertCurveValid(obj):
                if isPathObject(obj):
                    readPathProp(obj.ootSplineProperty, obj, scene, sceneObj, sceneName, transformMatrix)
                else:
                    readCrawlspace(obj, scene, transformMatrix)

        scene.validateIndices()
        scene.sortEntrances()
        exportCollisionCommon(scene.collision, sceneObj, transformMatrix, True, sceneName)

        ootCleanupScene(originalSceneObj, allObjs)

    except Exception as e:
        ootCleanupScene(originalSceneObj, allObjs)
        raise Exception(str(e))

    return scene


class BoundingBox:
    def __init__(self):
        self.minPoint = None
        self.maxPoint = None
        self.points = []

    def addPoint(self, point: tuple[float, float, float]):
        if self.minPoint is None:
            self.minPoint = list(point[:])
        else:
            for i in range(3):
                if point[i] < self.minPoint[i]:
                    self.minPoint[i] = point[i]
        if self.maxPoint is None:
            self.maxPoint = list(point[:])
        else:
            for i in range(3):
                if point[i] > self.maxPoint[i]:
                    self.maxPoint[i] = point[i]
        self.points.append(point)

    def addMeshObj(self, obj: bpy.types.Object, transform: mathutils.Matrix):
        mesh = obj.data
        for vertex in mesh.vertices:
            self.addPoint(transform @ vertex.co)

    def getEnclosingSphere(self) -> tuple[float, float]:
        centroid = (mathutils.Vector(self.minPoint) + mathutils.Vector(self.maxPoint)) / 2
        radius = 0
        for point in self.points:
            distance = (mathutils.Vector(point) - centroid).length
            if distance > radius:
                radius = distance

        # print(f"Radius: {radius}, Centroid: {centroid}")

        transformedCentroid = [round(value) for value in centroid]
        transformedRadius = round(radius)
        return transformedCentroid, transformedRadius


# This function should be called on a copy of an object
# The copy will have modifiers / scale applied and will be made single user
# When we duplicated obj hierarchy we stripped all ignore_renders from hierarchy.
def ootProcessMesh(
    roomMesh, DLGroup, sceneObj, obj, transformMatrix, convertTextureData, LODHierarchyObject, boundingBox: BoundingBox
):

    relativeTransform = transformMatrix @ sceneObj.matrix_world.inverted() @ obj.matrix_world
    translation, rotation, scale = relativeTransform.decompose()

    if obj.data is None and obj.ootEmptyType == "Cull Group":
        if LODHierarchyObject is not None:
            raise PluginError(
                obj.name
                + " cannot be used as a cull group because it is "
                + "in the sub-hierarchy of the LOD group empty "
                + LODHierarchyObject.name
            )

        cullProp = obj.ootCullGroupProperty
        checkUniformScale(scale, obj)
        DLGroup = roomMesh.addMeshGroup(
            CullGroup(
                ootConvertTranslation(translation),
                scale if cullProp.sizeControlsCull else [cullProp.manualRadius],
                obj.empty_display_size if cullProp.sizeControlsCull else 1,
            )
        ).DLGroup

    elif isinstance(obj.data, bpy.types.Mesh) and not obj.ignore_render:
        triConverterInfo = TriangleConverterInfo(obj, None, roomMesh.model.f3d, relativeTransform, getInfoDict(obj))
        fMeshes = saveStaticModel(
            triConverterInfo,
            roomMesh.model,
            obj,
            relativeTransform,
            roomMesh.model.name,
            convertTextureData,
            False,
            "oot",
        )
        if fMeshes is not None:
            for drawLayer, fMesh in fMeshes.items():
                DLGroup.addDLCall(fMesh.draw, drawLayer)

        boundingBox.addMeshObj(obj, relativeTransform)

    alphabeticalChildren = sorted(obj.children, key=lambda childObj: childObj.original_name.lower())
    for childObj in alphabeticalChildren:
        if childObj.data is None and childObj.ootEmptyType == "LOD":
            ootProcessLOD(
                roomMesh,
                DLGroup,
                sceneObj,
                childObj,
                transformMatrix,
                convertTextureData,
                LODHierarchyObject,
                boundingBox,
            )
        else:
            ootProcessMesh(
                roomMesh,
                DLGroup,
                sceneObj,
                childObj,
                transformMatrix,
                convertTextureData,
                LODHierarchyObject,
                boundingBox,
            )


def ootProcessLOD(
    roomMesh, DLGroup, sceneObj, obj, transformMatrix, convertTextureData, LODHierarchyObject, boundingBox: BoundingBox
):

    relativeTransform = transformMatrix @ sceneObj.matrix_world.inverted() @ obj.matrix_world
    translation, rotation, scale = relativeTransform.decompose()
    ootTranslation = ootConvertTranslation(translation)

    LODHierarchyObject = obj
    name = toAlnum(roomMesh.model.name + "_" + obj.name + "_lod")
    opaqueLOD = roomMesh.model.addLODGroup(name + "_opaque", ootTranslation, obj.f3d_lod_always_render_farthest)
    transparentLOD = roomMesh.model.addLODGroup(
        name + "_transparent", ootTranslation, obj.f3d_lod_always_render_farthest
    )

    index = 0
    for childObj in obj.children:
        # This group will not be converted to C directly, but its display lists will be converted through the FLODGroup.
        childDLGroup = OOTDLGroup(name + str(index), roomMesh.model.DLFormat)
        index += 1

        if childObj.data is None and childObj.ootEmptyType == "LOD":
            ootProcessLOD(
                roomMesh,
                childDLGroup,
                sceneObj,
                childObj,
                transformMatrix,
                convertTextureData,
                LODHierarchyObject,
                boundingBox,
            )
        else:
            ootProcessMesh(
                roomMesh,
                childDLGroup,
                sceneObj,
                childObj,
                transformMatrix,
                convertTextureData,
                LODHierarchyObject,
                boundingBox,
            )

        # We handle case with no geometry, for the cases where we have "gaps" in the LOD hierarchy.
        # This can happen if a LOD does not use transparency while the levels above and below it does.
        childDLGroup.createDLs()
        childDLGroup.terminateDLs()

        # Add lod AFTER processing hierarchy, so that DLs will be built by then
        opaqueLOD.add_lod(childDLGroup.opaque, childObj.f3d_lod_z * bpy.context.scene.ootBlenderScale)
        transparentLOD.add_lod(childDLGroup.transparent, childObj.f3d_lod_z * bpy.context.scene.ootBlenderScale)

    opaqueLOD.create_data()
    transparentLOD.create_data()

    DLGroup.addDLCall(opaqueLOD.draw, "Opaque")
    DLGroup.addDLCall(transparentLOD.draw, "Transparent")


def ootProcessEmpties(scene, room, sceneObj, obj, transformMatrix):
    translation, rotation, scale, orientedRotation = getConvertedTransform(transformMatrix, sceneObj, obj, True)

    if obj.data is None:
        if obj.ootEmptyType == "Actor":
            actorProp = obj.ootActorProperty

            # The Actor list is filled with ``("None", f"{i} (Deleted from the XML)", "None")`` for
            # the total number of actors defined in the XML. If the user deletes one, this will prevent
            # any data loss as Blender saves the index of the element in the Actor list used for the EnumProperty
            # and not the identifier as defined by the first element of the tuple. Therefore, we need to check if
            # the current Actor has the ID `None` to avoid export issues.
            if actorProp.actorID != "None":
                if actorProp.rotOverride:
                    actorRot = ", ".join([actorProp.rotOverrideX, actorProp.rotOverrideY, actorProp.rotOverrideZ])
                else:
                    actorRot = ", ".join(f"DEG_TO_BINANG({(rot * (180 / 0x8000)):.3f})" for rot in rotation)

                actorName = (
                    ootData.actorData.actorsByID[actorProp.actorID].name.replace(
                        f" - {actorProp.actorID.removeprefix('ACTOR_')}", ""
                    )
                    if actorProp.actorID != "Custom"
                    else "Custom Actor"
                )

                addActor(
                    room,
                    OOTActor(
                        actorName,
                        getCustomProperty(actorProp, "actorID"),
                        translation,
                        actorRot,
                        actorProp.actorParam,
                    ),
                    actorProp,
                    "actorList",
                    obj.name,
                )
        elif obj.ootEmptyType == "Transition Actor":
            transActorProp = obj.ootTransitionActorProperty
            if transActorProp.actor.actorID != "None":
                if transActorProp.dontTransition:
                    front = (255, getCustomProperty(transActorProp, "cameraTransitionBack"))
                    back = (room.roomIndex, getCustomProperty(transActorProp, "cameraTransitionFront"))
                else:
                    front = (room.roomIndex, getCustomProperty(transActorProp, "cameraTransitionFront"))
                    back = (transActorProp.roomIndex, getCustomProperty(transActorProp, "cameraTransitionBack"))

                transActorName = (
                    ootData.actorData.actorsByID[transActorProp.actor.actorID].name.replace(
                        f" - {transActorProp.actor.actorID.removeprefix('ACTOR_')}", ""
                    )
                    if transActorProp.actor.actorID != "Custom"
                    else "Custom Actor"
                )

                addActor(
                    scene,
                    OOTTransitionActor(
                        transActorName,
                        getCustomProperty(transActorProp.actor, "actorID"),
                        front[0],
                        back[0],
                        front[1],
                        back[1],
                        translation,
                        rotation[1],  # TODO: Correct axis?
                        transActorProp.actor.actorParam,
                    ),
                    transActorProp.actor,
                    "transitionActorList",
                    obj.name,
                )
        elif obj.ootEmptyType == "Entrance":
            entranceProp = obj.ootEntranceProperty
            spawnIndex = obj.ootEntranceProperty.spawnIndex
            addActor(scene, OOTEntrance(room.roomIndex, spawnIndex), entranceProp.actor, "entranceList", obj.name)
            addStartPosition(
                scene,
                spawnIndex,
                OOTActor(
                    "",
                    "ACTOR_PLAYER" if not entranceProp.customActor else entranceProp.actor.actorIDCustom,
                    translation,
                    ", ".join(f"DEG_TO_BINANG({(rot * (180 / 0x8000)):.3f})" for rot in rotation),
                    entranceProp.actor.actorParam,
                ),
                entranceProp.actor,
                obj.name,
            )
        elif obj.ootEmptyType == "Water Box":
            ootProcessWaterBox(sceneObj, obj, transformMatrix, scene, room.roomIndex)
    elif isinstance(obj.data, bpy.types.Camera):
        camPosProp = obj.ootCameraPositionProperty
        readCamPos(camPosProp, obj, scene, sceneObj, transformMatrix)
    elif isinstance(obj.data, bpy.types.Curve) and assertCurveValid(obj):
        if isPathObject(obj):
            readPathProp(obj.ootSplineProperty, obj, scene, sceneObj, scene.name, transformMatrix)
        else:
            readCrawlspace(obj, scene, transformMatrix)

    for childObj in obj.children:
        ootProcessEmpties(scene, room, sceneObj, childObj, transformMatrix)


def ootProcessWaterBox(sceneObj, obj, transformMatrix, scene, roomIndex):
    translation, rotation, scale, orientedRotation = getConvertedTransform(transformMatrix, sceneObj, obj, True)

    checkIdentityRotation(obj, orientedRotation, False)
    waterBoxProp = obj.ootWaterBoxProperty
    scene.collision.waterBoxes.append(
        OOTWaterBox(
            roomIndex,
            getCustomProperty(waterBoxProp, "lighting"),
            getCustomProperty(waterBoxProp, "camera"),
            waterBoxProp.flag19,
            translation,
            scale,
            obj.empty_display_size,
        )
    )


class OOT_ExportScene(bpy.types.Operator):
    """Export an OOT scene."""

    bl_idname = "object.oot_export_level"
    bl_label = "Export Scene"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        activeObj = None
        try:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            activeObj = context.view_layer.objects.active

            obj = context.scene.ootSceneExportObj
            if obj is None:
                raise PluginError("Scene object input not set.")
            elif obj.data is not None or obj.ootEmptyType != "Scene":
                raise PluginError("The input object is not an empty with the Scene type.")

            scaleValue = bpy.context.scene.ootBlenderScale
            finalTransform = mathutils.Matrix.Diagonal(mathutils.Vector((scaleValue, scaleValue, scaleValue))).to_4x4()

        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}
        try:
            settings = context.scene.ootSceneExportSettings
            levelName = settings.name
            option = settings.option
            if settings.customExport:
                exportInfo = ExportInfo(True, bpy.path.abspath(settings.exportPath), None, levelName)
            else:
                if option == "Custom":
                    subfolder = "assets/scenes/" + settings.subFolder + "/"
                else:
                    levelName = sceneNameFromID(option)
                    subfolder = None
                exportInfo = ExportInfo(False, bpy.path.abspath(context.scene.ootDecompPath), subfolder, levelName)

            bootOptions = context.scene.fast64.oot.bootupSceneOptions
            hackerFeaturesEnabled = context.scene.fast64.oot.hackerFeaturesEnabled
            ootExportSceneToC(
                obj,
                finalTransform,
                context.scene.f3d_type,
                context.scene.isHWv1,
                levelName,
                DLFormat.Static,
                context.scene.saveTextures,
                exportInfo,
                bootOptions if hackerFeaturesEnabled else None,
            )

            self.report({"INFO"}, "Success!")

            # don't select the scene
            for elem in bpy.context.selectable_objects:
                elem.select_set(False)

            context.view_layer.objects.active = activeObj
            if activeObj is not None:
                activeObj.select_set(True)

            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            # don't select the scene
            for elem in bpy.context.selectable_objects:
                elem.select_set(False)
            context.view_layer.objects.active = activeObj
            if activeObj is not None:
                activeObj.select_set(True)
            raisePluginError(self, e)
            return {"CANCELLED"}


def ootRemoveSceneC(exportInfo):
    modifySceneTable(None, exportInfo)
    editSpecFile(None, exportInfo, None)
    deleteSceneFiles(exportInfo)


class OOT_RemoveScene(bpy.types.Operator):
    """Remove an OOT scene from an existing decomp directory."""

    bl_idname = "object.oot_remove_level"
    bl_label = "OOT Remove Scene"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings: OOTRemoveSceneSettingsProperty = context.scene.ootSceneRemoveSettings
        levelName = settings.name
        option = settings.option

        if settings.customExport:
            self.report({"ERROR"}, "You can only remove scenes from your decomp path.")
            return {"FINISHED"}

        if option == "Custom":
            subfolder = "assets/scenes/" + settings.subFolder + "/"
        else:
            levelName = sceneNameFromID(option)
            subfolder = None
        exportInfo = ExportInfo(False, bpy.path.abspath(context.scene.ootDecompPath), subfolder, levelName)

        ootRemoveSceneC(exportInfo)

        self.report({"INFO"}, "Success!")
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Are you sure you want to remove this scene?")


def drawSceneSearchOp(layout, enumValue, opName):
    searchBox = layout.box().row()
    searchBox.operator(OOT_SearchSceneEnumOperator.bl_idname, icon="VIEWZOOM", text="").opName = opName
    searchBox.label(text=getEnumName(ootEnumSceneID, enumValue))


class OOT_ExportScenePanel(OOT_Panel):
    bl_idname = "OOT_PT_export_level"
    bl_label = "OOT Scene Exporter"

    def draw(self, context):
        col = self.layout.column()

        # Scene Exporter
        exportBox = col.box().column()
        exportBox.label(text="Scene Exporter")

        settings: OOTExportSceneSettingsProperty = context.scene.ootSceneExportSettings
        if settings.customExport:
            prop_split(exportBox, settings, "exportPath", "Directory")
            prop_split(exportBox, settings, "name", "Name")
            customExportWarning(exportBox)
        else:
            drawSceneSearchOp(exportBox, settings.option, "Export")
            if settings.option == "Custom":
                prop_split(exportBox, settings, "subFolder", "Subfolder")
                prop_split(exportBox, settings, "name", "Name")

        prop_split(exportBox, context.scene, "ootSceneExportObj", "Scene Object")

        exportBox.prop(settings, "singleFile")
        exportBox.prop(settings, "customExport")

        if context.scene.fast64.oot.hackerFeaturesEnabled:
            hackerOoTBox = exportBox.box().column()
            hackerOoTBox.label(text="HackerOoT Options")

            bootOptions = context.scene.fast64.oot.bootupSceneOptions
            hackerOoTBox.prop(bootOptions, "bootToScene", text="Boot To Scene (HackerOOT)")
            if bootOptions.bootToScene:
                hackerOoTBox.prop(bootOptions, "newGameOnly")
                prop_split(hackerOoTBox, bootOptions, "bootMode", "Boot Mode")
                if bootOptions.bootMode == "Play":
                    prop_split(hackerOoTBox, bootOptions, "newGameName", "New Game Name")
                if bootOptions.bootMode != "Map Select":
                    prop_split(hackerOoTBox, bootOptions, "spawnIndex", "Spawn")
                    hackerOoTBox.prop(bootOptions, "overrideHeader")
                    if bootOptions.overrideHeader:
                        prop_split(hackerOoTBox, bootOptions, "headerOption", "Header Option")
                        if bootOptions.headerOption == "Cutscene":
                            prop_split(hackerOoTBox, bootOptions, "cutsceneIndex", "Cutscene Index")
            hackerOoTBox.label(
                text="Note: Scene boot config changes aren't detected by the make process.", icon="ERROR"
            )
            hackerOoTBox.operator(OOT_ClearBootupScene.bl_idname, text="Undo Boot To Scene (HackerOOT Repo)")

        exportBox.operator(OOT_ExportScene.bl_idname)

        # Scene Importer
        importBox = col.box().column()
        importBox.label(text="Scene Importer")

        importSettings: OOTImportSceneSettingsProperty = context.scene.ootSceneImportSettings

        if not importSettings.isCustomDest:
            drawSceneSearchOp(importBox, importSettings.option, "Import")

        importSettings.draw(importBox, importSettings.option)
        importBox.operator(OOT_ImportScene.bl_idname)

        # Remove Scene
        removeBox = col.box().column()
        removeBox.label(text="Remove Scene")

        removeSettings: OOTRemoveSceneSettingsProperty = context.scene.ootSceneRemoveSettings
        drawSceneSearchOp(removeBox, removeSettings.option, "Remove")

        if removeSettings.option == "Custom":
            prop_split(removeBox, removeSettings, "subFolder", "Subfolder")
            prop_split(removeBox, removeSettings, "name", "Name")

            exportPath = (
                context.scene.ootDecompPath + f"assets/scenes/{removeSettings.subFolder}/{removeSettings.name}/"
            )

        removeRow = removeBox.row()
        removeRow.operator(OOT_RemoveScene.bl_idname, text="Remove Scene")

        if removeSettings.option == "Custom" and not os.path.exists(exportPath):
            removeRow.enabled = False
            removeBox.label(text="This path doesn't exist.")
        else:
            removeRow.enabled = True


oot_level_classes = (
    OOT_ExportScene,
    OOT_ImportScene,
    OOT_RemoveScene,
)

oot_level_panel_classes = (OOT_ExportScenePanel,)


def oot_level_panel_register():
    for cls in oot_level_panel_classes:
        register_class(cls)


def oot_level_panel_unregister():
    for cls in oot_level_panel_classes:
        unregister_class(cls)


def oot_level_register():
    for cls in oot_level_classes:
        register_class(cls)

    ootSceneBootupRegister()


def oot_level_unregister():
    for cls in reversed(oot_level_classes):
        unregister_class(cls)

    ootSceneBootupUnregister()
