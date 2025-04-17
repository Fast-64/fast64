import math

from dataclasses import dataclass
from mathutils import Matrix, Vector
from bpy.types import Mesh, Object
from bpy.ops import object
from typing import Optional
from ....utility import PluginError, CData, indent
from ...oot_utility import convertIntTo2sComplement
from ..utility import Utility
from .polygons import CollisionPoly, CollisionPolygons
from .surface import SurfaceType, SurfaceTypes
from .camera import BgCamInformations
from .waterbox import WaterBoxes
from .vertex import CollisionVertex, CollisionVertices


@dataclass
class CollisionUtility:
    """This class hosts different functions used to convert mesh data"""

    @staticmethod
    def updateBounds(position: tuple[int, int, int], colBounds: list[tuple[int, int, int]]):
        """This is used to update the scene's boundaries"""

        if len(colBounds) == 0:
            colBounds.append([position[0], position[1], position[2]])
            colBounds.append([position[0], position[1], position[2]])
            return

        minBounds = colBounds[0]
        maxBounds = colBounds[1]
        for i in range(3):
            if position[i] < minBounds[i]:
                minBounds[i] = position[i]
            if position[i] > maxBounds[i]:
                maxBounds[i] = position[i]

    @staticmethod
    def getVertexIndex(vertexPos: tuple[int, int, int], vertexList: list[CollisionVertex]):
        """Returns the index of a CollisionVertex based on position data, returns None if no match found"""

        for i in range(len(vertexList)):
            if vertexList[i].pos == vertexPos:
                return i
        return None

    @staticmethod
    def getMeshObjects(
        dataHolder: Object, curTransform: Matrix, transformFromMeshObj: dict[Object, Matrix], includeChildren: bool
    ):
        """Returns and updates a dictionnary containing mesh objects associated with their correct transforms"""

        if includeChildren:
            for obj in dataHolder.children:
                newTransform = curTransform @ obj.matrix_local

                if obj.type == "MESH" and not obj.ignore_collision:
                    transformFromMeshObj[obj] = newTransform

                if len(obj.children) > 0:
                    CollisionUtility.getMeshObjects(obj, newTransform, transformFromMeshObj, includeChildren)

        return transformFromMeshObj

    @staticmethod
    def getCollisionData(dataHolder: Optional[Object], transform: Matrix, useMacros: bool, includeChildren: bool):
        """Returns collision data, surface types and vertex positions from mesh objects"""

        object.select_all(action="DESELECT")
        dataHolder.select_set(True)

        colPolyFromSurfaceType: dict[SurfaceType, list[CollisionPoly]] = {}
        surfaceList: list[SurfaceType] = []
        polyList: list[CollisionPoly] = []
        vertexList: list[CollisionVertex] = []
        colBounds: list[tuple[int, int, int]] = []

        transformFromMeshObj: dict[Object, Matrix] = {}
        if dataHolder.type == "MESH" and not dataHolder.ignore_collision:
            transformFromMeshObj[dataHolder] = transform
        transformFromMeshObj = CollisionUtility.getMeshObjects(
            dataHolder, transform, transformFromMeshObj, includeChildren
        )
        for meshObj, transform in transformFromMeshObj.items():
            # Note: ``isinstance``only used to get the proper type hints
            if not meshObj.ignore_collision and isinstance(meshObj.data, Mesh):
                if len(meshObj.data.materials) == 0:
                    raise PluginError(f"'{meshObj.name}' must have a material associated with it.")

                meshObj.data.calc_loop_triangles()
                for face in meshObj.data.loop_triangles:
                    colProp = meshObj.material_slots[face.material_index].material.ootCollisionProperty

                    # get bounds and vertices data
                    planePoint = transform @ meshObj.data.vertices[face.vertices[0]].co
                    (x1, y1, z1) = Utility.roundPosition(planePoint)
                    (x2, y2, z2) = Utility.roundPosition(transform @ meshObj.data.vertices[face.vertices[1]].co)
                    (x3, y3, z3) = Utility.roundPosition(transform @ meshObj.data.vertices[face.vertices[2]].co)
                    CollisionUtility.updateBounds((x1, y1, z1), colBounds)
                    CollisionUtility.updateBounds((x2, y2, z2), colBounds)
                    CollisionUtility.updateBounds((x3, y3, z3), colBounds)

                    normal = (transform.inverted().transposed() @ face.normal).normalized()
                    distance = round(
                        -1 * (normal[0] * planePoint[0] + normal[1] * planePoint[1] + normal[2] * planePoint[2])
                    )
                    distance = convertIntTo2sComplement(distance, 2, True)

                    nx = (y2 - y1) * (z3 - z2) - (z2 - z1) * (y3 - y2)
                    ny = (z2 - z1) * (x3 - x2) - (x2 - x1) * (z3 - z2)
                    nz = (x2 - x1) * (y3 - y2) - (y2 - y1) * (x3 - x2)
                    magSqr = nx * nx + ny * ny + nz * nz
                    if magSqr <= 0:
                        print("INFO: Ignore denormalized triangle.")
                        continue

                    indices: list[int] = []
                    for pos in [(x1, y1, z1), (x2, y2, z2), (x3, y3, z3)]:
                        vertexIndex = CollisionUtility.getVertexIndex(pos, vertexList)
                        if vertexIndex is None:
                            vertexList.append(CollisionVertex(pos))
                            indices.append(len(vertexList) - 1)
                        else:
                            indices.append(vertexIndex)
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

                    # get surface type and collision poly data
                    useConveyor = colProp.conveyorOption != "None"
                    conveyorSpeed = int(Utility.getPropValue(colProp, "conveyorSpeed"), base=16) if useConveyor else 0
                    shouldKeepMomentum = colProp.conveyorKeepMomentum if useConveyor else False
                    surfaceType = SurfaceType(
                        colProp.cameraID,
                        colProp.exitID,
                        Utility.getPropValue(colProp, "floorProperty"),
                        0,  # unused?
                        Utility.getPropValue(colProp, "wallSetting"),
                        Utility.getPropValue(colProp, "floorSetting"),
                        colProp.decreaseHeight,
                        colProp.eponaBlock,
                        Utility.getPropValue(colProp, "sound"),
                        Utility.getPropValue(colProp, "terrain"),
                        colProp.lightingSetting,
                        int(colProp.echo, base=16),
                        colProp.hookshotable,
                        conveyorSpeed + (4 if shouldKeepMomentum else 0),
                        int(colProp.conveyorRotation / (2 * math.pi) * 0x3F) if useConveyor else 0,
                        colProp.isWallDamage,
                        useMacros,
                    )

                    if surfaceType not in colPolyFromSurfaceType:
                        colPolyFromSurfaceType[surfaceType] = []

                    colPolyFromSurfaceType[surfaceType].append(
                        CollisionPoly(
                            indices,
                            colProp.ignoreCameraCollision,
                            colProp.ignoreActorCollision,
                            colProp.ignoreProjectileCollision,
                            colProp.conveyorOption == "Land",
                            normal,
                            distance,
                            useMacros,
                        )
                    )

        count = 0
        for surface, colPolyList in colPolyFromSurfaceType.items():
            for colPoly in colPolyList:
                colPoly.type = count
                polyList.append(colPoly)
            surfaceList.append(surface)
            count += 1

        return colBounds, vertexList, polyList, surfaceList


