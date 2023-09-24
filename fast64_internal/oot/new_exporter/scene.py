import math

from dataclasses import dataclass, field
from mathutils import Vector, Quaternion
from bpy.types import Object, Mesh
from bpy.ops import object
from ...utility import PluginError, CData, exportColor, ootGetBaseOrCustomLight, checkIdentityRotation, indent
from ..oot_utility import convertIntTo2sComplement
from ..scene.properties import OOTSceneHeaderProperty, OOTLightProperty
from ..oot_constants import ootData
from ..oot_collision_classes import decomp_compat_map_CameraSType
from .commands import OOTSceneCommands
from .common import Common, TransitionActor, EntranceActor, altHeaderList
from .room import OOTRoom

from .collision import (
    OOTSceneCollisionHeader,
    CollisionHeaderVertices,
    CollisionHeaderCollisionPoly,
    CollisionHeaderSurfaceType,
    CollisionHeaderBgCamInfo,
    CollisionHeaderWaterBox,
    SurfaceType,
    CollisionPoly,
    Vertex,
    WaterBox,
    BgCamInfo,
    BgCamFuncData,
    CrawlspaceData,
)

from .scene_header import (
    EnvLightSettings,
    Path,
    OOTSceneHeader,
    OOTSceneAlternateHeader,
    OOTSceneHeaderInfos,
    OOTSceneHeaderLighting,
    OOTSceneHeaderCutscene,
    OOTSceneHeaderExits,
    OOTSceneHeaderActors,
    OOTSceneHeaderPath,
    OOTSceneHeaderCrawlspace,
)


