import math

from dataclasses import dataclass, field
from mathutils import Quaternion, Matrix
from bpy.types import Object
from ....utility import PluginError, CData, indent
from ...oot_utility import getObjectList
from ...collision.constants import decomp_compat_map_CameraSType
from ...collision.properties import OOTCameraPositionProperty
from ..utility import Utility


@dataclass
class CrawlspaceCamera:
    """This class defines camera data for crawlspaces, if used"""

    points: list[tuple[int, int, int]]
    camIndex: int

    arrayIndex: int = field(init=False, default=0)

    def getDataEntryC(self):
        """Returns an entry for the camera data array"""

        return "".join(indent + "{ " + f"{point[0]:6}, {point[1]:6}, {point[2]:6}" + " },\n" for point in self.points)

    def getInfoEntryC(self, posDataName: str):
        """Returns a crawlspace entry for the camera informations array"""

        return indent + "{ " + f"CAM_SET_CRAWLSPACE, 6, &{posDataName}[{self.arrayIndex}]" + " },\n"


@dataclass
class CameraData:
    """This class defines camera data, if used"""

    pos: tuple[int, int, int]
    rot: tuple[int, int, int]
    fov: int
    roomImageOverrideBgCamIndex: int

    def getEntryC(self):
        """Returns an entry for the camera data array"""

        return (
            (indent + "{ " + ", ".join(f"{p:6}" for p in self.pos) + " },\n")
            + (indent + "{ " + ", ".join(f"0x{r:04X}" for r in self.rot) + " },\n")
            + (indent + "{ " + f"{self.fov:6}, {self.roomImageOverrideBgCamIndex:6}, {-1:6}" + " },\n")
        )


@dataclass
class CameraInfo:
    """This class defines camera information data"""

    setting: str
    count: int
    data: CameraData
    camIndex: int

    arrayIndex: int = field(init=False, default=0)

    def __post_init__(self):
        self.hasPosData = self.data is not None

    def getInfoEntryC(self, posDataName: str):
        """Returns an entry for the camera information array"""

        ptr = f"&{posDataName}[{self.arrayIndex}]" if self.hasPosData else "NULL"
        return indent + "{ " + f"{self.setting}, {self.count}, {ptr}" + " },\n"


