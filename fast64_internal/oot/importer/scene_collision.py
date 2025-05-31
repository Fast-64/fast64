import math
import re
import bpy
import mathutils

from random import random
from bpy.types import Material

from ...utility import PluginError, parentObject, hexOrDecInt, get_include_data, yUpToZUp
from ..exporter.collision.surface import SurfaceType
from ..exporter.collision.polygons import CollisionPoly
from ..exporter.collision.waterbox import WaterBox
from ..collision.properties import OOTMaterialCollisionProperty
from ..oot_f3d_writer import getColliderMat
from ..oot_utility import setCustomProperty, ootParseRotation
from .utility import getDataMatch, getBits, checkBit, createCurveFromPoints, stripName
from .classes import SharedSceneData

from ..collision.constants import (
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
    camPosData = getDataMatch(sceneData, posDataName, "Vec3s", "camera position list", strip=True)
    camPosList = [value.replace("{", "").strip() for value in camPosData.split("},") if value.strip() != ""]
    posData = [camPosList[index : index + count][i] for i in range(0, count, 3)]

    points = []
    for posDataItem in posData:
        points.append([hexOrDecInt(value.strip()) for value in posDataItem.split(",") if value.strip() != ""])

    # name is important for alphabetical ordering
    curveObj = createCurveFromPoints(points, objName)
    curveObj.show_name = True
    crawlProp = curveObj.ootSplineProperty
    crawlProp.splineType = "Crawlspace"
    crawlProp.index = orderIndex
    setCustomProperty(crawlProp, "camSType", "CAM_SET_CRAWLSPACE", ootEnumCameraCrawlspaceSType)

    return curveObj


def parseCamDataList(sceneObj: bpy.types.Object, camDataListName: str, sceneData: str):
    camMatchData = getDataMatch(sceneData, camDataListName, ["CamData", "BgCamInfo"], "camera data list", strip=True)
    camDataList = [value.replace("{", "").strip() for value in camMatchData.split("},") if value.strip() != ""]

    # orderIndex used for naming cameras in alphabetical order
    orderIndex = 0
    for camEntry in camDataList:
        setting, count, posDataName = [value.strip() for value in camEntry.split(",") if value.strip() != ""]
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

    camPosData = getDataMatch(sceneData, posDataName, "Vec3s", "camera position list", strip=True)
    camPosList = [value.replace("{", "").strip() for value in camPosData.split("},") if value.strip() != ""]

    posData = camPosList[index : index + 3]
    position = yUpToZUp @ mathutils.Vector(
        [
            hexOrDecInt(value.strip()) / bpy.context.scene.ootBlenderScale
            for value in posData[0].split(",")
            if value.strip() != ""
        ]
    )

    # camera faces opposite direction
    rotation = (
        yUpToZUp.to_quaternion()
        @ mathutils.Euler(
            ootParseRotation([hexOrDecInt(value.strip()) for value in posData[1].split(",") if value.strip() != ""])
        ).to_quaternion()
        @ mathutils.Quaternion((0, 1, 0), math.radians(180.0))
    ).to_euler()

    fov, bgImageOverrideIndex, unknown = [value.strip() for value in posData[2].split(",") if value.strip() != ""]

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
    sharedSceneData: SharedSceneData,
):
    waterBoxListData = getDataMatch(sceneData, waterBoxListName, "WaterBox", "water box list", strip=True)
    waterBoxList = [value.replace("{", "").strip() for value in waterBoxListData.split("},") if value.strip() != ""]

    # orderIndex used for naming cameras in alphabetical order
    for orderIndex, waterBoxData in enumerate(waterBoxList):
        objName = f"{sceneObj.name}_waterBox_{format(orderIndex, '03')}"
        waterbox = WaterBox.from_data(waterBoxData, sharedSceneData.use_macros)

        topCorner = waterbox.get_blender_position()
        dimensions = waterbox.get_blender_scale()
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
        roomIndex = hexOrDecInt(waterbox.roomIndexC)
        waterBoxProp.lighting = waterbox.lightIndex
        waterBoxProp.camera = waterbox.bgCamIndex
        waterBoxProp.flag19 = waterbox.setFlag19C == "true"

        # 0x3F = -1 in 6bit value
        parent = roomObjs[roomIndex] if roomObjs is not None and len(roomObjs) > 0 and roomIndex != 0x3F else sceneObj
        parentObject(parent, waterBoxObj)


