import math
import mathutils
from ...room.properties import OOTRoomHeaderProperty, OOTAlternateRoomHeaderProperty
from ...oot_constants import ootData
from ...cutscene.exporter import convertCutsceneObject, readCutsceneData
from ...oot_spline import ootConvertPath
from ...oot_collision import OOTCameraData
from ...oot_collision_classes import OOTCameraPosData, OOTCrawlspaceData, decomp_compat_map_CameraSType
from .classes import OOTRoom, OOTLight, OOTExit, OOTBGImage

from ....utility import (
    PluginError,
    ootGetBaseOrCustomLight,
    exportColor,
    toAlnum,
)

from ...oot_utility import (
    getCustomProperty,
    ootConvertTranslation,
    ootConvertRotation,
)


def getConvertedTransformWithOrientation(transformMatrix, sceneObj, obj, orientation):
    relativeTransform = transformMatrix @ sceneObj.matrix_world.inverted() @ obj.matrix_world
    blenderTranslation, blenderRotation, scale = relativeTransform.decompose()
    rotation = blenderRotation @ orientation
    convertedTranslation = ootConvertTranslation(blenderTranslation)
    convertedRotation = ootConvertRotation(rotation)

    return convertedTranslation, convertedRotation, scale, rotation


def getConvertedTransform(transformMatrix, sceneObj, obj, handleOrientation):
    # Hacky solution to handle Z-up to Y-up conversion
    # We cannot apply rotation to empty, as that modifies scale
    if handleOrientation:
        orientation = mathutils.Quaternion((1, 0, 0), math.radians(90.0))
    else:
        orientation = mathutils.Matrix.Identity(4)
    return getConvertedTransformWithOrientation(transformMatrix, sceneObj, obj, orientation)


def addActor(owner, actor, actorProp, propName, actorObjName):
    sceneSetup = actorProp.headerSettings
    if (
        sceneSetup.sceneSetupPreset == "All Scene Setups"
        or sceneSetup.sceneSetupPreset == "All Non-Cutscene Scene Setups"
    ):
        getattr(owner, propName).add(actor)
        if owner.childNightHeader is not None:
            getattr(owner.childNightHeader, propName).add(actor)
        if owner.adultDayHeader is not None:
            getattr(owner.adultDayHeader, propName).add(actor)
        if owner.adultNightHeader is not None:
            getattr(owner.adultNightHeader, propName).add(actor)
        if sceneSetup.sceneSetupPreset == "All Scene Setups":
            for cutsceneHeader in owner.cutsceneHeaders:
                getattr(cutsceneHeader, propName).add(actor)
    elif sceneSetup.sceneSetupPreset == "Custom":
        if sceneSetup.childDayHeader and owner is not None:
            getattr(owner, propName).add(actor)
        if sceneSetup.childNightHeader and owner.childNightHeader is not None:
            getattr(owner.childNightHeader, propName).add(actor)
        if sceneSetup.adultDayHeader and owner.adultDayHeader is not None:
            getattr(owner.adultDayHeader, propName).add(actor)
        if sceneSetup.adultNightHeader and owner.adultNightHeader is not None:
            getattr(owner.adultNightHeader, propName).add(actor)
        for cutsceneHeader in sceneSetup.cutsceneHeaders:
            if cutsceneHeader.headerIndex >= len(owner.cutsceneHeaders) + 4:
                raise PluginError(
                    actorObjName
                    + " uses a cutscene header index that is outside the range of the current number of cutscene headers."
                )
            getattr(owner.cutsceneHeaders[cutsceneHeader.headerIndex - 4], propName).add(actor)
    else:
        raise PluginError("Unhandled scene setup preset: " + str(sceneSetup.sceneSetupPreset))


