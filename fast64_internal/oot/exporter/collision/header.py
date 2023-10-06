import math

from mathutils import Quaternion, Matrix
from bpy.types import Object
from dataclasses import dataclass, field
from ....utility import PluginError, CData, checkIdentityRotation, indent
from ...oot_collision_classes import decomp_compat_map_CameraSType
from ...collision.properties import OOTCameraPositionProperty
from ..base import Base

from .classes import (
    CollisionPoly,
    SurfaceType,
    CameraData,
    CrawlspaceCamera,
    CameraInfo,
    WaterBox,
    Vertex,
)


@dataclass
class HeaderBase(Base):
    sceneObj: Object
    transform: Matrix


@dataclass
class Vertices:
    """This class defines the array of vertices"""

    name: str
    vertexList: list[Vertex]

    def getC(self):
        vertData = CData()
        listName = f"Vec3s {self.name}[{len(self.vertexList)}]"

        # .h
        vertData.header = f"extern {listName};\n"

        # .c
        vertData.source = (
            (listName + " = {\n") + "\n".join(vertex.getEntryC() for vertex in self.vertexList) + "\n};\n\n"
        )

        return vertData


@dataclass
class CollisionPolygons:
    """This class defines the array of collision polys"""

    name: str
    polyList: list[CollisionPoly]

    def getC(self):
        colPolyData = CData()
        listName = f"CollisionPoly {self.name}[{len(self.polyList)}]"

        # .h
        colPolyData.header = f"extern {listName};\n"

        # .c
        colPolyData.source = (listName + " = {\n") + "\n".join(poly.getEntryC() for poly in self.polyList) + "\n};\n\n"

        return colPolyData


@dataclass
class SurfaceTypes:
    """This class defines the array of surface types"""

    name: str
    surfaceTypeList: list[SurfaceType]

    def getC(self):
        surfaceData = CData()
        listName = f"SurfaceType {self.name}[{len(self.surfaceTypeList)}]"

        # .h
        surfaceData.header = f"extern {listName};\n"

        # .c
        surfaceData.source = (
            (listName + " = {\n") + "\n".join(poly.getEntryC() for poly in self.surfaceTypeList) + "\n};\n\n"
        )

        return surfaceData