def parseSurfaceParams(
    surface_type: SurfaceType, collision_poly: CollisionPoly, col_props: OOTMaterialCollisionProperty
):
    col_props.eponaBlock = surface_type.isHorseBlocked
    col_props.decreaseHeight = surface_type.isSoft
    setCustomProperty(col_props, "floorSetting", surface_type.floorProperty, ootEnumFloorSetting)
    setCustomProperty(col_props, "wallSetting", surface_type.wallType, ootEnumWallSetting)
    setCustomProperty(col_props, "floorProperty", surface_type.floorType, ootEnumFloorProperty)
    col_props.exitID = surface_type.exitIndex
    col_props.cameraID = surface_type.bgCamIndex
    col_props.isWallDamage = surface_type.isWallDamage

    col_props.conveyorRotation = (surface_type.conveyorDirection / 0x3F) * (2 * math.pi)
    col_props.conveyorSpeed = "Custom"
    col_props.conveyorSpeedCustom = str(surface_type.conveyorSpeed)

    if col_props.conveyorRotation == 0 and col_props.conveyorSpeedCustom == "0":
        col_props.conveyorOption = "None"
    elif collision_poly.isLandConveyor:
        col_props.conveyorOption = "Land"
    else:
        col_props.conveyorOption = "Water"

    col_props.hookshotable = surface_type.canHookshot
    col_props.echo = str(surface_type.echo)
    col_props.lightingSetting = surface_type.lightSetting
    setCustomProperty(col_props, "terrain", str(surface_type.floorEffect), ootEnumCollisionTerrain)
    setCustomProperty(col_props, "sound", str(surface_type.material), ootEnumCollisionSound)

    col_props.ignoreCameraCollision = collision_poly.ignoreCamera
    col_props.ignoreActorCollision = collision_poly.ignoreEntity
    col_props.ignoreProjectileCollision = collision_poly.ignoreProjectile


def parseSurfaces(surfaceList: list[str]):
    surfaces: list[SurfaceType] = []

    for surfaceData in surfaceList:  # SurfaceType
        if "SURFACETYPE0" in surfaceData:
            split = surfaceData.removeprefix("SURFACETYPE0(").split("SURFACETYPE1(")
            surface0 = split[0].replace(")", "").split(",")
            surface1 = split[1].replace(")", "").split(",")

            surface = SurfaceType(
                hexOrDecInt(surface0[0]),  # bgCamIndex
                hexOrDecInt(surface0[1]),  # exitIndex
                surface0[2],
                hexOrDecInt(surface0[3]),  # unk18
                surface0[4],
                surface0[5],
                surface0[6] == "true",  # isSoft
                surface0[7] == "true",  # isHorseBlocked
                surface1[0],
                surface1[1],
                hexOrDecInt(surface1[2]),  # lightSetting
                hexOrDecInt(surface1[3]),  # echo
                surface1[4] == "true",  # canHookshot
                surface1[5],
                hexOrDecInt(surface1[6].removeprefix("CONVEYOR_DIRECTION_FROM_BINANG(").removesuffix(")")),
                surface1[7] == "true",  # unk27
                bpy.context.scene.fast64.oot.useDecompFeatures,
            )
        else:
            params = [hexOrDecInt(value.strip()) for value in surfaceData.split(",")]
            surface = SurfaceType.from_hex(params[0], params[1])

        surfaces.append(surface)

    return surfaces


def parseVertices(vertexList: list[str]):
    vertices = []
    for vertexData in vertexList:
        vertex = [hexOrDecInt(value.strip()) / bpy.context.scene.ootBlenderScale for value in vertexData.split(",")]
        position = yUpToZUp @ mathutils.Vector(vertex)
        vertices.append(position)

    return vertices


def parsePolygon(polygonData: list[str], sharedSceneData: SharedSceneData):
    assert len(polygonData) == 8
    return CollisionPoly.from_data(polygonData, sharedSceneData.use_macros)


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

        if "#include" in match.group(1):
            params = get_include_data(match.group(1)).splitlines()
            otherParams = [value.strip().split(",")[0] for value in params[10:-1]]
        else:
            params = [value.strip() for value in match.group(1).split(",")]
            otherParams = [value.strip() for value in params[6:]]
    else:
        otherParams = [value.strip() for value in match.group(3).split(",")]

    vertexListName = stripName(otherParams[1])
    polygonListName = stripName(otherParams[3])
    surfaceTypeListName = stripName(otherParams[4])
    camDataListName = stripName(otherParams[5])
    waterBoxListName = stripName(otherParams[7])

    if sharedSceneData.includeCollision:
        parseCollision(sceneObj, vertexListName, polygonListName, surfaceTypeListName, sceneData, sharedSceneData)
    if sharedSceneData.includeCameras and camDataListName != "NULL" and camDataListName != "0":
        parseCamDataList(sceneObj, camDataListName, sceneData)
    if sharedSceneData.includeWaterBoxes and waterBoxListName != "NULL" and waterBoxListName != "0":
        parseWaterBoxes(sceneObj, roomObjs, sceneData, waterBoxListName, sharedSceneData)


