from .....utility import CData
from ....oot_level_classes import OOTScene
from ....oot_spline import OOTPath
from ...data import indent


def getPathPointsData(path: OOTPath, layerIndex: int):
    """Returns the points data of a path"""
    pointData = CData()
    pointName = f"Vec3s {path.pathName(layerIndex)}[]"
    pointsData = " },\n".join(
        [indent + "{ " + ", ".join([f"{round(point[i])}" for i in range(len(point) - 1)]) for point in path.points]
    )

    # .h
    pointData.header = f"extern {pointName};\n"

    # .c
    pointData.source = f"{pointName}" + " = {\n" + pointsData + " },\n};\n\n"
    return pointData


def convertPathList(outScene: OOTScene, layerIndex: int):
    """Converts a path to C"""
    pathListData = CData()
    pointData = CData()
    pathListName = f"Path {outScene.getPathListName(layerIndex)}[{len(outScene.pathList)}]"

    # .h
    pathListData.header = f"extern {pathListName};\n"

    # .c
    pathListData.source = pathListName + " = {\n"

    for path in outScene.pathList.values():
        pathListData.source += indent + "{ " f"{len(path.points)}, {path.pathName(layerIndex)}" + " },\n"
        pointData.append(getPathPointsData(path, layerIndex))

    pathListData.source += "};\n\n"
    pointData.append(pathListData)
    return pointData
