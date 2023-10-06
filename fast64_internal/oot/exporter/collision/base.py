import math

from dataclasses import dataclass
from mathutils import Matrix, Vector
from bpy.types import Mesh, Object
from bpy.ops import object
from ....utility import PluginError
from ...oot_utility import convertIntTo2sComplement
from ..base import Base
from .classes import CollisionPoly, SurfaceType, Vertex


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
        # Ideally everything would be separated but this is complicated since it's all tied together

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

                    if not surfaceType in colPolyFromSurfaceType:
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