def parseCollision(
    sceneObj: bpy.types.Object,
    vertexListName: str,
    polygonListName: str,
    surfaceTypeListName: str,
    sceneData: str,
    sharedSceneData: SharedSceneData,
):
    vertMatchData = getDataMatch(sceneData, vertexListName, "Vec3s", "vertex list", strip=True)
    polyMatchData = getDataMatch(sceneData, polygonListName, "CollisionPoly", "polygon list", strip=True)

    surfMatchData = (
        getDataMatch(sceneData, surfaceTypeListName, "SurfaceType", "surface type list")
        .replace("\n", "")
        .replace(" ", "")
    )

    if sharedSceneData.is_fast64_data:
        poly_regex = r"\{([0-9\-]*),(COLPOLY_VTX\([0-9\-]*,[a-zA-Z0-9\-_|\s]*\)),(COLPOLY_VTX\([0-9\-]*,[a-zA-Z0-9\-_|\s]*\)),(COLPOLY_VTX_INDEX\([0-9]*\)),\{(COLPOLY_SNORMAL\([0-9.\-e]*\)),(COLPOLY_SNORMAL\([0-9.\-e]*\)),(COLPOLY_SNORMAL\([0-9.\-e]*\)),?\},?([0-9\-]*),?\}"
    elif sharedSceneData.use_macros:
        poly_regex = r"\{([0-9\-]*),\{(COLPOLY_VTX\([0-9\-]*,[a-zA-Z0-9\-_|\s]*\)),(COLPOLY_VTX\([0-9\-]*,[a-zA-Z0-9\-_|\s]*\)),(COLPOLY_VTX\([0-9]*,[0-9]*\)),\},\{(COLPOLY_SNORMAL\([0-9.\-]*\)),(COLPOLY_SNORMAL\([0-9.\-]*\)),(COLPOLY_SNORMAL\([0-9.\-]*\)),\},([0-9\-]*),\}"
    else:
        poly_regex = r"\{(0x[0-9a-fA-F]*),\s*(0x[0-9a-fA-F]*),\s*(0x[0-9a-fA-F]*),\s*(0x[0-9a-fA-F]*),\s*(0x[0-9a-fA-F]*),\s*(0x[0-9a-fA-F]*),\s*(0x[0-9a-fA-F]*),\s*(0x[0-9a-fA-F]*)\}"

    vertexList = [value.replace("{", "").strip() for value in vertMatchData.split("},") if value.strip() != ""]
    polygonList = [list(match.groups()) for match in re.finditer(poly_regex, polyMatchData, re.DOTALL)]
    surfaceList = [value.replace("{", "").strip() for value in surfMatchData.split("},") if value.strip() != ""]

    surface_map: dict[int, SurfaceType] = {}
    collision_list: list[CollisionPoly] = []

    surfaces = parseSurfaces(surfaceList)
    vertices = parseVertices(vertexList)

    for polygonData in polygonList:
        collision_poly = parsePolygon(polygonData, sharedSceneData)

        # it's impossible that this is set None but doesn't hurt to make sure
        assert collision_poly.type is not None

        if collision_poly.type not in surface_map:
            surface_map[collision_poly.type] = surfaces[collision_poly.type]

        collision_list.append(collision_poly)

    collisionName = f"{sceneObj.name}_collision"
    mesh = bpy.data.meshes.new(collisionName)
    obj = bpy.data.objects.new(collisionName, mesh)
    bpy.context.scene.collection.objects.link(obj)

    triData = []
    triMatData = []
    material_map: dict[int, Material] = {}

    # create the materials from the surface types
    for poly_type, _ in surface_map.items():
        randomColor = mathutils.Color((1, 1, 1))
        randomColor.hsv = (random(), 0.5, 0.5)
        collisionMat = getColliderMat(f"oot_collision_mat_{poly_type}", randomColor[:] + (0.5,))
        mesh.materials.append(collisionMat)
        material_map[poly_type] = collisionMat

    # create the triangles based on the collision data
    for collision_poly in collision_list:
        assert collision_poly.type is not None
        collision = material_map[collision_poly.type].ootCollisionProperty

        # ideally this would be above but we need the surface type and the collision poly
        parseSurfaceParams(surface_map[collision_poly.type], collision_poly, collision)

        triData.append(collision_poly.indices)
        triMatData += [collision_poly.type]
    mesh.from_pydata(vertices=vertices, edges=[], faces=triData)

    for i in range(len(mesh.polygons)):
        mesh.polygons[i].material_index = triMatData[i]

    obj.ignore_render = True

    parentObject(sceneObj, obj)
