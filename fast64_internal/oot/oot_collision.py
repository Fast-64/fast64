import bpy, os, math, mathutils
from bpy.utils import register_class, unregister_class
from ..panels import OOT_Panel
from .oot_constants import ootEnumSceneID

from ..utility import (
    PluginError,
    CData,
    prop_split,
    unhideAllAndGetHiddenList,
    hideObjsInList,
    writeCData,
    raisePluginError,
)

from .oot_collision_classes import (
    OOTCollisionVertex,
    OOTCollisionPolygon,
    OOTCollision,
    OOTCameraData,
    OOTCameraPosData,
    OOTCrawlspaceData,
    getPolygonType,
    ootEnumFloorSetting,
    ootEnumWallSetting,
    ootEnumFloorProperty,
    ootEnumConveyer,
    ootEnumConveyorSpeed,
    ootEnumCollisionTerrain,
    ootEnumCollisionSound,
    ootEnumCameraSType,
)

from .oot_utility import (
    OOTObjectCategorizer,
    ootGetObjectPath,
    convertIntTo2sComplement,
    addIncludeFiles,
    drawCollectionOps,
    drawEnumWithCustom,
    ootDuplicateHierarchy,
    ootCleanupScene,
    ootGetPath,
    getOOTScale,
)


class OOTCameraPositionProperty(bpy.types.PropertyGroup):
    index: bpy.props.IntProperty(min=0)
    bgImageOverrideIndex: bpy.props.IntProperty(default=-1, min=-1)
    camSType: bpy.props.EnumProperty(items=ootEnumCameraSType, default="CAM_SET_NONE")
    camSTypeCustom: bpy.props.StringProperty(default="CAM_SET_NONE")
    hasPositionData: bpy.props.BoolProperty(default=True, name="Has Position Data")


class OOTCameraPositionPropertyRef(bpy.types.PropertyGroup):
    camera: bpy.props.PointerProperty(type=bpy.types.Camera)


class OOTMaterialCollisionProperty(bpy.types.PropertyGroup):
    expandTab: bpy.props.BoolProperty()

    ignoreCameraCollision: bpy.props.BoolProperty()
    ignoreActorCollision: bpy.props.BoolProperty()
    ignoreProjectileCollision: bpy.props.BoolProperty()

    eponaBlock: bpy.props.BoolProperty()
    decreaseHeight: bpy.props.BoolProperty()
    floorSettingCustom: bpy.props.StringProperty(default="0x00")
    floorSetting: bpy.props.EnumProperty(items=ootEnumFloorSetting, default="0x00")
    wallSettingCustom: bpy.props.StringProperty(default="0x00")
    wallSetting: bpy.props.EnumProperty(items=ootEnumWallSetting, default="0x00")
    floorPropertyCustom: bpy.props.StringProperty(default="0x00")
    floorProperty: bpy.props.EnumProperty(items=ootEnumFloorProperty, default="0x00")
    exitID: bpy.props.IntProperty(default=0, min=0)
    cameraID: bpy.props.IntProperty(default=0, min=0)
    isWallDamage: bpy.props.BoolProperty()
    conveyorOption: bpy.props.EnumProperty(items=ootEnumConveyer)
    conveyorRotation: bpy.props.FloatProperty(min=0, max=2 * math.pi, subtype="ANGLE")
    conveyorSpeed: bpy.props.EnumProperty(items=ootEnumConveyorSpeed, default="0x00")
    conveyorSpeedCustom: bpy.props.StringProperty(default="0x00")
    conveyorKeepMomentum: bpy.props.BoolProperty()
    hookshotable: bpy.props.BoolProperty()
    echo: bpy.props.StringProperty(default="0x00")
    lightingSetting: bpy.props.IntProperty(default=0, min=0)
    terrainCustom: bpy.props.StringProperty(default="0x00")
    terrain: bpy.props.EnumProperty(items=ootEnumCollisionTerrain, default="0x00")
    soundCustom: bpy.props.StringProperty(default="0x00")
    sound: bpy.props.EnumProperty(items=ootEnumCollisionSound, default="0x00")


class OOTWaterBoxProperty(bpy.types.PropertyGroup):
    lighting: bpy.props.IntProperty(name="Lighting", min=0)
    camera: bpy.props.IntProperty(name="Camera", min=0)
    flag19: bpy.props.BoolProperty(name="Flag 19", default=False)


def drawWaterBoxProperty(layout, waterBoxProp):
    box = layout.column()
    # box.box().label(text = "Properties")
    prop_split(box, waterBoxProp, "lighting", "Lighting")
    prop_split(box, waterBoxProp, "camera", "Camera")
    box.prop(waterBoxProp, "flag19")
    box.label(text="Defined by top face of box empty.")
    box.label(text="No rotation allowed.")


