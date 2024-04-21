from dataclasses import dataclass
from mathutils import Vector
from typing import List

@dataclass
class OcclusionPlaneCandidate:
    v0, v1, v2, v3: Vector
    weight: float


class OcclusionPlaneCandidatesList:
    def __init__(self):
        self.planes: List[OcclusionPlaneCandidate] = []
        self.name: str = ""
