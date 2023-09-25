from dataclasses import dataclass, field
from ...utility import PluginError, CData, indent


@dataclass
class CollisionPoly:
    indices: list[int]
    ignoreCamera: bool
    ignoreActor: bool
    ignoreProjectile: bool
    enableConveyor: bool
    normal: tuple[int, int, int]
    dist: int
    type: int = None

    def getFlags_vIA(self):
        vertPart = self.indices[0] & 0x1FFF
        colPart = (1 if self.ignoreCamera else 0) + (2 if self.ignoreActor else 0) + (4 if self.ignoreProjectile else 0)
        return vertPart | (colPart << 13)

    def getFlags_vIB(self):
        vertPart = self.indices[1] & 0x1FFF
        conveyorPart = 1 if self.enableConveyor else 0
        return vertPart | (conveyorPart << 13)

    def getVIC(self):
        return self.indices[2] & 0x1FFF

    def getCollisionPolyEntryC(self):
        if self.type is None:
            raise PluginError("ERROR: Type unset!")
        return (
            (indent + "{ ")
            + ", ".join(
                (
                    f"0x{self.type:04X}",
                    f"0x{self.getFlags_vIA():04X}",
                    f"0x{self.getFlags_vIB():04X}",
                    f"0x{self.getVIC():04X}",
                    ", ".join(f"COLPOLY_SNORMAL({val})" for val in self.normal),
                    f"0x{self.dist:04X}",
                )
            )
            + " },"
        )


@dataclass
class SurfaceType:
    bgCamIndex: int
    exitIndex: int
    floorType: int
    unk18: int  # unused?
    wallType: int
    floorProperty: int
    isSoft: bool
    isHorseBlocked: bool

    material: int
    floorEffect: int
    lightSetting: int
    echo: int
    canHookshot: bool
    conveyorSpeed: int
    conveyorDirection: int
    isWallDamage: bool  # unk27

    conveyorKeepMomentum: bool
    useMacros: bool = True
    isSoftC: str = None
    isHorseBlockedC: str = None
    canHookshotC: str = None
    isWallDamageC: str = None

    def __post_init__(self):
        if self.conveyorKeepMomentum:
            self.conveyorSpeed += 4

        self.isSoftC = "1" if self.isSoft else "0"
        self.isHorseBlockedC = "1" if self.isHorseBlocked else "0"
        self.canHookshotC = "1" if self.canHookshot else "0"
        self.isWallDamageC = "1" if self.isWallDamage else "0"

    def getSurfaceType0(self):
        if self.useMacros:
            return (
                ("SURFACETYPE0(")
                + f"{self.bgCamIndex}, {self.exitIndex}, {self.floorType}, {self.unk18}, "
                + f"{self.wallType}, {self.floorProperty}, {self.isSoftC}, {self.isHorseBlockedC}"
                + ")"
            )
        else:
            return (
                (indent * 2 + "(")
                + " | ".join(
                    prop
                    for prop in [
                        f"(({self.isHorseBlockedC} & 1) << 31)",
                        f"(({self.isSoftC} & 1) << 30)",
                        f"(({self.floorProperty} & 0x0F) << 26)",
                        f"(({self.wallType} & 0x1F) << 21)",
                        f"(({self.unk18} & 0x07) << 18)",
                        f"(({self.floorType} & 0x1F) << 13)",
                        f"(({self.exitIndex} & 0x1F) << 8)",
                        f"({self.bgCamIndex} & 0xFF)",
                    ]
                )
                + ")"
            )

    def getSurfaceType1(self):
        if self.useMacros:
            return (
                ("SURFACETYPE1(")
                + f"{self.material}, {self.floorEffect}, {self.lightSetting}, {self.echo}, "
                + f"{self.canHookshotC}, {self.conveyorSpeed}, {self.conveyorDirection}, {self.isWallDamageC}"
                + ")"
            )
        else:
            return (
                (indent * 2 + "(")
                + " | ".join(
                    prop
                    for prop in [
                        f"(({self.isWallDamageC} & 1) << 27)",
                        f"(({self.conveyorDirection} & 0x3F) << 21)",
                        f"(({self.conveyorSpeed} & 0x07) << 18)",
                        f"(({self.canHookshotC} & 1) << 17)",
                        f"(({self.echo} & 0x3F) << 11)",
                        f"(({self.lightSetting} & 0x1F) << 6)",
                        f"(({self.floorEffect} & 0x03) << 4)",
                        f"({self.material} & 0x0F)",
                    ]
                )
                + ")"
            )

    def getSurfaceTypeEntryC(self):
        if self.useMacros:
            return indent + "{ " + self.getSurfaceType0() + ", " + self.getSurfaceType1() + " },"
        else:
            return (indent + "{\n") + self.getSurfaceType0() + ",\n" + self.getSurfaceType1() + ("\n" + indent + "},")


