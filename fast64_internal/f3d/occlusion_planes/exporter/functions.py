import bpy
import mathutils

from ....utility import PluginError
from .classes import OcclusionPlaneCandidate, OcclusionPlaneCandidatesList


def addOcclusionQuads(obj, candidatesList, includeChildren, transformMatrix):
    if obj.type == "MESH" and obj.is_occlusion_planes:
        obj.data.calc_loop_triangles()
        
