import math
import re
import bpy
import mathutils
from random import random
from collections import OrderedDict
from ....utility import PluginError, parentObject, hexOrDecInt, yUpToZUp
from ...collision.properties import OOTMaterialCollisionProperty
from ...oot_f3d_writer import getColliderMat
from ...oot_utility import setCustomProperty, ootParseRotation
from .utility import getDataMatch, getBits, checkBit, createCurveFromPoints, stripName
from .classes import SharedSceneData

from ...collision.constants import (
    ootEnumFloorSetting,
    ootEnumWallSetting,
    ootEnumFloorProperty,
    ootEnumCollisionTerrain,
    ootEnumCollisionSound,
    ootEnumCameraSType,
    ootEnumCameraCrawlspaceSType,
)


def parseCrawlSpaceData(
    setting: str, sceneData: str, posDataName: str, index: int, count: int, objName: str, orderIndex: str
):
    camPosData = getDataMatch(sceneData, posDataName, "Vec3s", "camera position list")
    camPosList = [value.replace("{", "").strip() for value in camPosData.split("},") if value.strip() != ""]
    posData = [camPosList[index : index + count][i] for i in range(0, count, 3)]

    points = []
    for posDataItem in posData:
        points.append([hexOrDecInt(value.strip()) for value in posDataItem.split(",")])

    # name is important for alphabetical ordering
    curveObj = createCurveFromPoints(points, objName)
    curveObj.show_name = True
    crawlProp = curveObj.ootSplineProperty
    crawlProp.splineType = "Crawlspace"
    crawlProp.index = orderIndex
    setCustomProperty(crawlProp, "camSType", "CAM_SET_CRAWLSPACE", ootEnumCameraCrawlspaceSType)

    return curveObj


def parseCamDataList(sceneObj: bpy.types.Object, camDataListName: str, sceneData: str):
    camMatchData = getDataMatch(sceneData, camDataListName, ["CamData", "BgCamInfo"], "camera data list")
    camDataList = [value.replace("{", "").strip() for value in camMatchData.split("},") if value.strip() != ""]

    # orderIndex used for naming cameras in alphabetical order
    orderIndex = 0
    for camEntry in camDataList:
        setting, count, posDataName = [value.strip() for value in camEntry.split(",")]
        index = None

        objName = f"{sceneObj.name}_camPos_{format(orderIndex, '03')}"

        if posDataName != "NULL" and posDataName != "0":
            index = hexOrDecInt(posDataName[posDataName.index("[") + 1 : -1])
            posDataName = posDataName[1 : posDataName.index("[")]  # remove '&' and '[n]'

        if setting == "CAM_SET_CRAWLSPACE" or setting == "0x001E":
            obj = parseCrawlSpaceData(setting, sceneData, posDataName, index, hexOrDecInt(count), objName, orderIndex)
        else:
            obj = parseCamPosData(setting, sceneData, posDataName, index, objName, orderIndex)

        parentObject(sceneObj, obj)
        orderIndex += 1


