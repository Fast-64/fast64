import bpy

from typing import Optional
from ...utility import hexOrDecInt, parentObject
from ..utility import is_game_oot, get_game_props
from .utility import getDataMatch, createCurveFromPoints, unsetAllHeadersExceptSpecified
from .classes import SharedSceneData


def parsePath(
    sceneObj: bpy.types.Object,
    sceneData: str,
    points_ptr: str,
    opt_path_idx: Optional[str],
    custom_value: Optional[str],
    headerIndex: int,
    sharedSceneData: SharedSceneData,
    orderIndex: int,
):
    pathData = getDataMatch(sceneData, points_ptr, "Vec3s", "path")
    pathPointsEntries = [value.replace("{", "").strip() for value in pathData.split("},") if value.strip() != ""]
    pathPointsInfo = []
    for pathPoint in pathPointsEntries:
        pathPointsInfo.append(tuple([hexOrDecInt(value.strip()) for value in pathPoint.split(",")]))
    pathPoints = tuple(pathPointsInfo)

    if sharedSceneData.addHeaderIfItemExists(pathPoints, "Curve", headerIndex):
        return

    curveObj = createCurveFromPoints(pathPoints, points_ptr)
    splineProp = curveObj.ootSplineProperty
    splineProp.index = orderIndex

    if not is_game_oot() and opt_path_idx is not None and custom_value is not None:
        splineProp.opt_path_index = int(opt_path_idx)
        splineProp.custom_value = int(custom_value)

    unsetAllHeadersExceptSpecified(get_game_props(curveObj, "path_header_settings"), headerIndex)
    sharedSceneData.pathDict[pathPoints] = curveObj

    parentObject(sceneObj, curveObj)


def parsePathList(
    sceneObj: bpy.types.Object,
    sceneData: str,
    pathListName: str,
    headerIndex: int,
    sharedSceneData: SharedSceneData,
):
    pathData = getDataMatch(sceneData, pathListName, "Path", "path list")
    pathList = [value.replace("{", "").strip() for value in pathData.split("},") if value.strip() != ""]
    for i, pathEntry in enumerate(pathList):
        if is_game_oot():
            count, points_ptr = [value.strip() for value in pathEntry.split(",")]
            opt_path_idx = custom_value = None
        else:
            count, opt_path_idx, custom_value, points_ptr = [value.strip() for value in pathEntry.split(",")]

        parsePath(sceneObj, sceneData, points_ptr, opt_path_idx, custom_value, headerIndex, sharedSceneData, i)
