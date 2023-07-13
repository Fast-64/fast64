import bpy
import mathutils

from ....utility import PluginError
from ...oot_utility import convertIntTo2sComplement
from .classes import OOTCollisionVertex, OOTCollisionPolygon, getPolygonType


def updateBounds(position, bounds):
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


def collisionVertIndex(vert, vertArray):
    for i in range(len(vertArray)):
        colVert = vertArray[i]
        if colVert.position == vert:
            return i
    return None


def roundPosition(position):
    # return [int.from_bytes(int(round(value)).to_bytes(2, 'big', signed = True), 'big') for value in position]
    return (int(round(position[0])), int(round(position[1])), int(round(position[2])))


def addCollisionTriangles(obj, collisionDict, includeChildren, transformMatrix, bounds):
    if isinstance(obj.data, bpy.types.Mesh) and not obj.ignore_collision:
        if len(obj.data.materials) == 0:
            raise PluginError(obj.name + " must have a material associated with it.")
        obj.data.calc_loop_triangles()
        for face in obj.data.loop_triangles:
            material = obj.material_slots[face.material_index].material
            polygonType = getPolygonType(material.ootCollisionProperty)

            planePoint = transformMatrix @ obj.data.vertices[face.vertices[0]].co
            (x1, y1, z1) = roundPosition(planePoint)
            (x2, y2, z2) = roundPosition(transformMatrix @ obj.data.vertices[face.vertices[1]].co)
            (x3, y3, z3) = roundPosition(transformMatrix @ obj.data.vertices[face.vertices[2]].co)

            updateBounds((x1, y1, z1), bounds)
            updateBounds((x2, y2, z2), bounds)
            updateBounds((x3, y3, z3), bounds)

            faceNormal = (transformMatrix.inverted().transposed() @ face.normal).normalized()
            distance = int(
                round(
                    -1 * (faceNormal[0] * planePoint[0] + faceNormal[1] * planePoint[1] + faceNormal[2] * planePoint[2])
                )
            )
            distance = convertIntTo2sComplement(distance, 2, True)

            nx = (y2 - y1) * (z3 - z2) - (z2 - z1) * (y3 - y2)
            ny = (z2 - z1) * (x3 - x2) - (x2 - x1) * (z3 - z2)
            nz = (x2 - x1) * (y3 - y2) - (y2 - y1) * (x3 - x2)
            magSqr = nx * nx + ny * ny + nz * nz

            if magSqr <= 0:
                print("Ignore denormalized triangle.")
                continue

            if polygonType not in collisionDict:
                collisionDict[polygonType] = []

            positions = ((x1, y1, z1), (x2, y2, z2), (x3, y3, z3))

            collisionDict[polygonType].append((positions, faceNormal, distance))

    if includeChildren:
        for child in obj.children:
            addCollisionTriangles(child, collisionDict, includeChildren, transformMatrix @ child.matrix_local, bounds)


# water boxes handled by level writer
def exportCollisionCommon(collision, obj, transformMatrix, includeChildren, name):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)

    # dict of collisionType : faces
    collisionDict = {}

    addCollisionTriangles(obj, collisionDict, includeChildren, transformMatrix, collision.bounds)
    for polygonType, faces in collisionDict.items():
        collision.polygonGroups[polygonType] = []
        for faceVerts, normal, distance in faces:
            assert len(faceVerts) == 3
            indices = []
            for roundedPosition in faceVerts:
                index = collisionVertIndex(roundedPosition, collision.vertices)
                if index is None:
                    collision.vertices.append(OOTCollisionVertex(roundedPosition))
                    indices.append(len(collision.vertices) - 1)
                else:
                    indices.append(index)
            assert len(indices) == 3

            # We need to ensure two things about the order in which the vertex indices are:
            #
            # 1) The vertex with the minimum y coordinate should be first.
            # This prevents a bug due to an optimization in OoT's CollisionPoly_GetMinY.
            # https://github.com/zeldaret/oot/blob/791d9018c09925138b9f830f7ae8142119905c05/src/code/z_bgcheck.c#L161
            #
            # 2) The vertices should wrap around the polygon normal **counter-clockwise**.
            # This is needed for OoT's dynapoly, which is collision that can move.
            # When it moves, the vertex coordinates and normals are recomputed.
            # The normal is computed based on the vertex coordinates, which makes the order of vertices matter.
            # https://github.com/zeldaret/oot/blob/791d9018c09925138b9f830f7ae8142119905c05/src/code/z_bgcheck.c#L2888

            # Address 1): sort by ascending y coordinate
            indices.sort(key=lambda index: collision.vertices[index].position[1])

            # Address 2):
            # swap indices[1] and indices[2],
            # if the normal computed from the vertices in the current order is the wrong way.
            v0 = mathutils.Vector(collision.vertices[indices[0]].position)
            v1 = mathutils.Vector(collision.vertices[indices[1]].position)
            v2 = mathutils.Vector(collision.vertices[indices[2]].position)
            if (v1 - v0).cross(v2 - v0).dot(mathutils.Vector(normal)) < 0:
                indices[1], indices[2] = indices[2], indices[1]

            collision.polygonGroups[polygonType].append(OOTCollisionPolygon(indices, normal, distance))
