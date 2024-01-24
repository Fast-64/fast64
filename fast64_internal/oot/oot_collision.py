import bpy, mathutils

from ..utility import (
    PluginError,
    CData,
    prop_split,
)

from .oot_collision_classes import (
    OOTCollisionVertex,
    OOTCollisionPolygon,
    OOTCameraData,
    OOTCameraPosData,
    OOTCrawlspaceData,
    getPolygonType,
)

from .oot_utility import (
    convertIntTo2sComplement,
    drawCollectionOps,
)


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


def addCollisionTriangles(obj, collisionDict, includeChildren, transformMatrix, bounds):
    if obj.type == "MESH" and not obj.ignore_collision:
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


def roundPosition(position):
    # return [int.from_bytes(int(round(value)).to_bytes(2, 'big', signed = True), 'big') for value in position]
    return (int(round(position[0])), int(round(position[1])), int(round(position[2])))


def collisionVertIndex(vert, vertArray):
    for i in range(len(vertArray)):
        colVert = vertArray[i]
        if colVert.position == vert:
            return i
    return None


def ootCollisionVertexToC(vertex):
    return "{ " + str(vertex.position[0]) + ", " + str(vertex.position[1]) + ", " + str(vertex.position[2]) + " },\n"


def ootCollisionPolygonToC(polygon, ignoreCamera, ignoreActor, ignoreProjectile, enableConveyor, polygonTypeIndex):
    return (
        "{ "
        + ", ".join(
            (
                format(polygonTypeIndex, "#06x"),
                format(polygon.convertShort02(ignoreCamera, ignoreActor, ignoreProjectile), "#06x"),
                format(polygon.convertShort04(enableConveyor), "#06x"),
                format(polygon.convertShort06(), "#06x"),
                "COLPOLY_SNORMAL({})".format(polygon.normal[0]),
                "COLPOLY_SNORMAL({})".format(polygon.normal[1]),
                "COLPOLY_SNORMAL({})".format(polygon.normal[2]),
                format(polygon.distance, "#06x"),
            )
        )
        + " },\n"
    )


def ootPolygonTypeToC(polygonType):
    return (
        "{ " + format(polygonType.convertHigh(), "#010x") + ", " + format(polygonType.convertLow(), "#010x") + " },\n"
    )


def ootWaterBoxToC(waterBox):
    return (
        "{ "
        + str(waterBox.low[0])
        + ", "
        + str(waterBox.height)
        + ", "
        + str(waterBox.low[1])
        + ", "
        + str(waterBox.high[0] - waterBox.low[0])
        + ", "
        + str(waterBox.high[1] - waterBox.low[1])
        + ", "
        + format(waterBox.propertyData(), "#010x")
        + " },\n"
    )


def ootCameraDataToC(camData):
    posC = CData()
    camC = CData()
    if len(camData.camPosDict) > 0:
        camDataName = "BgCamInfo " + camData.camDataName() + "[" + str(len(camData.camPosDict)) + "]"

        camC.source = camDataName + " = {\n"
        camC.header = "extern " + camDataName + ";\n"

        camPosIndex = 0

        for i in range(len(camData.camPosDict)):
            camItem = camData.camPosDict[i]
            if isinstance(camItem, OOTCameraPosData):
                camC.source += "\t" + ootCameraEntryToC(camItem, camData, camPosIndex) + ",\n"
                if camItem.hasPositionData:
                    posC.source += ootCameraPosToC(camItem)
                    camPosIndex += 3
            elif isinstance(camItem, OOTCrawlspaceData):
                camC.source += "\t" + ootCrawlspaceEntryToC(camItem, camData, camPosIndex) + ",\n"
                posC.source += ootCrawlspaceToC(camItem)
                camPosIndex += len(camItem.points) * 3
            else:
                raise PluginError(f"Invalid object type in camera position dict: {type(camItem)}")
        posC.source += "};\n\n"
        camC.source += "};\n\n"

        if camPosIndex > 0:
            posDataName = "Vec3s " + camData.camPositionsName() + "[" + str(camPosIndex) + "]"
            posC.header = "extern " + posDataName + ";\n"
            posC.source = posDataName + " = {\n" + posC.source
        else:
            posC = CData()

    return posC, camC


def ootCameraPosToC(camPos):
    return (
        "\t{ "
        + str(camPos.position[0])
        + ", "
        + str(camPos.position[1])
        + ", "
        + str(camPos.position[2])
        + " },\n\t{ "
        + str(camPos.rotation[0])
        + ", "
        + str(camPos.rotation[1])
        + ", "
        + str(camPos.rotation[2])
        + " },\n\t{ "
        + str(camPos.fov)
        + ", "
        + str(camPos.bgImageOverrideIndex)
        + ", "
        + str(camPos.unknown)
        + " },\n"
    )


