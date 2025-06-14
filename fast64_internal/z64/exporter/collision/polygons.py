from dataclasses import dataclass, field
from typing import Optional
from mathutils import Vector
from ....utility import PluginError, CData, indent


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
