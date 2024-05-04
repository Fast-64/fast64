from mathutils import Vector

from ...exporter import OcclusionPlaneCandidate, OcclusionPlaneCandidatesList
from .....utility import CData


def occVertexToC(vertex: Vector):
    return "\t\t\t{" + ", ".join([str(int(round(a))) for a in vertex]) + "},\n"


def occCandidateToC(candidate: OcclusionPlaneCandidate):
    return "\t{\n\t\t{\n" + "".join(map(occVertexToC, [
        candidate.v0, candidate.v1, candidate.v2, candidate.v3
    ])) + "\t\t},\n\t\t" + str(candidate.weight) + "f\n\t},\n"


def occCandidatesListToC(candidatesList: OcclusionPlaneCandidatesList):
    cdata = CData()
    if len(candidatesList.planes) > 0:
        name = "OcclusionPlaneCandidate " + candidatesList.name + "[" + \
            str(len(candidatesList.planes)) + "]"
        cdata.header = "extern " + name + ";\n"
        cdata.source = name + " = {\n" + \
            "".join(occCandidateToC(candidate) for candidate in candidatesList.planes) + \
            "};\n\n"
    return cdata
