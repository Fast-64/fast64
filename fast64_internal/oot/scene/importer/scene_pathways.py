import bpy

from ....utility import hexOrDecInt, parentObject
from .utility import getDataMatch, createCurveFromPoints, unsetAllHeadersExceptSpecified
from .classes import SharedSceneData


def parsePath(
    sceneObj: bpy.types.Object,
    sceneData: str,
    pathName: str,
    headerIndex: int,
    sharedSceneData: SharedSceneData,
    orderIndex: int,
):
    pathData = getDataMatch(sceneData, pathName, "Vec3s", "path")
    pathPointsEntries = [value.replace("{", "").strip() for value in pathData.split("},") if value.strip() != ""]
    pathPointsInfo = []
    for pathPoint in pathPointsEntries:
        pathPointsInfo.append(tuple([hexOrDecInt(value.strip()) for value in pathPoint.split(",")]))
    pathPoints = tuple(pathPointsInfo)

    if sharedSceneData.addHeaderIfItemExists(pathPoints, "Curve", headerIndex):
        return

    curveObj = createCurveFromPoints(pathPoints, pathName)
    splineProp = curveObj.ootSplineProperty
    splineProp.index = orderIndex

    unsetAllHeadersExceptSpecified(splineProp.headerSettings, headerIndex)
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
        numPoints, pathName = [value.strip() for value in pathEntry.split(",")]
        parsePath(sceneObj, sceneData, pathName, headerIndex, sharedSceneData, i)
