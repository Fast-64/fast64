from typing import Union, Optional, Callable, Any, List
from dataclasses import dataclass
import functools
import bpy, mathutils, os, re, copy, math
from mathutils import Vector
from math import ceil
from bpy.utils import register_class, unregister_class

from .f3d_enums import *
from .f3d_material import (
    all_combiner_uses,
    getMaterialScrollDimensions,
    isTexturePointSampled,
    RDPSettings,
)
from .f3d_texture_writer import MultitexManager, TileLoad, maybeSaveSingleLargeTextureSetup
from .f3d_gbi import *
from .f3d_bleed import BleedGraphics

from ..utility import *


def getColorLayer(mesh: bpy.types.Mesh, layer="Col"):
    if layer in mesh.attributes and getattr(mesh.attributes[layer], "data", None):
        return mesh.attributes[layer].data
    if layer in mesh.vertex_colors:
        return mesh.vertex_colors[layer].data
    return None


def getEdgeToFaceDict(mesh):
    edgeDict = {}
    for face in mesh.loop_triangles:
        for edgeKey in face.edge_keys:
            if edgeKey not in edgeDict:
                edgeDict[edgeKey] = []
            if face not in edgeDict[edgeKey]:
                edgeDict[edgeKey].append(face)
    return edgeDict


def getVertToFaceDict(mesh):
    vertDict = {}
    for face in mesh.loop_triangles:
        for vertIndex in face.vertices:
            if vertIndex not in vertDict:
                vertDict[vertIndex] = []
            if face not in vertDict[vertIndex]:
                vertDict[vertIndex].append(face)
    return vertDict


def getLoopFromVert(inputIndex, face):
    for i in range(len(face.vertices)):
        if face.vertices[i] == inputIndex:
            return face.loops[i]


class VertexGroupInfo:
    def __init__(self):
        self.vertexGroups = {}  # vertex index : vertex group
        self.vertexGroupToLimb = {}


class MeshInfo:
    def __init__(self):
        self.vert = {}  # all faces connected to a vert
        self.edge = {}  # all faces connected to an edge
        self.f3dVert = {}  # f3d vertex of a given loop
        self.edgeValid = {}  # bool given two faces
        self.validNeighbors = {}  # all neighbors of a face with a valid connecting edge
        self.texDimensions = {}  # texture dimensions for each material

        self.vertexGroupInfo = None


def get_original_name(obj: bpy.types.Object):
    return getattr(obj, "original_name", obj.name)


def getInfoDict(obj: bpy.types.Object):
    try:
        return getInfoDict_impl(obj)
    except:
        print(f"Error in getInfoDict_impl(obj name = {get_original_name(obj)!r})")
        raise


def check_face_materials(
    obj_name: str,
    material_slots: "bpy.types.bpy_prop_collection[bpy.types.MaterialSlot]",
    faces: "bpy.types.MeshPolygons | bpy.types.MeshLoopTriangles",
):
    """
    Check if all faces are correctly assigned to a F3D material
    Raise a PluginError with a helpful message if not.

    Somehow these two different collections of faces MeshPolygons and MeshLoopTriangles
    behave differently / store different info, fast64 uses both so check both
    """
    for face in faces:
        material_index = face.material_index
        if material_index >= len(material_slots):
            # Not supposed to be possible with how Blender behaves when removing material slots,
            # but has happened to some people somehow.
            raise PluginError(
                f"Mesh object {obj_name} has faces"
                " with an invalid material slot assigned."
                " Assign the faces to a valid slot."
                f" (0-indexed: slot {material_index}, aka the {material_index+1}th slot)."
            )
        material = material_slots[material_index].material
        if material is None:
            raise PluginError(
                f"Mesh object {obj_name} has faces"
                f" assigned to a material slot which isn't set to any material."
                " Set a material for the slot or assign the faces to an actual material."
                f" (0-indexed: slot {material_index}, aka the {material_index+1}th slot)."
            )
        if not material.is_f3d:
            raise PluginError(
                f"Mesh object {obj_name} has faces"
                f" assigned to a material which is not a F3D material: {material.name}"
            )


def getInfoDict_impl(obj: bpy.types.Object):
    mesh: bpy.types.Mesh = obj.data
    material_slots = obj.material_slots
    if len(mesh.materials) == 0 or len(material_slots) == 0:
        raise PluginError(f"Mesh object {get_original_name(obj)} does not have any Fast3D materials.")

    # check mesh.polygons, used by fixLargeUVs
    check_face_materials(get_original_name(obj), material_slots, mesh.polygons)
    fixLargeUVs(obj)

    mesh.calc_loop_triangles()
    # check mesh.loop_triangles (now that we computed them), used below
    check_face_materials(get_original_name(obj), material_slots, mesh.loop_triangles)

    # in blender version 4.1 func was removed, in 4.1+ normals are always calculated
    if bpy.app.version < (4, 1, 0):
        mesh.calc_normals_split()

    infoDict = MeshInfo()

    vertDict = infoDict.vert
    edgeDict = infoDict.edge
    f3dVertDict = infoDict.f3dVert
    edgeValidDict = infoDict.edgeValid
    validNeighborDict = infoDict.validNeighbors

    uv_data: bpy.types.bpy_prop_collection | list[bpy.types.MeshUVLoop] = None
    if len(obj.data.uv_layers) == 0:
        uv_data = obj.data.uv_layers.new().data
    else:
        uv_data = None
        for uv_layer in obj.data.uv_layers:
            if uv_layer.name == "UVMap":
                uv_data = uv_layer.data
        if uv_data is None:
            raise PluginError("Object '" + get_original_name(obj) + "' does not have a UV layer named 'UVMap.'")
    for face in mesh.loop_triangles:
        validNeighborDict[face] = []
        material = obj.material_slots[face.material_index].material
        if material is None:
            raise PluginError(
                f"There are some faces on your mesh object {get_original_name(obj)}"
                " that are assigned to an empty material slot."
            )
        for vertIndex in face.vertices:
            if vertIndex not in vertDict:
                vertDict[vertIndex] = []
            if face not in vertDict[vertIndex]:
                vertDict[vertIndex].append(face)
        for edgeKey in face.edge_keys:
            if edgeKey not in edgeDict:
                edgeDict[edgeKey] = []
            if face not in edgeDict[edgeKey]:
                edgeDict[edgeKey].append(face)

        for loopIndex in face.loops:
            convertInfo = LoopConvertInfo(uv_data, obj, obj.material_slots[face.material_index].material)
            f3dVertDict[loopIndex] = getF3DVert(mesh.loops[loopIndex], face, convertInfo, mesh)
    for face in mesh.loop_triangles:
        for edgeKey in face.edge_keys:
            for otherFace in edgeDict[edgeKey]:
                if otherFace == face:
                    continue
                if (otherFace, face) not in edgeValidDict and (face, otherFace) not in edgeValidDict:
                    edgeValid = (
                        f3dVertDict[getLoopFromVert(edgeKey[0], face)]
                        == f3dVertDict[getLoopFromVert(edgeKey[0], otherFace)]
                        and f3dVertDict[getLoopFromVert(edgeKey[1], face)]
                        == f3dVertDict[getLoopFromVert(edgeKey[1], otherFace)]
                    )
                    edgeValidDict[(otherFace, face)] = edgeValid
                    if edgeValid:
                        validNeighborDict[face].append(otherFace)
                        validNeighborDict[otherFace].append(face)
    return infoDict


def getSTUVRepeats(tex_prop: "TextureProperty") -> tuple[float, float]:
    SShift, TShift = 2**tex_prop.S.shift, 2**tex_prop.T.shift
    sMirrorScale = 2 if tex_prop.S.mirror else 1
    tMirrorScale = 2 if tex_prop.T.mirror else 1
    return (SShift * sMirrorScale, TShift * tMirrorScale)


def getUVInterval(f3dMat):
    useDict = all_combiner_uses(f3dMat)

    if useDict["Texture 0"] and f3dMat.tex0.tex_set:
        tex0UVInterval = getSTUVRepeats(f3dMat.tex0)
    else:
        tex0UVInterval = (1.0, 1.0)

    if useDict["Texture 1"] and f3dMat.tex1.tex_set:
        tex1UVInterval = getSTUVRepeats(f3dMat.tex1)
    else:
        tex1UVInterval = (1.0, 1.0)

    return (max(tex0UVInterval[0], tex1UVInterval[0]), max(tex0UVInterval[1], tex1UVInterval[1]))


def fixLargeUVs(obj):
    mesh = obj.data
    if len(obj.data.uv_layers) == 0:
        uv_data = obj.data.uv_layers.new().data
    else:
        uv_data = None
        for uv_layer in obj.data.uv_layers:
            if uv_layer.name == "UVMap":
                uv_data = uv_layer.data
        if uv_data is None:
            raise PluginError("Object '" + get_original_name(obj) + "' does not have a UV layer named 'UVMap.'")

    texSizeDict = {}
    if len(obj.data.materials) == 0:
        raise PluginError(f"{get_original_name(obj)}: This object needs an f3d material on it.")

        # Don't get tex dimensions here, as it also processes unused materials.
        # texSizeDict[material] = getTexDimensions(material)

    for polygon in mesh.polygons:
        material = obj.material_slots[polygon.material_index].material
        if material is None:
            raise PluginError(
                f"There are some faces on your mesh object {get_original_name(obj)}"
                " that are assigned to an empty material slot."
            )

        if material not in texSizeDict:
            texSizeDict[material] = getTexDimensions(material)
        if material.f3d_mat.use_large_textures:
            continue

        # To prevent wrong UVs when wrapping UVs into valid bounds,
        # we need to account for the highest texture shift and if mirroring is active.
        UVinterval = getUVInterval(material.f3d_mat)

        size = texSizeDict[material]
        if size[0] == 0 or size[1] == 0:
            continue
        cellSize = [1024 / size[0], 1024 / size[1]]
        minUV, maxUV = findUVBounds(polygon, uv_data)
        uvOffset = [0, 0]

        for i in range(2):
            # Move any UVs close to or straddling edge
            minDiff = (-cellSize[i] + 2) - minUV[i]
            if minDiff > 0:
                applyOffset(minUV, maxUV, uvOffset, ceil(minDiff / UVinterval[i]) * UVinterval[i], i)

            maxDiff = maxUV[i] - (cellSize[i] - 1)
            if maxDiff > 0:
                applyOffset(minUV, maxUV, uvOffset, -ceil(maxDiff / UVinterval[i]) * UVinterval[i], i)

        for loopIndex in polygon.loop_indices:
            newUV = (uv_data[loopIndex].uv[0] + uvOffset[0], uv_data[loopIndex].uv[1] + uvOffset[1])
            uv_data[loopIndex].uv = newUV


