from dataclasses import dataclass
from mathutils import Vector
from typing import List

@dataclass
class OcclusionPlaneCandidate:
    v0: Vector
    v1: Vector
    v2: Vector
    v3: Vector
    weight: float


class OcclusionPlaneCandidatesList:
    def __init__(self, ownerName):
        self.planes: List[OcclusionPlaneCandidate] = []
        self.name: str = ownerName + "_occlusionPlaneCandidates"