def parseCamPosData(setting: str, sceneData: str, posDataName: str, index: int, objName: str, orderIndex: str):
    camera = bpy.data.cameras.new("Camera")
    camObj = bpy.data.objects.new(objName, camera)
    bpy.context.scene.collection.objects.link(camObj)
    camProp = camObj.ootCameraPositionProperty
    setCustomProperty(camProp, "camSType", setting, ootEnumCameraSType)
    camProp.hasPositionData = posDataName != "NULL" and posDataName != "0"
    camProp.index = orderIndex

    # name is important for alphabetical ordering
    camObj.name = objName

    if index is None:
        camObj.location = [0, 0, 0]
        return camObj

    camPosData = getDataMatch(sceneData, posDataName, "Vec3s", "camera position list")
    camPosList = [value.replace("{", "").strip() for value in camPosData.split("},") if value.strip() != ""]

    posData = camPosList[index : index + 3]
    position = yUpToZUp @ mathutils.Vector(
        [hexOrDecInt(value.strip()) / bpy.context.scene.ootBlenderScale for value in posData[0].split(",")]
    )

    # camera faces opposite direction
    rotation = (
        yUpToZUp.to_quaternion()
        @ mathutils.Euler(
            ootParseRotation([hexOrDecInt(value.strip()) for value in posData[1].split(",")])
        ).to_quaternion()
        @ mathutils.Quaternion((0, 1, 0), math.radians(180.0))
    ).to_euler()

    fov, bgImageOverrideIndex, unknown = [value.strip() for value in posData[2].split(",")]

    camObj.location = position
    camObj.rotation_euler = rotation
    camObj.show_name = True

    camProp = camObj.ootCameraPositionProperty
    camProp.bgImageOverrideIndex = hexOrDecInt(bgImageOverrideIndex)

    fovValue = hexOrDecInt(fov)
    fovValue = int.from_bytes(fovValue.to_bytes(2, "big", signed=fovValue < 0x8000), "big", signed=True)
    if fovValue > 360:
        fovValue *= 0.01  # see CAM_DATA_SCALED() macro
    camObj.data.angle = math.radians(fovValue)

    return camObj


def parseWaterBoxes(
    sceneObj: bpy.types.Object,
    roomObjs: list[bpy.types.Object],
    sceneData: str,
    waterBoxListName: str,
):
    waterBoxListData = getDataMatch(sceneData, waterBoxListName, "WaterBox", "water box list")
    waterBoxList = [value.replace("{", "").strip() for value in waterBoxListData.split("},") if value.strip() != ""]

    # orderIndex used for naming cameras in alphabetical order
    orderIndex = 0
    for waterBoxData in waterBoxList:
        objName = f"{sceneObj.name}_waterBox_{format(orderIndex, '03')}"
        params = [value.strip() for value in waterBoxData.split(",")]
        topCorner = yUpToZUp @ mathutils.Vector(
            [hexOrDecInt(value) / bpy.context.scene.ootBlenderScale for value in params[0:3]]
        )
        dimensions = [hexOrDecInt(value) / bpy.context.scene.ootBlenderScale for value in params[3:5]]
        properties = hexOrDecInt(params[5])

        height = 1000 / bpy.context.scene.ootBlenderScale  # just to add volume

        location = mathutils.Vector([0, 0, 0])
        scale = [dimensions[0] / 2, dimensions[1] / 2, height / 2]
        location.x = topCorner[0] + scale[0]  # x
        location.y = topCorner[1] - scale[1]  # -z
        location.z = topCorner.z - scale[2]  # y

        waterBoxObj = bpy.data.objects.new(objName, None)
        bpy.context.scene.collection.objects.link(waterBoxObj)
        waterBoxObj.location = location
        waterBoxObj.scale = scale
        waterBoxProp = waterBoxObj.ootWaterBoxProperty

        waterBoxObj.show_name = True
        waterBoxObj.ootEmptyType = "Water Box"
        flag19 = checkBit(properties, 19)
        roomIndex = getBits(properties, 13, 6)
        waterBoxProp.lighting = getBits(properties, 8, 5)
        waterBoxProp.camera = getBits(properties, 0, 8)
        waterBoxProp.flag19 = flag19

        # 0x3F = -1 in 6bit value
        parentObject(roomObjs[roomIndex] if roomIndex != 0x3F else sceneObj, waterBoxObj)
        orderIndex += 1