def applyOffset(minUV, maxUV, uvOffset, offset, i):
    minUV[i] += offset
    maxUV[i] += offset
    uvOffset[i] += offset


def findUVBounds(polygon, uv_data):
    minUV = [None, None]
    maxUV = [None, None]
    for loopIndex in polygon.loop_indices:
        uv = uv_data[loopIndex].uv
        for i in range(2):
            minUV[i] = uv[i] if minUV[i] is None else min(minUV[i], uv[i])
            maxUV[i] = uv[i] if maxUV[i] is None else max(maxUV[i], uv[i])
    return minUV, maxUV


def saveMeshWithLargeTexturesByFaces(
    material,
    faces,
    fModel,
    fMesh,
    obj,
    drawLayer,
    convertTextureData,
    currentGroupIndex,
    triConverterInfo,
    existingVertData,
    matRegionDict,
    lastMaterialName,
):
    """
    lastMaterialName is for optimization; set it to None to disable optimization.
    """

    if len(faces) == 0:
        print("0 Faces Provided.")
        return

    if material.mat_ver > 3:
        f3dMat = material.f3d_mat
    else:
        f3dMat = material

    fMaterial, texDimensions = saveOrGetF3DMaterial(material, fModel, obj, drawLayer, convertTextureData)

    fImage0 = fImage1 = None
    if fMaterial.imageKey[0] is not None:
        fImage0 = fModel.getTextureAndHandleShared(fMaterial.imageKey[0])
    if fMaterial.imageKey[1] is not None:
        fImage1 = fModel.getTextureAndHandleShared(fMaterial.imageKey[1])

    tileLoads = []
    for face in faces:
        faceTileLoad = TileLoad(material, fMaterial, texDimensions)
        faceTileLoad.initWithFace(obj, face)

        for tileLoad in tileLoads:
            if tileLoad.trySubsume(faceTileLoad):
                break
        else:
            tileLoads.append(faceTileLoad)

    if material.name != lastMaterialName:
        fMesh.add_material_call(fMaterial)
    triGroup = fMesh.tri_group_new(fMaterial)
    fMesh.draw.commands.append(SPDisplayList(triGroup.triList))

    currentGroupIndex = None
    curImgSet = None
    curTileLines = [0 for _ in range(8)]
    for tileLoad in tileLoads:
        revertCommands = GfxList("temp", GfxListTag.Draw, fModel.DLFormat)
        # Need load sync because if some tris are not drawn by the RSP due to being
        # off screen, can run directly from one load tile into another with no sync,
        # potentially corrupting TMEM
        triGroup.triList.commands.append(DPLoadSync())
        curImgSet = maybeSaveSingleLargeTextureSetup(
            0,
            fMaterial,
            fModel,
            fImage0,
            triGroup.triList,
            f3dMat.tex0,
            texDimensions,
            tileLoad,
            curImgSet,
            curTileLines,
        )
        curImgSet = maybeSaveSingleLargeTextureSetup(
            1,
            fMaterial,
            fModel,
            fImage1,
            triGroup.triList,
            f3dMat.tex1,
            texDimensions,
            tileLoad,
            curImgSet,
            curTileLines,
        )

        triConverter = TriangleConverter(
            triConverterInfo,
            texDimensions,
            material,
            currentGroupIndex,
            triGroup,
            copy.deepcopy(existingVertData),
            copy.deepcopy(matRegionDict),
        )

        currentGroupIndex = saveTriangleStrip(triConverter, tileLoad.faces, tileLoad.offsets, obj.data, False)

        if len(revertCommands.commands) > 0:
            fMesh.draw.commands.extend(revertCommands.commands)

        firstFace = False

    triGroup.triList.commands.append(SPEndDisplayList())

    if fMaterial.revert is not None:
        fMesh.draw.commands.append(SPDisplayList(fMaterial.revert))

    return currentGroupIndex


# Make sure to set original_name before calling this
# used when duplicating an object
def saveStaticModel(
    triConverterInfo, fModel, obj, transformMatrix, ownerName, convertTextureData, revertMatAtEnd, drawLayerField
):
    if len(obj.data.polygons) == 0:
        return None

    # checkForF3DMaterial(obj)

    faces_by_mat = {}
    for face in obj.data.loop_triangles:
        if face.material_index not in faces_by_mat:
            faces_by_mat[face.material_index] = []
        faces_by_mat[face.material_index].append(face)

    # sort by material slot
    faces_by_mat = {
        mat_index: faces_by_mat[mat_index]
        for mat_index, _ in enumerate(obj.material_slots)
        if mat_index in faces_by_mat
    }

    fMeshes = {}
    for material_index, faces in faces_by_mat.items():
        material = obj.material_slots[material_index].material

        if drawLayerField is not None and material.mat_ver > 3:
            drawLayer = getattr(material.f3d_mat.draw_layer, drawLayerField)
            drawLayerName = drawLayer
        else:
            drawLayer = fModel.getDrawLayerV3(obj)
            drawLayerName = None

        if drawLayer not in fMeshes:
            fMesh = fModel.addMesh(obj.original_name, ownerName, drawLayerName, False, obj)
            fMeshes[drawLayer] = fMesh

            if obj.use_f3d_culling and (fModel.f3d.F3DEX_GBI or fModel.f3d.F3DEX_GBI_2):
                addCullCommand(obj, fMesh, transformMatrix, fModel.matWriteMethod)
        else:
            fMesh = fMeshes[drawLayer]

        checkForF3dMaterialInFaces(obj, material)
        fMaterial, texDimensions = saveOrGetF3DMaterial(material, fModel, obj, drawLayer, convertTextureData)

        if fMaterial.isTexLarge[0] or fMaterial.isTexLarge[1]:
            saveMeshWithLargeTexturesByFaces(
                material,
                faces,
                fModel,
                fMesh,
                obj,
                drawLayer,
                convertTextureData,
                None,
                triConverterInfo,
                None,
                None,
                None,
            )
        else:
            saveMeshByFaces(
                material,
                faces,
                fModel,
                fMesh,
                obj,
                drawLayer,
                convertTextureData,
                None,
                triConverterInfo,
                None,
                None,
                None,
            )

    for drawLayer, fMesh in fMeshes.items():
        if revertMatAtEnd:
            revertMatAndEndDraw(fMesh.draw, [])
        else:
            fModel.endDraw(fMesh, obj)
    return fMeshes


def addCullCommand(obj, fMesh, transformMatrix, matWriteMethod):
    fMesh.add_cull_vtx()
    # if the object has a specifically set culling bounds, use that instead
    for vertexPos in obj.get("culling_bounds", obj.bound_box):
        fMesh.cullVertexList.vertices.append(
            F3DVert(
                Vector(vertexPos),
                [0, 0],
                Vector([0, 0, 0]),
                None,
                0.0,
            ).toVtx(
                obj.data,
                [32, 32],
                transformMatrix,
                True,
            )
        )

    if matWriteMethod == GfxMatWriteMethod.WriteDifferingAndRevert:
        defaults = bpy.context.scene.world.rdp_defaults
        if defaults.g_lighting:
            cullCommands = [
                SPClearGeometryMode(["G_LIGHTING"]),
                SPVertex(fMesh.cullVertexList, 0, 8, 0),
                SPSetGeometryMode(["G_LIGHTING"]),
                SPCullDisplayList(0, 7),
            ]
        else:
            cullCommands = [SPVertex(fMesh.cullVertexList, 0, 8, 0), SPCullDisplayList(0, 7)]
    elif matWriteMethod == GfxMatWriteMethod.WriteAll:
        cullCommands = [
            SPClearGeometryMode(["G_LIGHTING"]),
            SPVertex(fMesh.cullVertexList, 0, 8, 0),
            SPSetGeometryMode(["G_LIGHTING"]),
            SPCullDisplayList(0, 7),
        ]
    else:
        raise PluginError("Unhandled material write method for f3d culling: " + str(matWriteMethod))
    fMesh.draw.commands = cullCommands + fMesh.draw.commands


def exportF3DCommon(obj, fModel, transformMatrix, includeChildren, name, DLFormat, convertTextureData):
    tempObj, meshList = combineObjects(obj, includeChildren, None, None)
    try:
        infoDict = getInfoDict(tempObj)
        triConverterInfo = TriangleConverterInfo(tempObj, None, fModel.f3d, transformMatrix, infoDict)
        revert_materials = fModel.matWriteMethod == GfxMatWriteMethod.WriteDifferingAndRevert
        fMeshes = saveStaticModel(
            triConverterInfo, fModel, tempObj, transformMatrix, name, convertTextureData, revert_materials, None
        )
        cleanupCombineObj(tempObj, meshList)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
    except Exception as e:
        cleanupCombineObj(tempObj, meshList)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        raise Exception(str(e))

    return fMeshes


def checkForF3dMaterialInFaces(obj, material):
    if not material.is_f3d:
        raise PluginError(
            "Material '"
            + material.name
            + "' on object '"
            + obj.name
            + "' is not a Fast3D material. Replace it with a Fast3D material."
        )


