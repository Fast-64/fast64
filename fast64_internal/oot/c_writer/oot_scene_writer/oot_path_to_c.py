from ....utility import CData
from ...oot_level_classes import OOTScene
from ...oot_spline import OOTPath
from ...oot_utility import indent


def getPathPointsData(path: OOTPath):
    """Returns the points data of a path"""
    pointData = CData()
    pointName = f"Vec3s {path.pathName()}[]"
    print(path.points)
    pointsData = " },\n".join(
        [indent + "{ " + ", ".join([f"{round(point[i])}" for i in range(len(point) - 1)]) for point in path.points]
    )

    # .h
    pointData.header = f"extern {pointName};\n"

    # .c
    pointData.source = f"Vec3s {pointName}" + " = {\n" + pointsData + " },\n};\n\n"
    return pointData


def ootPathListToC(scene: OOTScene):
    """Converts a path to C"""
    pathListData = CData()
    pointData = CData()
    pathListName = f"Path {scene.pathListName()}[{len(scene.pathList)}]"

    # .h
    pathListData.header = f"extern {pathListName};\n"

    # .c
    pathListData.source = pathListName + " = {\n"

    for path in scene.pathList.values():
        pathListData.source += indent + "{ " f"{len(path.points)}, {path.pathName()}" + " },\n"
        pointData.append(getPathPointsData(path))

    pathListData.source += "};\n\n"
    pointData.append(pathListData)
    return pointData