def drawCameraPosProperty(layout, cameraRefProp, index, headerIndex, objName):
    camBox = layout.box().column()
    prop_split(camBox, cameraRefProp, "camera", "Camera " + str(index))
    drawCollectionOps(camBox, index, "Camera Position", headerIndex, objName)


class OOT_CameraPosPanel(bpy.types.Panel):
    bl_label = "Camera Position Inspector"
    bl_idname = "OBJECT_PT_OOT_Camera_Position_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "OOT" and isinstance(context.object.data, bpy.types.Camera)

    def draw(self, context):
        box = self.layout.box().column()
        obj = context.object

        box.box().label(text="Camera Data")
        drawEnumWithCustom(box, obj.ootCameraPositionProperty, "camSType", "Camera S Type", "")
        prop_split(box, obj.ootCameraPositionProperty, "index", "Camera Index")
        box.prop(obj.ootCameraPositionProperty, "hasPositionData")
        if obj.ootCameraPositionProperty.hasPositionData:
            prop_split(box, obj.data, "angle", "Field Of View")
            prop_split(box, obj.ootCameraPositionProperty, "bgImageOverrideIndex", "BG Index Override")

        # drawParentSceneRoom(box, context.object)


class OOT_CollisionPanel(bpy.types.Panel):
    bl_label = "Collision Inspector"
    bl_idname = "MATERIAL_PT_OOT_Collision_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "OOT" and context.material is not None

    def draw(self, context):
        box = self.layout.box().column()
        collisionProp = context.material.ootCollisionProperty

        box.prop(
            collisionProp,
            "expandTab",
            text="OOT Collision Properties",
            icon="TRIA_DOWN" if collisionProp.expandTab else "TRIA_RIGHT",
        )
        if collisionProp.expandTab:
            prop_split(box, collisionProp, "exitID", "Exit ID")
            prop_split(box, collisionProp, "cameraID", "Camera ID")
            prop_split(box, collisionProp, "echo", "Echo")
            prop_split(box, collisionProp, "lightingSetting", "Lighting")
            drawEnumWithCustom(box, collisionProp, "terrain", "Terrain", "")
            drawEnumWithCustom(box, collisionProp, "sound", "Sound", "")

            box.prop(collisionProp, "eponaBlock", text="Blocks Epona")
            box.prop(collisionProp, "decreaseHeight", text="Decrease Height 1 Unit")
            box.prop(collisionProp, "isWallDamage", text="Is Wall Damage")
            box.prop(collisionProp, "hookshotable", text="Hookshotable")

            drawEnumWithCustom(box, collisionProp, "floorSetting", "Floor Setting", "")
            drawEnumWithCustom(box, collisionProp, "wallSetting", "Wall Setting", "")
            drawEnumWithCustom(box, collisionProp, "floorProperty", "Floor Property", "")

            box.prop(collisionProp, "ignoreCameraCollision", text="Ignore Camera Collision")
            box.prop(collisionProp, "ignoreActorCollision", text="Ignore Actor Collision")
            box.prop(collisionProp, "ignoreProjectileCollision", text="Ignore Projectile Collision")
            prop_split(box, collisionProp, "conveyorOption", "Conveyor Option")
            if collisionProp.conveyorOption != "None":
                prop_split(box, collisionProp, "conveyorRotation", "Conveyor Rotation")
                drawEnumWithCustom(box, collisionProp, "conveyorSpeed", "Conveyor Speed", "")
                if collisionProp.conveyorSpeed != "Custom":
                    box.prop(collisionProp, "conveyorKeepMomentum", text="Keep Momentum")


# water boxes handled by level writer
def exportCollisionCommon(collision, obj, transformMatrix, includeChildren, name):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)

    # dict of collisionType : faces
    collisionDict = {}

    addCollisionTriangles(obj, collisionDict, includeChildren, transformMatrix, collision.bounds)
    for polygonType, faces in collisionDict.items():
        collision.polygonGroups[polygonType] = []
        for (faceVerts, normal, distance) in faces:
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