def checkForF3DMaterial(obj):
    if len(obj.material_slots) == 0:
        raise PluginError(obj.name + " has no Fast3D material. Make sure to add a Fast3D material to it.")
    for materialSlot in obj.material_slots:
        if materialSlot.material is None or not materialSlot.material.is_f3d:
            raise PluginError(
                obj.name
                + " has either empty material slots "
                + "or non-Fast3D materials. Remove any regular blender materials / empty slots."
            )


def revertMatAndEndDraw(gfxList, otherCommands):
    gfxList.commands.extend(
        [
            DPPipeSync(),
            SPSetGeometryMode(["G_LIGHTING"]),
            SPClearGeometryMode(["G_TEXTURE_GEN"]),
            DPSetCombineMode(
                *(
                    ["0", "0", "0", "SHADE"]
                    + ["0", "0", "0", "ENVIRONMENT"]
                    + ["0", "0", "0", "SHADE"]
                    + ["0", "0", "0", "ENVIRONMENT"]
                )
            ),
            SPTexture(0xFFFF, 0xFFFF, 0, 0, 0),
        ]
        + otherCommands
    )

    if gfxList.DLFormat != DLFormat.Dynamic:
        gfxList.commands.append(SPEndDisplayList())


def getCommonEdge(face1, face2, mesh):
    for edgeKey1 in face1.edge_keys:
        for edgeKey2 in face2.edge_keys:
            if edgeKey1 == edgeKey2:
                return edgeKey1
    raise PluginError("No common edge between faces " + str(face1.index) + " and " + str(face2.index))


def edgeValid(edgeValidDict, face, otherFace):
    if (face, otherFace) in edgeValidDict:
        return edgeValidDict[(face, otherFace)]
    else:
        return edgeValidDict[(otherFace, face)]


def getLowestUnvisitedNeighborCountFace(unvisitedFaces, infoDict):
    lowestNeighborFace = unvisitedFaces[0]
    lowestNeighborCount = len(infoDict.validNeighbors[lowestNeighborFace])
    for face in unvisitedFaces:
        neighborCount = len(infoDict.validNeighbors[face])
        if neighborCount < lowestNeighborCount:
            lowestNeighborFace = face
            lowestNeighborCount = neighborCount
    return lowestNeighborFace


def getNextNeighborFace(faces, face, lastEdgeKey, visitedFaces, possibleFaces, infoDict):
    if lastEdgeKey is not None:
        handledEdgeKeys = [lastEdgeKey]
        nextEdgeKey = face.edge_keys[(face.edge_keys.index(lastEdgeKey) + 1) % 3]
    else:
        handledEdgeKeys = []
        nextEdgeKey = face.edge_keys[0]

    nextFaceAndEdge = (None, None)
    while nextEdgeKey not in handledEdgeKeys:
        for linkedFace in infoDict.edge[nextEdgeKey]:
            if linkedFace == face or linkedFace not in faces:
                continue
            elif edgeValid(infoDict.edgeValid, linkedFace, face) and linkedFace not in visitedFaces:
                if nextFaceAndEdge[0] is None:
                    # print(nextLoop.face)
                    nextFaceAndEdge = (linkedFace, nextEdgeKey)
                else:
                    # Move face to front of queue
                    if linkedFace in possibleFaces:
                        possibleFaces.remove(linkedFace)
                    possibleFaces.insert(0, linkedFace)
        handledEdgeKeys.append(nextEdgeKey)
        nextEdgeKey = face.edge_keys[(face.edge_keys.index(nextEdgeKey) + 1) % 3]
    return nextFaceAndEdge


def saveTriangleStrip(triConverter, faces, faceSTOffsets, mesh, terminateDL):
    visitedFaces = []
    unvisitedFaces = copy.copy(faces)
    possibleFaces = []
    lastEdgeKey = None
    infoDict = triConverter.triConverterInfo.infoDict
    neighborFace = getLowestUnvisitedNeighborCountFace(unvisitedFaces, infoDict)

    while len(visitedFaces) < len(faces):
        # print(str(len(visitedFaces)) + " " + str(len(bFaces)))
        if neighborFace is None:
            if len(possibleFaces) > 0:
                # print("get neighbor from queue")
                neighborFace = possibleFaces[0]
                lastEdgeKey = None
                possibleFaces = []
            else:
                # print('get new neighbor')
                neighborFace = getLowestUnvisitedNeighborCountFace(unvisitedFaces, infoDict)
                lastEdgeKey = None

        stOffset = None if faceSTOffsets is None else faceSTOffsets[faces.index(neighborFace)]
        triConverter.addFace(neighborFace, stOffset)
        if neighborFace in visitedFaces:
            raise PluginError("Repeated face")
        visitedFaces.append(neighborFace)
        unvisitedFaces.remove(neighborFace)
        if neighborFace in possibleFaces:
            possibleFaces.remove(neighborFace)
        for otherFace in infoDict.validNeighbors[neighborFace]:
            infoDict.validNeighbors[otherFace].remove(neighborFace)

        neighborFace, lastEdgeKey = getNextNeighborFace(
            faces, neighborFace, lastEdgeKey, visitedFaces, possibleFaces, infoDict
        )

    triConverter.finish(terminateDL)
    return triConverter.currentGroupIndex


def saveMeshByFaces(
    material,
    faces,
    fModel,
    fMesh,
    obj,
    drawLayer,
    convertTextureData,
    currentGroupIndex,
    triConverterInfo,
    existingVertData,
    matRegionDict,
    lastMaterialName,
):
    """
    lastMaterialName is for optimization; set it to None to disable optimization.
    """

    if len(faces) == 0:
        print("0 Faces Provided.")
        return
    fMaterial, texDimensions = saveOrGetF3DMaterial(material, fModel, obj, drawLayer, convertTextureData)

    if material.name != lastMaterialName:
        fMesh.add_material_call(fMaterial)
    triGroup = fMesh.tri_group_new(fMaterial)
    fMesh.draw.commands.append(SPDisplayList(triGroup.triList))

    triConverter = TriangleConverter(
        triConverterInfo,
        texDimensions,
        material,
        currentGroupIndex,
        triGroup,
        copy.deepcopy(existingVertData),
        copy.deepcopy(matRegionDict),
    )

    currentGroupIndex = saveTriangleStrip(triConverter, faces, None, obj.data, True)

    if fMaterial.revert is not None:
        fMesh.draw.commands.append(SPDisplayList(fMaterial.revert))

    return currentGroupIndex


@dataclass
class LoopConvertInfo:
    uv_data: bpy.types.bpy_prop_collection | list[bpy.types.MeshUVLoop]
    obj: bpy.types.Object
    material: bpy.types.Material


def getNewIndices(existingIndices, bufferStart):
    n = bufferStart
    newIndices = []
    for index in existingIndices:
        if index is None:
            newIndices.append(n)
            n += 1
        else:
            newIndices.append(index)
    return newIndices


class F3DVert:
    def __init__(
        self,
        position: Vector,
        uv: Vector,
        rgb: Optional[Vector],
        normal: Optional[Vector],
        alpha: float,
    ):
        self.position: Vector = position
        self.uv: Vector = uv
        self.stOffset: Optional[tuple(int, int)] = None
        self.rgb: Optional[Vector] = rgb
        self.normal: Optional[Vector] = normal
        self.alpha: float = alpha

    def __eq__(self, other):
        if not isinstance(other, F3DVert):
            return False
        return (
            self.position == other.position
            and self.uv == other.uv
            and self.stOffset == other.stOffset
            and self.rgb == other.rgb
            and self.normal == other.normal
            and self.alpha == other.alpha
        )

    def toVtx(self, mesh, texDimensions, transformMatrix, isPointSampled: bool, tex_scale=(1, 1)) -> Vtx:
        # Position (8 bytes)
        position = [int(round(floatValue)) for floatValue in (transformMatrix @ self.position)]

        # UV (4 bytes)
        # For F3D, Bilinear samples the point from the center of the pixel.
        # However, Point samples from the corner.
        # Thus we add 0.5 to the UV only if bilinear filtering.
        # see section 13.7.5.3 in programming manual.
        pixelOffset = (
            (0, 0)
            if (isPointSampled or tex_scale[0] == 0 or tex_scale[1] == 0)
            else (0.5 / tex_scale[0], 0.5 / tex_scale[1])
        )
        pixelOffset = self.stOffset if self.stOffset is not None else pixelOffset

        uv = [
            convertFloatToFixed16(self.uv[0] * texDimensions[0] - pixelOffset[0]),
            convertFloatToFixed16(self.uv[1] * texDimensions[1] - pixelOffset[1]),
        ]

        packedNormal = 0
        if self.normal is not None:
            # normal transformed correctly.
            normal = (transformMatrix.inverted().transposed() @ self.normal).normalized()
            if self.rgb is not None:
                packedNormal = packNormal(normal)

        if self.rgb is not None:
            colorOrNormal = [scaleToU8(c).to_bytes(1, "big")[0] for c in self.rgb]
        else:
            colorOrNormal = [
                int(round(normal[0] * 127)).to_bytes(1, "big", signed=True)[0],
                int(round(normal[1] * 127)).to_bytes(1, "big", signed=True)[0],
                int(round(normal[2] * 127)).to_bytes(1, "big", signed=True)[0],
            ]
        colorOrNormal.append(scaleToU8(self.alpha).to_bytes(1, "big")[0])

        return Vtx(position, uv, colorOrNormal, packedNormal)


# groupIndex is either a vertex group (writing), or name of c variable identifying a transform group, like a limb (parsing)
class BufferVertex:
    def __init__(self, f3dVert: F3DVert, groupIndex: int | str, materialIndex: int):
        self.f3dVert: F3DVert = f3dVert
        self.groupIndex: int | str = groupIndex
        self.materialIndex: int = materialIndex

    def __eq__(self, other):
        if not isinstance(other, BufferVertex):
            return False
        return (
            self.f3dVert == other.f3dVert
            and self.groupIndex == other.groupIndex
            and self.materialIndex == other.materialIndex
        )