def parseSurfaceParams(
    surface: tuple[int, int], polygonParams: tuple[bool, bool, bool, bool], collision: OOTMaterialCollisionProperty
):
    params = surface
    ignoreCamera, ignoreActor, ignoreProjectile, enableConveyor = polygonParams

    collision.eponaBlock = checkBit(params[0], 31)
    collision.decreaseHeight = checkBit(params[0], 30)
    setCustomProperty(collision, "floorSetting", str(getBits(params[0], 26, 4)), ootEnumFloorSetting)
    setCustomProperty(collision, "wallSetting", str(getBits(params[0], 21, 5)), ootEnumWallSetting)
    setCustomProperty(collision, "floorProperty", str(getBits(params[0], 13, 8)), ootEnumFloorProperty)
    collision.exitID = getBits(params[0], 8, 5)
    collision.cameraID = getBits(params[0], 0, 8)
    collision.isWallDamage = checkBit(params[1], 27)

    collision.conveyorRotation = (getBits(params[1], 21, 6) / 0x3F) * (2 * math.pi)
    collision.conveyorSpeed = "Custom"
    collision.conveyorSpeedCustom = str(getBits(params[1], 18, 3))

    if collision.conveyorRotation == 0 and collision.conveyorSpeedCustom == "0":
        collision.conveyorOption = "None"
    elif enableConveyor:
        collision.conveyorOption = "Land"
    else:
        collision.conveyorOption = "Water"

    collision.hookshotable = checkBit(params[1], 17)
    collision.echo = str(getBits(params[1], 11, 6))
    collision.lightingSetting = getBits(params[1], 6, 5)
    setCustomProperty(collision, "terrain", str(getBits(params[1], 4, 2)), ootEnumCollisionTerrain)
    setCustomProperty(collision, "sound", str(getBits(params[1], 0, 4)), ootEnumCollisionSound)

    collision.ignoreCameraCollision = ignoreCamera
    collision.ignoreActorCollision = ignoreActor
    collision.ignoreProjectileCollision = ignoreProjectile


def parseSurfaces(surfaceList: list[str]):
    surfaces = []
    for surfaceData in surfaceList:
        params = [hexOrDecInt(value.strip()) for value in surfaceData.split(",")]
        surfaces.append(tuple(params))

    return surfaces


def parseVertices(vertexList: list[str]):
    vertices = []
    for vertexData in vertexList:
        vertex = [hexOrDecInt(value.strip()) / bpy.context.scene.ootBlenderScale for value in vertexData.split(",")]
        position = yUpToZUp @ mathutils.Vector(vertex)
        vertices.append(position)

    return vertices


def parsePolygon(polygonData: str):
    shorts = [
        hexOrDecInt(value.strip()) if "COLPOLY_SNORMAL" not in value else value.strip()
        for value in polygonData.split(",")
    ]
    vertIndices = [0, 0, 0]

    # 00
    surfaceIndex = shorts[0]

    # 02
    vertIndices[0] = shorts[1] & 0x1FFF
    ignoreCamera = 1 & (shorts[1] >> 13) == 1
    ignoreActor = 1 & (shorts[1] >> 14) == 1
    ignoreProjectile = 1 & (shorts[1] >> 15) == 1

    # 04
    vertIndices[1] = shorts[2] & 0x1FFF
    enableConveyor = 1 & (shorts[2] >> 13) == 1

    # 06
    vertIndices[2] = shorts[3] & 0x1FFF

    # 08-0C
    normal = []
    for value in shorts[4:7]:
        if isinstance(value, str) and "COLPOLY_SNORMAL" in value:
            normal.append(float(value[value.index("(") + 1 : value.index(")")]))
        else:
            normal.append(int.from_bytes(value.to_bytes(2, "big", signed=value < 0x8000), "big", signed=True) / 0x7FFF)

    # 0E
    distance = shorts[7]

    return (ignoreCamera, ignoreActor, ignoreProjectile, enableConveyor), surfaceIndex, vertIndices, normal