@dataclass
class BgCamInformations(HeaderBase):
    """This class defines the array of camera informations and the array of the associated data"""

    name: str
    posDataName: str

    bgCamInfoList: list[CameraInfo] = field(default_factory=list)
    crawlspacePosList: list[CrawlspaceCamera] = field(default_factory=list)
    arrayIdx: int = 0
    crawlspaceCount: int = 6
    camFromIndex: dict[int, CameraInfo | CrawlspaceCamera] = field(default_factory=dict)

    def initCrawlspaceList(self):
        """Returns a list of crawlspace data from every splines objects with the type 'Crawlspace'"""

        crawlspaceObjList: list[Object] = [
            obj
            for obj in self.sceneObj.children_recursive
            if obj.type == "CURVE" and obj.ootSplineProperty.splineType == "Crawlspace"
        ]

        for obj in crawlspaceObjList:
            if self.validateCurveData(obj):
                self.crawlspacePosList.append(
                    CrawlspaceCamera(
                        [
                            [round(value) for value in self.transform @ obj.matrix_world @ point.co]
                            for point in obj.data.splines[0].points
                        ],
                        obj.ootSplineProperty.index,
                    )
                )

    def initBgCamInfoList(self):
        """Returns a list of camera informations from camera objects"""

        camObjList: list[Object] = [obj for obj in self.sceneObj.children_recursive if obj.type == "CAMERA"]
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
                pos, rot, _, _ = self.getConvertedTransformWithOrientation(
                    self.transform, self.sceneObj, camObj, Quaternion((0, 1, 0), math.radians(180.0))
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
        self.bgCamInfoList = list(camInfoData.values())

    def initCamTable(self):
        for bgCam in self.bgCamInfoList:
            if not bgCam.camIndex in self.camFromIndex:
                self.camFromIndex[bgCam.camIndex] = bgCam
            else:
                raise PluginError(f"ERROR (CameraInfo): Camera index already used: {bgCam.camIndex}")

        for crawlCam in self.crawlspacePosList:
            if not crawlCam.camIndex in self.camFromIndex:
                self.camFromIndex[crawlCam.camIndex] = crawlCam
            else:
                raise PluginError(f"ERROR (Crawlspace): Camera index already used: {crawlCam.camIndex}")

        self.camFromIndex = dict(sorted(self.camFromIndex.items()))
        if list(self.camFromIndex.keys()) != list(range(len(self.camFromIndex))):
            raise PluginError("ERROR: The camera indices are not consecutive!")

        i = 0
        for val in self.camFromIndex.values():
            if isinstance(val, CrawlspaceCamera):
                val.arrayIndex = i
                i += 6  # crawlspaces are using 6 entries in the data array
            elif val.hasPosData:
                val.arrayIndex = i
                i += 3

    def __post_init__(self):
        self.initCrawlspaceList()
        self.initBgCamInfoList()
        self.initCamTable()

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


@dataclass
class WaterBoxes(HeaderBase):
    """This class defines the array of waterboxes"""

    name: str
    useMacros: bool

    waterboxList: list[WaterBox] = field(default_factory=list)

    def __post_init__(self):
        waterboxObjList: list[Object] = [
            obj for obj in self.sceneObj.children_recursive if obj.type == "EMPTY" and obj.ootEmptyType == "Water Box"
        ]

        for waterboxObj in waterboxObjList:
            emptyScale = waterboxObj.empty_display_size
            pos, _, scale, orientedRot = self.getConvertedTransform(self.transform, self.sceneObj, waterboxObj, True)
            checkIdentityRotation(waterboxObj, orientedRot, False)

            wboxProp = waterboxObj.ootWaterBoxProperty
            roomObj = self.getRoomObjectFromChild(waterboxObj)
            self.waterboxList.append(
                WaterBox(
                    pos,
                    scale,
                    emptyScale,
                    wboxProp.camera,
                    wboxProp.lighting,
                    roomObj.ootRoomHeader.roomIndex if roomObj is not None else 0x3F,
                    wboxProp.flag19,
                    self.useMacros,
                )
            )

    def getC(self):
        wboxData = CData()
        listName = f"WaterBox {self.name}[{len(self.waterboxList)}]"

        # .h
        wboxData.header = f"extern {listName};\n"

        # .c
        wboxData.source = (listName + " = {\n") + "\n".join(wBox.getEntryC() for wBox in self.waterboxList) + "\n};\n\n"

        return wboxData


@dataclass
class CollisionHeader(HeaderBase):
    """This class defines the collision header used by the scene"""

    name: str
    sceneName: str
    useMacros: bool

    # Ideally functions inside base.py would be there but the file would be really long
    colBounds: list[tuple[int, int, int]]
    vertexList: list[Vertex]
    polyList: list[CollisionPoly]
    surfaceTypeList: list[SurfaceType]

    minBounds: tuple[int, int, int] = None
    maxBounds: tuple[int, int, int] = None
    vertices: Vertices = None
    collisionPoly: CollisionPolygons = None
    surfaceType: SurfaceTypes = None
    bgCamInfo: BgCamInformations = None
    waterbox: WaterBoxes = None

    def __post_init__(self):
        self.minBounds = self.colBounds[0]
        self.maxBounds = self.colBounds[1]
        self.vertices = Vertices(f"{self.sceneName}_vertices", self.vertexList)
        self.collisionPoly = CollisionPolygons(f"{self.sceneName}_polygons", self.polyList)
        self.surfaceType = SurfaceTypes(f"{self.sceneName}_polygonTypes", self.surfaceTypeList)
        self.bgCamInfo = BgCamInformations(
            self.sceneObj, self.transform, f"{self.sceneName}_bgCamInfo", f"{self.sceneName}_camPosData"
        )
        self.waterbox = WaterBoxes(self.sceneObj, self.transform, f"{self.sceneName}_waterBoxes", self.useMacros)

    def getCmd(self):
        return indent + f"SCENE_CMD_COL_HEADER(&{self.name}),\n"

    def getC(self):
        """Returns the collision header for the selected scene"""

        headerData = CData()
        colData = CData()
        varName = f"CollisionHeader {self.name}"

        wBoxPtrLine = colPolyPtrLine = vtxPtrLine = "0, NULL"
        camPtrLine = surfacePtrLine = "NULL"

        # Add waterbox data if necessary
        if len(self.waterbox.waterboxList) > 0:
            colData.append(self.waterbox.getC())
            wBoxPtrLine = f"ARRAY_COUNT({self.waterbox.name}), {self.waterbox.name}"

        # Add camera data if necessary
        if len(self.bgCamInfo.bgCamInfoList) > 0 or len(self.bgCamInfo.crawlspacePosList) > 0:
            infoData = self.bgCamInfo.getInfoArrayC()
            if "&" in infoData.source:
                colData.append(self.bgCamInfo.getDataArrayC())
            colData.append(infoData)
            camPtrLine = f"{self.bgCamInfo.name}"

        # Add surface types
        if len(self.surfaceType.surfaceTypeList) > 0:
            colData.append(self.surfaceType.getC())
            surfacePtrLine = f"{self.surfaceType.name}"

        # Add vertex data
        if len(self.vertices.vertexList) > 0:
            colData.append(self.vertices.getC())
            vtxPtrLine = f"ARRAY_COUNT({self.vertices.name}), {self.vertices.name}"

        # Add collision poly data
        if len(self.collisionPoly.polyList) > 0:
            colData.append(self.collisionPoly.getC())
            colPolyPtrLine = f"ARRAY_COUNT({self.collisionPoly.name}), {self.collisionPoly.name}"

        # build the C data of the collision header

        # .h
        headerData.header = f"extern {varName};\n"

        # .c
        headerData.source += (
            (varName + " = {\n")
            + ",\n".join(
                indent + val
                for val in [
                    ("{ " + ", ".join(f"{val}" for val in self.minBounds) + " }"),
                    ("{ " + ", ".join(f"{val}" for val in self.maxBounds) + " }"),
                    vtxPtrLine,
                    colPolyPtrLine,
                    surfacePtrLine,
                    camPtrLine,
                    wBoxPtrLine,
                ]
            )
            + "\n};\n\n"
        )

        headerData.append(colData)
        return headerData