@dataclass
class BgCamInformations:
    """This class defines the array of camera informations and the array of the associated data"""

    name: str
    posDataName: str
    bgCamInfoList: list[CameraInfo]
    crawlspacePosList: list[CrawlspaceCamera]
    arrayIdx: int
    crawlspaceCount: int
    camFromIndex: dict[int, CameraInfo | CrawlspaceCamera]

    @staticmethod
    def getCrawlspacePosList(dataHolder: Object, transform: Matrix):
        """Returns a list of crawlspace data from every splines objects with the type 'Crawlspace'"""

        crawlspacePosList: list[CrawlspaceCamera] = []
        crawlspaceObjList = getObjectList(dataHolder.children_recursive, "CURVE", splineType="Crawlspace")
        for obj in crawlspaceObjList:
            if Utility.validateCurveData(obj):
                points = [
                    [round(value) for value in transform @ obj.matrix_world @ point.co]
                    for point in obj.data.splines[0].points
                ]
                crawlspacePosList.append(
                    CrawlspaceCamera(
                        [points[0], points[0], points[0], points[1], points[1], points[1]],
                        obj.ootSplineProperty.index,
                    )
                )
        return crawlspacePosList

    @staticmethod
    def getBgCamInfoList(dataHolder: Object, transform: Matrix):
        """Returns a list of camera informations from camera objects"""

        camObjList = getObjectList(dataHolder.children_recursive, "CAMERA")
        camPosData: dict[int, CameraData] = {}
        camInfoData: dict[int, CameraInfo] = {}

        for camObj in camObjList:
            camProp: OOTCameraPositionProperty = camObj.ootCameraPositionProperty

            if camProp.camSType == "Custom":
                setting = camProp.camSTypeCustom
            else:
                setting = decomp_compat_map_CameraSType.get(camProp.camSType, camProp.camSType)

            if camProp.hasPositionData:
                if camProp.index in camPosData:
                    raise PluginError(f"ERROR: Repeated camera position index: {camProp.index} for {camObj.name}")

                # Camera faces opposite direction
                pos, rot, _, _ = Utility.getConvertedTransformWithOrientation(
                    transform, dataHolder, camObj, Quaternion((0, 1, 0), math.radians(180.0))
                )

                fov = math.degrees(camObj.data.angle)
                camPosData[camProp.index] = CameraData(
                    pos,
                    rot,
                    round(fov * 100 if fov > 3.6 else fov),  # see CAM_DATA_SCALED() macro
                    camObj.ootCameraPositionProperty.bgImageOverrideIndex,
                )

            if camProp.index in camInfoData:
                raise PluginError(f"ERROR: Repeated camera entry: {camProp.index} for {camObj.name}")

            camInfoData[camProp.index] = CameraInfo(
                setting,
                3 if camProp.hasPositionData else 0,  # cameras are using 3 entries in the data array
                camPosData[camProp.index] if camProp.hasPositionData else None,
                camProp.index,
            )
        return list(camInfoData.values())

    @staticmethod
    def getCamTable(dataHolder: Object, crawlspacePosList: list[CrawlspaceCamera], bgCamInfoList: list[CameraInfo]):
        camFromIndex: dict[int, CameraInfo | CrawlspaceCamera] = {}
        for bgCam in bgCamInfoList:
            if bgCam.camIndex not in camFromIndex:
                camFromIndex[bgCam.camIndex] = bgCam
            else:
                raise PluginError(f"ERROR (CameraInfo): Camera index already used: {bgCam.camIndex}")

        for crawlCam in crawlspacePosList:
            if crawlCam.camIndex not in camFromIndex:
                camFromIndex[crawlCam.camIndex] = crawlCam
            else:
                raise PluginError(f"ERROR (Crawlspace): Camera index already used: {crawlCam.camIndex}")

        camFromIndex = dict(sorted(camFromIndex.items()))
        if list(camFromIndex.keys()) != list(range(len(camFromIndex))):
            raise PluginError("ERROR: The camera indices are not consecutive!")

        i = 0
        for val in camFromIndex.values():
            if isinstance(val, CrawlspaceCamera):
                val.arrayIndex = i
                i += 6  # crawlspaces are using 6 entries in the data array
            elif val.hasPosData:
                val.arrayIndex = i
                i += 3
        return camFromIndex

    @staticmethod
    def new(name: str, posDataName: str, dataHolder: Object, transform: Matrix):
        crawlspacePosList = BgCamInformations.getCrawlspacePosList(dataHolder, transform)
        bgCamInfoList = BgCamInformations.getBgCamInfoList(dataHolder, transform)
        camFromIndex = BgCamInformations.getCamTable(dataHolder, crawlspacePosList, bgCamInfoList)
        return BgCamInformations(name, posDataName, bgCamInfoList, crawlspacePosList, 0, 6, camFromIndex)

    def getDataArrayC(self):
        """Returns the camera data/crawlspace positions array"""

        posData = CData()
        listName = f"Vec3s {self.posDataName}[]"

        # .h
        posData.header = f"extern {listName};\n"

        # .c
        posData.source = listName + " = {\n"
        for val in self.camFromIndex.values():
            if isinstance(val, CrawlspaceCamera):
                posData.source += val.getDataEntryC() + "\n"
            elif val.hasPosData:
                posData.source += val.data.getEntryC() + "\n"
        posData.source = posData.source[:-1]  # remove extra newline
        posData.source += "};\n\n"

        return posData

    def getInfoArrayC(self):
        """Returns the array containing the informations of each cameras"""

        bgCamInfoData = CData()
        listName = f"BgCamInfo {self.name}[]"

        # .h
        bgCamInfoData.header = f"extern {listName};\n"

        # .c
        bgCamInfoData.source = (
            (listName + " = {\n")
            + "".join(val.getInfoEntryC(self.posDataName) for val in self.camFromIndex.values())
            + "};\n\n"
        )

        return bgCamInfoData
