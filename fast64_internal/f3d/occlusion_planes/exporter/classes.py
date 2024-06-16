from dataclasses import dataclass
from mathutils import Vector
from typing import List

from .....utility import CData, indent


@dataclass
class OcclusionPlaneCandidate:
    v0: Vector
    v1: Vector
    v2: Vector
    v3: Vector
    weight: float

    def to_c(self):
        def occVertexToC(vertex: Vector):
            return indent * 3 + "{" + ", ".join([str(int(round(a))) for a in vertex]) + "},\n"

        return (
            indent
            + "{\n"
            + indent * 2
            + "{\n"
            + "".join(map(occVertexToC, [self.v0, self.v1, self.v2, self.v3]))
            + indent * 2
            + "},\n"
            + indent * 2
            + str(self.weight)
            + "f\n"
            + indent
            + "},\n"
        )


class OcclusionPlaneCandidatesList:
    def __init__(self, ownerName):
        self.planes: List[OcclusionPlaneCandidate] = []
        self.name: str = ownerName + "_occlusionPlaneCandidates"

    def to_c(self):
        cdata = CData()
        if len(self.planes) > 0:
            name = "OcclusionPlaneCandidate " + self.name + "[" + str(len(self.planes)) + "]"
            cdata.header = "extern " + name + ";\n"
            cdata.source = name + " = {\n" + "".join(occCandidateToC(candidate) for candidate in self.planes) + "};\n\n"
        return cdata