def addStartPosition(scene, index, actor, actorProp, actorObjName):
    sceneSetup = actorProp.headerSettings
    if (
        sceneSetup.sceneSetupPreset == "All Scene Setups"
        or sceneSetup.sceneSetupPreset == "All Non-Cutscene Scene Setups"
    ):
        addStartPosAtIndex(scene.startPositions, index, actor)
        if scene.childNightHeader is not None:
            addStartPosAtIndex(scene.childNightHeader.startPositions, index, actor)
        if scene.adultDayHeader is not None:
            addStartPosAtIndex(scene.adultDayHeader.startPositions, index, actor)
        if scene.adultNightHeader is not None:
            addStartPosAtIndex(scene.adultNightHeader.startPositions, index, actor)
        if sceneSetup.sceneSetupPreset == "All Scene Setups":
            for cutsceneHeader in scene.cutsceneHeaders:
                addStartPosAtIndex(cutsceneHeader.startPositions, index, actor)
    elif sceneSetup.sceneSetupPreset == "Custom":
        if sceneSetup.childDayHeader and scene is not None:
            addStartPosAtIndex(scene.startPositions, index, actor)
        if sceneSetup.childNightHeader and scene.childNightHeader is not None:
            addStartPosAtIndex(scene.childNightHeader.startPositions, index, actor)
        if sceneSetup.adultDayHeader and scene.adultDayHeader is not None:
            addStartPosAtIndex(scene.adultDayHeader.startPositions, index, actor)
        if sceneSetup.adultNightHeader and scene.adultNightHeader is not None:
            addStartPosAtIndex(scene.adultNightHeader.startPositions, index, actor)
        for cutsceneHeader in sceneSetup.cutsceneHeaders:
            if cutsceneHeader.headerIndex >= len(scene.cutsceneHeaders) + 4:
                raise PluginError(
                    actorObjName
                    + " uses a cutscene header index that is outside the range of the current number of cutscene headers."
                )
            addStartPosAtIndex(scene.cutsceneHeaders[cutsceneHeader.headerIndex - 4].startPositions, index, actor)
    else:
        raise PluginError("Unhandled scene setup preset: " + str(sceneSetup.sceneSetupPreset))


def addStartPosAtIndex(startPosDict, index, value):
    if index in startPosDict:
        raise PluginError("Error: Repeated start position spawn index: " + str(index))
    startPosDict[index] = value


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
        timeOfDayLights = [
            sceneHeader.timeOfDayLights.dawn,
            sceneHeader.timeOfDayLights.day,
            sceneHeader.timeOfDayLights.dusk,
            sceneHeader.timeOfDayLights.night,
        ]
        for todLight in timeOfDayLights:
            light = OOTLight()
            light.ambient = exportColor(todLight.ambient)
            light.diffuse0, light.diffuseDir0 = ootGetBaseOrCustomLight(todLight, 0, True, True)
            light.diffuse1, light.diffuseDir1 = ootGetBaseOrCustomLight(todLight, 1, True, True)
            light.fogColor = exportColor(todLight.fogColor)
            light.fogNear = todLight.fogNear
            light.transitionSpeed = todLight.transitionSpeed
            light.fogFar = todLight.fogFar
            scene.lights.append(light)
    else:
        for lightProp in sceneHeader.lightList:
            light = OOTLight()
            light.ambient = exportColor(lightProp.ambient)
            light.diffuse0, light.diffuseDir0 = ootGetBaseOrCustomLight(lightProp, 0, True, True)
            light.diffuse1, light.diffuseDir1 = ootGetBaseOrCustomLight(lightProp, 1, True, True)
            light.fogColor = exportColor(lightProp.fogColor)
            light.fogNear = lightProp.fogNear
            light.transitionSpeed = lightProp.transitionSpeed
            light.fogFar = lightProp.fogFar
            scene.lights.append(light)

    for exitProp in sceneHeader.exitList:
        if exitProp.exitIndex != "Custom":
            raise PluginError("Exit index enums not implemented yet.")
        scene.exitList.append(OOTExit(exitProp.exitIndexCustom))

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
