import bpy
import re

from mathutils import Vector
from dataclasses import dataclass
from mathutils import Matrix
from bpy.types import Object

from ....utility import CData, hexOrDecInt, checkIdentityRotation, indent, yUpToZUp
from ...utility import getObjectList
from ..utility import Utility


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
    def new(
        position: tuple[int, int, int],
        scale: float,
        emptyDisplaySize: float,
        bgCamIndex: int,
        lightIndex: int,
        roomIndex: int,
        setFlag19: bool,
        useMacros: bool,
    ):
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
            useMacros,
        )

    @staticmethod
    def from_data(raw_data: str, not_zapd_assets: bool):
        if not_zapd_assets:
            regex = r"(.*?)\s*,\s*WATERBOX_PROPERTIES\((.*?)\)"
        else:
            regex = r"(.*?)\s*,\s*(0x.*),?"

        match = re.search(regex, raw_data, re.DOTALL)
        assert match is not None

        pos_scale = [hexOrDecInt(value) for value in match.group(1).split(",")]

        if not_zapd_assets:
            params = match.group(2).split(",")
            properties = [
                hexOrDecInt(params[0]),
                hexOrDecInt(params[1]),
                params[2],
                params[3],
            ]
        else:
            params = hexOrDecInt(match.group(2))
            properties = [
                ((params >> 0) & 0xFF),  # bgCamIndex
                ((params >> 8) & 0x1F),  # lightIndex
                str(((params >> 13) & 0x3F)),  # room
                str(((params >> 19) & 1) == 1).lower(),  # setFlag19
            ]

        return WaterBox(
            properties[0],
            properties[1],
            properties[2],
            properties[3],
            pos_scale[0],
            pos_scale[1],
            pos_scale[2],
            pos_scale[3],
            pos_scale[4],
            not_zapd_assets,
        )

    def get_blender_position(self):
        pos = [self.xMin, self.ySurface, self.zMin]
        return yUpToZUp @ Vector([value / bpy.context.scene.ootBlenderScale for value in pos])

    def get_blender_scale(self) -> list[int]:
        scale = [self.xLength, self.zLength]
        return [value / bpy.context.scene.ootBlenderScale for value in scale]

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
            pos, _, scale, orientedRot = Utility.getConvertedTransform(transform, dataHolder, waterboxObj, True)
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
