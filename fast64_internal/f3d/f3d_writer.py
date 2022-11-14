from typing import Union
import functools
import bpy, bmesh, mathutils, os, re, copy, math
from math import pi, ceil
from io import BytesIO
from bpy.utils import register_class, unregister_class

from .f3d_enums import *
from .f3d_constants import *
from .f3d_material import (
    all_combiner_uses,
    getMaterialScrollDimensions,
    getTmemWordUsage,
    getTmemMax,
    bitSizeDict,
    texBitSizeOf,
    texFormatOf,
    TextureProperty,
    F3DMaterialProperty,
)
from .f3d_gbi import *
from .f3d_gbi import _DPLoadTextureBlock

from ..utility import *


class FImageKey:
    def __init__(
        self, image: bpy.types.Image, texFormat: str, palFormat: str, imagesSharingPalette: list[bpy.types.Image] = []
    ):
        self.image = image
        self.texFormat = texFormat
        self.palFormat = palFormat
        self.imagesSharingPalette = tuple(imagesSharingPalette)

    def __hash__(self) -> int:
        return hash((self.image, self.texFormat, self.palFormat, self.imagesSharingPalette))

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, FImageKey):
            return False
        return (
            self.image == __o.image
            and self.texFormat == __o.texFormat
            and self.palFormat == __o.palFormat
            and self.imagesSharingPalette == __o.imagesSharingPalette
        )


class FPaletteKey:
    def __init__(self, palFormat: str, imagesSharingPalette: list[bpy.types.Image] = []):
        self.palFormat = palFormat
        self.imagesSharingPalette = tuple(imagesSharingPalette)

    def __hash__(self) -> int:
        return hash((self.palFormat, self.imagesSharingPalette))

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, FPaletteKey):
            return False
        return self.palFormat == __o.palFormat and self.imagesSharingPalette == __o.imagesSharingPalette


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


def getInfoDict(obj):
    fixLargeUVs(obj)
    obj.data.calc_loop_triangles()
    obj.data.calc_normals_split()
    if len(obj.data.materials) == 0:
        raise PluginError("Mesh does not have any Fast3D materials.")

    infoDict = MeshInfo()

    vertDict = infoDict.vert
    edgeDict = infoDict.edge
    f3dVertDict = infoDict.f3dVert
    edgeValidDict = infoDict.edgeValid
    validNeighborDict = infoDict.validNeighbors

    mesh: bpy.types.Mesh = obj.data
    uv_data: bpy.types.bpy_prop_collection | list[bpy.types.MeshUVLoop] = None
    if len(obj.data.uv_layers) == 0:
        uv_data = obj.data.uv_layers.new().data
    else:
        uv_data = None
        for uv_layer in obj.data.uv_layers:
            if uv_layer.name == "UVMap":
                uv_data = uv_layer.data
        if uv_data is None:
            raise PluginError("Object '" + obj.name + "' does not have a UV layer named 'UVMap.'")
    for face in mesh.loop_triangles:
        validNeighborDict[face] = []
        material = obj.material_slots[face.material_index].material
        if material is None:
            raise PluginError("There are some faces on your mesh that are assigned to an empty material slot.")
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
            convertInfo = LoopConvertInfo(
                uv_data, obj, isLightingDisabled(obj.material_slots[face.material_index].material)
            )
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
            raise PluginError("Object '" + obj.name + "' does not have a UV layer named 'UVMap.'")

    texSizeDict = {}
    if len(obj.data.materials) == 0:
        raise PluginError(f"{obj.name}: This object needs an f3d material on it.")

        # Don't get tex dimensions here, as it also processes unused materials.
        # texSizeDict[material] = getTexDimensions(material)

    for polygon in mesh.polygons:
        material = obj.material_slots[polygon.material_index].material
        if material is None:
            raise PluginError("There are some faces on your mesh that are assigned to an empty material slot.")

        if material not in texSizeDict:
            texSizeDict[material] = getTexDimensions(material)
        if material.f3d_mat.use_large_textures:
            continue

        f3dMat = material.f3d_mat

        UVinterval = [
            2 if f3dMat.tex0.S.mirror or f3dMat.tex1.S.mirror else 1,
            2 if f3dMat.tex0.T.mirror or f3dMat.tex1.T.mirror else 1,
        ]

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


class TileLoad:
    def __init__(self, texFormat, twoTextures, texDimensions):
        self.sl = None
        self.sh = None
        self.tl = None
        self.th = None

        self.texFormat = texFormat
        self.twoTextures = twoTextures
        self.texDimensions = texDimensions
        self.tmemMax = getTmemMax(texFormat)

    def getLow(self, value):
        return int(max(math.floor(value), 0))

    def getHigh(self, value, field):
        # 1024 wraps around to 0
        # -1 is because the high value is (max value - 1)
        # ex. 32 pixel width -> high = 31
        return int(min(math.ceil(value), min(self.texDimensions[field], 1024)) - 1)

    def tryAppend(self, other):
        return self.appendTile(other.sl, other.sh, other.tl, other.th)

    def appendTile(self, sl, sh, tl, th):
        new_sl = min(sl, self.sl)
        new_sh = max(sh, self.sh)
        new_tl = min(tl, self.tl)
        new_th = max(th, self.th)
        newWidth = abs(new_sl - new_sh) + 1
        newHeight = abs(new_tl - new_th) + 1

        tmemUsage = getTmemWordUsage(self.texFormat, newWidth, newHeight) * 8 * (2 if self.twoTextures else 1)

        if tmemUsage > self.tmemMax:
            return False
        else:
            self.sl = new_sl
            self.sh = new_sh
            self.tl = new_tl
            self.th = new_th
            return True

    def tryAdd(self, points):
        if len(points) == 0:
            return True

        sl = self.getLow(points[0][0])
        sh = self.getHigh(points[0][0], 0)
        tl = self.getLow(points[0][1])
        th = self.getHigh(points[0][1], 1)

        if self.sl is None:
            self.sl = sl
            self.sh = sh
            self.tl = tl
            self.th = th

        for point in points:
            sl = min(self.getLow(point[0]), sl)
            sh = max(self.getHigh(point[0], 0), sh)
            tl = min(self.getLow(point[1]), tl)
            th = max(self.getHigh(point[1], 1), th)

        return self.appendTile(sl, sh, tl, th)

    def getDimensions(self):
        return [abs(self.sl - self.sh) + 1, abs(self.tl - self.th) + 1]


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
    isPointSampled = isTexturePointSampled(material)
    exportVertexColors = isLightingDisabled(material)
    uv_data = obj.data.uv_layers["UVMap"].data
    convertInfo = LoopConvertInfo(uv_data, obj, exportVertexColors)

    if fMaterial.largeTextureIndex == 0:
        texFormat = f3dMat.tex0.tex_format
        otherTex = f3dMat.tex1
        otherTextureIndex = 1
    else:
        texFormat = f3dMat.tex1.tex_format
        otherTex = f3dMat.tex0
        otherTextureIndex = 0

    twoTextures = fMaterial.texturesLoaded[0] and fMaterial.texturesLoaded[1]
    tileLoads = {}
    faceTileLoads = {}
    for face in faces:
        uvs = [UVtoST(obj, loopIndex, uv_data, texDimensions, isPointSampled) for loopIndex in face.loops]

        faceTileLoad = TileLoad(texFormat, twoTextures, texDimensions)
        faceTileLoads[face] = faceTileLoad
        if not faceTileLoad.tryAdd(uvs):
            raise PluginError(
                "Large texture material "
                + str(material.name)
                + " has a triangle that is too large to fit in a single tile load."
            )

        added = False
        for tileLoad, sortedFaces in tileLoads.items():
            if tileLoad.tryAppend(faceTileLoad):
                sortedFaces.append(face)
                added = True
                break
        if not added:
            tileLoads[faceTileLoad] = [face]

    tileLoads = list(tileLoads.items())

    if material.name != lastMaterialName:
        fMesh.add_material_call(fMaterial)
    triGroup = fMesh.tri_group_new(fMaterial)
    fMesh.draw.commands.append(SPDisplayList(triGroup.triList))

    # For materials with tex0 and tex1, if the other texture can fit into a single tile load,
    # we load it once at the beginning only.
    otherTexSingleLoad = False
    if fMaterial.texturesLoaded[otherTextureIndex]:
        tmem = getTmemWordUsage(otherTex.tex_format, otherTex.tex.size[0], otherTex.tex.size[1]) * 8
        if tmem <= getTmemMax(otherTex.tex_format):
            otherTexSingleLoad = True
            # nextTmem = 0
            # revertCommands = GfxList("temp", GfxListTag.Draw, fModel.DLFormat) # Unhandled?
            # texDimensions, nextTmem = \
            # 	saveTextureIndex(material.name, fModel, fMaterial, triGroup.triList, revertCommands, otherTex, 0, nextTmem,
            # 		None, False, None, True, True)

    # saveGeometry(obj, triList, fMesh.vertexList, bFaces,
    # 	bMesh, texDimensions, transformMatrix, isPointSampled, isFlatShaded,
    # 	exportVertexColors, fModel.f3d)
    currentGroupIndex = None
    imageKey0, imageKey1 = getImageKeys(f3dMat, False)
    for tileLoad, tileFaces in tileLoads:
        revertCommands = GfxList("temp", GfxListTag.Draw, fModel.DLFormat)
        nextTmem = 0
        triGroup.triList.commands.append(DPPipeSync())
        if fMaterial.texturesLoaded[0] and not (otherTextureIndex == 0 and otherTexSingleLoad):
            texDimensions0, nextTmem, fImage0 = saveTextureIndex(
                material.name,
                fModel,
                fMaterial,
                triGroup.triList,
                revertCommands,
                f3dMat.tex0,
                0,
                nextTmem,
                None,
                False,
                [tileLoad, None],
                True,
                False,
                None,
                imageKey0,
            )
        if fMaterial.texturesLoaded[1] and not (otherTextureIndex == 1 and otherTexSingleLoad):
            texDimensions1, nextTmem, fImage1 = saveTextureIndex(
                material.name,
                fModel,
                fMaterial,
                triGroup.triList,
                revertCommands,
                f3dMat.tex1,
                1,
                nextTmem,
                None,
                False,
                [None, tileLoad],
                True,
                False,
                None,
                imageKey1,
            )

        triConverter = TriangleConverter(
            triConverterInfo,
            texDimensions,
            material,
            currentGroupIndex,
            triGroup.triList,
            triGroup.vertexList,
            copy.deepcopy(existingVertData),
            copy.deepcopy(matRegionDict),
        )

        currentGroupIndex = saveTriangleStrip(triConverter, tileFaces, obj.data, False)

        if len(revertCommands.commands) > 0:
            fMesh.draw.commands.extend(revertCommands.commands)

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

    facesByMat = {}
    for face in obj.data.loop_triangles:
        if face.material_index not in facesByMat:
            facesByMat[face.material_index] = []
        facesByMat[face.material_index].append(face)

    fMeshes = {}
    for material_index, faces in facesByMat.items():
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

        if fMaterial.useLargeTextures:
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
            fModel.onEndDraw(fMesh, obj)
            revertMatAndEndDraw(fMesh.draw, [])
        else:
            fModel.endDraw(fMesh, obj)
    return fMeshes


