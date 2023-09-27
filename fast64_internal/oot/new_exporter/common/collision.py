import math

from dataclasses import dataclass
from mathutils import Vector, Quaternion, Matrix
from bpy.types import Object, Mesh
from bpy.ops import object
from ....utility import PluginError, checkIdentityRotation
from ...oot_utility import convertIntTo2sComplement
from ...oot_collision_classes import decomp_compat_map_CameraSType
from .classes import Common

from ..collision_classes import (
    SurfaceType,
    CollisionPoly,
    Vertex,
    WaterBox,
    BgCamInfo,
    BgCamFuncData,
    CrawlspaceData,
)


@dataclass
class CollisionCommon(Common):
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

    def getMeshObjects(
        self, parentObj: Object, transform: Matrix, matrixTable: dict[Object, Matrix]
    ) -> dict[Object, Matrix]:
        for obj in parentObj.children:
            newTransform = transform @ obj.matrix_local
            if obj.type == "MESH" and not obj.ignore_collision:
                matrixTable[obj] = newTransform
            self.getMeshObjects(obj, newTransform, matrixTable)
        return matrixTable

    def getColSurfaceVtxDataFromMeshObj(self):
        object.select_all(action="DESELECT")
        self.sceneObj.select_set(True)

        matrixTable: dict[Object, Matrix] = {}
        surfaceTypeData: dict[int, SurfaceType] = {}
        polyList: list[CollisionPoly] = []
        vertexList: list[Vertex] = []
        bounds = []

        i = 0
        matrixTable = self.getMeshObjects(self.sceneObj, self.transform, matrixTable)
        for meshObj, transform in matrixTable.items():
            # Note: ``isinstance``only used to get the proper type hints
            if not meshObj.ignore_collision and isinstance(meshObj.data, Mesh):
                if len(meshObj.data.materials) == 0:
                    raise PluginError(f"'{meshObj.name}' must have a material associated with it.")

                meshObj.data.calc_loop_triangles()
                for face in meshObj.data.loop_triangles:
                    colProp = meshObj.material_slots[face.material_index].material.ootCollisionProperty

                    planePoint = transform @ meshObj.data.vertices[face.vertices[0]].co
                    (x1, y1, z1) = self.roundPosition(planePoint)
                    (x2, y2, z2) = self.roundPosition(transform @ meshObj.data.vertices[face.vertices[1]].co)
                    (x3, y3, z3) = self.roundPosition(transform @ meshObj.data.vertices[face.vertices[2]].co)
                    self.updateBounds((x1, y1, z1), bounds)
                    self.updateBounds((x2, y2, z2), bounds)
                    self.updateBounds((x3, y3, z3), bounds)

                    normal = (transform.inverted().transposed() @ face.normal).normalized()
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

                    surfaceIndex = i + face.material_index
                    useConveyor = colProp.conveyorOption != "None"
                    if not surfaceIndex in surfaceTypeData:
                        surfaceTypeData[surfaceIndex] = SurfaceType(
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
                            normal,
                            distance,
                            surfaceIndex,
                        )
                    )
                i += 1
        surfaceList = [surfaceTypeData[i] for i in range(min(surfaceTypeData.keys()), len(surfaceTypeData))]
        return bounds, vertexList, polyList, surfaceList

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

    def getCrawlspaceDataFromObjects(self, startIndex: int):
        crawlspaceList: list[CrawlspaceData] = []
        crawlspaceObjList: list[Object] = [
            obj
            for obj in self.sceneObj.children_recursive
            if obj.type == "CURVE" and obj.ootSplineProperty.splineType == "Crawlspace"
        ]

        index = startIndex
        for obj in crawlspaceObjList:
            if self.validateCurveData(obj):
                crawlspaceList.append(
                    CrawlspaceData(
                        [
                            [round(value) for value in self.transform @ obj.matrix_world @ point.co]
                            for point in obj.data.splines[0].points
                        ],
                        index,
                    )
                )
                index += 6
        return crawlspaceList

    def getBgCamInfoDataFromObjects(self):
        camObjList = [obj for obj in self.sceneObj.children_recursive if obj.type == "CAMERA"]
        camPosData: dict[int, BgCamFuncData] = {}
        camInfoData: dict[int, BgCamInfo] = {}

        index = 0
        for camObj in camObjList:
            camProp = camObj.ootCameraPositionProperty

            if camProp.camSType == "Custom":
                setting = camProp.camSTypeCustom
            else:
                setting = decomp_compat_map_CameraSType.get(camProp.camSType, camProp.camSType)

            if camProp.hasPositionData:
                count = 3
                if camProp.index in camPosData:
                    raise PluginError(f"ERROR: Repeated camera position index: {camProp.index} for {camObj.name}")
                camPosData[camProp.index] = self.getBgCamFuncDataFromObjects(camObj)
            else:
                count = 0

            if camProp.index in camInfoData:
                raise PluginError(f"ERROR: Repeated camera entry: {camProp.index} for {camObj.name}")
            camInfoData[camProp.index] = BgCamInfo(
                setting,
                count,
                index,
                camPosData[camProp.index] if camProp.hasPositionData else None,
            )

            index += count
        return (
            [camInfoData[i] for i in range(min(camInfoData.keys()), len(camInfoData))] if len(camInfoData) > 0 else []
        )

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

    def getCount(self, bgCamInfoList: list[BgCamInfo]):
        count = 0
        for elem in bgCamInfoList:
            if elem.count != 0:  # 0 means no pos data
                count += elem.count
        return count
