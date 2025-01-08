from dataclasses import dataclass, field
from typing import Optional
from mathutils import Matrix
from bpy.types import Object
from ....game_data import game_data
from ....utility import PluginError, CData, indent
from ...utility import getObjectList
from ..utility import Utility


@dataclass
class ScenePath:
    """This class defines a pathway"""

    name: str
    additional_path_index: Optional[int]
    custom_value: Optional[int]
    points: list[tuple[int, int, int]]

    def getC(self):
        """Returns the pathway position array"""

        pathData = CData()
        pathName = f"Vec3s {self.name}"

        # .h
        pathData.header = f"extern {pathName}[];\n"

        # .c
        pathData.source = (
            f"{pathName}[]"
            + " = {\n"
            + "\n".join(
                indent + "{ " + ", ".join(f"{round(curPoint):5}" for curPoint in point) + " }," for point in self.points
            )
            + "\n};\n\n"
        )

        return pathData


@dataclass
class ScenePathways:
    """This class hosts pathways array data"""

    name: str
    pathList: list[ScenePath]

    @staticmethod
    def new(name: str, sceneObj: Object, transform: Matrix, headerIndex: int):
        pathFromIndex: dict[int, ScenePath] = {}
        pathObjList = getObjectList(sceneObj.children_recursive, "CURVE", splineType="Path")

        for obj in pathObjList:
            relativeTransform = transform @ sceneObj.matrix_world.inverted() @ obj.matrix_world
            pathProps = obj.ootSplineProperty
            isHeaderValid = Utility.isCurrentHeaderValid(obj.ootSplineProperty.headerSettings, headerIndex)
            if isHeaderValid and Utility.validateCurveData(obj):
                if pathProps.index not in pathFromIndex:
                    pathFromIndex[pathProps.index] = ScenePath(
                        f"{name}List{pathProps.index:02}",
                        pathProps.opt_path_index if game_data.z64.is_mm() else None,
                        pathProps.custom_value if game_data.z64.is_mm() else None,
                        [relativeTransform @ point.co.xyz for point in obj.data.splines[0].points],
                    )
                else:
                    raise PluginError(f"ERROR: Path index already used ({obj.name})")

        pathFromIndex = dict(sorted(pathFromIndex.items()))
        if list(pathFromIndex.keys()) != list(range(len(pathFromIndex))):
            raise PluginError("ERROR: Path indices are not consecutive!")

        return ScenePathways(name, list(pathFromIndex.values()))

    def getCmd(self):
        """Returns the path list scene command"""

        return indent + f"SCENE_CMD_PATH_LIST({self.name}),\n" if len(self.pathList) > 0 else ""

    def getC(self):
        """Returns a ``CData`` containing the C data of the pathway array"""

        pathData = CData()
        pathListData = CData()
        listName = f"Path {self.name}[{len(self.pathList)}]"

        # .h
        pathListData.header = f"extern {listName};\n"

        # .c
        pathListData.source = listName + " = {\n"

        for path in self.pathList:
            pathListData.source += (
                (indent + "{ ")
                + f"ARRAY_COUNTU({path.name}), "
                + (f"{path.additional_path_index}, " if game_data.z64.is_mm() else "")
                + (f"{path.custom_value}, " if game_data.z64.is_mm() else "")
                + f"{path.name}"
                + " },\n"
            )
            pathData.append(path.getC())

        pathListData.source += "};\n\n"
        pathData.append(pathListData)

        return pathData