class TriangleConverterInfo:
    def __init__(self, obj, armature, f3d, transformMatrix, infoDict):
        self.infoDict = infoDict
        self.vertexGroupInfo = self.infoDict.vertexGroupInfo
        self.armature = armature
        self.obj = obj
        self.mesh = obj.data
        self.f3d = f3d
        self.transformMatrix = transformMatrix

        # Caching names
        self.groupNames = {}

    def getMatrixAddrFromGroup(self, groupIndex):
        raise PluginError(
            "TriangleConverterInfo must be extended with getMatrixAddrFromGroup implemented for game specific uses."
        )

    def getTransformMatrix(self, groupIndex):
        if self.armature is None or groupIndex is None:
            groupMatrix = mathutils.Matrix.Identity(4)
        else:
            if groupIndex not in self.groupNames:
                self.groupNames[groupIndex] = getGroupNameFromIndex(self.obj, groupIndex)
            name = self.groupNames[groupIndex]
            if name not in self.armature.bones:
                print("Vertex group " + name + " not found in bones.")
                groupMatrix = mathutils.Matrix.Identity(4)
            else:
                groupMatrix = self.armature.bones[name].matrix_local.inverted()
        return self.transformMatrix @ groupMatrix


# existingVertexData is used for cases where we want to assume the presence of vertex data
# loaded in from a previous matrix transform (ex. sm64 skinning)
class TriangleConverter:
    def __init__(
        self,
        triConverterInfo: TriangleConverterInfo,
        texDimensions: tuple[int, int],
        material: bpy.types.Material,
        currentGroupIndex,
        triGroup: FTriGroup,
        existingVertexData: list[BufferVertex],
        existingVertexMaterialRegions,
    ):
        self.triConverterInfo = triConverterInfo
        self.currentGroupIndex = currentGroupIndex
        self.originalGroupIndex = currentGroupIndex

        # Existing data assumed to be already loaded in.
        self.vertBuffer: list[BufferVertex] = []
        if existingVertexData is not None:
            self.vertBuffer: list[BufferVertex] = existingVertexData
        self.existingVertexMaterialRegions = existingVertexMaterialRegions
        self.bufferStart = len(self.vertBuffer)
        self.vertexBufferTriangles = []  # [(index0, index1, index2)]

        self.triGroup = triGroup
        self.triList = triGroup.triList
        self.vtxList = triGroup.vertexList

        self.material = material
        uv_data = triConverterInfo.obj.data.uv_layers["UVMap"].data
        self.convertInfo = LoopConvertInfo(uv_data, triConverterInfo.obj, material)
        self.texDimensions = texDimensions
        self.isPointSampled = isTexturePointSampled(material)
        self.tex_scale = material.f3d_mat.tex_scale

    def vertInBuffer(self, bufferVert, material_index):
        if self.existingVertexMaterialRegions is None:
            return bufferVert in self.vertBuffer
        else:
            if material_index in self.existingVertexMaterialRegions:
                matRegion = self.existingVertexMaterialRegions[material_index]
                if bufferVert in self.vertBuffer[matRegion[0] : matRegion[1]]:
                    return True

            return bufferVert in self.vertBuffer[self.bufferStart :]

    def getSortedBuffer(self) -> dict[int, list[BufferVertex]]:
        limbVerts: dict[int, list[BufferVertex]] = {}
        for bufferVert in self.vertBuffer[self.bufferStart :]:
            if bufferVert.groupIndex not in limbVerts:
                limbVerts[bufferVert.groupIndex] = []
            limbVerts[bufferVert.groupIndex].append(bufferVert)

        return limbVerts

    def processGeometry(self):
        # Sort verts by limb index, then load current limb verts
        bufferStart = self.bufferStart
        bufferEnd = self.bufferStart
        limbVerts = self.getSortedBuffer()

        if self.currentGroupIndex in limbVerts:
            currentLimbVerts = limbVerts[self.currentGroupIndex]
            self.vertBuffer = self.vertBuffer[: self.bufferStart] + currentLimbVerts
            self.triList.commands.append(
                SPVertex(self.vtxList, len(self.vtxList.vertices), len(currentLimbVerts), self.bufferStart)
            )
            bufferEnd += len(currentLimbVerts)
            del limbVerts[self.currentGroupIndex]

            # Save vertices
            for bufferVert in self.vertBuffer[bufferStart:bufferEnd]:
                self.vtxList.vertices.append(
                    bufferVert.f3dVert.toVtx(
                        self.triConverterInfo.mesh,
                        self.texDimensions,
                        self.triConverterInfo.getTransformMatrix(bufferVert.groupIndex),
                        self.isPointSampled,
                        tex_scale=self.tex_scale,
                    )
                )

            bufferStart = bufferEnd
        else:
            self.vertBuffer = self.vertBuffer[: self.bufferStart]

        # Load other limb verts
        for groupIndex, bufferVerts in limbVerts.items():
            if groupIndex != self.currentGroupIndex:
                self.triList.commands.append(
                    SPMatrix(self.triConverterInfo.getMatrixAddrFromGroup(groupIndex), "G_MTX_LOAD")
                )
                self.currentGroupIndex = groupIndex
            self.triList.commands.append(
                SPVertex(self.vtxList, len(self.vtxList.vertices), len(bufferVerts), bufferStart)
            )

            self.vertBuffer += bufferVerts
            bufferEnd += len(bufferVerts)

            # Save vertices
            for bufferVert in self.vertBuffer[bufferStart:bufferEnd]:
                self.vtxList.vertices.append(
                    bufferVert.f3dVert.toVtx(
                        self.triConverterInfo.mesh,
                        self.texDimensions,
                        self.triConverterInfo.getTransformMatrix(bufferVert.groupIndex),
                        self.isPointSampled,
                        tex_scale=self.tex_scale,
                    )
                )

            bufferStart = bufferEnd

        # Load triangles
        triCmds = createTriangleCommands(
            self.vertexBufferTriangles, self.vertBuffer, not self.triConverterInfo.f3d.F3D_OLD_GBI
        )
        if not self.material.f3d_mat.use_cel_shading:
            self.triList.commands.extend(triCmds)
        else:
            if len(triCmds) <= 2:
                self.writeCelLevels(triCmds=triCmds)
            else:
                celTriList = self.triGroup.add_cel_tri_list()
                celTriList.commands.extend(triCmds)
                celTriList.commands.append(SPEndDisplayList())
                self.writeCelLevels(celTriList=celTriList)

    def writeCelLevels(self, celTriList: Optional[GfxList] = None, triCmds: Optional[List[GbiMacro]] = None) -> None:
        assert (celTriList == None) != (triCmds == None)
        f3dMat = self.material.f3d_mat
        cel = f3dMat.cel_shading
        f3d = get_F3D_GBI()

        # Don't want to have to change back and forth arbitrarily between decal and
        # opaque mode. So if you're using both lighter and darker, need to do those
        # first before switching to decal.
        if f3dMat.rdp_settings.zmode != "ZMODE_OPA":
            raise PluginError(
                f"Material {self.material.name} with cel shading: zmode in blender / rendermode must be opaque.",
                icon="ERROR",
            )
        wroteLighter = wroteDarker = usesDecal = False
        if len(cel.levels) == 0:
            raise PluginError(f"Material {self.material.name} with cel shading has no cel levels")
        for level in cel.levels:
            if level.threshMode == "Darker":
                if wroteDarker:
                    usesDecal = True
                elif usesDecal:
                    raise PluginError(
                        f"Material {self.material.name}: must use Lighter and Darker cel levels before duplicating either of them"
                    )
                wroteDarker = True
            else:
                if wroteLighter:
                    usesDecal = True
                elif usesDecal:
                    raise PluginError(
                        f"Material {self.material.name}: must use Lighter and Darker cel levels before duplicating either of them"
                    )
                wroteLighter = True

        # Because this might not be the first tri list in the object with this
        # material, we have to set things even if they were set up already in
        # the material.
        wroteLighter = wroteDarker = wroteOpaque = wroteDecal = False
        lastDarker = None
        for level in cel.levels:
            darker = level.threshMode == "Darker"
            self.triList.commands.append(DPPipeSync())
            if usesDecal:
                if not wroteOpaque:
                    wroteOpaque = True
                    self.triList.commands.append(SPSetOtherMode("G_SETOTHERMODE_L", 10, 2, ["ZMODE_OPA"]))
                if not wroteDecal and (darker and wroteDarker or not darker and wroteLighter):
                    wroteDecal = True
                    self.triList.commands.append(SPSetOtherMode("G_SETOTHERMODE_L", 10, 2, ["ZMODE_DEC"]))
            if darker:
                wroteDarker = True
            else:
                wroteLighter = True

            if lastDarker != darker:
                lastDarker = darker
                # Set up CC.
                ccSettings = []
                for prop in ["A", "B", "C", "D"]:
                    ccSettings.append(getattr(f3dMat.combiner1, prop))
                ccSettings.extend(["1", "SHADE"] if darker else ["SHADE", "0"])
                ccSettings.extend([cel.cutoutSource, "0"])
                if f3dMat.rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE":
                    for prop in ["A", "B", "C", "D", "A_alpha", "B_alpha", "C_alpha", "D_alpha"]:
                        ccSettings.append(getattr(f3dMat.combiner2, prop))
                else:
                    ccSettings *= 2
                self.triList.commands.append(DPSetCombineMode(*ccSettings))

            # Set up tint color and level
            if level.tintType == "Fixed":
                color = exportColor(level.tintFixedColor)
                if cel.tintPipeline == "CC":
                    self.triList.commands.append(
                        DPSetPrimColor(0, 0, color[0], color[1], color[2], level.tintFixedLevel)
                    )
                else:
                    self.triList.commands.append(DPSetFogColor(color[0], color[1], color[2], level.tintFixedLevel))
            elif level.tintType == "Segment":
                self.triList.commands.append(
                    SPDisplayList(
                        GfxList(
                            f"{level.tintSegmentNum:#04x}{level.tintSegmentOffset * 8:06x}",
                            GfxListTag.Material,
                            DLFormat.Static,
                        )
                    )
                )
            elif level.tintType == "Light":
                if cel.tintPipeline == "CC":
                    self.triList.commands.append(SPLightToPrimColor(level.tintLightSlot, level.tintFixedLevel, 0, 0))
                else:
                    self.triList.commands.append(SPLightToFogColor(level.tintLightSlot, level.tintFixedLevel))
            else:
                raise PluginError("Unknown tint type")

            # Set up threshold
            self.triList.commands.append(
                DPSetBlendColor(255, 255, 255, 0x100 - level.threshold if darker else level.threshold)
            )
            self.triList.commands.append(
                SPAlphaCompareCull(
                    "G_ALPHA_COMPARE_CULL_ABOVE" if darker else "G_ALPHA_COMPARE_CULL_BELOW", level.threshold
                )
            )

            # Draw tris, inline or by call
            if triCmds is not None:
                self.triList.commands.extend(triCmds)
            else:
                self.triList.commands.append(SPDisplayList(celTriList))

        # Disable alpha compare culling for future DLs
        self.triList.commands.append(SPAlphaCompareCull("G_ALPHA_COMPARE_CULL_DISABLE", 0))

    def addFace(self, face, stOffset):
        triIndices = []
        addedVerts = []  # verts added to existing vertexBuffer
        allVerts = []  # all verts not in 'untouched' buffer region

        for loopIndex in face.loops:
            loop = self.triConverterInfo.mesh.loops[loopIndex]
            vertexGroup = (
                self.triConverterInfo.vertexGroupInfo.vertexGroups[loop.vertex_index]
                if self.triConverterInfo.vertexGroupInfo is not None
                else None
            )
            bufferVert = BufferVertex(
                getF3DVert(loop, face, self.convertInfo, self.triConverterInfo.mesh), vertexGroup, face.material_index
            )
            bufferVert.f3dVert.stOffset = stOffset
            triIndices.append(bufferVert)
            if not self.vertInBuffer(bufferVert, face.material_index):
                addedVerts.append(bufferVert)

            if bufferVert not in self.vertBuffer[: self.bufferStart]:
                allVerts.append(bufferVert)

        # We care only about load size, since loading is what takes up time.
        # Even if vert_buffer is larger, its still another load to fill it.
        if len(self.vertBuffer) + len(addedVerts) > self.triConverterInfo.f3d.vert_load_size:
            self.processGeometry()
            self.vertBuffer = self.vertBuffer[: self.bufferStart] + allVerts
            self.vertexBufferTriangles = [triIndices]
        else:
            self.vertBuffer.extend(addedVerts)
            self.vertexBufferTriangles.append(triIndices)

    def finish(self, terminateDL):
        if len(self.vertexBufferTriangles) > 0:
            self.processGeometry()

        # if self.originalGroupIndex != self.currentGroupIndex:
        # 	self.triList.commands.append(SPMatrix(getMatrixAddrFromGroup(self.originalGroupIndex), "G_MTX_LOAD"))
        if terminateDL:
            self.triList.commands.append(SPEndDisplayList())


