from dataclasses import dataclass, field
from mathutils import Matrix
from bpy.types import Object
from ....utility import PluginError, CData, indent
from ...scene.properties import OOTSceneHeaderProperty
from ..base import Base


@dataclass
class Path:
    """This class defines a pathway"""

    name: str
    points: list[tuple[int, int, int]] = field(default_factory=list)

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
class ScenePathways(Base):
    """This class hosts pathways array data"""

    props: OOTSceneHeaderProperty
    name: str
    sceneObj: Object
    transform: Matrix
    headerIndex: int

    pathList: list[Path] = field(default_factory=list)

    def __post_init__(self):
        pathFromIndex: dict[int, Path] = {}
        pathObjList: list[Object] = [
            obj
            for obj in self.sceneObj.children_recursive
            if obj.type == "CURVE" and obj.ootSplineProperty.splineType == "Path"
        ]

        for obj in pathObjList:
            relativeTransform = self.transform @ self.sceneObj.matrix_world.inverted() @ obj.matrix_world
            pathProps = obj.ootSplineProperty
            isHeaderValid = self.isCurrentHeaderValid(pathProps.headerSettings, self.headerIndex)
            if isHeaderValid and self.validateCurveData(obj):
                if not pathProps.index in pathFromIndex:
                    pathFromIndex[pathProps.index] = Path(
                        f"{self.name}List{pathProps.index:02}",
                        [relativeTransform @ point.co.xyz for point in obj.data.splines[0].points],
                    )
                else:
                    raise PluginError(f"ERROR: Path index already used ({obj.name})")

        pathFromIndex = dict(sorted(pathFromIndex.items()))
        if list(pathFromIndex.keys()) != list(range(len(pathFromIndex))):
            raise PluginError("ERROR: Path indices are not consecutive!")

        self.pathList = list(pathFromIndex.values())

    def getCmd(self):
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
            pathListData.source += indent + "{ " + f"ARRAY_COUNTU({path.name}), {path.name}" + " },\n"
            pathData.append(path.getC())

        pathListData.source += "};\n\n"
        pathData.append(pathListData)

        return pathData