from dataclasses import dataclass, field
from typing import Optional
from mathutils import Matrix
from bpy.types import Object
from ...oot_utility import getObjectList
from ....utility import CData, checkIdentityRotation, indent
from ..base import Utility


@dataclass
class WaterBox:
    """This class defines waterbox data"""

    # Properties
    bgCamIndex: int
    lightIndex: int
    roomIndexC: str
    setFlag19C: str

    xMin: int
    ySurface: int
    zMin: int
    xLength: int
    zLength: int

    useMacros: bool

    @staticmethod
    def new(position: tuple[int, int, int], scale: float, emptyDisplaySize: float, bgCamIndex: int, lightIndex: int, roomIndex: int, setFlag19: bool, useMacros: bool):
        # The scale ordering is due to the fact that scaling happens AFTER rotation.
        # Thus the translation uses Y-up, while the scale uses Z-up.
        xMax = round(position[0] + scale[0] * emptyDisplaySize)
        zMax = round(position[2] + scale[1] * emptyDisplaySize)
        xMin = round(position[0] - scale[0] * emptyDisplaySize)
        zMin = round(position[2] - scale[1] * emptyDisplaySize)

        return WaterBox(
            bgCamIndex, 
            lightIndex, 
            f"0x{roomIndex:02X}" if roomIndex == 0x3F else f"{roomIndex}",
            "1" if setFlag19 else "0",
            xMin,
            round(position[1] + scale[2] * emptyDisplaySize),
            zMin,
            xMax - xMin,
            zMax - zMin,
            useMacros
        )

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
class WaterBoxes:
    """This class defines the array of waterboxes"""

    name: str
    waterboxList: list[WaterBox]

    @staticmethod
    def new(name: str, dataHolder: Object, transform: Matrix, useMacros: bool):
        waterboxList: list[WaterBox] = []
        waterboxObjList = getObjectList(dataHolder.children_recursive, "EMPTY", "Water Box")
        for waterboxObj in waterboxObjList:
            emptyScale = waterboxObj.empty_display_size
            pos, _, scale, orientedRot = Utility.getConvertedTransform(
                transform, dataHolder, waterboxObj, True
            )
            checkIdentityRotation(waterboxObj, orientedRot, False)

            wboxProp = waterboxObj.ootWaterBoxProperty

            # temp solution
            roomObj = None
            if dataHolder.type == "EMPTY" and dataHolder.ootEmptyType == "Scene":
                for obj in dataHolder.children_recursive:
                    if obj.type == "EMPTY" and obj.ootEmptyType == "Room":
                        for o in obj.children_recursive:
                            if o == waterboxObj:
                                roomObj = obj
                                break

            waterboxList.append(
                WaterBox.new(
                    pos,
                    scale,
                    emptyScale,
                    wboxProp.camera,
                    wboxProp.lighting,
                    roomObj.ootRoomHeader.roomIndex if roomObj is not None else 0x3F,
                    wboxProp.flag19,
                    useMacros,
                )
            )
        return WaterBoxes(name, waterboxList)

    def getC(self):
        wboxData = CData()
        listName = f"WaterBox {self.name}[{len(self.waterboxList)}]"

        # .h
        wboxData.header = f"extern {listName};\n"

        # .c
        wboxData.source = (listName + " = {\n") + "\n".join(wBox.getEntryC() for wBox in self.waterboxList) + "\n};\n\n"

        return wboxData