def parseCollisionHeader(
    sceneObj: bpy.types.Object,
    roomObjs: list[bpy.types.Object],
    sceneData: str,
    collisionHeaderName: str,
    sharedSceneData: SharedSceneData,
):
    match = re.search(
        rf"CollisionHeader\s*{re.escape(collisionHeaderName)}\s*=\s*\{{\s*\{{(.*?)\}}\s*,\s*\{{(.*?)\}}\s*,(.*?)\}}\s*;",
        sceneData,
        flags=re.DOTALL,
    )

    if not match:
        match = re.search(
            rf"CollisionHeader\s*{re.escape(collisionHeaderName)}\s*=\s*\{{(.*?)\}}\s*;",
            sceneData,
            flags=re.DOTALL,
        )
        if not match:
            raise PluginError(f"Could not find collision header {collisionHeaderName}.")

        params = [value.strip() for value in match.group(1).split(",")]
        minBounds = [hexOrDecInt(value.strip()) for value in params[0:3]]
        maxBounds = [hexOrDecInt(value.strip()) for value in params[3:6]]
        otherParams = [value.strip() for value in params[6:]]

    else:
        minBounds = [hexOrDecInt(value.strip()) for value in match.group(1).split(",")]
        maxBounds = [hexOrDecInt(value.strip()) for value in match.group(2).split(",")]
        otherParams = [value.strip() for value in match.group(3).split(",")]

    vertexListName = stripName(otherParams[1])
    polygonListName = stripName(otherParams[3])
    surfaceTypeListName = stripName(otherParams[4])
    camDataListName = stripName(otherParams[5])
    waterBoxListName = stripName(otherParams[7])

    if sharedSceneData.includeCollision:
        parseCollision(sceneObj, vertexListName, polygonListName, surfaceTypeListName, sceneData)
    if sharedSceneData.includeCameras and camDataListName != "NULL" and camDataListName != "0":
        parseCamDataList(sceneObj, camDataListName, sceneData)
    if sharedSceneData.includeWaterBoxes and waterBoxListName != "NULL" and waterBoxListName != "0":
        parseWaterBoxes(sceneObj, roomObjs, sceneData, waterBoxListName)


def parseCollision(
    sceneObj: bpy.types.Object, vertexListName: str, polygonListName: str, surfaceTypeListName: str, sceneData: str
):
    vertMatchData = getDataMatch(sceneData, vertexListName, "Vec3s", "vertex list")
    polyMatchData = getDataMatch(sceneData, polygonListName, "CollisionPoly", "polygon list")
    surfMatchData = getDataMatch(sceneData, surfaceTypeListName, "SurfaceType", "surface type list")

    vertexList = [value.replace("{", "").strip() for value in vertMatchData.split("},") if value.strip() != ""]
    polygonList = [value.replace("{", "").strip() for value in polyMatchData.split("},") if value.strip() != ""]
    surfaceList = [value.replace("{", "").strip() for value in surfMatchData.split("},") if value.strip() != ""]

    # Although polygon params are geometry based, we will group them with surface.
    collisionDict = OrderedDict()  # (surface, polygonParams) : list[triangles]

    surfaces = parseSurfaces(surfaceList)
    vertices = parseVertices(vertexList)

    for polygonData in polygonList:
        polygonParams, surfaceIndex, vertIndices, normal = parsePolygon(polygonData)
        key = (surfaces[surfaceIndex], polygonParams)
        if key not in collisionDict:
            collisionDict[key] = []

        collisionDict[key].append((vertIndices, normal))

    collisionName = f"{sceneObj.name}_collision"
    mesh = bpy.data.meshes.new(collisionName)
    obj = bpy.data.objects.new(collisionName, mesh)
    bpy.context.scene.collection.objects.link(obj)

    triData = []
    triMatData = []

    surfaceIndex = 0
    for (surface, polygonParams), triList in collisionDict.items():
        randomColor = mathutils.Color((1, 1, 1))
        randomColor.hsv = (random(), 0.5, 0.5)
        collisionMat = getColliderMat(f"oot_collision_mat_{surfaceIndex}", randomColor[:] + (0.5,))
        collision = collisionMat.ootCollisionProperty
        parseSurfaceParams(surface, polygonParams, collision)

        mesh.materials.append(collisionMat)
        for j in range(len(triList)):
            triData.append(triList[j][0])
            triMatData += [surfaceIndex]
        surfaceIndex += 1

    mesh.from_pydata(vertices=vertices, edges=[], faces=triData)
    for i in range(len(mesh.polygons)):
        mesh.polygons[i].material_index = triMatData[i]

    obj.ignore_render = True

    parentObject(sceneObj, obj)
