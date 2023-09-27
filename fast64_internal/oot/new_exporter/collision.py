from dataclasses import dataclass
from ...utility import CData, indent

from .collision_classes import (
    SurfaceType,
    CollisionPoly,
    Vertex,
    WaterBox,
    BgCamInfo,
    CrawlspaceData,
)


@dataclass
class CollisionHeaderVertices:
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
class CollisionHeaderCollisionPoly:
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
class CollisionHeaderSurfaceType:
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
class CollisionHeaderBgCamInfo:
    """This class defines the array of camera informations and the array of the associated data"""

    name: str
    posDataName: str
    bgCamInfoList: list[BgCamInfo]
    crawlspacePosList: list[CrawlspaceData]

    arrayIdx: int = 0
    crawlspaceCount: int = 6

    def __post_init__(self):
        if len(self.bgCamInfoList) > 0:
            self.arrayIdx = self.bgCamInfoList[-1].arrayIndex + self.crawlspaceCount

    def getDataArrayC(self):
        """Returns the camera data/crawlspace positions array"""

        posData = CData()
        listName = f"Vec3s {self.posDataName}[]"

        # .h
        posData.header = f"extern {listName};\n"

        # .c
        posData.source = (
            (listName + " = {\n")
            + "\n".join(cam.camData.getEntryC() for cam in self.bgCamInfoList if cam.hasPosData)
            + "\n".join(crawlspace.getDataEntryC() for crawlspace in self.crawlspacePosList)
            + "};\n\n"
        )

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
            + "".join(cam.getInfoEntryC(self.posDataName) for cam in self.bgCamInfoList)
            + "".join(crawlspace.getInfoEntryC(self.posDataName) for crawlspace in self.crawlspacePosList)
            + "};\n\n"
        )

        return bgCamInfoData


@dataclass
class CollisionHeaderWaterBox:
    """This class defines the array of waterboxes"""

    name: str
    waterboxList: list[WaterBox]

    def getC(self):
        wboxData = CData()
        listName = f"WaterBox {self.name}[{len(self.waterboxList)}]"

        # .h
        wboxData.header = f"extern {listName};\n"

        # .c
        wboxData.source = (listName + " = {\n") + "\n".join(wBox.getEntryC() for wBox in self.waterboxList) + "\n};\n\n"

        return wboxData


@dataclass
class OOTSceneCollisionHeader:
    """This class defines the collision header used by the scene"""

    name: str
    minBounds: tuple[int, int, int] = None
    maxBounds: tuple[int, int, int] = None
    vertices: CollisionHeaderVertices = None
    collisionPoly: CollisionHeaderCollisionPoly = None
    surfaceType: CollisionHeaderSurfaceType = None
    bgCamInfo: CollisionHeaderBgCamInfo = None
    waterbox: CollisionHeaderWaterBox = None

    def getSceneCollisionC(self):
        """Returns the collision header for the selected scene"""

        headerData = CData()
        colData = CData()
        varName = f"CollisionHeader {self.name}"

        vtxPtrLine = "0, NULL"
        colPolyPtrLine = "0, NULL"
        surfacePtrLine = "NULL"
        camPtrLine = "NULL"
        wBoxPtrLine = "0, NULL"

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