def ootCameraEntryToC(camPos, camData, camPosIndex):
    return " ".join(
        (
            "{",
            camPos.camSType + ",",
            ("3" if camPos.hasPositionData else "0") + ",",
            ("&" + camData.camPositionsName() + "[" + str(camPosIndex) + "]" if camPos.hasPositionData else "NULL"),
            "}",
        )
    )


def ootCrawlspaceToC(camItem: OOTCrawlspaceData):
    data = ""
    for point in camItem.points:
        data += f"\t{{{point[0]}, {point[1]}, {point[2]}}},\n" * 3

    return data


def ootCrawlspaceEntryToC(camItem: OOTCrawlspaceData, camData: OOTCameraData, camPosIndex: int):
    return " ".join(
        (
            "{",
            camItem.camSType + ",",
            str((len(camItem.points) * 3)) + ",",
            (("&" + camData.camPositionsName() + "[" + str(camPosIndex) + "]") if len(camItem.points) > 0 else "NULL"),
            "}",
        )
    )


def ootCollisionToC(collision):
    data = CData()
    posC, camC = ootCameraDataToC(collision.cameraData)

    data.append(posC)
    data.append(camC)

    if len(collision.polygonGroups) > 0:
        data.header += "extern SurfaceType " + collision.polygonTypesName() + "[];\n"
        data.header += "extern CollisionPoly " + collision.polygonsName() + "[];\n"
        polygonTypeC = "SurfaceType " + collision.polygonTypesName() + "[] = {\n"
        polygonC = "CollisionPoly " + collision.polygonsName() + "[] = {\n"
        polygonIndex = 0
        for polygonType, polygons in collision.polygonGroups.items():
            polygonTypeC += "\t" + ootPolygonTypeToC(polygonType)
            for polygon in polygons:
                polygonC += "\t" + ootCollisionPolygonToC(
                    polygon,
                    polygonType.ignoreCameraCollision,
                    polygonType.ignoreActorCollision,
                    polygonType.ignoreProjectileCollision,
                    polygonType.enableConveyor,
                    polygonIndex,
                )
            polygonIndex += 1
        polygonTypeC += "};\n\n"
        polygonC += "};\n\n"

        data.source += polygonTypeC + polygonC
        polygonTypesName = collision.polygonTypesName()
        polygonsName = collision.polygonsName()
    else:
        polygonTypesName = "0"
        polygonsName = "0"

    if len(collision.vertices) > 0:
        data.header += "extern Vec3s " + collision.verticesName() + "[" + str(len(collision.vertices)) + "];\n"
        data.source += "Vec3s " + collision.verticesName() + "[" + str(len(collision.vertices)) + "] = {\n"
        for vertex in collision.vertices:
            data.source += "\t" + ootCollisionVertexToC(vertex)
        data.source += "};\n\n"
        collisionVerticesName = collision.verticesName()
    else:
        collisionVerticesName = "0"

    if len(collision.waterBoxes) > 0:
        data.header += "extern WaterBox " + collision.waterBoxesName() + "[];\n"
        data.source += "WaterBox " + collision.waterBoxesName() + "[] = {\n"
        for waterBox in collision.waterBoxes:
            data.source += "\t" + ootWaterBoxToC(waterBox)
        data.source += "};\n\n"
        waterBoxesName = collision.waterBoxesName()
    else:
        waterBoxesName = "0"

    if len(collision.cameraData.camPosDict) > 0:
        camDataName = collision.camDataName()
    else:
        camDataName = "0"

    data.header += "extern CollisionHeader " + collision.headerName() + ";\n"
    data.source += "CollisionHeader " + collision.headerName() + " = {\n"

    if len(collision.bounds) == 2:
        for bound in range(2):  # min, max bound
            for field in range(3):  # x, y, z
                data.source += "\t" + str(collision.bounds[bound][field]) + ",\n"
    else:
        data.source += "0, 0, 0, 0, 0, 0, "

    data.source += (
        "\t"
        + str(len(collision.vertices))
        + ",\n"
        + "\t"
        + collisionVerticesName
        + ",\n"
        + "\t"
        + str(collision.polygonCount())
        + ",\n"
        + "\t"
        + polygonsName
        + ",\n"
        + "\t"
        + polygonTypesName
        + ",\n"
        + "\t"
        + camDataName
        + ",\n"
        + "\t"
        + str(len(collision.waterBoxes))
        + ",\n"
        + "\t"
        + waterBoxesName
        + "\n"
        + "};\n\n"
    )

    return data
