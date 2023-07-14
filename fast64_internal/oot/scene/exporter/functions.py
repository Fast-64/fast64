import bpy

from ....f3d.f3d_writer import TriangleConverterInfo, saveStaticModel, getInfoDict
from ...oot_constants import ootData
from ...oot_spline import assertCurveValid
from ...oot_model_classes import OOTModel
from ...oot_collision import exportCollisionCommon
from ...oot_collision_classes import OOTWaterBox
from .classes import BoundingBox

from .utility import (
    getConvertedTransform,
    readCamPos,
    readCrawlspace,
    readPathProp,
    readRoomData,
    readSceneData,
    addActor,
    addStartPosition,
)

from ....utility import (
    PluginError,
    checkIdentityRotation,
    restoreHiddenState,
    unhideAllAndGetHiddenState,
    toAlnum,
)

from ...oot_utility import (
    OOTObjectCategorizer,
    CullGroup,
    checkUniformScale,
    ootDuplicateHierarchy,
    ootCleanupScene,
    getCustomProperty,
    ootConvertTranslation,
    isPathObject,
)

from .classes import (
    OOTScene,
    OOTActor,
    OOTTransitionActor,
    OOTEntrance,
    OOTDLGroup,
)


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


def ootConvertScene(originalSceneObj, transformMatrix, f3dType, isHWv1, sceneName, DLFormat, convertTextureData):
    if originalSceneObj.data is not None or originalSceneObj.ootEmptyType != "Scene":
        raise PluginError(originalSceneObj.name + ' is not an empty with the "Scene" empty type.')

    if bpy.context.scene.exportHiddenGeometry:
        hiddenState = unhideAllAndGetHiddenState(bpy.context.scene)

    # Don't remove ignore_render, as we want to reuse this for collision
    sceneObj, allObjs = ootDuplicateHierarchy(originalSceneObj, None, True, OOTObjectCategorizer())

    if bpy.context.scene.exportHiddenGeometry:
        restoreHiddenState(hiddenState)

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
