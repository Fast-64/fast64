from .....utility import CData, indent


def ootPathToC(path, headerIndex: int, index: int):
    data = CData()
    data.header = "extern Vec3s " + path.pathName(headerIndex, index) + "[];\n"
    data.source = "Vec3s " + path.pathName(headerIndex, index) + "[] = {\n"
    for point in path.points:
        data.source += (
            indent
            + "{ "
            + str(int(round(point[0])))
            + ", "
            + str(int(round(point[1])))
            + ", "
            + str(int(round(point[2])))
            + " },\n"
        )
    data.source += "};\n\n"

    return data


def ootPathListToC(scene, headerIndex: int):
    data = CData()
    data.header = "extern Path " + scene.pathListName(headerIndex) + "[" + str(len(scene.pathList)) + "];\n"
    data.source = "Path " + scene.pathListName(headerIndex) + "[" + str(len(scene.pathList)) + "] = {\n"
    pathData = CData()

    # Parse in alphabetical order of names
    sortedPathList = sorted(scene.pathList, key=lambda x: x.objName.lower())
    for i in range(len(sortedPathList)):
        path = sortedPathList[i]
        data.source += indent + "{ " + str(len(path.points)) + ", " + path.pathName(headerIndex, i) + " },\n"
        pathData.append(ootPathToC(path, headerIndex, i))
    data.source += "};\n\n"
    pathData.append(data)
    return pathData
