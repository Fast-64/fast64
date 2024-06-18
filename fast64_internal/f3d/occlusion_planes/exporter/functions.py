import bpy
from mathutils import Vector, Matrix

from ....utility import PluginError, colorToLuminance, gammaCorrect
from .classes import OcclusionPlaneCandidate, OcclusionPlaneCandidatesList
from ...f3d_writer import getColorLayer


def addOcclusionQuads(
    obj: bpy.types.Object,
    candidatesList: OcclusionPlaneCandidatesList,
    includeChildren: bool,
    transformRelToScene: Matrix,
):
    if obj.type == "MESH" and obj.is_occlusion_planes:
        mesh = obj.data
        color_layer = getColorLayer(mesh, layer="Col")
        if not color_layer:
            raise PluginError(
                f'Occlusion planes mesh {obj.name} must have a vertex colors layer named "Col", which you paint the weight for each plane into.'
            )
        for polygon in mesh.polygons:
            # Weight is the average of the luminance across the four corners
            weight = 0.0
            verts = []
            if polygon.loop_total != 4:
                raise PluginError(
                    f"Occlusion planes mesh {obj.name} contains a polygon with {polygon.loop_total} verts. Occlusion planes must be quads."
                )
            for loopIndex in polygon.loop_indices:
                loop = mesh.loops[loopIndex]
                weight += colorToLuminance(gammaCorrect(color_layer[loop.index].color))
                verts.append(transformRelToScene @ obj.matrix_world @ mesh.vertices[loop.vertex_index].co)
            weight *= 0.25
            # Check that the quad is planar. Are the normals to the two tris forming
            # halves of the quad pointing in the same direction? If either tri is
            # degenerate, it's OK.
            edge1 = (verts[1] - verts[0]).normalized()
            midA = (verts[2] - verts[0]).normalized()
            edge3 = (verts[3] - verts[0]).normalized()
            normal1 = edge1.cross(midA)
            normal2 = midA.cross(edge3)
            if (
                normal1.length > 0.001
                and normal2.length > 0.001
                and normal1.normalized().dot(normal2.normalized()) < 0.999
            ):
                raise PluginError(f"Occlusion planes mesh {obj.name} contains a quad which is not planar (flat).")
            # Check that the quad is convex. Are the cross products at each corner
            # all pointing in the same direction?
            edge01 = verts[1] - verts[0]
            edge12 = verts[2] - verts[1]
            edge23 = verts[3] - verts[2]
            edge30 = verts[0] - verts[3]
            cross1 = edge01.cross(edge12)
            cross2 = edge12.cross(edge23)
            cross3 = edge23.cross(edge30)
            cross0 = edge30.cross(edge01)
            if cross0.dot(cross1) < 0.0 or cross0.dot(cross2) < 0.0 or cross0.dot(cross3) < 0.0:
                raise PluginError(f"Occlusion planes mesh {obj.name} contains a quad which is not convex.")
            candidatesList.planes.append(OcclusionPlaneCandidate(verts[3], verts[2], verts[1], verts[0], weight))

    if includeChildren:
        for child in obj.children:
            addOcclusionQuads(child, candidatesList, includeChildren, transformRelToScene)
