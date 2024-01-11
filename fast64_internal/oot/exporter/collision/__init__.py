import math

from dataclasses import dataclass
from mathutils import Matrix, Vector
from bpy.types import Mesh, Object
from bpy.ops import object
from ....utility import PluginError, CData, indent
from ...oot_utility import convertIntTo2sComplement
from ..base import Base
from .polygons import CollisionPoly, CollisionPolygons
from .surface import SurfaceType, SurfaceTypes
from .camera import BgCamInformations
from .waterbox import WaterBoxes
from .vertex import Vertex, Vertices


@dataclass
class CollisionBase(Base):
    """This class hosts different functions used to convert mesh data"""

    sceneObj: Object
    transform: Matrix
    useMacros: bool

    def updateBounds(self, position: tuple[int, int, int], colBounds: list[tuple[int, int, int]]):
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

    def getVertexIndex(self, vertexPos: tuple[int, int, int], vertexList: list[Vertex]):
        """Returns the index of a Vertex based on position data, returns None if no match found"""

        for i in range(len(vertexList)):
            if vertexList[i].pos == vertexPos:
                return i
        return None

    def getMeshObjects(self, parentObj: Object, curTransform: Matrix, transformFromMeshObj: dict[Object, Matrix]):
        """Returns and updates a dictionnary containing mesh objects associated with their correct transforms"""

        objList: list[Object] = parentObj.children
        for obj in objList:
            newTransform = curTransform @ obj.matrix_local

            if obj.type == "MESH" and not obj.ignore_collision:
                transformFromMeshObj[obj] = newTransform

            if len(obj.children) > 0:
                self.getMeshObjects(obj, newTransform, transformFromMeshObj)

        return transformFromMeshObj

    def getCollisionData(self):
        """Returns collision data, surface types and vertex positions from mesh objects"""

        object.select_all(action="DESELECT")
        self.sceneObj.select_set(True)

        colPolyFromSurfaceType: dict[SurfaceType, list[CollisionPoly]] = {}
        surfaceList: list[SurfaceType] = []
        polyList: list[CollisionPoly] = []
        vertexList: list[Vertex] = []
        colBounds: list[tuple[int, int, int]] = []

        transformFromMeshObj: dict[Object, Matrix] = {}
        transformFromMeshObj = self.getMeshObjects(self.sceneObj, self.transform, transformFromMeshObj)
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
                    (x1, y1, z1) = self.roundPosition(planePoint)
                    (x2, y2, z2) = self.roundPosition(transform @ meshObj.data.vertices[face.vertices[1]].co)
                    (x3, y3, z3) = self.roundPosition(transform @ meshObj.data.vertices[face.vertices[2]].co)
                    self.updateBounds((x1, y1, z1), colBounds)
                    self.updateBounds((x2, y2, z2), colBounds)
                    self.updateBounds((x3, y3, z3), colBounds)

                    normal = (transform.inverted().transposed() @ face.normal).normalized()
                    distance = round(
                        -1 * (normal[0] * planePoint[0] + normal[1] * planePoint[1] + normal[2] * planePoint[2])
                    )
                    distance = convertIntTo2sComplement(distance, 2, True)

                    # TODO: can this be improved?
                    nx = (y2 - y1) * (z3 - z2) - (z2 - z1) * (y3 - y2)
                    ny = (z2 - z1) * (x3 - x2) - (x2 - x1) * (z3 - z2)
                    nz = (x2 - x1) * (y3 - y2) - (y2 - y1) * (x3 - x2)
                    magSqr = nx * nx + ny * ny + nz * nz
                    if magSqr <= 0:
                        print("INFO: Ignore denormalized triangle.")
                        continue

                    indices: list[int] = []
                    for pos in [(x1, y1, z1), (x2, y2, z2), (x3, y3, z3)]:
                        vertexIndex = self.getVertexIndex(pos, vertexList)
                        if vertexIndex is None:
                            vertexList.append(Vertex(pos))
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
                    surfaceType = SurfaceType(
                        colProp.cameraID,
                        colProp.exitID,
                        int(self.getPropValue(colProp, "floorProperty"), base=16),
                        0,  # unused?
                        int(self.getPropValue(colProp, "wallSetting"), base=16),
                        int(self.getPropValue(colProp, "floorSetting"), base=16),
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
                        self.useMacros,
                    )

                    if surfaceType not in colPolyFromSurfaceType.keys():
                        colPolyFromSurfaceType[surfaceType] = []

                    colPolyFromSurfaceType[surfaceType].append(
                        CollisionPoly(
                            indices,
                            colProp.ignoreCameraCollision,
                            colProp.ignoreActorCollision,
                            colProp.ignoreProjectileCollision,
                            useConveyor,
                            normal,
                            distance,
                            self.useMacros,
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
class CollisionHeader(CollisionBase):
    """This class defines the collision header used by the scene"""

    name: str
    sceneName: str

    minBounds: tuple[int, int, int] = None
    maxBounds: tuple[int, int, int] = None
    vertices: Vertices = None
    collisionPoly: CollisionPolygons = None
    surfaceType: SurfaceTypes = None
    bgCamInfo: BgCamInformations = None
    waterbox: WaterBoxes = None

    def __post_init__(self):
        # Ideally everything would be separated but this is complicated since it's all tied together
        colBounds, vertexList, polyList, surfaceTypeList = self.getCollisionData()

        self.minBounds = colBounds[0]
        self.maxBounds = colBounds[1]
        self.vertices = Vertices(f"{self.sceneName}_vertices", vertexList)
        self.collisionPoly = CollisionPolygons(f"{self.sceneName}_polygons", polyList)
        self.surfaceType = SurfaceTypes(f"{self.sceneName}_polygonTypes", surfaceTypeList)
        self.bgCamInfo = BgCamInformations(
            self.sceneObj, self.transform, f"{self.sceneName}_bgCamInfo", f"{self.sceneName}_camPosData"
        )
        self.waterbox = WaterBoxes(self.sceneObj, self.transform, f"{self.sceneName}_waterBoxes", self.useMacros)

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