@dataclass
class BgCamFuncData:  # CameraPosData
    pos: tuple[int, int, int]
    rot: tuple[int, int, int]
    fov: int
    roomImageOverrideBgCamIndex: int


@dataclass
class CrawlspaceData:
    points: list[tuple[int, int, int]] = field(default_factory=list)

    def getCrawlspacePointEntriesC(self):
        return "".join(indent + "{ " + f"{point[0]:6}, {point[1]:6}, {point[2]:6}" + " },\n" for point in self.points)


@dataclass
class BgCamInfo:
    setting: str
    count: int
    arrayIndex: int
    bgCamFuncDataList: list[BgCamFuncData]

    def getCamPosEntriesC(self):
        source = ""

        for camData in self.bgCamFuncDataList:
            source += (
                (indent + "{ " + ", ".join(f"{p:6}" for p in camData.pos) + " },\n")
                + (indent + "{ " + ", ".join(f"{r:6}" for r in camData.rot) + " },\n")
                + (indent + "{ " + f"{camData.fov:6}, {camData.roomImageOverrideBgCamIndex:6}, {-1:6}" + " },\n")
            )

        return source

    def getBgCamInfoEntryC(self, posDataName: str):
        ptr = f"&{posDataName}[{self.arrayIndex}]" if len(self.bgCamFuncDataList) > 0 else "NULL"
        return indent + "{ " + f"{self.setting}, {self.count}, {ptr}" + " },\n"


@dataclass
class WaterBox:
    position: tuple[int, int, int]
    scale: float
    emptyDisplaySize: float

    # Properties
    bgCamIndex: int
    lightIndex: int
    roomIndex: int
    setFlag19: bool

    xMin: int = None
    ySurface: int = None
    zMin: int = None
    xLength: int = None
    zLength: int = None

    useMacros: bool = True
    setFlag19C: str = None
    roomIndexC: str = None

    def __post_init__(self):
        self.setFlag19C = "1" if self.setFlag19 else "0"
        self.roomIndexC = f"0x{self.roomIndex:02X}" if self.roomIndex == 0x3F else f"{self.roomIndex}"

        # The scale ordering is due to the fact that scaling happens AFTER rotation.
        # Thus the translation uses Y-up, while the scale uses Z-up.
        xMax = round(self.position[0] + self.scale[0] * self.emptyDisplaySize)
        zMax = round(self.position[2] + self.scale[1] * self.emptyDisplaySize)

        self.xMin = round(self.position[0] - self.scale[0] * self.emptyDisplaySize)
        self.ySurface = round(self.position[1] + self.scale[2] * self.emptyDisplaySize)
        self.zMin = round(self.position[2] - self.scale[1] * self.emptyDisplaySize)
        self.xLength = xMax - self.xMin
        self.zLength = zMax - self.zMin

    def getWaterboxProperties(self):
        if self.useMacros:
            return f"WATERBOX_PROPERTIES({self.bgCamIndex}, {self.lightIndex}, {self.roomIndexC}, {self.setFlag19C})"
        else:
            return (
                "("
                + " | ".join(
                    prop
                    for prop in [
                        f"(({self.setFlag19C} & 1) << 19)",
                        f"(({self.roomIndexC} & 0x3F) << 13)",
                        f"(({self.lightIndex} & 0x1F) <<  8)",
                        f"(({self.bgCamIndex}) & 0xFF)",
                    ]
                )
                + ")"
            )

    def getWaterboxEntryC(self):
        return (
            (indent + "{ ")
            + f"{self.xMin}, {self.ySurface}, {self.zMin}, {self.xLength}, {self.zLength}, "
            + self.getWaterboxProperties()
            + " },"
        )


@dataclass
class Vertex:
    pos: tuple[int, int, int]

    def getVertexEntryC(self):
        return indent + "{ " + ", ".join(f"{p:6}" for p in self.pos) + " },"


@dataclass
class CollisionHeaderVertices:
    name: str
    vertexList: list[Vertex]

    def getVertexListC(self):
        vertData = CData()
        listName = f"Vec3s {self.name}[{len(self.vertexList)}]"

        # .h
        vertData.header = f"extern {listName};\n"

        # .c
        vertData.source = (
            (listName + " = {\n") + "\n".join(vertex.getVertexEntryC() for vertex in self.vertexList) + "\n};\n\n"
        )

        return vertData


@dataclass
class CollisionHeaderCollisionPoly:
    name: str
    polyList: list[CollisionPoly]

    def getCollisionPolyDataC(self):
        colPolyData = CData()
        listName = f"CollisionPoly {self.name}[{len(self.polyList)}]"

        # .h
        colPolyData.header = f"extern {listName};\n"

        # .c
        colPolyData.source = (
            (listName + " = {\n") + "\n".join(poly.getCollisionPolyEntryC() for poly in self.polyList) + "\n};\n\n"
        )

        return colPolyData