def getF3DVert(loop: bpy.types.MeshLoop, face, convertInfo: LoopConvertInfo, mesh: bpy.types.Mesh):
    position: Vector = mesh.vertices[loop.vertex_index].co.copy().freeze()
    # N64 is -Y, Blender is +Y
    uv: Vector = convertInfo.uv_data[loop.index].uv.copy()
    uv[:] = [field if not math.isnan(field) else 0 for field in uv]
    uv[1] = 1 - uv[1]
    uv = uv.freeze()

    has_rgb, has_normal, _ = getRgbNormalSettings(convertInfo.material.f3d_mat)
    mesh = convertInfo.obj.data
    color = getLoopColor(loop, mesh)
    rgb = color[:3] if has_rgb else None
    normal = getLoopNormal(loop) if has_normal else None
    alpha = color[3]

    return F3DVert(position, uv, rgb, normal, alpha)


def getLoopNormal(loop: bpy.types.MeshLoop) -> Vector:
    # Have to quantize to something because F3DVerts will be compared, and we
    # don't want floating-point inaccuracy causing "same" vertices not to be
    # merged. But, it hasn't been transformed yet, so quantizing to s8 here will
    # lose some accuracy.
    return Vector(
        (
            round(loop.normal[0] * 2**16) / 2**16,
            round(loop.normal[1] * 2**16) / 2**16,
            round(loop.normal[2] * 2**16) / 2**16,
        )
    ).freeze()


@functools.lru_cache(0)
def is3_2_or_above():
    return bpy.app.version >= (3, 2, 0)


def getLoopColor(loop: bpy.types.MeshLoop, mesh: bpy.types.Mesh) -> Vector:
    color_layer = getColorLayer(mesh, layer="Col")
    alpha_layer = getColorLayer(mesh, layer="Alpha")

    if color_layer is not None:
        # Apparently already gamma corrected to linear
        normalizedRGB = color_layer[loop.index].color
        if is3_2_or_above():
            normalizedRGB = gammaCorrect(normalizedRGB)
    else:
        normalizedRGB = [1, 1, 1]
    if alpha_layer is not None:
        normalizedAColor = alpha_layer[loop.index].color
        if is3_2_or_above():
            normalizedAColor = gammaCorrect(normalizedAColor)
        normalizedA = colorToLuminance(normalizedAColor[0:3])
    else:
        normalizedA = 1

    return mathutils.Vector((normalizedRGB[0], normalizedRGB[1], normalizedRGB[2], normalizedA))


def createTriangleCommands(triangles, vertexBuffer, useSP2Triangle):
    triangles = copy.deepcopy(triangles)
    commands = []

    def getIndices(tri):
        return [vertexBuffer.index(v) for v in tri]

    t = 0
    while t < len(triangles):
        firstTriIndices = getIndices(triangles[t])
        t += 1
        if useSP2Triangle and t < len(triangles):
            commands.append(SP2Triangles(*firstTriIndices, 0, *getIndices(triangles[t]), 0))
            t += 1
        else:
            commands.append(SP1Triangle(*firstTriIndices, 0))

    return commands


# white diffuse, grey ambient, normal = (1,1,1)
defaultLighting = [
    (mathutils.Vector((1, 1, 1)), mathutils.Vector((1, 1, 1)).normalized()),
    (mathutils.Vector((0.5, 0.5, 0.5)), mathutils.Vector((1, 1, 1)).normalized()),
]


def getTexDimensions(material):
    f3dMat = material.f3d_mat

    texDimensions0 = None
    texDimensions1 = None
    useDict = all_combiner_uses(f3dMat)
    if useDict["Texture 0"] and f3dMat.tex0.tex_set:
        if f3dMat.tex0.use_tex_reference:
            texDimensions0 = f3dMat.tex0.tex_reference_size
        else:
            if f3dMat.tex0.tex is None:
                raise PluginError('In material "' + material.name + '", a texture has not been set.')
            texDimensions0 = f3dMat.tex0.tex.size[0], f3dMat.tex0.tex.size[1]
    if useDict["Texture 1"] and f3dMat.tex1.tex_set:
        if f3dMat.tex1.use_tex_reference:
            texDimensions1 = f3dMat.tex1.tex_reference_size
        else:
            if f3dMat.tex1.tex is None:
                raise PluginError('In material "' + material.name + '", a texture has not been set.')
            texDimensions1 = f3dMat.tex1.tex.size[0], f3dMat.tex1.tex.size[1]

    if texDimensions0 is not None and texDimensions1 is not None:
        texDimensions = texDimensions0 if f3dMat.uv_basis == "TEXEL0" else texDimensions1
    elif texDimensions0 is not None:
        texDimensions = texDimensions0
    elif texDimensions1 is not None:
        texDimensions = texDimensions1
    else:
        texDimensions = [32, 32]
    return texDimensions


