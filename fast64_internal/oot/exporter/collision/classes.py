from dataclasses import dataclass
from mathutils import Vector
from ....utility import PluginError, indent


@dataclass
class CollisionPoly:
    """This class defines a single collision poly"""

    indices: list[int]
    ignoreCamera: bool
    ignoreEntity: bool
    ignoreProjectile: bool
    enableConveyor: bool
    normal: Vector
    dist: int
    useMacros: bool
    type: int = None

    def getFlags_vIA(self):
        """Returns the value of ``flags_vIA``"""

        vtxId = self.indices[0] & 0x1FFF
        if self.ignoreProjectile or self.ignoreEntity or self.ignoreCamera:
            flag1 = ("COLPOLY_IGNORE_PROJECTILES" if self.useMacros else "(1 << 2)") if self.ignoreProjectile else ""
            flag2 = ("COLPOLY_IGNORE_ENTITY" if self.useMacros else "(1 << 1)") if self.ignoreEntity else ""
            flag3 = ("COLPOLY_IGNORE_CAMERA" if self.useMacros else "(1 << 0)") if self.ignoreCamera else ""
            flags = "(" + " | ".join(flag for flag in [flag1, flag2, flag3] if len(flag) > 0) + ")"
        else:
            flags = "COLPOLY_IGNORE_NONE" if self.useMacros else "0"

        return f"COLPOLY_VTX({vtxId}, {flags})" if self.useMacros else f"((({flags} & 7) << 13) | ({vtxId} & 0x1FFF))"

    def getFlags_vIB(self):
        """Returns the value of ``flags_vIB``"""

        vtxId = self.indices[1] & 0x1FFF
        if self.enableConveyor:
            flags = "COLPOLY_IS_FLOOR_CONVEYOR" if self.useMacros else "(1 << 0)"
        else:
            flags = "COLPOLY_IGNORE_NONE" if self.useMacros else "0"
        return f"COLPOLY_VTX({vtxId}, {flags})" if self.useMacros else f"((({flags} & 7) << 13) | ({vtxId} & 0x1FFF))"

    def getEntryC(self):
        """Returns an entry for the collision poly array"""

        vtxId = self.indices[2] & 0x1FFF
        if self.type is None:
            raise PluginError("ERROR: Surface Type missing!")
        return (
            (indent + "{ ")
            + ", ".join(
                (
                    f"{self.type}",
                    self.getFlags_vIA(),
                    self.getFlags_vIB(),
                    f"COLPOLY_VTX_INDEX({vtxId})" if self.useMacros else f"{vtxId} & 0x1FFF",
                    ", ".join(f"COLPOLY_SNORMAL({val})" for val in self.normal),
                    f"{self.dist}",
                )
            )
            + " },"
        )


@dataclass
class SurfaceType:
    """This class defines a single surface type"""

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
    useMacros: bool
    isSoftC: str = None
    isHorseBlockedC: str = None
    canHookshotC: str = None
    isWallDamageC: str = None

    def __hash__(self):
        return hash(
            (
                self.bgCamIndex,
                self.exitIndex,
                self.floorType,
                self.unk18,
                self.wallType,
                self.floorProperty,
                self.isSoft,
                self.isHorseBlocked,
                self.material,
                self.floorEffect,
                self.lightSetting,
                self.echo,
                self.canHookshot,
                self.conveyorSpeed,
                self.conveyorDirection,
                self.isWallDamage,
                self.conveyorKeepMomentum,
            )
        )

    def __post_init__(self):
        if self.conveyorKeepMomentum:
            self.conveyorSpeed += 4

        self.isSoftC = "1" if self.isSoft else "0"
        self.isHorseBlockedC = "1" if self.isHorseBlocked else "0"
        self.canHookshotC = "1" if self.canHookshot else "0"
        self.isWallDamageC = "1" if self.isWallDamage else "0"

    def getSurfaceType0(self):
        """Returns surface type properties for the first element of the data array"""

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
        """Returns surface type properties for the second element of the data array"""

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

    def getEntryC(self):
        """Returns an entry for the surface type array"""

        if self.useMacros:
            return indent + "{ " + self.getSurfaceType0() + ", " + self.getSurfaceType1() + " },"
        else:
            return (indent + "{\n") + self.getSurfaceType0() + ",\n" + self.getSurfaceType1() + ("\n" + indent + "},")


@dataclass
class CrawlspaceCamera:
    """This class defines camera data for crawlspaces, if used"""

    points: list[tuple[int, int, int]]
    camIndex: int
    arrayIndex: int = 0

    def __post_init__(self):
        self.points = [self.points[0], self.points[0], self.points[0], self.points[1], self.points[1], self.points[1]]

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
    arrayIndex: int = 0
    hasPosData: bool = False

    def __post_init__(self):
        self.hasPosData = self.data is not None

    def getInfoEntryC(self, posDataName: str):
        """Returns an entry for the camera information array"""
        ptr = f"&{posDataName}[{self.arrayIndex}]" if self.hasPosData else "NULL"
        return indent + "{ " + f"{self.setting}, {self.count}, {ptr}" + " },\n"


@dataclass
class WaterBox:
    """This class defines waterbox data"""

    position: tuple[int, int, int]
    scale: float
    emptyDisplaySize: float

    # Properties
    bgCamIndex: int
    lightIndex: int
    roomIndex: int
    setFlag19: bool

    useMacros: bool
    xMin: int = None
    ySurface: int = None
    zMin: int = None
    xLength: int = None
    zLength: int = None

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

    def getProperties(self):
        """Returns the waterbox properties"""

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

    def getEntryC(self):
        """Returns a waterbox entry"""

        return (
            (indent + "{ ")
            + f"{self.xMin}, {self.ySurface}, {self.zMin}, {self.xLength}, {self.zLength}, "
            + self.getProperties()
            + " },"
        )


@dataclass
class Vertex:
    """This class defines a vertex data"""

    pos: tuple[int, int, int]

    def getEntryC(self):
        """Returns a vertex entry"""

        return indent + "{ " + ", ".join(f"{p:6}" for p in self.pos) + " },"
