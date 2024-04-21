from mathutils import Vector

from ...exporter import OcclusionPlaneCandidate, OcclusionPlaneCandidatesList


def occVertexToC(vertex: Vector):
    return "\t\t\t{" + ", ".join([str(round(a)) for a in vertex]) + "},\n"


def occCandidateToC(candidate: OcclusionPlaneCandidate):
    return "\t{\n" + map(occVertexToC, [
        candidate.v0, candidate.v1, candidate.v2, candidate.v3
    ]) + "\t\t" + str(candidate.weight) + "f\n},\n"


def occCandidatesListToC(candidatesList: OcclusionPlaneCandidatesList):
    cdata = CData()
    name = "OcclusionPlaneCandidate " + candidatesList.name + "[" + \
        str(len(candidatesList.planes)) + "]"
    cdata.header = "extern " + name + ";\n"
    cdata.source = name + " = {\n" + \
        "".join(occCandidateToC(candidate) for candidate in candidatesList.planes) + \
        "};\n\n"
    return cdata