def exportCollisionToC(originalObj, transformMatrix, includeChildren, name, isCustomExport, folderName, exportPath):
    collision = OOTCollision(name)
    collision.cameraData = OOTCameraData(name)

    if bpy.context.scene.exportHiddenGeometry:
        hiddenObjs = unhideAllAndGetHiddenList(bpy.context.scene)

    # Don't remove ignore_render, as we want to resuse this for collision
    obj, allObjs = ootDuplicateHierarchy(originalObj, None, True, OOTObjectCategorizer())

    if bpy.context.scene.exportHiddenGeometry:
        hideObjsInList(hiddenObjs)

    try:
        exportCollisionCommon(collision, obj, transformMatrix, includeChildren, name)
        ootCleanupScene(originalObj, allObjs)
    except Exception as e:
        ootCleanupScene(originalObj, allObjs)
        raise Exception(str(e))

    collisionC = ootCollisionToC(collision)

    data = CData()
    data.source += '#include "ultra64.h"\n#include "z64.h"\n#include "macros.h"\n'
    if not isCustomExport:
        data.source += '#include "' + folderName + '.h"\n\n'
    else:
        data.source += "\n"

    data.append(collisionC)

    path = ootGetPath(exportPath, isCustomExport, "assets/objects/", folderName, False, False)
    writeCData(data, os.path.join(path, name + ".h"), os.path.join(path, name + ".c"))

    if not isCustomExport:
        addIncludeFiles(folderName, path, name)


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

        camDataName = "CamData " + camData.camDataName() + "[" + str(len(camData.camPosDict)) + "]"

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


class OOT_ExportCollision(bpy.types.Operator):
    # set bl_ properties
    bl_idname = "object.oot_export_collision"
    bl_label = "Export Collision"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        obj = None
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        if len(context.selected_objects) == 0:
            raise PluginError("No object selected.")
        obj = context.active_object
        if type(obj.data) is not bpy.types.Mesh:
            raise PluginError("No mesh object selected.")

        finalTransform = mathutils.Matrix.Scale(getOOTScale(obj.ootActorScale), 4)

        try:
            includeChildren = context.scene.ootColIncludeChildren
            name = context.scene.ootColName
            isCustomExport = context.scene.ootColCustomExport
            folderName = context.scene.ootColFolder
            exportPath = bpy.path.abspath(context.scene.ootColExportPath)

            filepath = ootGetObjectPath(isCustomExport, exportPath, folderName)
            exportCollisionToC(obj, finalTransform, includeChildren, name, isCustomExport, folderName, filepath)

            self.report({"INFO"}, "Success!")
            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


class OOT_ExportCollisionPanel(OOT_Panel):
    bl_idname = "OOT_PT_export_collision"
    bl_label = "OOT Collision Exporter"

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.operator(OOT_ExportCollision.bl_idname)

        prop_split(col, context.scene, "ootColName", "Name")
        if context.scene.ootColCustomExport:
            prop_split(col, context.scene, "ootColExportPath", "Custom Folder")
        else:
            prop_split(col, context.scene, "ootColFolder", "Object")
        col.prop(context.scene, "ootColCustomExport")
        col.prop(context.scene, "ootColIncludeChildren")


oot_col_classes = (
    OOT_ExportCollision,
    OOTWaterBoxProperty,
    OOTCameraPositionPropertyRef,
    OOTCameraPositionProperty,
    OOTMaterialCollisionProperty,
)

oot_col_panel_classes = (
    OOT_CollisionPanel,
    OOT_CameraPosPanel,
    OOT_ExportCollisionPanel,
)


def oot_col_panel_register():
    for cls in oot_col_panel_classes:
        register_class(cls)


def oot_col_panel_unregister():
    for cls in oot_col_panel_classes:
        unregister_class(cls)


def oot_col_register():
    for cls in oot_col_classes:
        register_class(cls)

    # Collision
    bpy.types.Scene.ootColExportPath = bpy.props.StringProperty(name="Directory", subtype="FILE_PATH")
    bpy.types.Scene.ootColExportLevel = bpy.props.EnumProperty(
        items=ootEnumSceneID, name="Level Used By Collision", default="SCENE_YDAN"
    )
    bpy.types.Scene.ootColIncludeChildren = bpy.props.BoolProperty(name="Include child objects", default=True)
    bpy.types.Scene.ootColName = bpy.props.StringProperty(name="Name", default="collision")
    bpy.types.Scene.ootColLevelName = bpy.props.StringProperty(name="Name", default="SCENE_YDAN")
    bpy.types.Scene.ootColCustomExport = bpy.props.BoolProperty(name="Custom Export Path")
    bpy.types.Scene.ootColFolder = bpy.props.StringProperty(name="Object Name", default="gameplay_keep")

    bpy.types.Object.ootCameraPositionProperty = bpy.props.PointerProperty(type=OOTCameraPositionProperty)
    bpy.types.Material.ootCollisionProperty = bpy.props.PointerProperty(type=OOTMaterialCollisionProperty)


def oot_col_unregister():
    # Collision
    del bpy.types.Scene.ootColExportPath
    del bpy.types.Scene.ootColExportLevel
    del bpy.types.Scene.ootColName
    del bpy.types.Scene.ootColLevelName
    del bpy.types.Scene.ootColIncludeChildren
    del bpy.types.Scene.ootColCustomExport
    del bpy.types.Scene.ootColFolder

    for cls in reversed(oot_col_classes):
        unregister_class(cls)