@dataclass
class CollisionHeaderSurfaceType:
    name: str
    surfaceTypeList: list[SurfaceType]

    def getSurfaceTypeDataC(self):
        surfaceData = CData()
        listName = f"SurfaceType {self.name}[{len(self.surfaceTypeList)}]"

        # .h
        surfaceData.header = f"extern {listName};\n"

        # .c
        surfaceData.source = (
            (listName + " = {\n") + "\n".join(poly.getSurfaceTypeEntryC() for poly in self.surfaceTypeList) + "\n};\n\n"
        )

        return surfaceData


@dataclass
class CollisionHeaderBgCamInfo:
    name: str
    posDataName: str
    bgCamInfoList: list[BgCamInfo]
    crawlspacePosList: list[CrawlspaceData]

    crawlspaceCount: int = 6
    arrayIdx: int = 0

    def __post_init__(self):
        if len(self.bgCamInfoList) > 0:
            self.arrayIdx = self.bgCamInfoList[-1].arrayIndex + self.crawlspaceCount

    def getCamPosListC(self):
        posData = CData()
        listName = f"Vec3s {self.posDataName}[]"

        # .h
        posData.header = f"extern {listName};"

        # .c
        posData.source = (
            (listName + " = {\n")
            + "".join(cam.getCamPosEntriesC() for cam in self.bgCamInfoList)
            + "".join(crawlspace.getCrawlspacePointEntriesC() for crawlspace in self.crawlspacePosList)
            + "};\n\n"
        )

        return posData

    def getCrawlspaceInfoEntries(self):
        source = ""

        for _ in self.crawlspacePosList:
            source += indent + "{ " + f"CAM_SET_CRAWLSPACE, 6, &{self.posDataName}[{self.arrayIdx}]" + " },\n"
            self.arrayIdx += self.crawlspaceCount

        return source

    def getBgCamInfoListC(self):
        bgCamInfoData = CData()
        listName = f"BgCamInfo {self.name}[]"

        # .h
        bgCamInfoData.header = f"extern {listName};"

        # .c
        bgCamInfoData.source = (
            (listName + " = {\n")
            + "".join(cam.getBgCamInfoEntryC(self.posDataName) for cam in self.bgCamInfoList)
            + self.getCrawlspaceInfoEntries()
            + "};\n\n"
        )

        return bgCamInfoData


@dataclass
class CollisionHeaderWaterBox:
    name: str
    waterboxList: list[WaterBox]

    def getWaterboxListC(self):
        wboxData = CData()
        listName = f"WaterBox {self.name}[{len(self.waterboxList)}]"

        # .h
        wboxData.header = f"extern {listName};\n"

        # .c
        wboxData.source = (
            (listName + " = {\n") + "\n".join(wBox.getWaterboxEntryC() for wBox in self.waterboxList) + "\n};\n\n"
        )

        return wboxData


@dataclass
class OOTSceneCollisionHeader:
    name: str
    minBounds: tuple[int, int, int] = None
    maxBounds: tuple[int, int, int] = None
    vertices: CollisionHeaderVertices = None
    collisionPoly: CollisionHeaderCollisionPoly = None
    surfaceType: CollisionHeaderSurfaceType = None
    bgCamInfo: CollisionHeaderBgCamInfo = None
    waterbox: CollisionHeaderWaterBox = None

    def getCollisionDataC(self):
        headerData = CData()
        colData = CData()
        varName = f"CollisionHeader {self.name}"

        vtxPtrLine = "0, NULL"
        colPolyPtrLine = "0, NULL"
        surfacePtrLine = "NULL"
        camPtrLine = "NULL"
        wBoxPtrLine = "0, NULL"

        if len(self.waterbox.waterboxList) > 0:
            colData.append(self.waterbox.getWaterboxListC())
            wBoxPtrLine = f"ARRAY_COUNT({self.waterbox.name}), {self.waterbox.name}"
        
        if len(self.bgCamInfo.bgCamInfoList) > 0 or len(self.bgCamInfo.crawlspacePosList) > 0:
            colData.append(self.bgCamInfo.getCamPosListC())
            colData.append(self.bgCamInfo.getBgCamInfoListC())
            camPtrLine = f"{self.bgCamInfo.name}"
        
        if len(self.surfaceType.surfaceTypeList) > 0:
            colData.append(self.surfaceType.getSurfaceTypeDataC())
            surfacePtrLine = f"{self.surfaceType.name}"

        if len(self.vertices.vertexList) > 0:
            colData.append(self.vertices.getVertexListC())
            vtxPtrLine = f"ARRAY_COUNT({self.vertices.name}), {self.vertices.name}"

        if len(self.collisionPoly.polyList) > 0:
            colData.append(self.collisionPoly.getCollisionPolyDataC())
            colPolyPtrLine = f"ARRAY_COUNT({self.collisionPoly.name}), {self.collisionPoly.name}"

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
