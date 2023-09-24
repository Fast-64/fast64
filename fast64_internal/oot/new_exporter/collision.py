from dataclasses import dataclass
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
    name: str
    pos: tuple[int, int, int]
    rot: tuple[int, int, int]
    fov: int
    roomImageOverrideBgCamIndex: int
    timer: int
    flags: int
    unk_10: int = 0  # unused


@dataclass
class CrawlspaceData:
    name: str
    points: list[tuple[int, int, int]]


@dataclass
class BgCamInfo:
    name: str
    setting: int
    count: int

    # Export one of these but never both, see BgCamInfo in z64bgcheck.h
    bgCamFuncDataList: list[BgCamFuncData]
    crawlspaceList: list[CrawlspaceData]


@dataclass
class WaterBox:
    name: str
    xMin: int
    ySurface: int
    zMin: int
    xLength: int
    zLength: int

    # Properties
    bgCamIndex: int
    lightIndex: int
    roomIndex: int
    setFlag19: bool

    def getWaterboxProperties(self):
        return (
            "("
            + " | ".join(
                prop
                for prop in [
                    f"(({'1' if self.setFlag19 else '0'} & 1) << 19)",
                    f"(({self.roomIndex} & 0x3F) << 13)",
                    f"(({self.lightIndex} & 0x1F) <<  8)",
                    f"(({self.bgCamIndex}) & 0xFF)",
                ]
            )
            + ")"
        )


@dataclass
class Vertex:
    pos: tuple[int, int, int]

    def getVertexEntryC(self):
        return indent + "{ " + ", ".join(f"{p}" for p in self.pos) + " },"


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
    bgCamInfoList: list[BgCamInfo]


@dataclass
class CollisionHeaderWaterBox:
    name: str
    waterboxList: list[WaterBox]


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
        colData = CData()

        if len(self.vertices.vertexList) > 0:
            colData.append(self.vertices.getVertexListC())

        if len(self.collisionPoly.polyList) > 0:
            colData.append(self.collisionPoly.getCollisionPolyDataC())

        if len(self.surfaceType.surfaceTypeList) > 0:
            colData.append(self.surfaceType.getSurfaceTypeDataC())

        return colData
