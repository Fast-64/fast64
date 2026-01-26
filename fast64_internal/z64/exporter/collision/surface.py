import bpy
import math

from dataclasses import dataclass, field
from bpy.types import Material
from typing import Optional

from ....utility import CData, indent
from ....game_data import game_data
from ...collision.properties import OOTMaterialCollisionProperty
from ..utility import Utility


@dataclass(unsafe_hash=True)
class SurfaceType:
    """This class defines a single surface type"""

    # surface type 0
    bgCamIndex: int
    exitIndex: int
    floorType: str
    unk18: int  # unused?
    wallType: str
    floorProperty: str
    isSoft: bool
    isHorseBlocked: bool

    # surface type 1
    material: str
    floorEffect: str
    lightSetting: int
    echo: int
    canHookshot: bool
    conveyorSpeed: int | str
    conveyorDirection: int
    isWallDamage: bool  # unk27

    useMacros: bool
    data_material: Optional[Material] = field(init=False, default=None)

    @staticmethod
    def new(col_props: OOTMaterialCollisionProperty, use_macros: bool, material: Optional[Material] = None):
        use_conveyor = col_props.conveyorOption != "None"
        if use_conveyor:
            if col_props.conveyorSpeed == "Custom":
                conveyor_speed = col_props.conveyorSpeedCustom
            else:
                conveyor_speed = int(col_props.conveyorSpeed, base=16) + (4 if col_props.conveyorKeepMomentum else 0)
        else:
            conveyor_speed = 0

        new_type = SurfaceType(
            col_props.cameraID,
            col_props.exitID,
            Utility.getPropValue(col_props, "floorProperty"),
            0,  # unused?
            Utility.getPropValue(col_props, "wallSetting"),
            Utility.getPropValue(col_props, "floorSetting"),
            col_props.decreaseHeight,
            col_props.eponaBlock,
            Utility.getPropValue(col_props, "sound"),
            Utility.getPropValue(col_props, "terrain"),
            col_props.lightingSetting,
            int(col_props.echo, base=16),
            col_props.hookshotable,
            conveyor_speed,
            int(col_props.conveyorRotation / (2 * math.pi) * 0x3F) if use_conveyor else 0,
            col_props.isWallDamage,
            use_macros,
        )

        new_type.data_material = material
        return new_type

    @staticmethod
    def from_hex(surface0: int, surface1: int):
        return SurfaceType(
            ((surface0 >> 0) & 0xFF),
            ((surface0 >> 8) & 0x1F),
            game_data.z64.enums.enumByKey["floor_type"].item_by_index[((surface0 >> 13) & 0x1F)].id,
            ((surface0 >> 18) & 0x07),
            game_data.z64.enums.enumByKey["wall_type"].item_by_index[((surface0 >> 21) & 0x1F)].id,
            game_data.z64.enums.enumByKey["floor_property"].item_by_index[((surface0 >> 26) & 0x0F)].id,
            ((surface0 >> 30) & 1) > 0,
            ((surface0 >> 31) & 1) > 0,
            game_data.z64.enums.enumByKey["surface_material"].item_by_index[((surface1 >> 0) & 0x0F)].id,
            game_data.z64.enums.enumByKey["floor_effect"].item_by_index[((surface1 >> 4) & 0x03)].id,
            ((surface1 >> 6) & 0x1F),
            ((surface1 >> 11) & 0x3F),
            ((surface1 >> 17) & 1) > 0,
            game_data.z64.enums.enumByKey["conveyor_speed"].item_by_index[((surface1 >> 18) & 0x07)].id,
            ((surface1 >> 21) & 0x3F),
            ((surface1 >> 27) & 1) > 0,
            bpy.context.scene.fast64.oot.useDecompFeatures,
        )

    def getIsSoftC(self):
        return "1" if self.isSoft else "0"

    def getIsHorseBlockedC(self):
        return "1" if self.isHorseBlocked else "0"

    def getCanHookshotC(self):
        return "1" if self.canHookshot else "0"

    def getIsWallDamageC(self):
        return "1" if self.isWallDamage else "0"

    def getSurfaceType0(self):
        """Returns surface type properties for the first element of the data array"""

        if self.useMacros:
            return (
                ("SURFACETYPE0(")
                + f"{self.bgCamIndex}, {self.exitIndex}, {self.floorType}, {self.unk18}, "
                + f"{self.wallType}, {self.floorProperty}, {self.getIsSoftC()}, {self.getIsHorseBlockedC()}"
                + ")"
            )
        else:
            return (
                (indent * 2 + "(")
                + " | ".join(
                    prop
                    for prop in [
                        f"(({self.getIsHorseBlockedC()} & 1) << 31)",
                        f"(({self.getIsSoftC()} & 1) << 30)",
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
                + f"{self.getCanHookshotC()}, {self.conveyorSpeed}, {self.conveyorDirection}, {self.getIsWallDamageC()}"
                + ")"
            )
        else:
            return (
                (indent * 2 + "(")
                + " | ".join(
                    prop
                    for prop in [
                        f"(({self.getIsWallDamageC()} & 1) << 27)",
                        f"(({self.conveyorDirection} & 0x3F) << 21)",
                        f"(({self.conveyorSpeed} & 0x07) << 18)",
                        f"(({self.getCanHookshotC()} & 1) << 17)",
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
