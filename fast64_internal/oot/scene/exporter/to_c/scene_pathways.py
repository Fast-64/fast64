from .....utility import CData, indent
from ....oot_spline import OOTPath
from ....oot_level_classes import OOTScene


def getPathPointData(path: OOTPath, headerIndex: int, pathIndex: int):
    pathData = CData()
    declarationBase = f"Vec3s {path.pathName(headerIndex, pathIndex)}"

    # .h
    pathData.header = f"extern {declarationBase}[];\n"

    # .c
    pathData.source = (
        f"{declarationBase}[]"
        + " = {\n"
        + "\n".join(
            indent + "{ " + ", ".join(f"{round(curPoint):5}" for curPoint in point) + " }," for point in path.points
        )
        + "\n};\n\n"
    )

    return pathData


def getPathData(outScene: OOTScene, headerIndex: int):
    pathData = CData()
    pathListData = CData()
    declarationBase = f"Path {outScene.pathListName(headerIndex)}[{len(outScene.pathList)}]"

    # .h
    pathListData.header = f"extern {declarationBase};\n"

    # .c
    pathListData.source = declarationBase + " = {\n"

    # Parse in alphabetical order of names
    sortedPathList = sorted(outScene.pathList, key=lambda x: x.objName.lower())
    for i, curPath in enumerate(sortedPathList):
        pathName = curPath.pathName(headerIndex, i)
        pathListData.source += indent + "{ " + f"ARRAY_COUNTU({pathName}), {pathName}" + " },\n"
        pathData.append(getPathPointData(curPath, headerIndex, i))

    pathListData.source += "};\n\n"
    pathData.append(pathListData)

    return pathData