@dataclass
class OOTScene(Common, OOTSceneCommands):
    name: str = None
    headerIndex: int = None
    mainHeader: OOTSceneHeader = None
    altHeader: OOTSceneAlternateHeader = None
    roomList: list[OOTRoom] = field(default_factory=list)
    roomListName: str = None

    colHeader: OOTSceneCollisionHeader = None

    def __post_init__(self):
        self.roomListName = f"{self.name}_roomList"

    def validateCurveData(self, curveObj: Object):
        curveData = curveObj.data
        if curveObj.type != "CURVE" or curveData.splines[0].type != "NURBS":
            # Curve was likely not intended to be exported
            return False

        if len(curveData.splines) != 1:
            # Curve was intended to be exported but has multiple disconnected segments
            raise PluginError(f"Exported curves should have only one single segment, found {len(curveData.splines)}")

        return True

    def validateRoomIndices(self):
        for i, room in enumerate(self.roomList):
            if i != room.roomIndex:
                return False

        return True

    def validateScene(self):
        if not len(self.roomList) > 0:
            raise PluginError("ERROR: This scene does not have any rooms!")

        if not self.validateRoomIndices():
            raise PluginError("ERROR: Room indices do not have a consecutive list of indices.")

    def hasAlternateHeaders(self):
        return self.altHeader is not None

    def getSceneHeaderFromIndex(self, headerIndex: int) -> OOTSceneHeader | None:
        if headerIndex == 0:
            return self.mainHeader

        for i, header in enumerate(altHeaderList, 1):
            if headerIndex == i:
                return getattr(self.altHeader, header)

        for i, csHeader in enumerate(self.altHeader.cutscenes, 4):
            if headerIndex == i:
                return csHeader

        return None

    def getExitListFromProps(self, headerProp: OOTSceneHeaderProperty):
        """Returns the exit list and performs safety checks"""

        exitList: list[tuple[int, str]] = []

        for i, exitProp in enumerate(headerProp.exitList):
            if exitProp.exitIndex != "Custom":
                raise PluginError("ERROR: Exits are unfinished, please use 'Custom'.")

            exitList.append((i, exitProp.exitIndexCustom))

        return exitList

    def getRoomObjectFromChild(self, childObj: Object) -> Object | None:
        # Note: temporary solution until PRs #243 & #255 are merged
        for obj in self.sceneObj.children_recursive:
            if obj.type == "EMPTY" and obj.ootEmptyType == "Room":
                for o in obj.children_recursive:
                    if o == childObj:
                        return obj
        return None

    def getTransActorListFromProps(self):
        actorList: list[TransitionActor] = []
        actorObjList: list[Object] = [
            obj
            for obj in self.sceneObj.children_recursive
            if obj.type == "EMPTY" and obj.ootEmptyType == "Transition Actor"
        ]
        for obj in actorObjList:
            roomObj = self.getRoomObjectFromChild(obj)
            if roomObj is None:
                raise PluginError("ERROR: Room Object not found!")
            self.roomIndex = roomObj.ootRoomHeader.roomIndex

            transActorProp = obj.ootTransitionActorProperty

            if not self.isCurrentHeaderValid(transActorProp.actor.headerSettings, self.headerIndex):
                continue

            if transActorProp.actor.actorID != "None":
                pos, rot, _, _ = self.getConvertedTransform(self.transform, self.sceneObj, obj, True)
                transActor = TransitionActor()

                if transActorProp.dontTransition:
                    front = (255, self.getPropValue(transActorProp, "cameraTransitionBack"))
                    back = (self.roomIndex, self.getPropValue(transActorProp, "cameraTransitionFront"))
                else:
                    front = (self.roomIndex, self.getPropValue(transActorProp, "cameraTransitionFront"))
                    back = (transActorProp.roomIndex, self.getPropValue(transActorProp, "cameraTransitionBack"))

                if transActorProp.actor.actorID == "Custom":
                    transActor.id = transActorProp.actor.actorIDCustom
                else:
                    transActor.id = transActorProp.actor.actorID

                transActor.name = (
                    ootData.actorData.actorsByID[transActorProp.actor.actorID].name.replace(
                        f" - {transActorProp.actor.actorID.removeprefix('ACTOR_')}", ""
                    )
                    if transActorProp.actor.actorID != "Custom"
                    else "Custom Actor"
                )

                transActor.pos = pos
                transActor.rot = f"DEG_TO_BINANG({(rot[1] * (180 / 0x8000)):.3f})"  # TODO: Correct axis?
                transActor.params = transActorProp.actor.actorParam
                transActor.roomFrom, transActor.cameraFront = front
                transActor.roomTo, transActor.cameraBack = back
                actorList.append(transActor)
        return actorList

    def getEntranceActorListFromProps(self):
        actorList: list[EntranceActor] = []
        actorObjList: list[Object] = [
            obj for obj in self.sceneObj.children_recursive if obj.type == "EMPTY" and obj.ootEmptyType == "Entrance"
        ]
        for obj in actorObjList:
            roomObj = self.getRoomObjectFromChild(obj)
            if roomObj is None:
                raise PluginError("ERROR: Room Object not found!")

            entranceProp = obj.ootEntranceProperty
            if not self.isCurrentHeaderValid(entranceProp.actor.headerSettings, self.headerIndex):
                continue

            if entranceProp.actor.actorID != "None":
                pos, rot, _, _ = self.getConvertedTransform(self.transform, self.sceneObj, obj, True)
                entranceActor = EntranceActor()

                entranceActor.name = (
                    ootData.actorData.actorsByID[entranceProp.actor.actorID].name.replace(
                        f" - {entranceProp.actor.actorID.removeprefix('ACTOR_')}", ""
                    )
                    if entranceProp.actor.actorID != "Custom"
                    else "Custom Actor"
                )

                entranceActor.id = "ACTOR_PLAYER" if not entranceProp.customActor else entranceProp.actor.actorIDCustom
                entranceActor.pos = pos
                entranceActor.rot = ", ".join(f"DEG_TO_BINANG({(r * (180 / 0x8000)):.3f})" for r in rot)
                entranceActor.params = entranceProp.actor.actorParam
                entranceActor.roomIndex = roomObj.ootRoomHeader.roomIndex
                entranceActor.spawnIndex = entranceProp.spawnIndex
                actorList.append(entranceActor)
        return actorList

    def getPathListFromProps(self, listNameBase: str):
        pathList: list[Path] = []
        pathObjList: list[Object] = [
            obj
            for obj in self.sceneObj.children_recursive
            if obj.type == "CURVE" and obj.ootSplineProperty.splineType == "Path"
        ]

        for i, obj in enumerate(pathObjList):
            isHeaderValid = self.isCurrentHeaderValid(obj.ootSplineProperty.headerSettings, self.headerIndex)
            if isHeaderValid and self.validateCurveData(obj):
                pathList.append(
                    Path(
                        f"{listNameBase}{i:02}", [self.transform @ point.co.xyz for point in obj.data.splines[0].points]
                    )
                )

        return pathList

    def getEnvLightSettingsListFromProps(self, headerProp: OOTSceneHeaderProperty, lightMode: str):
        lightList: list[OOTLightProperty] = []
        lightSettings: list[EnvLightSettings] = []

        if lightMode == "LIGHT_MODE_TIME":
            todLights = headerProp.timeOfDayLights
            lightList = [todLights.dawn, todLights.day, todLights.dusk, todLights.night]
        else:
            lightList = headerProp.lightList

        for lightProp in lightList:
            light1 = ootGetBaseOrCustomLight(lightProp, 0, True, True)
            light2 = ootGetBaseOrCustomLight(lightProp, 1, True, True)
            lightSettings.append(
                EnvLightSettings(
                    lightMode,
                    exportColor(lightProp.ambient),
                    light1[0],
                    light1[1],
                    light2[0],
                    light2[1],
                    exportColor(lightProp.fogColor),
                    lightProp.fogNear,
                    lightProp.fogFar,
                    lightProp.transitionSpeed,
                )
            )

        return lightSettings

    def getNewSceneHeader(self, headerProp: OOTSceneHeaderProperty, headerIndex: int = 0):
        """Returns a single scene header with the informations from the scene empty object"""

        self.headerIndex = headerIndex
        headerName = f"{self.name}_header{self.headerIndex:02}"
        lightMode = self.getPropValue(headerProp, "skyboxLighting")

        if headerProp.writeCutscene and headerProp.csWriteType == "Embedded":
            raise PluginError("ERROR: 'Embedded' CS Write Type is not supported!")

        return OOTSceneHeader(
            headerName,
            OOTSceneHeaderInfos(
                self.getPropValue(headerProp, "globalObject"),
                self.getPropValue(headerProp, "naviCup"),
                self.getPropValue(headerProp.sceneTableEntry, "drawConfig"),
                headerProp.appendNullEntrance,
                self.sceneObj.fast64.oot.scene.write_dummy_room_list,
                self.getPropValue(headerProp, "skyboxID"),
                self.getPropValue(headerProp, "skyboxCloudiness"),
                self.getPropValue(headerProp, "musicSeq"),
                self.getPropValue(headerProp, "nightSeq"),
                self.getPropValue(headerProp, "audioSessionPreset"),
                self.getPropValue(headerProp, "mapLocation"),
                self.getPropValue(headerProp, "cameraMode"),
            ),
            OOTSceneHeaderLighting(
                f"{headerName}_lightSettings",
                lightMode,
                self.getEnvLightSettingsListFromProps(headerProp, lightMode),
            ),
            OOTSceneHeaderCutscene(
                headerProp.csWriteObject.name.removeprefix("Cutscene."),
                headerProp.csWriteType,
                headerProp.writeCutscene,
                headerProp.csWriteObject,
                headerProp.csWriteCustom if headerProp.csWriteType == "Custom" else None,
                [csObj for csObj in headerProp.extraCutscenes],
            ),
            OOTSceneHeaderExits(f"{headerName}_exitList", self.getExitListFromProps(headerProp)),
            OOTSceneHeaderActors(
                f"{headerName}_entranceList",
                f"{headerName}_playerEntryList",
                f"{headerName}_transitionActors",
                self.getTransActorListFromProps(),
                self.getEntranceActorListFromProps(),
            ),
            OOTSceneHeaderPath(f"{headerName}_pathway", self.getPathListFromProps(f"{headerName}_pathwayList")),
            OOTSceneHeaderCrawlspace(None),  # not implemented yet
        )

    def getRoomListC(self):
        roomList = CData()
        listName = f"RomFile {self.roomListName}[]"

        # generating segment rom names for every room
        segNames = []
        for i in range(len(self.roomList)):
            roomName = self.roomList[i].name
            segNames.append((f"_{roomName}SegmentRomStart", f"_{roomName}SegmentRomEnd"))

        # .h
        roomList.header += f"extern {listName};\n"

        if not self.mainHeader.infos.useDummyRoomList:
            # Write externs for rom segments
            roomList.header += "".join(
                f"extern u8 {startName}[];\n" + f"extern u8 {stopName}[];\n" for startName, stopName in segNames
            )

        # .c
        roomList.source = listName + " = {\n"

        if self.mainHeader.infos.useDummyRoomList:
            roomList.source = (
                "// Dummy room list\n" + roomList.source + ((indent + "{ NULL, NULL },\n") * len(self.roomList))
            )
        else:
            roomList.source += (
                " },\n".join(
                    indent + "{ " + f"(uintptr_t){startName}, (uintptr_t){stopName}" for startName, stopName in segNames
                )
                + " },\n"
            )

        roomList.source += "};\n\n"
        return roomList

    def updateBounds(self, position: tuple[int, int, int], bounds: list[tuple[int, int, int]]):
        if len(bounds) == 0:
            bounds.append([position[0], position[1], position[2]])
            bounds.append([position[0], position[1], position[2]])
            return

        minBounds = bounds[0]
        maxBounds = bounds[1]
        for i in range(3):
            if position[i] < minBounds[i]:
                minBounds[i] = position[i]
            if position[i] > maxBounds[i]:
                maxBounds[i] = position[i]

    def getVertIndex(self, vert: tuple[int, int, int], vertArray: list[Vertex]):
        for i in range(len(vertArray)):
            colVert = vertArray[i].pos
            if colVert == vert:
                return i
        return None

    def getColSurfaceVtxDataFromMeshObj(self):
        meshObjList = [obj for obj in self.sceneObj.children_recursive if obj.type == "MESH"]
        object.select_all(action="DESELECT")
        self.sceneObj.select_set(True)

        surfaceTypeData: dict[int, SurfaceType] = {}
        polyList: list[CollisionPoly] = []
        vertexList: list[Vertex] = []
        bounds = []

        i = 0
        for meshObj in meshObjList:
            if not meshObj.ignore_collision:
                if len(meshObj.data.materials) == 0:
                    raise PluginError(f"'{meshObj.name}' must have a material associated with it.")

                meshObj.data.calc_loop_triangles()
                for face in meshObj.data.loop_triangles:
                    colProp = meshObj.material_slots[face.material_index].material.ootCollisionProperty

                    planePoint = self.transform @ meshObj.data.vertices[face.vertices[0]].co
                    (x1, y1, z1) = self.roundPosition(planePoint)
                    (x2, y2, z2) = self.roundPosition(self.transform @ meshObj.data.vertices[face.vertices[1]].co)
                    (x3, y3, z3) = self.roundPosition(self.transform @ meshObj.data.vertices[face.vertices[2]].co)

                    self.updateBounds((x1, y1, z1), bounds)
                    self.updateBounds((x2, y2, z2), bounds)
                    self.updateBounds((x3, y3, z3), bounds)

                    normal = (self.transform.inverted().transposed() @ face.normal).normalized()
                    distance = int(
                        round(-1 * (normal[0] * planePoint[0] + normal[1] * planePoint[1] + normal[2] * planePoint[2]))
                    )
                    distance = convertIntTo2sComplement(distance, 2, True)

                    indices: list[int] = []
                    for vertex in [(x1, y1, z1), (x2, y2, z2), (x3, y3, z3)]:
                        index = self.getVertIndex(vertex, vertexList)
                        if index is None:
                            vertexList.append(Vertex(vertex))
                            indices.append(len(vertexList) - 1)
                        else:
                            indices.append(index)
                    assert len(indices) == 3

                    # We need to ensure two things about the order in which the vertex indices are:
                    #
                    # 1) The vertex with the minimum y coordinate should be first.
                    # This prevents a bug due to an optimization in OoT's CollisionPoly_GetMinY.
                    # https://github.com/zeldaret/oot/blob/873c55faad48a67f7544be713cc115e2b858a4e8/src/code/z_bgcheck.c#L202
                    #
                    # 2) The vertices should wrap around the polygon normal **counter-clockwise**.
                    # This is needed for OoT's dynapoly, which is collision that can move.
                    # When it moves, the vertex coordinates and normals are recomputed.
                    # The normal is computed based on the vertex coordinates, which makes the order of vertices matter.
                    # https://github.com/zeldaret/oot/blob/873c55faad48a67f7544be713cc115e2b858a4e8/src/code/z_bgcheck.c#L2976

                    # Address 1): sort by ascending y coordinate
                    indices.sort(key=lambda index: vertexList[index].pos[1])

                    # Address 2):
                    # swap indices[1] and indices[2],
                    # if the normal computed from the vertices in the current order is the wrong way.
                    v0 = Vector(vertexList[indices[0]].pos)
                    v1 = Vector(vertexList[indices[1]].pos)
                    v2 = Vector(vertexList[indices[2]].pos)
                    if (v1 - v0).cross(v2 - v0).dot(Vector(normal)) < 0:
                        indices[1], indices[2] = indices[2], indices[1]

                    useConveyor = colProp.conveyorOption != "None"
                    surfaceTypeData[i] = SurfaceType(
                        colProp.cameraID,
                        colProp.exitID,
                        int(self.getPropValue(colProp, "floorSetting"), base=16),
                        0,  # unused?
                        int(self.getPropValue(colProp, "wallSetting"), base=16),
                        int(self.getPropValue(colProp, "floorProperty"), base=16),
                        colProp.decreaseHeight,
                        colProp.eponaBlock,
                        int(self.getPropValue(colProp, "sound"), base=16),
                        int(self.getPropValue(colProp, "terrain"), base=16),
                        colProp.lightingSetting,
                        int(colProp.echo, base=16),
                        colProp.hookshotable,
                        int(self.getPropValue(colProp, "conveyorSpeed"), base=16) if useConveyor else 0,
                        int(colProp.conveyorRotation / (2 * math.pi) * 0x3F) if useConveyor else 0,
                        colProp.isWallDamage,
                        colProp.conveyorKeepMomentum if useConveyor else False,
                    )

                    polyList.append(
                        CollisionPoly(
                            indices,
                            colProp.ignoreCameraCollision,
                            colProp.ignoreActorCollision,
                            colProp.ignoreProjectileCollision,
                            useConveyor,
                            tuple(normal),
                            distance,
                            i,
                        )
                    )
                i += 1
        return bounds, vertexList, polyList, [surfaceTypeData[i] for i in range(len(surfaceTypeData))]

    def getBgCamFuncDataFromObjects(self, camObj: Object):
        camProp = camObj.ootCameraPositionProperty

        # Camera faces opposite direction
        pos, rot, _, _ = self.getConvertedTransformWithOrientation(
            self.transform, self.sceneObj, camObj, Quaternion((0, 1, 0), math.radians(180.0))
        )

        fov = math.degrees(camObj.data.angle)
        if fov > 3.6:
            fov *= 100  # see CAM_DATA_SCALED() macro

        return BgCamFuncData(
            pos,
            rot,
            round(fov),
            camProp.bgImageOverrideIndex,
        )

    def getCrawlspaceDataFromObjects(self):
        crawlspaceList: list[CrawlspaceData] = []
        crawlspaceObjList: list[Object] = [
            obj
            for obj in self.sceneObj.children_recursive
            if obj.type == "CURVE" and obj.ootSplineProperty.splineType == "Crawlspace"
        ]

        for obj in crawlspaceObjList:
            if self.validateCurveData(obj):
                crawlspaceList.append(
                    CrawlspaceData(
                        [
                            [round(value) for value in self.transform @ obj.matrix_world @ point.co]
                            for point in obj.data.splines[0].points
                        ]
                    )
                )

        return crawlspaceList

    def getBgCamInfoDataFromObjects(self):
        camObjList = [obj for obj in self.sceneObj.children_recursive if obj.type == "CAMERA"]
        camPosData: dict[int, BgCamFuncData] = {}
        bgCamList: list[BgCamInfo] = []

        index = 0
        for camObj in camObjList:
            camProp = camObj.ootCameraPositionProperty

            if camProp.camSType == "Custom":
                setting = camProp.camSTypeCustom
            else:
                setting = decomp_compat_map_CameraSType.get(camProp.camSType, camProp.camSType)

            if camProp.hasPositionData:
                count = 3
                index = camProp.index
                if index in camPosData:
                    raise PluginError(f"Error: Repeated camera position index: {index} for {camObj.name}")
                camPosData[index] = self.getBgCamFuncDataFromObjects(camObj)
            else:
                count = 0

            bgCamList.append(BgCamInfo(setting, count, index, [camPosData[i] for i in range(len(camPosData))]))
            index += count
        return bgCamList

    def getWaterBoxDataFromObjects(self):
        waterboxObjList = [
            obj for obj in self.sceneObj.children_recursive if obj.type == "EMPTY" and obj.ootEmptyType == "Water Box"
        ]
        waterboxList: list[WaterBox] = []

        for waterboxObj in waterboxObjList:
            emptyScale = waterboxObj.empty_display_size
            pos, _, scale, orientedRot = self.getConvertedTransform(self.transform, self.sceneObj, waterboxObj, True)
            checkIdentityRotation(waterboxObj, orientedRot, False)

            wboxProp = waterboxObj.ootWaterBoxProperty
            roomObj = self.getRoomObjectFromChild(waterboxObj)
            waterboxList.append(
                WaterBox(
                    pos,
                    scale,
                    emptyScale,
                    wboxProp.camera,
                    wboxProp.lighting,
                    roomObj.ootRoomHeader.roomIndex if roomObj is not None else 0x3F,
                    wboxProp.flag19,
                )
            )

        return waterboxList

    def getNewCollisionHeader(self):
        colBounds, vertexList, polyList, surfaceTypeList = self.getColSurfaceVtxDataFromMeshObj()
        return OOTSceneCollisionHeader(
            f"{self.name}_collisionHeader",
            colBounds[0],
            colBounds[1],
            CollisionHeaderVertices(f"{self.name}_vertices", vertexList),
            CollisionHeaderCollisionPoly(f"{self.name}_polygons", polyList),
            CollisionHeaderSurfaceType(f"{self.name}_polygonTypes", surfaceTypeList),
            CollisionHeaderBgCamInfo(
                f"{self.name}_bgCamInfo",
                f"{self.name}_camPosData",
                self.getBgCamInfoDataFromObjects(),
                self.getCrawlspaceDataFromObjects(),
            ),
            CollisionHeaderWaterBox(f"{self.name}_waterBoxes", self.getWaterBoxDataFromObjects()),
        )

    def getSceneMainC(self):
        sceneC = CData()
        headers: list[tuple[OOTSceneHeader, str]] = []
        altHeaderPtrs = None

        if self.hasAlternateHeaders():
            headers = [
                (self.altHeader.childNight, "Child Night"),
                (self.altHeader.adultDay, "Adult Day"),
                (self.altHeader.adultNight, "Adult Night"),
            ]

            for i, csHeader in enumerate(self.altHeader.cutscenes):
                headers.append((csHeader, f"Cutscene No. {i + 1}"))

            altHeaderPtrs = "\n".join(
                indent + curHeader.name + "," if curHeader is not None else indent + "NULL," if i < 4 else ""
                for i, (curHeader, _) in enumerate(headers, 1)
            )

        headers.insert(0, (self.mainHeader, "Child Day (Default)"))
        for i, (curHeader, headerDesc) in enumerate(headers):
            if curHeader is not None:
                sceneC.source += "/**\n * " + f"Header {headerDesc}\n" + "*/\n"
                sceneC.append(self.getSceneCommandList(self, curHeader, i))

                if i == 0:
                    if self.hasAlternateHeaders() and altHeaderPtrs is not None:
                        altHeaderListName = f"SceneCmd* {self.altHeader.name}[]"
                        sceneC.header += f"extern {altHeaderListName};\n"
                        sceneC.source += altHeaderListName + " = {\n" + altHeaderPtrs + "\n};\n\n"

                    # Write the room segment list
                    sceneC.append(self.getRoomListC())

                sceneC.append(curHeader.getHeaderC())

        return sceneC

    def getSceneCutscenesC(self):
        # will be implemented when PR #208 is merged
        csDataList: list[CData] = []
        return csDataList
