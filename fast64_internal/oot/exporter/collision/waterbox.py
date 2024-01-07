from dataclasses import dataclass, field
from typing import Optional
from mathutils import Matrix
from bpy.types import Object
from ....utility import CData, checkIdentityRotation, indent
from ..base import Base


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
    xMin: Optional[int] = None
    ySurface: Optional[int] = None
    zMin: Optional[int] = None
    xLength: Optional[int] = None
    zLength: Optional[int] = None

    setFlag19C: Optional[str] = None
    roomIndexC: Optional[str] = None

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
class WaterBoxes(Base):
    """This class defines the array of waterboxes"""

    sceneObj: Object
    transform: Matrix
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
