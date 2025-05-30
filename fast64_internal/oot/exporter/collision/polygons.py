from dataclasses import dataclass, field
from typing import Optional
from mathutils import Vector

from ....utility import PluginError, CData, hexOrDecInt, indent


@dataclass
class CollisionPoly:
    """This class defines a single collision poly"""

    indices: list[int]
    ignoreCamera: bool
    ignoreEntity: bool
    ignoreProjectile: bool
    isLandConveyor: bool
    normal: Vector
    dist: int
    useMacros: bool

    type: Optional[int] = field(init=False, default=None)

    @staticmethod
    def from_data(poly_data: list[str], use_macros: bool):
        if use_macros:
            # format: [ [vtxId, flags], [vtxId, flags], [vtxId, flags] ] (str)
            vtx = [
                poly_data[1].removeprefix("COLPOLY_VTX(").removesuffix(")").split(","),
                poly_data[2].removeprefix("COLPOLY_VTX(").removesuffix(")").split(","),
                poly_data[3].removeprefix("COLPOLY_VTX(").removesuffix(")").split(","),
            ]

            new_poly = CollisionPoly(
                [hexOrDecInt(vtx[0][0]), hexOrDecInt(vtx[1][0]), hexOrDecInt(vtx[2][0])],
                "COLPOLY_IGNORE_CAMERA" in vtx[0][1],
                "COLPOLY_IGNORE_ENTITY" in vtx[0][1],
                "COLPOLY_IGNORE_PROJECTILES" in vtx[0][1],
                "COLPOLY_IS_FLOOR_CONVEYOR" in vtx[1][1],
                Vector(
                    (
                        float(poly_data[4].removeprefix("COLPOLY_SNORMAL(").removesuffix(")")),
                        float(poly_data[5].removeprefix("COLPOLY_SNORMAL(").removesuffix(")")),
                        float(poly_data[6].removeprefix("COLPOLY_SNORMAL(").removesuffix(")")),
                    )
                ),
                hexOrDecInt(poly_data[7]),
                use_macros,
            )
        else:

            def get_normal(value: int):
                return int.from_bytes(value.to_bytes(2, "big", signed=value < 0x8000), "big", signed=True) / 0x7FFF

            vtx1 = hexOrDecInt(poly_data[1])
            vtx2 = hexOrDecInt(poly_data[2])
            vtx3 = hexOrDecInt(poly_data[3])

            # format: [ [vtxId, flags], [vtxId, flags], [vtxId, flags] ] (int)
            vtx = [
                [vtx1 & 0x1FFF, (vtx1 >> 13) & 7],
                [vtx2 & 0x1FFF, (vtx2 >> 13) & 7],
                [vtx3 & 0x1FFF, (vtx3 >> 13) & 7],
            ]

            new_poly = CollisionPoly(
                [vtx[0][0], vtx[1][0], vtx[2][0]],
                ((vtx[0][1] >> (1 << 0)) & 1) == 1,
                ((vtx[0][1] >> (1 << 1)) & 1) == 1,
                ((vtx[0][1] >> (1 << 2)) & 1) == 1,
                ((vtx[1][1] >> (1 << 0)) & 1) == 1,
                Vector(
                    (
                        get_normal(hexOrDecInt(poly_data[4])),
                        get_normal(hexOrDecInt(poly_data[5])),
                        get_normal(hexOrDecInt(poly_data[6])),
                    )
                ),
                hexOrDecInt(poly_data[7]),
                use_macros,
            )

        new_poly.type = hexOrDecInt(poly_data[0])
        return new_poly

    def __post_init__(self):
        for i, val in enumerate(self.normal):
            if val < -1.0 or val > 1.0:
                raise PluginError(f"ERROR: Invalid value for normal {['X', 'Y', 'Z'][i]}! (``{val}``)")

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
        if self.isLandConveyor:
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
                    ("{ " + ", ".join(f"COLPOLY_SNORMAL({val})" for val in self.normal) + " }"),
                    f"{self.dist}",
                )
            )
            + " },"
        )


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
