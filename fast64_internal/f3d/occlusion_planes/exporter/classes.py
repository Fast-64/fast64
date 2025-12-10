from dataclasses import dataclass
from mathutils import Vector
from bpy.types import Object

from ....utility import CData, indent


@dataclass
class OcclusionPlaneCandidate:
    verts: tuple[Vector, Vector, Vector, Vector]
    weight: float

    def vertex_to_c(self, vertex: Vector, indent_char: str):
        coords = ", ".join([str(round(a)) for a in vertex])
        return f"{indent_char}{{{coords}}},\n"

    def vertices_to_c(self, indent_char: str):
        return "".join(map(self.vertex_to_c, self.verts, [indent_char] * 4))

    def to_c(self, indent_char: str) -> str:
        return (
            f"{indent_char}{{\n"
            f"{indent_char * 2}{{\n"
            f"{self.vertices_to_c(indent_char * 3)}"
            f"{indent_char * 2}}},\n"
            f"{indent_char * 2}{self.weight}f\n"
            f"{indent_char}}},\n"
        )


class OcclusionPlaneCandidatesList:
    def __init__(self, owner_name: str):
        self.planes: list[OcclusionPlaneCandidate] = []
        self.name: str = owner_name + "_occlusionPlaneCandidates"
        self.indent_char: str = indent

    def add_plane(self, obj: Object, verts: tuple[Vector, Vector, Vector, Vector], weight: float):
        self.planes.append(OcclusionPlaneCandidate(verts, weight))

    def to_c(self) -> CData:
        cdata = CData()
        if len(self.planes) > 0:
            name = f"OcclusionPlaneCandidate {self.name}[{len(self.planes)}]"
            cdata.header = f"extern {name};\n"

            plane_c_code = "".join(candidate.to_c(self.indent_char) for candidate in self.planes)
            cdata.source = f"{name} = {{\n{plane_c_code}}};\n\n"
        return cdata