def addCullCommand(obj, fMesh, transformMatrix, matWriteMethod):
    fMesh.add_cull_vtx()
    # if the object has a specifically set culling bounds, use that instead
    for vertexPos in obj.get("culling_bounds", obj.bound_box):
        # Most other fields of convertVertexData are unnecessary for bounding box verts
        fMesh.cullVertexList.vertices.append(
            convertVertexData(
                obj.data,
                mathutils.Vector(vertexPos),
                [0, 0],
                mathutils.Vector([0, 0, 0, 0]),
                [32, 32],
                transformMatrix,
                False,
                False,
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
            SPCullDisplayList(0, 7),
        ]
    else:
        raise PluginError("Unhandled material write method for f3d culling: " + str(matWriteMethod))
    fMesh.draw.commands = cullCommands + fMesh.draw.commands


def exportF3DCommon(obj, fModel, transformMatrix, includeChildren, name, DLFormat, convertTextureData):
    tempObj, meshList = combineObjects(obj, includeChildren, None, None)
    try:
        drawLayer = fModel.getDrawLayerV3(tempObj)
        infoDict = getInfoDict(tempObj)
        triConverterInfo = TriangleConverterInfo(tempObj, None, fModel.f3d, transformMatrix, infoDict)
        fMesh = saveStaticModel(
            triConverterInfo, fModel, tempObj, transformMatrix, name, convertTextureData, True, None
        )[drawLayer]
        cleanupCombineObj(tempObj, meshList)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
    except Exception as e:
        cleanupCombineObj(tempObj, meshList)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        raise Exception(str(e))

    return fMesh


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
            DPSetCombineMode(*S_SHADED_SOLID),
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


def saveTriangleStrip(triConverter, faces, mesh, terminateDL):
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

        triConverter.addFace(neighborFace)
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


# Necessary for UV half pixel offset (see 13.7.5.3)
def isTexturePointSampled(material):
    f3dMat = material.f3d_mat

    return f3dMat.rdp_settings.g_mdsft_text_filt == "G_TF_POINT"


def isLightingDisabled(material):
    f3dMat = material.f3d_mat
    return not f3dMat.rdp_settings.g_lighting


# Necessary as G_SHADE_SMOOTH actually does nothing
def checkIfFlatShaded(material):
    if material.mat_ver > 3:
        f3dMat = material.f3d_mat
    else:
        f3dMat = material
    return not f3dMat.rdp_settings.g_shade_smooth


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
    isPointSampled = isTexturePointSampled(material)
    exportVertexColors = isLightingDisabled(material)
    uv_data = obj.data.uv_layers["UVMap"].data
    convertInfo = LoopConvertInfo(uv_data, obj, exportVertexColors)

    if material.name != lastMaterialName:
        fMesh.add_material_call(fMaterial)
    triGroup = fMesh.tri_group_new(fMaterial)
    fMesh.draw.commands.append(SPDisplayList(triGroup.triList))

    triConverter = TriangleConverter(
        triConverterInfo,
        texDimensions,
        material,
        currentGroupIndex,
        triGroup.triList,
        triGroup.vertexList,
        copy.deepcopy(existingVertData),
        copy.deepcopy(matRegionDict),
    )

    currentGroupIndex = saveTriangleStrip(triConverter, faces, obj.data, True)

    if fMaterial.revert is not None:
        fMesh.draw.commands.append(SPDisplayList(fMaterial.revert))

    return currentGroupIndex


def get8bitRoundedNormal(loop: bpy.types.MeshLoop, mesh):
    alpha_layer = getColorLayer(mesh, "Alpha")

    if alpha_layer is not None:
        normalizedAColor = alpha_layer[loop.index].color
        if is3_2_or_above():
            normalizedAColor = gammaCorrect(normalizedAColor)
        normalizedA = colorToLuminance(normalizedAColor[0:3])
    else:
        normalizedA = 1

    # Don't round, as this may move UV toward UV bounds.
    return mathutils.Vector(
        (int(loop.normal[0] * 128) / 128, int(loop.normal[1] * 128) / 128, int(loop.normal[2] * 128) / 128, normalizedA)
    )


class LoopConvertInfo:
    def __init__(self, uv_data: bpy.types.bpy_prop_collection | list[bpy.types.MeshUVLoop], obj, exportVertexColors):
        self.uv_data: bpy.types.bpy_prop_collection | list[bpy.types.MeshUVLoop] = uv_data
        self.obj = obj
        self.exportVertexColors = exportVertexColors


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


# Color and normal are separate, since for parsing, the normal must be transformed into
# bone/object space while the color should just be a regular conversion.
class F3DVert:
    def __init__(
        self,
        position: mathutils.Vector,
        uv: mathutils.Vector,
        color: mathutils.Vector | None,  # 4 components
        normal: mathutils.Vector | None,  # 4 components
    ):
        self.position: mathutils.Vector = position
        self.uv: mathutils.Vector = uv
        self.color: mathutils.Vector | None = color
        self.normal: mathutils.Vector | None = normal

    def __eq__(self, other):
        if not isinstance(other, F3DVert):
            return False
        return (
            self.position == other.position
            and self.uv == other.uv
            and self.color == other.color
            and self.normal == other.normal
        )

    def getColorOrNormal(self):
        if self.color is None and self.normal is None:
            raise PluginError("An F3D vert has neither a color or a normal.")
        elif self.color is not None:
            return self.color
        else:
            return self.normal


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
        triList,
        vtxList,
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

        self.triList = triList
        self.vtxList = vtxList

        isPointSampled = isTexturePointSampled(material)
        exportVertexColors = isLightingDisabled(material)
        uv_data = triConverterInfo.obj.data.uv_layers["UVMap"].data
        self.convertInfo = LoopConvertInfo(uv_data, triConverterInfo.obj, exportVertexColors)
        self.texDimensions = texDimensions
        self.isPointSampled = isPointSampled
        self.exportVertexColors = exportVertexColors
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
                    convertVertexData(
                        self.triConverterInfo.mesh,
                        bufferVert.f3dVert.position,
                        bufferVert.f3dVert.uv,
                        bufferVert.f3dVert.getColorOrNormal(),
                        self.texDimensions,
                        self.triConverterInfo.getTransformMatrix(bufferVert.groupIndex),
                        self.isPointSampled,
                        self.exportVertexColors,
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
                    convertVertexData(
                        self.triConverterInfo.mesh,
                        bufferVert.f3dVert.position,
                        bufferVert.f3dVert.uv,
                        bufferVert.f3dVert.getColorOrNormal(),
                        self.texDimensions,
                        self.triConverterInfo.getTransformMatrix(bufferVert.groupIndex),
                        self.isPointSampled,
                        self.exportVertexColors,
                        tex_scale=self.tex_scale,
                    )
                )

            bufferStart = bufferEnd

        # Load triangles
        self.triList.commands.extend(
            createTriangleCommands(self.vertexBufferTriangles, self.vertBuffer, self.triConverterInfo.f3d.F3DEX_GBI)
        )

    def addFace(self, face):
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
    position: mathutils.Vector = mesh.vertices[loop.vertex_index].co.copy().freeze()
    # N64 is -Y, Blender is +Y
    uv: mathutils.Vector = convertInfo.uv_data[loop.index].uv.copy()
    uv[:] = [field if not math.isnan(field) else 0 for field in uv]
    uv[1] = 1 - uv[1]
    uv = uv.freeze()
    color, normal = getLoopColorOrNormal(
        loop, face, convertInfo.obj.data, convertInfo.obj, convertInfo.exportVertexColors
    )

    return F3DVert(position, uv, color, normal)


def getLoopNormal(loop: bpy.types.MeshLoop, face, mesh, isFlatShaded):
    # This is a workaround for flat shading not working well.
    # Since we support custom blender normals we can now ignore this.
    # if isFlatShaded:
    # 	normal = -face.normal #???
    # else:
    # 	normal = -loop.normal #???
    # return get8bitRoundedNormal(normal).freeze()
    return get8bitRoundedNormal(loop, mesh).freeze()


"""
def getLoopNormalCreased(bLoop, obj):
	edges = obj.data.edges
	centerVert = bLoop.vert

	availableFaces = []
	visitedFaces = [bLoop.face]
	connectedFaces = getConnectedFaces(bLoop.face, bLoop.vert)
	if len(connectedFaces) == 0:
		return bLoop.calc_normal()

	for face in connectedFaces:
		availableFaces.append(FaceWeight(face, bLoop.face, 1))

	curNormal = bLoop.calc_normal() * bLoop.calc_angle()
	while len(availableFaces) > 0:
		nextFaceWeight = getHighestFaceWeight(availableFaces)
		curNormal += getWeightedNormalAndMoveToNextFace(
			nextFaceWeight, visitedFaces, availableFaces, centerVert, edges)

	return curNormal.normalized()

def getConnectedFaces(bFace, bVert):
	connectedFaces = []
	for face in bVert.link_faces:
		if face == bFace:
			continue
		for edge in face.edges:
			if bFace in edge.link_faces:
				connectedFaces.append(face)
	return connectedFaces

# returns false if not enough faces to check for creasing
def getNextFace(faceWeight, bVert, visitedFaces, availableFaces):
	connectedFaces = getConnectedFaces(faceWeight.face, bVert)
	visitedFaces.append(faceWeight.face)

	newFaceFound = False
	nextPrevFace = faceWeight.face
	for face in connectedFaces:
		if face in visitedFaces:
			continue
		elif not newFaceFound:
			newFaceFound = True
			faceWeight.prevFace = faceWeight.face
			faceWeight.face = face
		else:
			availableFaces.append(FaceWeight(face, nextPrevFace,
				faceWeight.weight))

	if not newFaceFound:
		availableFaces.remove(faceWeight)

	removedFaceWeights = []
	for otherFaceWeight in availableFaces:
		if otherFaceWeight.face in visitedFaces:
			removedFaceWeights.append(otherFaceWeight)
	for removedFaceWeight in removedFaceWeights:
		availableFaces.remove(removedFaceWeight)

def getLoopFromFaceVert(bFace, bVert):
	for loop in bFace.loops:
		if loop.vert == bVert:
			return loop
	return None

def getEdgeBetweenFaces(faceWeight):
	face1 = faceWeight.face
	face2 = faceWeight.prevFace
	for edge1 in face1.edges:
		for edge2 in face2.edges:
			if edge1 == edge2:
				return edge1
	return None

class FaceWeight:
	def __init__(self, face, prevFace, weight):
		self.face = face
		self.prevFace = prevFace
		self.weight = weight

def getWeightedNormalAndMoveToNextFace(selectFaceWeight, visitedFaces,
	availableFaces, centerVert, edges):
	selectLoop = getLoopFromFaceVert(selectFaceWeight.face, centerVert)
	edgeIndex = getEdgeBetweenFaces(selectFaceWeight).index

	# Ignore triangulated faces
	if edgeIndex < len(edges):
		selectFaceWeight.weight *= 1 - edges[edgeIndex].crease

	getNextFace(selectFaceWeight, centerVert, visitedFaces, availableFaces)
	return selectLoop.calc_normal() * selectLoop.calc_angle() * \
		selectFaceWeight.weight

def getHighestFaceWeight(faceWeights):
	highestFaceWeight = faceWeights[0]
	for faceWeight in faceWeights[1:]:
		if faceWeight.weight > highestFaceWeight.weight:
			highestFaceWeight = faceWeight
	return highestFaceWeight
"""


def UVtoST(obj, loopIndex, uv_data, texDimensions, isPointSampled):
    uv = uv_data[loopIndex].uv.copy()
    uv[1] = 1 - uv[1]
    loopUV = uv.freeze()

    pixelOffset = 0 if isPointSampled else 0.5
    return [
        convertFloatToFixed16(loopUV[0] * texDimensions[0] - pixelOffset) / 32,
        convertFloatToFixed16(loopUV[1] * texDimensions[1] - pixelOffset) / 32,
    ]


def convertVertexData(
    mesh,
    loopPos,
    loopUV,
    loopColorOrNormal,
    texDimensions,
    transformMatrix,
    isPointSampled,
    exportVertexColors,
    tex_scale=(1, 1),
):
    # Position (8 bytes)
    position = [int(round(floatValue)) for floatValue in (transformMatrix @ loopPos)]

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

    uv = [
        convertFloatToFixed16(loopUV[0] * texDimensions[0] - pixelOffset[0]),
        convertFloatToFixed16(loopUV[1] * texDimensions[1] - pixelOffset[1]),
    ]

    # Color/Normal (4 bytes)
    if exportVertexColors:
        colorOrNormal = [scaleToU8(c).to_bytes(1, "big")[0] for c in loopColorOrNormal]
    else:
        # normal transformed correctly.
        normal = (transformMatrix.inverted().transposed() @ loopColorOrNormal).normalized()
        colorOrNormal = [
            int(round(normal[0] * 127)).to_bytes(1, "big", signed=True)[0],
            int(round(normal[1] * 127)).to_bytes(1, "big", signed=True)[0],
            int(round(normal[2] * 127)).to_bytes(1, "big", signed=True)[0],
            scaleToU8(loopColorOrNormal[3]).to_bytes(1, "big")[0],
        ]

    return Vtx(position, uv, colorOrNormal)


@functools.lru_cache(0)
def is3_2_or_above():
    return bpy.app.version[0] >= 3 and bpy.app.version[1] >= 2


def getLoopColor(loop: bpy.types.MeshLoop, mesh, mat_ver):

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


def getLoopColorOrNormal(
    loop: bpy.types.MeshLoop, face, mesh: bpy.types.Mesh, obj: bpy.types.Object, exportVertexColors: bool
) -> tuple[mathutils.Vector, None] | tuple[None, mathutils.Vector]:
    material = obj.material_slots[face.material_index].material
    isFlatShaded = checkIfFlatShaded(material)
    if exportVertexColors:
        return getLoopColor(loop, mesh, material.mat_ver), None
    else:
        return None, getLoopNormal(loop, face, mesh, isFlatShaded)


def createTriangleCommands(triangles, vertexBuffer, useSP2Triangle):
    triangles = copy.deepcopy(triangles)
    commands = []
    if useSP2Triangle:
        while len(triangles) > 0:
            if len(triangles) >= 2:
                commands.append(
                    SP2Triangles(
                        vertexBuffer.index(triangles[0][0]),
                        vertexBuffer.index(triangles[0][1]),
                        vertexBuffer.index(triangles[0][2]),
                        0,
                        vertexBuffer.index(triangles[1][0]),
                        vertexBuffer.index(triangles[1][1]),
                        vertexBuffer.index(triangles[1][2]),
                        0,
                    )
                )
                triangles = triangles[2:]
            else:
                commands.append(
                    SP1Triangle(
                        vertexBuffer.index(triangles[0][0]),
                        vertexBuffer.index(triangles[0][1]),
                        vertexBuffer.index(triangles[0][2]),
                        0,
                    )
                )
                triangles = []
    else:
        while len(triangles) > 0:
            commands.append(
                SP1Triangle(
                    vertexBuffer.index(triangles[0][0]),
                    vertexBuffer.index(triangles[0][1]),
                    vertexBuffer.index(triangles[0][2]),
                    0,
                )
            )
            triangles = triangles[1:]

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


class FSharedPalette:
    def __init__(self, name):
        self.name = name
        self.palette = []


def getImageKeys(f3dMat: F3DMaterialProperty, useSharedCIPalette: bool) -> tuple[FImageKey, FImageKey]:
    imageKey0 = FImageKey(
        f3dMat.tex0.tex,
        f3dMat.tex0.tex_format,
        f3dMat.tex0.ci_format,
        [f3dMat.tex0.tex] + ([f3dMat.tex1.tex] if useSharedCIPalette else []),
    )
    imageKey1 = FImageKey(
        f3dMat.tex1.tex,
        f3dMat.tex1.tex_format,
        f3dMat.tex1.ci_format,
        ([f3dMat.tex0.tex] if useSharedCIPalette else []) + [f3dMat.tex1.tex],
    )

    return imageKey0, imageKey1


def saveOrGetF3DMaterial(material, fModel, obj, drawLayer, convertTextureData):
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
    fMaterial = FMaterial(materialName, fModel.DLFormat)
    fMaterial.material.commands.append(DPPipeSync())
    fMaterial.revert.commands.append(DPPipeSync())

    if not material.is_f3d:
        raise PluginError("Material named " + material.name + " is not an F3D material.")

    fMaterial.getScrollData(material, getMaterialScrollDimensions(f3dMat))

    if f3dMat.set_combiner:
        if f3dMat.rdp_settings.g_mdsft_cycletype == "G_CYC_2CYCLE":
            fMaterial.material.commands.append(
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
            fMaterial.material.commands.append(
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
        fMaterial.material.commands.extend(
            [
                DPSetFogColor(*corrected_color),
                SPFogPosition(fog_position[0], fog_position[1]),
            ]
        )

    useDict = all_combiner_uses(f3dMat)

    if drawLayer is not None:
        defaultRM = fModel.getRenderMode(drawLayer)
    else:
        defaultRM = None

    defaults = bpy.context.scene.world.rdp_defaults
    if fModel.f3d.F3DEX_GBI_2:
        saveGeoModeDefinitionF3DEX2(fMaterial, f3dMat.rdp_settings, defaults, fModel.matWriteMethod)
    else:
        saveGeoModeDefinition(fMaterial, f3dMat.rdp_settings, defaults, fModel.matWriteMethod)
    saveOtherModeHDefinition(fMaterial, f3dMat.rdp_settings, defaults, fModel.f3d._HW_VERSION_1, fModel.matWriteMethod)
    saveOtherModeLDefinition(fMaterial, f3dMat.rdp_settings, defaults, defaultRM, fModel.matWriteMethod)
    saveOtherDefinition(fMaterial, f3dMat, defaults)

    # Set scale
    s = int(min(round(f3dMat.tex_scale[0] * 0x10000), 0xFFFF))
    t = int(min(round(f3dMat.tex_scale[1] * 0x10000), 0xFFFF))
    if f3dMat.rdp_settings.g_mdsft_textlod == "G_TL_LOD":
        fMaterial.material.commands.append(
            SPTexture(s, t, f3dMat.rdp_settings.num_textures_mipmapped - 1, fModel.f3d.G_TX_RENDERTILE, 1)
        )
    else:
        fMaterial.material.commands.append(SPTexture(s, t, 0, fModel.f3d.G_TX_RENDERTILE, 1))

    # Save textures
    texDimensions0 = None
    texDimensions1 = None
    nextTmem = 0

    useLargeTextures = material.mat_ver > 3 and f3dMat.use_large_textures

    useTex0 = useDict["Texture 0"] and f3dMat.tex0.tex_set
    isTex0CI = f3dMat.tex0.tex_format[:2] == "CI"
    useTex1 = useDict["Texture 1"] and f3dMat.tex1.tex_set
    isTex1CI = f3dMat.tex1.tex_format[:2] == "CI"

    useSharedCIPalette = (
        useTex0
        and useTex1
        and isTex0CI
        and isTex1CI
        and not f3dMat.tex0.use_tex_reference
        and not f3dMat.tex1.use_tex_reference
        and f3dMat.tex0.tex_format == f3dMat.tex1.tex_format
        and f3dMat.tex0.ci_format == f3dMat.tex1.ci_format
    )

    # Without shared palette: (load pal0 -> load tex0) or (load pal1 -> load tex1)
    # with shared palette: load pal -> load tex0 -> load tex1
    if useSharedCIPalette:
        sharedPalette = FSharedPalette(getSharedPaletteName(f3dMat))

        # dummy lists to be appended in later
        loadGfx = GfxList(None, None, fModel.DLFormat)
        revertGfx = GfxList(None, None, fModel.DLFormat)
    else:
        sharedPalette = None
        loadGfx = fMaterial.material
        revertGfx = fMaterial.revert

    imageKey0, imageKey1 = getImageKeys(f3dMat, useSharedCIPalette)

    if useTex0:
        if f3dMat.tex0.tex is None and not f3dMat.tex0.use_tex_reference:
            raise PluginError('In material "' + material.name + '", a texture has not been set.')

        fMaterial.useLargeTextures = useLargeTextures
        fMaterial.texturesLoaded[0] = True
        texDimensions0, nextTmem, fImage0 = saveTextureIndex(
            material.name,
            fModel,
            fMaterial,
            loadGfx,
            revertGfx,
            f3dMat.tex0,
            0,
            nextTmem,
            None,
            convertTextureData,
            None,
            True,
            True,
            sharedPalette,
            imageKey0,
        )

    # If the texture in both texels is the same then it can be rewritten to the same location in tmem
    # This allows for a texture that fills tmem to still be used for both texel0 and texel1
    if f3dMat.tex0.tex == f3dMat.tex1.tex:
        if nextTmem >= (512 if f3dMat.tex0.tex_format[:2] != "CI" else 256):
            nextTmem = 0

    if useTex1:
        if f3dMat.tex1.tex is None and not f3dMat.tex1.use_tex_reference:
            raise PluginError('In material "' + material.name + '", a texture has not been set.')

        fMaterial.useLargeTextures = useLargeTextures
        fMaterial.texturesLoaded[1] = True
        texDimensions1, nextTmem, fImage1 = saveTextureIndex(
            material.name,
            fModel,
            fMaterial,
            loadGfx,
            revertGfx,
            f3dMat.tex1,
            1,
            nextTmem,
            None,
            convertTextureData,
            None,
            True,
            True,
            sharedPalette,
            imageKey1,
        )

    if useSharedCIPalette:
        texFormat = f3dMat.tex0.tex_format
        palFormat = f3dMat.tex0.ci_format

        fPalette, paletteKey = saveOrGetPaletteOnlyDefinition(
            fMaterial,
            fModel,
            [f3dMat.tex0.tex, f3dMat.tex1.tex],
            sharedPalette.name,
            texFormat,
            palFormat,
            convertTextureData,
            sharedPalette.palette,
        )
        savePaletteLoading(
            fMaterial.material,
            fMaterial.revert,
            fPalette,
            palFormat,
            0,
            fPalette.height,
            fModel.f3d,
            fModel.matWriteMethod,
        )

        # Append these commands after palette loading commands
        fMaterial.material.commands.extend(loadGfx.commands)
        fMaterial.revert.commands.extend(revertGfx.commands)

        fImage0.paletteKey = paletteKey
        fImage1.paletteKey = paletteKey

    # Used so we know how to convert normalized UVs when saving verts.
    if texDimensions0 is not None and texDimensions1 is not None:
        if f3dMat.uv_basis == "TEXEL0":
            texDimensions = texDimensions0
            fMaterial.largeTextureIndex = 0
        else:
            texDimensions = texDimensions1
            fMaterial.largeTextureIndex = 1

    elif texDimensions0 is not None:
        texDimensions = texDimensions0
        fMaterial.largeTextureIndex = 0
    elif texDimensions1 is not None:
        texDimensions = texDimensions1
        fMaterial.largeTextureIndex = 1
    else:
        texDimensions = [32, 32]

    nodes = material.node_tree.nodes
    if useDict["Primitive"] and f3dMat.set_prim:
        color = exportColor(f3dMat.prim_color[0:3]) + [scaleToU8(f3dMat.prim_color[3])]
        fMaterial.material.commands.append(
            DPSetPrimColor(scaleToU8(f3dMat.prim_lod_min), scaleToU8(f3dMat.prim_lod_frac), *color)
        )

    if useDict["Environment"] and f3dMat.set_env:
        color = exportColor(f3dMat.env_color[0:3]) + [scaleToU8(f3dMat.env_color[3])]
        fMaterial.material.commands.append(DPSetEnvColor(*color))

    # Checking for f3dMat.rdp_settings.g_lighting here will prevent accidental exports,
    # There may be some edge case where this isn't desired.
    if useDict["Shade"] and f3dMat.set_lights and f3dMat.rdp_settings.g_lighting:
        fLights = saveLightsDefinition(fModel, fMaterial, f3dMat, materialName + "_lights")
        fMaterial.material.commands.extend([SPSetLights(fLights)])  # TODO: handle synching: NO NEED?

    if useDict["Key"] and f3dMat.set_key:
        if material.mat_ver == 4:
            center = f3dMat.key_center
        else:
            center = nodes["Chroma Key Center"].outputs[0].default_value
        scale = f3dMat.key_scale
        width = f3dMat.key_width
        fMaterial.material.commands.extend(
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
        fMaterial.material.commands.extend(
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

    materialKey = (
        material,
        (drawLayer if f3dMat.rdp_settings.set_rendermode else None),
        fModel.global_data.getCurrentAreaKey(f3dMat),
    )
    fModel.materials[materialKey] = (fMaterial, texDimensions)

    return fMaterial, texDimensions


def getTextureName(texProp: TextureProperty, fModelName: str, overrideName: str) -> str:
    tex = texProp.tex
    texFormat = texProp.tex_format
    if not texProp.use_tex_reference:
        if tex.filepath == "":
            name = tex.name
        else:
            name = tex.filepath
    else:
        name = texProp.tex_reference
    texName = (
        fModelName
        + "_"
        + (getNameFromPath(name, True) + "_" + texFormat.lower() if overrideName is None else overrideName)
    )

    return texName


def getSharedPaletteName(f3dMat: F3DMaterialProperty):
    image0 = f3dMat.tex0.tex
    image1 = f3dMat.tex1.tex
    texFormat = f3dMat.tex0.tex_format.lower()
    tex0Name = getNameFromPath(image0.filepath if image0.filepath != "" else image0.name, True)
    tex1Name = getNameFromPath(image1.filepath if image1.filepath != "" else image1.name, True)

    return f"{tex0Name}_x_{tex1Name}_{texFormat}_pal"


def getTextureNameTexRef(texProp: TextureProperty, fModelName: str) -> str:
    texFormat = texProp.tex_format
    name = texProp.tex_reference
    texName = fModelName + "_" + (getNameFromPath(name, True) + "_" + texFormat.lower())

    return texName


def saveTextureIndex(
    propName: str,
    fModel: FModel,
    fMaterial: FMaterial,
    loadTexGfx: GfxList,
    revertTexGfx: GfxList,
    texProp: TextureProperty,
    index: int,
    tmem: int,
    overrideName: str,
    convertTextureData: bool,
    tileSettingsOverride,
    loadTextures: bool,
    loadPalettes: bool,
    sharedPalette: FSharedPalette,
    imageKey: FImageKey,
) -> tuple[list[int], int, FImage]:
    tex = texProp.tex

    if tex is not None and (tex.size[0] == 0 or tex.size[1] == 0):
        raise PluginError(
            "Image " + tex.name + " has either a 0 width or height; image may have been removed from original location."
        )

    if not texProp.use_tex_reference:
        if tex is None:
            raise PluginError("In " + propName + ", no texture is selected.")
        elif len(tex.pixels) == 0:
            raise PluginError(
                "Could not load missing texture: "
                + tex.name
                + ". Make sure this texture has not been deleted or moved on disk."
            )

    texFormat = texProp.tex_format
    isCITexture = texFormat[:2] == "CI"
    palFormat = texProp.ci_format if isCITexture else ""

    texName = getTextureName(texProp, fModel.name, overrideName)

    if tileSettingsOverride is not None:
        tileSettings = tileSettingsOverride[index]
        width, height = tileSettings.getDimensions()
        setTLUTMode = False
    else:
        tileSettings = None
        if texProp.use_tex_reference:
            width, height = texProp.tex_reference_size
        else:
            width, height = tex.size
        setTLUTMode = fModel.matWriteMethod == GfxMatWriteMethod.WriteAll

    nextTmem = tmem + getTmemWordUsage(texFormat, width, height)

    if not (bpy.context.scene.ignoreTextureRestrictions or fMaterial.useLargeTextures):
        if nextTmem > (512 if texFormat[:2] != "CI" else 256):
            raise PluginError(
                'Error in "'
                + propName
                + '": Textures are too big. Max TMEM size is 4k '
                + "bytes, ex. 2 32x32 RGBA 16 bit textures.\nNote that texture width will be internally padded to 64 bit boundaries."
            )
    if width > 1024 or height > 1024:
        raise PluginError('Error in "' + propName + '": Any side of an image cannot be greater ' + "than 1024.")

    if tileSettings is None:
        clamp_S = texProp.S.clamp
        mirror_S = texProp.S.mirror
        tex_SL = texProp.S.low
        tex_SH = texProp.S.high
        mask_S = texProp.S.mask
        shift_S = texProp.S.shift

        clamp_T = texProp.T.clamp
        mirror_T = texProp.T.mirror
        tex_TL = texProp.T.low
        tex_TH = texProp.T.high
        mask_T = texProp.T.mask
        shift_T = texProp.T.shift

    else:
        clamp_S = True
        mirror_S = False
        tex_SL = tileSettings.sl
        tex_SH = tileSettings.sh
        mask_S = 0
        shift_S = 0

        clamp_T = True
        mirror_T = False
        tex_TL = tileSettings.tl
        tex_TH = tileSettings.th
        mask_T = 0
        shift_T = 0

    if isCITexture:
        if texProp.use_tex_reference:
            fImage = FImage(texProp.tex_reference, None, None, width, height, None, False)
            fPalette = FImage(texProp.pal_reference, None, None, 1, texProp.pal_reference_size, None, False)
        else:
            # fPalette should be an fImage here, since sharedPalette is None
            fImage, fPalette, alreadyExists = saveOrGetPaletteAndImageDefinition(
                fMaterial,
                fModel,
                tex,
                texName,
                texFormat,
                palFormat,
                convertTextureData,
                sharedPalette,
                imageKey,
            )

        if loadPalettes and sharedPalette is None:
            savePaletteLoading(
                loadTexGfx, revertTexGfx, fPalette, palFormat, 0, fPalette.height, fModel.f3d, fModel.matWriteMethod
            )
    else:
        if texProp.use_tex_reference:
            fImage = FImage(texProp.tex_reference, None, None, width, height, None, False)
        else:
            fImage = saveOrGetTextureDefinition(fMaterial, fModel, tex, texName, texFormat, convertTextureData)

    if setTLUTMode and not isCITexture:
        loadTexGfx.commands.append(DPSetTextureLUT("G_TT_NONE"))
    if loadTextures:
        saveTextureLoading(
            fMaterial,
            fImage,
            loadTexGfx,
            clamp_S,
            mirror_S,
            clamp_T,
            mirror_T,
            mask_S,
            mask_T,
            shift_S,
            shift_T,
            tex_SL,
            tex_TL,
            tex_SH,
            tex_TH,
            texFormat,
            index,
            fModel.f3d,
            tmem,
        )
    texDimensions = fImage.width, fImage.height
    # fImage = saveTextureDefinition(fModel, tex, texName,
    # 	texFormatOf[texFormat], texBitSizeOf[texFormat])
    # fModel.textures[texName] = fImage

    return texDimensions, nextTmem, fImage


# texIndex: 0 for texture0, 1 for texture1
def saveTextureLoading(
    fMaterial,
    fImage,
    loadTexGfx,
    clamp_S,
    mirror_S,
    clamp_T,
    mirror_T,
    mask_S,
    mask_T,
    shift_S,
    shift_T,
    SL,
    TL,
    SH,
    TH,
    tex_format,
    texIndex,
    f3d: F3D,
    tmem,
):
    cms = [("G_TX_CLAMP" if clamp_S else "G_TX_WRAP"), ("G_TX_MIRROR" if mirror_S else "G_TX_NOMIRROR")]
    cmt = [("G_TX_CLAMP" if clamp_T else "G_TX_WRAP"), ("G_TX_MIRROR" if mirror_T else "G_TX_NOMIRROR")]
    masks = mask_S
    maskt = mask_T
    shifts = shift_S if shift_S >= 0 else (shift_S + 16)
    shiftt = shift_T if shift_T >= 0 else (shift_T + 16)

    # print('Low ' + str(SL) + ' ' + str(TL))
    sl = int(SL * (2**f3d.G_TEXTURE_IMAGE_FRAC))
    tl = int(TL * (2**f3d.G_TEXTURE_IMAGE_FRAC))
    sh = int(SH * (2**f3d.G_TEXTURE_IMAGE_FRAC))
    th = int(TH * (2**f3d.G_TEXTURE_IMAGE_FRAC))

    fmt = texFormatOf[tex_format]
    siz = texBitSizeOf[tex_format]
    pal = 0 if fmt[:2] != "CI" else 0  # handle palettes

    # texelsPerWord = int(round(64 / bitSizeDict[siz]))
    useLoadBlock = not fImage.isLargeTexture and isPowerOf2(fImage.width) and isPowerOf2(fImage.height)

    # LoadTile will pad rows to 64 bit word alignment, while
    # LoadBlock assumes this is already done.

    # These commands are basically DPLoadMultiBlock/Tile,
    # except for the load tile index which will be 6 instead of 7 for render tile = 1.
    # This may be unnecessary, but at this point DPLoadMultiBlock/Tile is not implemented yet
    # so it would be extra work for the same outcome.
    base_width = int(fImage.width)
    if fImage.isLargeTexture:
        # TODO: Use width of block to load
        base_width = int(SH - SL)

    if siz == "G_IM_SIZ_4b":
        sl2 = int(SL * (2 ** (f3d.G_TEXTURE_IMAGE_FRAC - 1)))
        sh2 = int(SH * (2 ** (f3d.G_TEXTURE_IMAGE_FRAC - 1)))

        dxt = f3d.CALC_DXT_4b(fImage.width)
        line = (((base_width + 1) >> 1) + 7) >> 3

        if useLoadBlock:
            loadTexGfx.commands.extend(
                [
                    DPSetTextureImage(fmt, "G_IM_SIZ_16b", 1, fImage),
                    DPSetTile(
                        fmt,
                        "G_IM_SIZ_16b",
                        0,
                        tmem,
                        f3d.G_TX_LOADTILE - texIndex,
                        0,
                        cmt,
                        maskt,
                        shiftt,
                        cms,
                        masks,
                        shifts,
                    ),
                    DPLoadBlock(
                        f3d.G_TX_LOADTILE - texIndex, 0, 0, (((fImage.width) * (fImage.height) + 3) >> 2) - 1, dxt
                    ),
                ]
            )
        else:
            loadTexGfx.commands.extend(
                [
                    DPSetTextureImage(fmt, "G_IM_SIZ_8b", fImage.width >> 1, fImage),
                    DPSetTile(
                        fmt,
                        "G_IM_SIZ_8b",
                        line,
                        tmem,
                        f3d.G_TX_LOADTILE - texIndex,
                        0,
                        cmt,
                        maskt,
                        shiftt,
                        cms,
                        masks,
                        shifts,
                    ),
                    DPLoadTile(f3d.G_TX_LOADTILE - texIndex, sl2, tl, sh2, th),
                ]
            )

    else:
        dxt = f3d.CALC_DXT(fImage.width, f3d.G_IM_SIZ_VARS[siz + "_BYTES"])
        # Note that _LINE_BYTES and _TILE_BYTES variables are the same.
        line = int((base_width * f3d.G_IM_SIZ_VARS[siz + "_LINE_BYTES"]) + 7) >> 3

        if useLoadBlock:
            loadTexGfx.commands.extend(
                [
                    # Load Block version
                    DPSetTextureImage(fmt, siz + "_LOAD_BLOCK", 1, fImage),
                    DPSetTile(
                        fmt,
                        siz + "_LOAD_BLOCK",
                        0,
                        tmem,
                        f3d.G_TX_LOADTILE - texIndex,
                        0,
                        cmt,
                        maskt,
                        shiftt,
                        cms,
                        masks,
                        shifts,
                    ),
                    DPLoadBlock(
                        f3d.G_TX_LOADTILE - texIndex,
                        0,
                        0,
                        (
                            ((fImage.width) * (fImage.height) + f3d.G_IM_SIZ_VARS[siz + "_INCR"])
                            >> f3d.G_IM_SIZ_VARS[siz + "_SHIFT"]
                        )
                        - 1,
                        dxt,
                    ),
                ]
            )
        else:
            loadTexGfx.commands.extend(
                [
                    # Load Tile version
                    DPSetTextureImage(fmt, siz, fImage.width, fImage),
                    DPSetTile(
                        fmt, siz, line, tmem, f3d.G_TX_LOADTILE - texIndex, 0, cmt, maskt, shiftt, cms, masks, shifts
                    ),
                    DPLoadTile(f3d.G_TX_LOADTILE - texIndex, sl, tl, sh, th),
                ]
            )  # added in

    tileSizeCommand = DPSetTileSize(f3d.G_TX_RENDERTILE + texIndex, sl, tl, sh, th)
    loadTexGfx.commands.extend(
        [
            DPSetTile(
                fmt, siz, line, tmem, f3d.G_TX_RENDERTILE + texIndex, pal, cmt, maskt, shiftt, cms, masks, shifts
            ),
            tileSizeCommand,
        ]
    )  # added in)

    # hasattr check for FTexRect
    if hasattr(fMaterial, "tileSizeCommands"):
        fMaterial.tileSizeCommands[f3d.G_TX_RENDERTILE + texIndex] = tileSizeCommand


# palette stored in upper half of TMEM (words 256-511)
# pal is palette number (0-16), for CI8 always set to 0
def savePaletteLoading(loadTexGfx, revertTexGfx, fPalette, palFormat, pal, colorCount, f3d, matWriteMethod):
    palFmt = texFormatOf[palFormat]
    cms = ["G_TX_WRAP", "G_TX_NOMIRROR"]
    cmt = ["G_TX_WRAP", "G_TX_NOMIRROR"]

    loadTexGfx.commands.append(DPSetTextureLUT("G_TT_RGBA16" if palFmt == "G_IM_FMT_RGBA" else "G_TT_IA16"))
    if matWriteMethod == GfxMatWriteMethod.WriteDifferingAndRevert:
        revertTexGfx.commands.append(DPSetTextureLUT("G_TT_NONE"))

    if not f3d._HW_VERSION_1:
        loadTexGfx.commands.extend(
            [
                DPSetTextureImage(palFmt, "G_IM_SIZ_16b", 1, fPalette),
                DPSetTile("0", "0", 0, (256 + (((pal) & 0xF) * 16)), f3d.G_TX_LOADTILE, 0, cmt, 0, 0, cms, 0, 0),
                DPLoadTLUTCmd(f3d.G_TX_LOADTILE, colorCount - 1),
                DPLoadSync(),
            ]
        )
    else:
        loadTexGfx.commands.extend(
            [
                _DPLoadTextureBlock(
                    fPalette,
                    (256 + (((pal) & 0xF) * 16)),
                    palFmt,
                    "G_IM_SIZ_16b",
                    4 * colorCount,
                    1,
                    pal,
                    cms,
                    cmt,
                    0,
                    0,
                    0,
                    0,
                )
            ]
        )


def saveOrGetPaletteOnlyDefinition(
    fMaterial: FMaterial,
    fModel: FModel,
    images: list[bpy.types.Image],
    imageName: str,
    texFmt: str,
    palFmt: str,
    convertTextureData: bool,
    palette: list[int],
) -> tuple[FImage, tuple[bpy.types.Image, tuple[str, str]]]:

    palFormat = texFormatOf[palFmt]
    paletteName = checkDuplicateTextureName(fModel, toAlnum(imageName) + "_pal_" + palFmt.lower())
    paletteKey = FPaletteKey(palFmt, images)
    paletteFilename = getNameFromPath(imageName, True) + "." + fModel.getTextureSuffixFromFormat(texFmt) + ".pal"

    fPalette = FImage(
        paletteName,
        palFormat,
        "G_IM_SIZ_16b",
        1,
        len(palette),
        paletteFilename,
        convertTextureData,
    )

    if fMaterial.useLargeTextures:
        fPalette.isLargeTexture = True

    if convertTextureData:
        for color in palette:
            fPalette.data.extend(color.to_bytes(2, "big"))

    # print(f"Palette data: {paletteName} - length {len(fPalette.data)}")

    fModel.addTexture(paletteKey, fPalette, fMaterial)
    return fPalette, paletteKey


def saveOrGetPaletteAndImageDefinition(
    fMaterial,
    fModelOrTexRect,
    image,
    imageName,
    texFmt,
    palFmt,
    convertTextureData,
    sharedPalette: FSharedPalette,
    imageKey: FImageKey,
) -> tuple[FImage, FImage, bool]:
    texFormat = texFormatOf[texFmt]
    palFormat = texFormatOf[palFmt]
    bitSize = texBitSizeOf[texFmt]
    # If image already loaded, return that data.
    fImage, fPalette = fModelOrTexRect.getTextureAndHandleShared(imageKey)
    if fImage is not None:
        # print(f"Image already exists")
        return fImage, fPalette, True

    # print(f"Size: {str(image.size[0])} x {str(image.size[1])}, Data: {str(len(image.pixels))}")
    if sharedPalette is not None:
        palette = sharedPalette.palette
    else:
        palette = []
    texture = []
    maxColors = 16 if bitSize == "G_IM_SIZ_4b" else 256
    if convertTextureData:
        # N64 is -Y, Blender is +Y
        pixels = image.pixels[:]
        for j in reversed(range(image.size[1])):
            for i in range(image.size[0]):
                color = [1, 1, 1, 1]
                for field in range(image.channels):
                    color[field] = pixels[(j * image.size[0] + i) * image.channels + field]
                if palFormat == "G_IM_FMT_RGBA":
                    pixelColor = getRGBA16Tuple(color)
                elif palFormat == "G_IM_FMT_IA":
                    pixelColor = getIA16Tuple(color)
                else:
                    raise PluginError("Invalid combo: " + palFormat + ", " + bitSize)

                if pixelColor not in palette:
                    palette.append(pixelColor)
                    if len(palette) > maxColors:
                        raise PluginError(
                            "Texture "
                            + imageName
                            + " has more than "
                            + str(maxColors)
                            + " colors, or is part of a shared palette with too many colors."
                        )
                texture.append(palette.index(pixelColor))

    if image.filepath == "":
        name = image.name
    else:
        name = image.filepath
    filename = getNameFromPath(name, True) + "." + fModelOrTexRect.getTextureSuffixFromFormat(texFmt) + ".inc.c"

    # paletteFilename = getNameFromPath(name, True) + '.' + \
    # 	fModelOrTexRect.getTextureSuffixFromFormat(palFmt) + '.inc.c'
    fImage = FImage(
        checkDuplicateTextureName(fModelOrTexRect, toAlnum(imageName)),
        texFormat,
        bitSize,
        image.size[0],
        image.size[1],
        filename,
        convertTextureData,
    )

    if fMaterial.useLargeTextures:
        fImage.isLargeTexture = True

    # paletteImage = bpy.data.images.new(paletteName, 1, len(palette))
    # paletteImage.pixels = palette
    # paletteImage.filepath = paletteFilename

    if convertTextureData:
        if bitSize == "G_IM_SIZ_4b":
            fImage.data = compactNibbleArray(texture, image.size[0], image.size[1])
        else:
            fImage.data = bytearray(texture)

    fModelOrTexRect.addTexture(imageKey, fImage, fMaterial)

    # For shared palettes, paletteName should be the same for the same imageName until
    # the next saveOrGetPaletteOnlyDefinition
    # Make sure paletteName is read here before saveOrGetPaletteOnlyDefinition is called.
    paletteName = checkDuplicateTextureName(fModelOrTexRect, toAlnum(imageName) + "_pal_" + palFmt.lower())

    if sharedPalette is None:
        fPalette, paletteKey = saveOrGetPaletteOnlyDefinition(
            fMaterial, fModelOrTexRect, [image], imageName, texFmt, palFmt, convertTextureData, palette
        )
        fImage.paletteKey = paletteKey
    else:
        fPalette = None
        fImage.paletteKey = None

    return fImage, fPalette, False  # , paletteImage


def compactNibbleArray(texture, width, height):
    nibbleData = bytearray(0)
    dataSize = int(width * height / 2)

    nibbleData = [((texture[i * 2] & 0xF) << 4) | (texture[i * 2 + 1] & 0xF) for i in range(dataSize)]

    if (width * height) % 2 == 1:
        nibbleData.append((texture[-1] & 0xF) << 4)

    return bytearray(nibbleData)


def checkDuplicateTextureName(fModelOrTexRect, name):
    names = []
    for info, texture in fModelOrTexRect.textures.items():
        names.append(texture.name)
    while name in names:
        name = name + "_copy"
    return name


def saveOrGetTextureDefinition(fMaterial, fModel, image: bpy.types.Image, imageName, texFormat, convertTextureData):
    fmt = texFormatOf[texFormat]
    bitSize = texBitSizeOf[texFormat]

    # If image already loaded, return that data.
    # We use NONE here for pal format since this function is only to be called for non-ci textures.
    imageKey = FImageKey(image, texFormat, "NONE")
    fImage, fPalette = fModel.getTextureAndHandleShared(imageKey)
    if fImage is not None:
        return fImage

    if image.filepath == "":
        name = image.name
    else:
        name = image.filepath
    filename = getNameFromPath(name, True) + "." + fModel.getTextureSuffixFromFormat(texFormat) + ".inc.c"

    fImage = FImage(
        checkDuplicateTextureName(fModel, toAlnum(imageName)),
        fmt,
        bitSize,
        image.size[0],
        image.size[1],
        filename,
        convertTextureData,
    )
    if fMaterial.useLargeTextures:
        fImage.isLargeTexture = True

    if convertTextureData:
        pixels = image.pixels[:]
        # print(f"Converting texture data for {filename}")
        if fmt == "G_IM_FMT_RGBA":
            if bitSize == "G_IM_SIZ_16b":
                # fImage.data = bytearray([byteVal for doubleByte in [
                # 	(((int(image.pixels[(j * image.size[0] + i) * image.channels + 0] * 0x1F) & 0x1F) << 11) | \
                # 	((int(image.pixels[(j * image.size[0] + i) * image.channels + 1] * 0x1F) & 0x1F) << 6) | \
                # 	((int(image.pixels[(j * image.size[0] + i) * image.channels + 2] * 0x1F) & 0x1F) << 1) | \
                # 	(1 if image.pixels[(j * image.size[0] + i) * image.channels + 3] > 0.5 else 0)
                # 	).to_bytes(2, 'big')
                # 	for j in reversed(range(image.size[1])) for i in range(image.size[0])] for byteVal in doubleByte])

                fImage.data = bytearray(
                    [
                        byteVal
                        for doubleByte in [
                            (
                                (
                                    (
                                        (int(round(pixels[(j * image.size[0] + i) * image.channels + 0] * 0x1F)) & 0x1F)
                                        << 3
                                    )
                                    | (
                                        (int(round(pixels[(j * image.size[0] + i) * image.channels + 1] * 0x1F)) & 0x1F)
                                        >> 2
                                    )
                                ),
                                (
                                    (
                                        (int(round(pixels[(j * image.size[0] + i) * image.channels + 1] * 0x1F)) & 0x03)
                                        << 6
                                    )
                                    | (
                                        (int(round(pixels[(j * image.size[0] + i) * image.channels + 2] * 0x1F)) & 0x1F)
                                        << 1
                                    )
                                    | (1 if pixels[(j * image.size[0] + i) * image.channels + 3] > 0.5 else 0)
                                ),
                            )
                            for j in reversed(range(image.size[1]))
                            for i in range(image.size[0])
                        ]
                        for byteVal in doubleByte
                    ]
                )
            elif bitSize == "G_IM_SIZ_32b":
                fImage.data = bytearray(
                    [
                        int(round(pixels[(j * image.size[0] + i) * image.channels + field] * 0xFF)) & 0xFF
                        for j in reversed(range(image.size[1]))
                        for i in range(image.size[0])
                        for field in range(image.channels)
                    ]
                )
            else:
                raise PluginError("Invalid combo: " + fmt + ", " + bitSize)

        elif fmt == "G_IM_FMT_YUV":
            raise PluginError("YUV not yet implemented.")
            if bitSize == "G_IM_SIZ_16b":
                pass
            else:
                raise PluginError("Invalid combo: " + fmt + ", " + bitSize)

        elif fmt == "G_IM_FMT_CI":
            raise PluginError("CI not yet implemented.")

        elif fmt == "G_IM_FMT_IA":
            if bitSize == "G_IM_SIZ_4b":
                fImage.data = bytearray(
                    [
                        (
                            (
                                int(
                                    round(
                                        colorToLuminance(
                                            pixels[
                                                (j * image.size[0] + i)
                                                * image.channels : (j * image.size[0] + i)
                                                * image.channels
                                                + 3
                                            ]
                                        )
                                        * 0x7
                                    )
                                )
                                & 0x7
                            )
                            << 1
                        )
                        | (1 if pixels[(j * image.size[0] + i) * image.channels + 3] > 0.5 else 0)
                        for j in reversed(range(image.size[1]))
                        for i in range(image.size[0])
                    ]
                )
            elif bitSize == "G_IM_SIZ_8b":
                fImage.data = bytearray(
                    [
                        (
                            (
                                int(
                                    round(
                                        colorToLuminance(
                                            pixels[
                                                (j * image.size[0] + i)
                                                * image.channels : (j * image.size[0] + i)
                                                * image.channels
                                                + 3
                                            ]
                                        )
                                        * 0xF
                                    )
                                )
                                & 0xF
                            )
                            << 4
                        )
                        | (int(round(pixels[(j * image.size[0] + i) * image.channels + 3] * 0xF)) & 0xF)
                        for j in reversed(range(image.size[1]))
                        for i in range(image.size[0])
                    ]
                )
            elif bitSize == "G_IM_SIZ_16b":
                fImage.data = bytearray(
                    [
                        byteVal
                        for doubleByte in [
                            (
                                int(
                                    round(
                                        colorToLuminance(
                                            pixels[
                                                (j * image.size[0] + i)
                                                * image.channels : (j * image.size[0] + i)
                                                * image.channels
                                                + 3
                                            ]
                                        )
                                        * 0xFF
                                    )
                                )
                                & 0xFF,
                                int(round(pixels[(j * image.size[0] + i) * image.channels + 3] * 0xFF)) & 0xFF,
                            )
                            for j in reversed(range(image.size[1]))
                            for i in range(image.size[0])
                        ]
                        for byteVal in doubleByte
                    ]
                )
            else:
                raise PluginError("Invalid combo: " + fmt + ", " + bitSize)
        elif fmt == "G_IM_FMT_I":
            if bitSize == "G_IM_SIZ_4b":
                fImage.data = bytearray(
                    [
                        int(
                            round(
                                colorToLuminance(
                                    pixels[
                                        (j * image.size[0] + i)
                                        * image.channels : (j * image.size[0] + i)
                                        * image.channels
                                        + 3
                                    ]
                                )
                                * 0xF
                            )
                        )
                        & 0xF
                        for j in reversed(range(image.size[1]))
                        for i in range(image.size[0])
                    ]
                )
            elif bitSize == "G_IM_SIZ_8b":
                fImage.data = bytearray(
                    [
                        int(
                            round(
                                colorToLuminance(
                                    pixels[
                                        (j * image.size[0] + i)
                                        * image.channels : (j * image.size[0] + i)
                                        * image.channels
                                        + 3
                                    ]
                                )
                                * 0xFF
                            )
                        )
                        & 0xFF
                        for j in reversed(range(image.size[1]))
                        for i in range(image.size[0])
                    ]
                )
            else:
                raise PluginError("Invalid combo: " + fmt + ", " + bitSize)
        else:
            raise PluginError("Invalid image format " + fmt)

        # We stored 4bit values in byte arrays, now to convert
        if bitSize == "G_IM_SIZ_4b":
            fImage.data = compactNibbleArray(fImage.data, image.size[0], image.size[1])

    print("Finished converting.")
    fModel.addTexture(imageKey, fImage, fMaterial)

    return fImage


def saveLightsDefinition(fModel, fMaterial, material, lightsName):
    lights = fModel.getLightAndHandleShared(lightsName)
    if lights is not None:
        return lights

    lights = Lights(toAlnum(lightsName))

    if material.use_default_lighting:
        lights.a = Ambient(exportColor(material.ambient_light_color))
        lights.l.append(Light(exportColor(material.default_light_color), [0x28, 0x28, 0x28]))
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


def saveGeoModeDefinitionF3DEX2(fMaterial, settings, defaults, matWriteMethod):
    geo = SPGeometryMode([], [])

    saveBitGeoF3DEX2(settings.g_zbuffer, defaults.g_zbuffer, "G_ZBUFFER", geo, matWriteMethod)
    saveBitGeoF3DEX2(settings.g_shade, defaults.g_shade, "G_SHADE", geo, matWriteMethod)
    saveBitGeoF3DEX2(settings.g_cull_front, defaults.g_cull_front, "G_CULL_FRONT", geo, matWriteMethod)
    saveBitGeoF3DEX2(settings.g_cull_back, defaults.g_cull_back, "G_CULL_BACK", geo, matWriteMethod)
    saveBitGeoF3DEX2(settings.g_fog, defaults.g_fog, "G_FOG", geo, matWriteMethod)
    saveBitGeoF3DEX2(settings.g_lighting, defaults.g_lighting, "G_LIGHTING", geo, matWriteMethod)

    # make sure normals are saved correctly.
    saveBitGeoF3DEX2(settings.g_tex_gen, defaults.g_tex_gen, "G_TEXTURE_GEN", geo, matWriteMethod)
    saveBitGeoF3DEX2(settings.g_tex_gen_linear, defaults.g_tex_gen_linear, "G_TEXTURE_GEN_LINEAR", geo, matWriteMethod)
    saveBitGeoF3DEX2(settings.g_shade_smooth, defaults.g_shade_smooth, "G_SHADING_SMOOTH", geo, matWriteMethod)
    saveBitGeoF3DEX2(settings.g_clipping, defaults.g_clipping, "G_CLIPPING", geo, matWriteMethod)

    if len(geo.clearFlagList) != 0 or len(geo.setFlagList) != 0:
        if len(geo.clearFlagList) == 0:
            geo.clearFlagList.append("0")
        elif len(geo.setFlagList) == 0:
            geo.setFlagList.append("0")

        if matWriteMethod == GfxMatWriteMethod.WriteAll:
            fMaterial.material.commands.append(SPLoadGeometryMode(geo.setFlagList))
        else:
            fMaterial.material.commands.append(geo)
            fMaterial.revert.commands.append(SPGeometryMode(geo.setFlagList, geo.clearFlagList))


def saveBitGeo(value, defaultValue, flagName, setGeo, clearGeo, matWriteMethod):
    if value != defaultValue or matWriteMethod == GfxMatWriteMethod.WriteAll:
        if value:
            setGeo.flagList.append(flagName)
        else:
            clearGeo.flagList.append(flagName)


def saveGeoModeDefinition(fMaterial, settings, defaults, matWriteMethod):
    setGeo = SPSetGeometryMode([])
    clearGeo = SPClearGeometryMode([])

    saveBitGeo(settings.g_zbuffer, defaults.g_zbuffer, "G_ZBUFFER", setGeo, clearGeo, matWriteMethod)
    saveBitGeo(settings.g_shade, defaults.g_shade, "G_SHADE", setGeo, clearGeo, matWriteMethod)
    saveBitGeo(settings.g_cull_front, defaults.g_cull_front, "G_CULL_FRONT", setGeo, clearGeo, matWriteMethod)
    saveBitGeo(settings.g_cull_back, defaults.g_cull_back, "G_CULL_BACK", setGeo, clearGeo, matWriteMethod)
    saveBitGeo(settings.g_fog, defaults.g_fog, "G_FOG", setGeo, clearGeo, matWriteMethod)
    saveBitGeo(settings.g_lighting, defaults.g_lighting, "G_LIGHTING", setGeo, clearGeo, matWriteMethod)

    # make sure normals are saved correctly.
    saveBitGeo(settings.g_tex_gen, defaults.g_tex_gen, "G_TEXTURE_GEN", setGeo, clearGeo, matWriteMethod)
    saveBitGeo(
        settings.g_tex_gen_linear, defaults.g_tex_gen_linear, "G_TEXTURE_GEN_LINEAR", setGeo, clearGeo, matWriteMethod
    )
    saveBitGeo(settings.g_shade_smooth, defaults.g_shade_smooth, "G_SHADING_SMOOTH", setGeo, clearGeo, matWriteMethod)
    if bpy.context.scene.f3d_type == "F3DEX_GBI_2" or bpy.context.scene.f3d_type == "F3DEX_GBI":
        saveBitGeo(settings.g_clipping, defaults.g_clipping, "G_CLIPPING", setGeo, clearGeo, matWriteMethod)

    if len(setGeo.flagList) > 0:
        fMaterial.material.commands.append(setGeo)
        if matWriteMethod == GfxMatWriteMethod.WriteDifferingAndRevert:
            fMaterial.revert.commands.append(SPClearGeometryMode(setGeo.flagList))
    if len(clearGeo.flagList) > 0:
        fMaterial.material.commands.append(clearGeo)
        if matWriteMethod == GfxMatWriteMethod.WriteDifferingAndRevert:
            fMaterial.revert.commands.append(SPSetGeometryMode(clearGeo.flagList))


def saveModeSetting(fMaterial, value, defaultValue, cmdClass):
    if value != defaultValue:
        fMaterial.material.commands.append(cmdClass(value))
        fMaterial.revert.commands.append(cmdClass(defaultValue))


def saveOtherModeHDefinition(fMaterial, settings, defaults, isHWv1, matWriteMethod):
    if matWriteMethod == GfxMatWriteMethod.WriteAll:
        saveOtherModeHDefinitionAll(fMaterial, settings, defaults, isHWv1)
    elif matWriteMethod == GfxMatWriteMethod.WriteDifferingAndRevert:
        saveOtherModeHDefinitionIndividual(fMaterial, settings, defaults, isHWv1)
    else:
        raise PluginError("Unhandled material write method: " + str(matWriteMethod))


def saveOtherModeHDefinitionAll(fMaterial, settings, defaults, isHWv1):
    cmd = SPSetOtherMode("G_SETOTHERMODE_H", 4, 20, [])
    cmd.flagList.append(settings.g_mdsft_alpha_dither)
    if not isHWv1:
        cmd.flagList.append(settings.g_mdsft_rgb_dither)
        cmd.flagList.append(settings.g_mdsft_combkey)
    cmd.flagList.append(settings.g_mdsft_textconv)
    cmd.flagList.append(settings.g_mdsft_text_filt)
    cmd.flagList.append(settings.g_mdsft_textlod)
    cmd.flagList.append(settings.g_mdsft_textdetail)
    cmd.flagList.append(settings.g_mdsft_textpersp)
    cmd.flagList.append(settings.g_mdsft_cycletype)
    if isHWv1:
        cmd.flagList.append(settings.g_mdsft_color_dither)
    cmd.flagList.append(settings.g_mdsft_pipeline)

    fMaterial.material.commands.append(cmd)


def saveOtherModeHDefinitionIndividual(fMaterial, settings, defaults, isHWv1):
    saveModeSetting(fMaterial, settings.g_mdsft_alpha_dither, defaults.g_mdsft_alpha_dither, DPSetAlphaDither)

    if not isHWv1:
        saveModeSetting(fMaterial, settings.g_mdsft_rgb_dither, defaults.g_mdsft_rgb_dither, DPSetColorDither)

        saveModeSetting(fMaterial, settings.g_mdsft_combkey, defaults.g_mdsft_combkey, DPSetCombineKey)

    saveModeSetting(fMaterial, settings.g_mdsft_textconv, defaults.g_mdsft_textconv, DPSetTextureConvert)

    saveModeSetting(fMaterial, settings.g_mdsft_text_filt, defaults.g_mdsft_text_filt, DPSetTextureFilter)

    # saveModeSetting(fMaterial, settings.g_mdsft_textlut,
    # 	defaults.g_mdsft_textlut, DPSetTextureLUT)

    saveModeSetting(fMaterial, settings.g_mdsft_textlod, defaults.g_mdsft_textlod, DPSetTextureLOD)

    saveModeSetting(fMaterial, settings.g_mdsft_textdetail, defaults.g_mdsft_textdetail, DPSetTextureDetail)

    saveModeSetting(fMaterial, settings.g_mdsft_textpersp, defaults.g_mdsft_textpersp, DPSetTexturePersp)

    saveModeSetting(fMaterial, settings.g_mdsft_cycletype, defaults.g_mdsft_cycletype, DPSetCycleType)

    if isHWv1:
        saveModeSetting(fMaterial, settings.g_mdsft_color_dither, defaults.g_mdsft_color_dither, DPSetColorDither)

    saveModeSetting(fMaterial, settings.g_mdsft_pipeline, defaults.g_mdsft_pipeline, DPPipelineMode)


def saveOtherModeLDefinition(fMaterial, settings, defaults, defaultRenderMode, matWriteMethod):
    if matWriteMethod == GfxMatWriteMethod.WriteAll:
        saveOtherModeLDefinitionAll(fMaterial, settings, defaults, defaultRenderMode)
    elif matWriteMethod == GfxMatWriteMethod.WriteDifferingAndRevert:
        saveOtherModeLDefinitionIndividual(fMaterial, settings, defaults, defaultRenderMode)
    else:
        raise PluginError("Unhandled material write method: " + str(matWriteMethod))


def saveOtherModeLDefinitionAll(fMaterial: FMaterial, settings, defaults, defaultRenderMode):
    if not settings.set_rendermode and defaultRenderMode is None:
        cmd = SPSetOtherMode("G_SETOTHERMODE_L", 0, 3, [])
        cmd.flagList.append(settings.g_mdsft_alpha_compare)
        cmd.flagList.append(settings.g_mdsft_zsrcsel)

    else:
        cmd = SPSetOtherMode("G_SETOTHERMODE_L", 0, 32, [])
        cmd.flagList.append(settings.g_mdsft_alpha_compare)
        cmd.flagList.append(settings.g_mdsft_zsrcsel)

        if settings.set_rendermode:
            flagList, blendList = getRenderModeFlagList(settings, fMaterial)
            cmd.flagList.extend(flagList)
            if blendList is not None:
                cmd.flagList.extend(
                    [
                        "GBL_c1("
                        + blendList[0]
                        + ", "
                        + blendList[1]
                        + ", "
                        + blendList[2]
                        + ", "
                        + blendList[3]
                        + ")",
                        "GBL_c2("
                        + blendList[4]
                        + ", "
                        + blendList[5]
                        + ", "
                        + blendList[6]
                        + ", "
                        + blendList[7]
                        + ")",
                    ]
                )
        else:
            cmd.flagList.extend(defaultRenderMode)

    fMaterial.material.commands.append(cmd)

    if settings.g_mdsft_zsrcsel == "G_ZS_PRIM":
        fMaterial.material.commands.append(DPSetPrimDepth(z=settings.prim_depth.z, dz=settings.prim_depth.dz))
        fMaterial.revert.commands.append(DPSetPrimDepth())


def saveOtherModeLDefinitionIndividual(fMaterial, settings, defaults, defaultRenderMode):
    saveModeSetting(fMaterial, settings.g_mdsft_alpha_compare, defaults.g_mdsft_alpha_compare, DPSetAlphaCompare)

    saveModeSetting(fMaterial, settings.g_mdsft_zsrcsel, defaults.g_mdsft_zsrcsel, DPSetDepthSource)

    if settings.g_mdsft_zsrcsel == "G_ZS_PRIM":
        fMaterial.material.commands.append(DPSetPrimDepth(z=settings.prim_depth.z, dz=settings.prim_depth.dz))
        fMaterial.revert.commands.append(DPSetPrimDepth())

    if settings.set_rendermode:
        flagList, blendList = getRenderModeFlagList(settings, fMaterial)
        renderModeSet = DPSetRenderMode(flagList, blendList)

        fMaterial.material.commands.append(renderModeSet)
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
        fMaterial.material.commands.append(SPClipRatio(settings.clip_ratio))
        fMaterial.revert.commands.append(SPClipRatio(defaults.clip_ratio))

    if material.set_blend:
        fMaterial.material.commands.append(
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


def exportF3DtoC(
    dirPath, obj, DLFormat, transformMatrix, f3dType, isHWv1, texDir, savePNG, texSeparate, name, matWriteMethod
):

    fModel = FModel(f3dType, isHWv1, name, DLFormat, matWriteMethod)
    fMesh = exportF3DCommon(obj, fModel, transformMatrix, True, name, DLFormat, not savePNG)

    modelDirPath = os.path.join(dirPath, toAlnum(name))

    if not os.path.exists(modelDirPath):
        os.makedirs(modelDirPath)

    gfxFormatter = GfxFormatter(ScrollMethod.Vertex, 64)
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
            if not isinstance(obj.data, bpy.types.Mesh):
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
            f3dType = context.scene.f3d_type
            isHWv1 = context.scene.isHWv1
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
                f3dType,
                isHWv1,
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