def saveOrGetF3DMaterial(material, fModel, obj, drawLayer, convertTextureData):
    print(f"Writing material {material.name}")
    if material.mat_ver > 3:
        f3dMat = material.f3d_mat
    else:
        f3dMat = material

    areaKey = fModel.global_data.getCurrentAreaKey(f3dMat)
    areaIndex = fModel.global_data.current_area_index

    if f3dMat.rdp_settings.set_rendermode:
        materialKey = (material, drawLayer, areaKey)
    else:
        materialKey = (material, None, areaKey)

    materialItem = fModel.getMaterialAndHandleShared(materialKey)
    if materialItem is not None:
        return materialItem

    if len(obj.data.materials) == 0:
        raise PluginError("Mesh must have at least one material.")
    materialName = (
        fModel.name
        + "_"
        + toAlnum(material.name)
        + (("_layer" + str(drawLayer)) if f3dMat.rdp_settings.set_rendermode and drawLayer is not None else "")
        + (("_area" + str(areaIndex)) if f3dMat.set_fog and f3dMat.use_global_fog and areaKey is not None else "")
    )
    fMaterial = fModel.addMaterial(materialName)
    fMaterial.mat_only_DL.commands.append(DPPipeSync())
    fMaterial.revert.commands.append(DPPipeSync())

    if not material.is_f3d:
        raise PluginError("Material named " + material.name + " is not an F3D material.")

    fMaterial.getScrollData(material, getMaterialScrollDimensions(f3dMat))

    if f3dMat.set_combiner:
        if f3dMat.rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE":
            fMaterial.mat_only_DL.commands.append(
                DPSetCombineMode(
                    f3dMat.combiner1.A,
                    f3dMat.combiner1.B,
                    f3dMat.combiner1.C,
                    f3dMat.combiner1.D,
                    f3dMat.combiner1.A_alpha,
                    f3dMat.combiner1.B_alpha,
                    f3dMat.combiner1.C_alpha,
                    f3dMat.combiner1.D_alpha,
                    f3dMat.combiner2.A,
                    f3dMat.combiner2.B,
                    f3dMat.combiner2.C,
                    f3dMat.combiner2.D,
                    f3dMat.combiner2.A_alpha,
                    f3dMat.combiner2.B_alpha,
                    f3dMat.combiner2.C_alpha,
                    f3dMat.combiner2.D_alpha,
                )
            )
        else:
            fMaterial.mat_only_DL.commands.append(
                DPSetCombineMode(
                    f3dMat.combiner1.A,
                    f3dMat.combiner1.B,
                    f3dMat.combiner1.C,
                    f3dMat.combiner1.D,
                    f3dMat.combiner1.A_alpha,
                    f3dMat.combiner1.B_alpha,
                    f3dMat.combiner1.C_alpha,
                    f3dMat.combiner1.D_alpha,
                    f3dMat.combiner1.A,
                    f3dMat.combiner1.B,
                    f3dMat.combiner1.C,
                    f3dMat.combiner1.D,
                    f3dMat.combiner1.A_alpha,
                    f3dMat.combiner1.B_alpha,
                    f3dMat.combiner1.C_alpha,
                    f3dMat.combiner1.D_alpha,
                )
            )

    if f3dMat.set_ao:
        fMaterial.mat_only_DL.commands.append(
            SPAmbOcclusion(
                min(round(f3dMat.ao_ambient * 2**16), 0xFFFF),
                min(round(f3dMat.ao_directional * 2**16), 0xFFFF),
                min(round(f3dMat.ao_point * 2**16), 0xFFFF),
            )
        )

    if f3dMat.set_fresnel:
        dotMin = round(f3dMat.fresnel_lo * 0x7FFF)
        dotMax = round(f3dMat.fresnel_hi * 0x7FFF)
        scale = max(min(0x3F8000 // (dotMax - dotMin), 0x7FFF), -0x8000)
        offset = max(min(-(0x7F * dotMin) // (dotMax - dotMin), 0x7FFF), -0x8000)
        fMaterial.mat_only_DL.commands.append(SPFresnel(scale, offset))

    if f3dMat.set_attroffs_st:
        fMaterial.mat_only_DL.commands.append(
            SPAttrOffsetST(
                to_s16(f3dMat.attroffs_st[0] * 32),
                to_s16(f3dMat.attroffs_st[1] * 32),
            )
        )

    if f3dMat.set_attroffs_z:
        fMaterial.mat_only_DL.commands.append(SPAttrOffsetZ(f3dMat.attroffs_z))

    if f3dMat.set_fog:
        if f3dMat.use_global_fog and fModel.global_data.getCurrentAreaData() is not None:
            fogData = fModel.global_data.getCurrentAreaData().fog_data
            fog_position = fogData.position
            fog_color = fogData.color
        else:
            fog_position = f3dMat.fog_position
            fog_color = f3dMat.fog_color
        # TODO: (V5) update fog color to reverse gamma corrected for V3/V4 upgrades
        corrected_color = exportColor(fog_color[0:3]) + [scaleToU8(fog_color[3])]
        fMaterial.mat_only_DL.commands.extend(
            [
                DPSetFogColor(*corrected_color),
                SPFogPosition(fog_position[0], fog_position[1]),
            ]
        )

    useDict = all_combiner_uses(f3dMat)
    multitexManager = MultitexManager(material, fMaterial, fModel)

    # Set othermode
    if drawLayer is not None:
        defaultRM = fModel.getRenderMode(drawLayer)
    else:
        defaultRM = None

    defaults = bpy.context.scene.world.rdp_defaults
    if fModel.f3d.F3DEX_GBI_2:
        saveGeoModeDefinitionF3DEX2(fMaterial, f3dMat.rdp_settings, defaults, fModel.matWriteMethod)
    else:
        saveGeoModeDefinition(fMaterial, f3dMat.rdp_settings, defaults, fModel.matWriteMethod)
    saveOtherModeHDefinition(
        fMaterial,
        f3dMat.rdp_settings,
        multitexManager.getTT(),
        defaults,
        fModel.matWriteMethod,
        fModel.f3d,
    )
    saveOtherModeLDefinition(fMaterial, f3dMat.rdp_settings, defaults, defaultRM, fModel.matWriteMethod, fModel.f3d)
    saveOtherDefinition(fMaterial, f3dMat, defaults)

    # Set scale
    s = int(min(round(f3dMat.tex_scale[0] * 0x10000), 0xFFFF))
    t = int(min(round(f3dMat.tex_scale[1] * 0x10000), 0xFFFF))
    if f3dMat.rdp_settings.g_mdsft_textlod == "G_TL_LOD":
        fMaterial.mat_only_DL.commands.append(
            SPTexture(s, t, f3dMat.rdp_settings.num_textures_mipmapped - 1, fModel.f3d.G_TX_RENDERTILE, 1)
        )
    else:
        fMaterial.mat_only_DL.commands.append(SPTexture(s, t, 0, fModel.f3d.G_TX_RENDERTILE, 1))

    # Write textures
    multitexManager.writeAll(material, fMaterial, fModel, convertTextureData)

    # Write colors
    nodes = material.node_tree.nodes
    if useDict["Primitive"] and f3dMat.set_prim:
        color = exportColor(f3dMat.prim_color[0:3]) + [scaleToU8(f3dMat.prim_color[3])]
        fMaterial.mat_only_DL.commands.append(
            DPSetPrimColor(scaleToU8(f3dMat.prim_lod_min), scaleToU8(f3dMat.prim_lod_frac), *color)
        )

    if useDict["Environment"] and f3dMat.set_env:
        color = exportColor(f3dMat.env_color[0:3]) + [scaleToU8(f3dMat.env_color[3])]
        fMaterial.mat_only_DL.commands.append(DPSetEnvColor(*color))

    # Checking for f3dMat.rdp_settings.g_lighting here will prevent accidental exports,
    # There may be some edge case where this isn't desired.
    if useDict["Shade"] and f3dMat.set_lights and f3dMat.rdp_settings.g_lighting:
        fLights = saveLightsDefinition(fModel, fMaterial, f3dMat, materialName + "_lights")
        fMaterial.mat_only_DL.commands.extend([SPSetLights(fLights)])  # TODO: handle synching: NO NEED?

    if useDict["Key"] and f3dMat.set_key:
        if material.mat_ver >= 4:
            center = f3dMat.key_center
        else:
            center = nodes["Chroma Key Center"].outputs[0].default_value
        scale = f3dMat.key_scale
        width = f3dMat.key_width
        fMaterial.mat_only_DL.commands.extend(
            [
                DPSetCombineKey("G_CK_KEY"),
                # TODO: Add UI handling width
                DPSetKeyR(int(center[0] * 255), int(scale[0] * 255), int(width[0] * 2**8)),
                DPSetKeyGB(
                    int(center[1] * 255),
                    int(scale[1] * 255),
                    int(width[1] * 2**8),
                    int(center[2] * 255),
                    int(scale[2] * 255),
                    int(width[2] * 2**8),
                ),
            ]
        )

    # all k0-5 set at once
    # make sure to handle this in node shader
    # or don't, who cares
    if useDict["Convert"] and f3dMat.set_k0_5:
        fMaterial.mat_only_DL.commands.extend(
            [
                DPSetTextureConvert("G_TC_FILTCONV"),  # TODO: allow filter option
                DPSetConvert(
                    int(f3dMat.k0 * 255),
                    int(f3dMat.k1 * 255),
                    int(f3dMat.k2 * 255),
                    int(f3dMat.k3 * 255),
                    int(f3dMat.k4 * 255),
                    int(f3dMat.k5 * 255),
                ),
            ]
        )

    fModel.onMaterialCommandsBuilt(fMaterial, material, drawLayer)

    # End Display List
    # For dynamic calls, materials will be called as functions and should not end the DL.
    if fModel.DLFormat == DLFormat.Static:
        fMaterial.material.commands.append(SPEndDisplayList())

    # revertMatAndEndDraw(fMaterial.revert)
    if len(fMaterial.revert.commands) > 1:  # 1 being the pipe sync
        if fMaterial.DLFormat == DLFormat.Static:
            fMaterial.revert.commands.append(SPEndDisplayList())
    else:
        fMaterial.revert = None

    texDimensions = multitexManager.getTexDimensions()
    materialKey = (
        material,
        (drawLayer if f3dMat.rdp_settings.set_rendermode else None),
        fModel.global_data.getCurrentAreaKey(f3dMat),
    )
    fModel.materials[materialKey] = (fMaterial, texDimensions)

    return fMaterial, texDimensions


def saveLightsDefinition(fModel, fMaterial, material, lightsName):
    lights = fModel.getLightAndHandleShared(lightsName)
    if lights is not None:
        return lights

    lights = Lights(toAlnum(lightsName), fModel.f3d)

    if material.use_default_lighting:
        lights.a = Ambient(exportColor(material.ambient_light_color))
        lights.l.append(Light(exportColor(material.default_light_color), [0x49, 0x49, 0x49]))
    else:
        lights.a = Ambient(exportColor(material.ambient_light_color))

        if material.f3d_light1 is not None:
            addLightDefinition(material, material.f3d_light1, lights)
        if material.f3d_light2 is not None:
            addLightDefinition(material, material.f3d_light2, lights)
        if material.f3d_light3 is not None:
            addLightDefinition(material, material.f3d_light3, lights)
        if material.f3d_light4 is not None:
            addLightDefinition(material, material.f3d_light4, lights)
        if material.f3d_light5 is not None:
            addLightDefinition(material, material.f3d_light5, lights)
        if material.f3d_light6 is not None:
            addLightDefinition(material, material.f3d_light6, lights)
        if material.f3d_light7 is not None:
            addLightDefinition(material, material.f3d_light7, lights)

    if lightsName in fModel.lights:
        raise PluginError("Duplicate light name.")
    fModel.addLight(lightsName, lights, fMaterial)
    return lights


def addLightDefinition(mat, f3d_light, fLights):
    lightObj = lightDataToObj(f3d_light)
    fLights.l.append(
        Light(
            exportColor(f3d_light.color),
            normToSigned8Vector(getObjDirectionVec(lightObj, True)),
        )
    )


def saveBitGeoF3DEX2(value, defaultValue, flagName, geo, matWriteMethod):
    if value != defaultValue or matWriteMethod == GfxMatWriteMethod.WriteAll:
        if value:
            geo.setFlagList.append(flagName)
        else:
            geo.clearFlagList.append(flagName)


def saveBitGeo(value, defaultValue, flagName, setGeo, clearGeo, matWriteMethod):
    if value != defaultValue or matWriteMethod == GfxMatWriteMethod.WriteAll:
        if value:
            setGeo.flagList.append(flagName)
        else:
            clearGeo.flagList.append(flagName)


def saveGeoModeCommon(saveFunc: Callable, settings: RDPSettings, defaults: RDPSettings, args: Any):
    saveFunc(settings.g_zbuffer, defaults.g_zbuffer, "G_ZBUFFER", *args)
    saveFunc(settings.g_shade, defaults.g_shade, "G_SHADE", *args)
    saveFunc(settings.g_cull_front, defaults.g_cull_front, "G_CULL_FRONT", *args)
    saveFunc(settings.g_cull_back, defaults.g_cull_back, "G_CULL_BACK", *args)
    if bpy.context.scene.f3d_type == "F3DEX3":
        saveFunc(settings.g_ambocclusion, defaults.g_ambocclusion, "G_AMBOCCLUSION", *args)
        saveFunc(settings.g_attroffset_z_enable, defaults.g_attroffset_z_enable, "G_ATTROFFSET_Z_ENABLE", *args)
        saveFunc(settings.g_attroffset_st_enable, defaults.g_attroffset_st_enable, "G_ATTROFFSET_ST_ENABLE", *args)
        saveFunc(settings.g_packed_normals, defaults.g_packed_normals, "G_PACKED_NORMALS", *args)
        saveFunc(settings.g_lighttoalpha, defaults.g_lighttoalpha, "G_LIGHTTOALPHA", *args)
        saveFunc(settings.g_lighting_specular, defaults.g_lighting_specular, "G_LIGHTING_SPECULAR", *args)
        saveFunc(settings.g_fresnel_color, defaults.g_fresnel_color, "G_FRESNEL_COLOR", *args)
        saveFunc(settings.g_fresnel_alpha, defaults.g_fresnel_alpha, "G_FRESNEL_ALPHA", *args)
    saveFunc(settings.g_fog, defaults.g_fog, "G_FOG", *args)
    saveFunc(settings.g_lighting, defaults.g_lighting, "G_LIGHTING", *args)
    saveFunc(settings.g_tex_gen, defaults.g_tex_gen, "G_TEXTURE_GEN", *args)
    saveFunc(settings.g_tex_gen_linear, defaults.g_tex_gen_linear, "G_TEXTURE_GEN_LINEAR", *args)
    saveFunc(settings.g_lod, defaults.g_lod, "G_LOD", *args)
    saveFunc(settings.g_shade_smooth, defaults.g_shade_smooth, "G_SHADING_SMOOTH", *args)
    if isUcodeF3DEX1(bpy.context.scene.f3d_type):
        saveFunc(settings.g_clipping, defaults.g_clipping, "G_CLIPPING", *args)


def saveGeoModeDefinitionF3DEX2(fMaterial, settings, defaults, matWriteMethod):
    geo = SPGeometryMode([], [])
    saveGeoModeCommon(saveBitGeoF3DEX2, settings, defaults, (geo, matWriteMethod))

    if len(geo.clearFlagList) != 0 or len(geo.setFlagList) != 0:
        if len(geo.clearFlagList) == 0:
            geo.clearFlagList.append("0")
        elif len(geo.setFlagList) == 0:
            geo.setFlagList.append("0")

        if matWriteMethod == GfxMatWriteMethod.WriteAll:
            fMaterial.mat_only_DL.commands.append(SPLoadGeometryMode(geo.setFlagList))
        else:
            fMaterial.mat_only_DL.commands.append(geo)
            fMaterial.revert.commands.append(SPGeometryMode(geo.setFlagList, geo.clearFlagList))


def saveGeoModeDefinition(fMaterial, settings, defaults, matWriteMethod):
    setGeo = SPSetGeometryMode([])
    clearGeo = SPClearGeometryMode([])

    saveGeoModeCommon(saveBitGeo, settings, defaults, (setGeo, clearGeo, matWriteMethod))

    if len(setGeo.flagList) > 0:
        fMaterial.mat_only_DL.commands.append(setGeo)
        if matWriteMethod == GfxMatWriteMethod.WriteDifferingAndRevert:
            fMaterial.revert.commands.append(SPClearGeometryMode(setGeo.flagList))
    if len(clearGeo.flagList) > 0:
        fMaterial.mat_only_DL.commands.append(clearGeo)
        if matWriteMethod == GfxMatWriteMethod.WriteDifferingAndRevert:
            fMaterial.revert.commands.append(SPSetGeometryMode(clearGeo.flagList))


def saveModeSetting(fMaterial, value, defaultValue, cmdClass):
    if value != defaultValue:
        fMaterial.mat_only_DL.commands.append(cmdClass(value))
        fMaterial.revert.commands.append(cmdClass(defaultValue))


def saveOtherModeHDefinition(fMaterial, settings, tlut, defaults, matWriteMethod, f3d):
    if matWriteMethod == GfxMatWriteMethod.WriteAll:
        saveOtherModeHDefinitionAll(fMaterial, settings, tlut, defaults, f3d)
    elif matWriteMethod == GfxMatWriteMethod.WriteDifferingAndRevert:
        saveOtherModeHDefinitionIndividual(fMaterial, settings, tlut, defaults)
    else:
        raise PluginError("Unhandled material write method: " + str(matWriteMethod))


def saveOtherModeHDefinitionAll(fMaterial, settings, tlut, defaults, f3d):
    cmd = SPSetOtherMode("G_SETOTHERMODE_H", 4, 20 - f3d.F3D_OLD_GBI, [])
    cmd.flagList.append(settings.g_mdsft_alpha_dither)
    cmd.flagList.append(settings.g_mdsft_rgb_dither)
    cmd.flagList.append(settings.g_mdsft_combkey)
    cmd.flagList.append(settings.g_mdsft_textconv)
    cmd.flagList.append(settings.g_mdsft_text_filt)
    cmd.flagList.append(tlut)
    cmd.flagList.append(settings.g_mdsft_textlod)
    cmd.flagList.append(settings.g_mdsft_textdetail)
    cmd.flagList.append(settings.g_mdsft_textpersp)
    cmd.flagList.append(settings.g_mdsft_cycletype)
    cmd.flagList.append(settings.g_mdsft_pipeline)

    fMaterial.mat_only_DL.commands.append(cmd)


def saveOtherModeHDefinitionIndividual(fMaterial, settings, tlut, defaults):
    saveModeSetting(fMaterial, settings.g_mdsft_alpha_dither, defaults.g_mdsft_alpha_dither, DPSetAlphaDither)
    saveModeSetting(fMaterial, settings.g_mdsft_rgb_dither, defaults.g_mdsft_rgb_dither, DPSetColorDither)
    saveModeSetting(fMaterial, settings.g_mdsft_combkey, defaults.g_mdsft_combkey, DPSetCombineKey)
    saveModeSetting(fMaterial, settings.g_mdsft_textconv, defaults.g_mdsft_textconv, DPSetTextureConvert)
    saveModeSetting(fMaterial, settings.g_mdsft_text_filt, defaults.g_mdsft_text_filt, DPSetTextureFilter)
    saveModeSetting(fMaterial, tlut, "G_TT_NONE", DPSetTextureLUT)
    saveModeSetting(fMaterial, settings.g_mdsft_textlod, defaults.g_mdsft_textlod, DPSetTextureLOD)
    saveModeSetting(fMaterial, settings.g_mdsft_textdetail, defaults.g_mdsft_textdetail, DPSetTextureDetail)
    saveModeSetting(fMaterial, settings.g_mdsft_textpersp, defaults.g_mdsft_textpersp, DPSetTexturePersp)
    saveModeSetting(fMaterial, settings.g_mdsft_cycletype, defaults.g_mdsft_cycletype, DPSetCycleType)
    saveModeSetting(fMaterial, settings.g_mdsft_pipeline, defaults.g_mdsft_pipeline, DPPipelineMode)


def saveOtherModeLDefinition(fMaterial, settings, defaults, defaultRenderMode, matWriteMethod, f3d):
    if matWriteMethod == GfxMatWriteMethod.WriteAll:
        saveOtherModeLDefinitionAll(fMaterial, settings, defaults, f3d)
    elif matWriteMethod == GfxMatWriteMethod.WriteDifferingAndRevert:
        saveOtherModeLDefinitionIndividual(fMaterial, settings, defaults, defaultRenderMode)
    else:
        raise PluginError("Unhandled material write method: " + str(matWriteMethod))


def saveOtherModeLDefinitionAll(fMaterial: FMaterial, settings, defaults, f3d):
    baseLength = 3 if not settings.set_rendermode else 32
    cmd = SPSetOtherMode("G_SETOTHERMODE_L", 0, baseLength - f3d.F3D_OLD_GBI, [])
    cmd.flagList.append(settings.g_mdsft_alpha_compare)
    cmd.flagList.append(settings.g_mdsft_zsrcsel)

    if settings.set_rendermode:
        flagList, blendList = getRenderModeFlagList(settings, fMaterial)
        cmd.flagList.extend(flagList)
        if blendList is not None:
            cmd.flagList.extend(
                [
                    "GBL_c1(" + blendList[0] + ", " + blendList[1] + ", " + blendList[2] + ", " + blendList[3] + ")",
                    "GBL_c2(" + blendList[4] + ", " + blendList[5] + ", " + blendList[6] + ", " + blendList[7] + ")",
                ]
            )

    fMaterial.mat_only_DL.commands.append(cmd)

    if settings.g_mdsft_zsrcsel == "G_ZS_PRIM":
        fMaterial.mat_only_DL.commands.append(DPSetPrimDepth(z=settings.prim_depth.z, dz=settings.prim_depth.dz))


def saveOtherModeLDefinitionIndividual(fMaterial, settings, defaults, defaultRenderMode):
    saveModeSetting(fMaterial, settings.g_mdsft_alpha_compare, defaults.g_mdsft_alpha_compare, DPSetAlphaCompare)

    saveModeSetting(fMaterial, settings.g_mdsft_zsrcsel, defaults.g_mdsft_zsrcsel, DPSetDepthSource)

    if settings.g_mdsft_zsrcsel == "G_ZS_PRIM":
        fMaterial.mat_only_DL.commands.append(DPSetPrimDepth(z=settings.prim_depth.z, dz=settings.prim_depth.dz))
        fMaterial.revert.commands.append(DPSetPrimDepth())

    if settings.set_rendermode:
        flagList, blendList = getRenderModeFlagList(settings, fMaterial)
        renderModeSet = DPSetRenderMode(flagList, blendList)

        fMaterial.mat_only_DL.commands.append(renderModeSet)
        if defaultRenderMode is not None:
            fMaterial.revert.commands.append(DPSetRenderMode(defaultRenderMode, None))


def getRenderModeFlagList(settings, fMaterial):
    flagList = []
    blendList = None
    # cycle independent

    if not settings.rendermode_advanced_enabled:
        fMaterial.renderModeUseDrawLayer = [
            settings.rendermode_preset_cycle_1 == "Use Draw Layer",
            settings.rendermode_preset_cycle_2 == "Use Draw Layer",
        ]

        if settings.g_mdsft_cycletype == "G_CYC_2CYCLE":
            flagList = [settings.rendermode_preset_cycle_1, settings.rendermode_preset_cycle_2]
        else:
            cycle2 = settings.rendermode_preset_cycle_1 + "2"
            if cycle2 not in [value[0] for value in enumRenderModesCycle2]:
                cycle2 = "G_RM_NOOP"
            flagList = [settings.rendermode_preset_cycle_1, cycle2]
    else:
        if settings.g_mdsft_cycletype == "G_CYC_2CYCLE":
            blendList = [
                settings.blend_p1,
                settings.blend_a1,
                settings.blend_m1,
                settings.blend_b1,
                settings.blend_p2,
                settings.blend_a2,
                settings.blend_m2,
                settings.blend_b2,
            ]
        else:
            blendList = [
                settings.blend_p1,
                settings.blend_a1,
                settings.blend_m1,
                settings.blend_b1,
                settings.blend_p1,
                settings.blend_a1,
                settings.blend_m1,
                settings.blend_b1,
            ]

        if settings.aa_en:
            flagList.append("AA_EN")
        if settings.z_cmp:
            flagList.append("Z_CMP")
        if settings.z_upd:
            flagList.append("Z_UPD")
        if settings.im_rd:
            flagList.append("IM_RD")
        if settings.clr_on_cvg:
            flagList.append("CLR_ON_CVG")

        flagList.append(settings.cvg_dst)
        flagList.append(settings.zmode)

        if settings.cvg_x_alpha:
            flagList.append("CVG_X_ALPHA")
        if settings.alpha_cvg_sel:
            flagList.append("ALPHA_CVG_SEL")
        if settings.force_bl:
            flagList.append("FORCE_BL")

    return flagList, blendList


def saveOtherDefinition(fMaterial, material, defaults):
    settings = material.rdp_settings
    if settings.clip_ratio != defaults.clip_ratio:
        fMaterial.mat_only_DL.commands.append(SPClipRatio(settings.clip_ratio))
        fMaterial.revert.commands.append(SPClipRatio(defaults.clip_ratio))

    if material.set_blend:
        fMaterial.mat_only_DL.commands.append(
            DPSetBlendColor(
                int(material.blend_color[0] * 255),
                int(material.blend_color[1] * 255),
                int(material.blend_color[2] * 255),
                int(material.blend_color[3] * 255),
            )
        )


enumMatWriteMethod = [
    ("Differing", "Write Differing And Revert", "Write Differing And Revert"),
    ("All", "Write All", "Write All"),
]

matWriteMethodEnumDict = {"Differing": GfxMatWriteMethod.WriteDifferingAndRevert, "All": GfxMatWriteMethod.WriteAll}


def getWriteMethodFromEnum(enumVal):
    if enumVal not in matWriteMethodEnumDict:
        raise PluginError("Enum value " + str(enumVal) + " not found in material write method dict.")
    else:
        return matWriteMethodEnumDict[enumVal]


def exportF3DtoC(dirPath, obj, DLFormat, transformMatrix, texDir, savePNG, texSeparate, name, matWriteMethod):
    inline = bpy.context.scene.exportInlineF3D
    fModel = FModel(name, DLFormat, matWriteMethod if not inline else GfxMatWriteMethod.WriteAll)
    fMeshes = exportF3DCommon(obj, fModel, transformMatrix, True, name, DLFormat, not savePNG)

    if inline:
        bleed_gfx = BleedGraphics()
        bleed_gfx.bleed_fModel(fModel, fMeshes)

    modelDirPath = os.path.join(dirPath, toAlnum(name))

    if not os.path.exists(modelDirPath):
        os.makedirs(modelDirPath)

    gfxFormatter = GfxFormatter(ScrollMethod.Vertex, 64, None)
    exportData = fModel.to_c(TextureExportSettings(texSeparate, savePNG, texDir, modelDirPath), gfxFormatter)
    staticData = exportData.staticData
    dynamicData = exportData.dynamicData
    texC = exportData.textureData

    if DLFormat == DLFormat.Static:
        staticData.append(dynamicData)
    else:
        geoString = writeMaterialFiles(
            dirPath,
            modelDirPath,
            '#include "actors/' + toAlnum(name) + '/header.h"',
            '#include "actors/' + toAlnum(name) + '/material.inc.h"',
            dynamicData.header,
            dynamicData.source,
            "",
            True,
        )

    if texSeparate:
        texCFile = open(os.path.join(modelDirPath, "texture.inc.c"), "w", newline="\n")
        texCFile.write(texC.source)
        texCFile.close()

    writeCData(staticData, os.path.join(modelDirPath, "header.h"), os.path.join(modelDirPath, "model.inc.c"))


def removeDL(sourcePath, headerPath, DLName):
    DLDataC = readFile(sourcePath)
    originalDataC = DLDataC

    DLDataH = readFile(headerPath)
    originalDataH = DLDataH

    matchResult = re.search(
        "Gfx\s*" + re.escape(DLName) + "\s*\[\s*[0-9x]*\s*\]\s*=\s*\{([^}]*)}\s*;\s*", DLDataC, re.DOTALL
    )
    if matchResult is not None:
        DLDataC = DLDataC[: matchResult.start(0)] + DLDataC[matchResult.end(0) :]

    headerMatch = getDeclaration(DLDataH, DLName)
    if headerMatch is not None:
        DLDataH = DLDataH[: headerMatch.start(0)] + DLDataH[headerMatch.end(0) :]

    if DLDataC != originalDataC:
        writeFile(sourcePath, DLDataC)

    if DLDataH != originalDataH:
        writeFile(headerPath, DLDataH)


class F3D_ExportDL(bpy.types.Operator):
    # set bl_ properties
    bl_idname = "object.f3d_export_dl"
    bl_label = "Export Display List"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            allObjs = context.selected_objects
            if len(allObjs) == 0:
                raise PluginError("No objects selected.")
            obj = context.selected_objects[0]
            if obj.type != "MESH":
                raise PluginError("Object is not a mesh.")

            scaleValue = bpy.context.scene.blenderF3DScale
            finalTransform = mathutils.Matrix.Diagonal(mathutils.Vector((scaleValue, scaleValue, scaleValue))).to_4x4()

        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        try:
            applyRotation([obj], math.radians(90), "X")

            exportPath = bpy.path.abspath(context.scene.DLExportPath)
            dlFormat = DLFormat.Static if context.scene.DLExportisStatic else DLFormat.Dynamic
            texDir = bpy.context.scene.DLTexDir
            savePNG = bpy.context.scene.saveTextures
            separateTexDef = bpy.context.scene.DLSeparateTextureDef
            DLName = bpy.context.scene.DLName
            matWriteMethod = getWriteMethodFromEnum(context.scene.matWriteMethod)

            exportF3DtoC(
                exportPath,
                obj,
                dlFormat,
                finalTransform,
                texDir,
                savePNG,
                separateTexDef,
                DLName,
                matWriteMethod,
            )

            self.report({"INFO"}, "Success!")

            applyRotation([obj], math.radians(-90), "X")
            return {"FINISHED"}  # must return a set

        except Exception as e:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            applyRotation([obj], math.radians(-90), "X")

            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


class F3D_ExportDLPanel(bpy.types.Panel):
    bl_idname = "F3D_PT_export_dl"
    bl_label = "F3D Exporter"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Fast64"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return True

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.operator(F3D_ExportDL.bl_idname)

        prop_split(col, context.scene, "DLName", "Name")
        prop_split(col, context.scene, "DLExportPath", "Export Path")
        prop_split(col, context.scene, "blenderF3DScale", "Scale")
        prop_split(col, context.scene, "matWriteMethod", "Material Write Method")
        col.prop(context.scene, "DLExportisStatic")

        if context.scene.saveTextures:
            prop_split(col, context.scene, "DLTexDir", "Texture Include Path")
            col.prop(context.scene, "DLSeparateTextureDef")


f3d_writer_classes = (
    F3D_ExportDL,
    F3D_ExportDLPanel,
)


def f3d_writer_register():
    for cls in f3d_writer_classes:
        register_class(cls)

    bpy.types.Scene.matWriteMethod = bpy.props.EnumProperty(items=enumMatWriteMethod)


def f3d_writer_unregister():
    for cls in reversed(f3d_writer_classes):
        unregister_class(cls)

    del bpy.types.Scene.matWriteMethod