@dataclass
class CollisionHeader:
    """This class defines the collision header used by the scene"""

    name: str
    minBounds: tuple[int, int, int]
    maxBounds: tuple[int, int, int]
    vertices: CollisionVertices
    collisionPoly: CollisionPolygons
    surfaceType: SurfaceTypes
    bgCamInfo: BgCamInformations
    waterbox: WaterBoxes

    @staticmethod
    def new(
        name: str,
        sceneName: str,
        dataHolder: Object,
        transform: Matrix,
        useMacros: bool,
        includeChildren: bool,
    ):
        # Ideally everything would be separated but this is complicated since it's all tied together
        colBounds, vertexList, polyList, surfaceTypeList = CollisionUtility.getCollisionData(
            dataHolder, transform, useMacros, includeChildren
        )

        return CollisionHeader(
            name,
            colBounds[0],
            colBounds[1],
            CollisionVertices(f"{sceneName}_vertices", vertexList),
            CollisionPolygons(f"{sceneName}_polygons", polyList),
            SurfaceTypes(f"{sceneName}_polygonTypes", surfaceTypeList),
            BgCamInformations.new(f"{sceneName}_bgCamInfo", f"{sceneName}_camPosData", dataHolder, transform),
            WaterBoxes.new(f"{sceneName}_waterBoxes", dataHolder, transform, useMacros),
        )

    def getCmd(self):
        """Returns the collision header scene command"""

        return indent + f"SCENE_CMD_COL_HEADER(&{self.name}),\n"

    def getC(self):
        """Returns the collision header for the selected scene"""

        headerData = CData()
        colData = CData()
        varName = f"CollisionHeader {self.name}"

        wBoxPtrLine = colPolyPtrLine = vtxPtrLine = "0, NULL"
        camPtrLine = surfacePtrLine = "NULL"

        # Add waterbox data if necessary
        if len(self.waterbox.waterboxList) > 0:
            colData.append(self.waterbox.getC())
            wBoxPtrLine = f"ARRAY_COUNT({self.waterbox.name}), {self.waterbox.name}"

        # Add camera data if necessary
        if len(self.bgCamInfo.bgCamInfoList) > 0 or len(self.bgCamInfo.crawlspacePosList) > 0:
            infoData = self.bgCamInfo.getInfoArrayC()
            if "&" in infoData.source:
                colData.append(self.bgCamInfo.getDataArrayC())
            colData.append(infoData)
            camPtrLine = f"{self.bgCamInfo.name}"

        # Add surface types
        if len(self.surfaceType.surfaceTypeList) > 0:
            colData.append(self.surfaceType.getC())
            surfacePtrLine = f"{self.surfaceType.name}"

        # Add vertex data
        if len(self.vertices.vertexList) > 0:
            colData.append(self.vertices.getC())
            vtxPtrLine = f"ARRAY_COUNT({self.vertices.name}), {self.vertices.name}"

        # Add collision poly data
        if len(self.collisionPoly.polyList) > 0:
            colData.append(self.collisionPoly.getC())
            colPolyPtrLine = f"ARRAY_COUNT({self.collisionPoly.name}), {self.collisionPoly.name}"

        # build the C data of the collision header

        # .h
        headerData.header = f"extern {varName};\n"

        # .c
        headerData.source += (
            (varName + " = {\n")
            + ",\n".join(
                indent + val
                for val in [
                    ("{ " + ", ".join(f"{val}" for val in self.minBounds) + " }"),
                    ("{ " + ", ".join(f"{val}" for val in self.maxBounds) + " }"),
                    vtxPtrLine,
                    colPolyPtrLine,
                    surfacePtrLine,
                    camPtrLine,
                    wBoxPtrLine,
                ]
            )
            + "\n};\n\n"
        )

        headerData.append(colData)
        return headerData
