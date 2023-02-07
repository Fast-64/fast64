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
    texBitSizeF3D,
    texFormatOf,
    TextureProperty,
    F3DMaterialProperty,
)
from .f3d_gbi import *
from .f3d_gbi import _DPLoadTextureBlock

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
    def __init__(self, material, fMaterial, texDimensions):
        self.sl = self.tl = 1000000  # above any actual value
        self.sh = self.th = -1  # below any actual value

        self.texFormat = fMaterial.largeTexFmt
        self.is4bit = texBitSizeInt[self.texFormat] == 4
        self.tmemWordsAvail = fMaterial.largeTexWords
        self.texDimensions = texDimensions
        self.materialName = material.name
        self.isPointSampled = isTexturePointSampled(material)
        self.largeEdges = material.f3d_mat.large_edges

        self.faces = []
        self.offsets = []

    def getLow(self, value, field):
        value = int(math.floor(value))
        if self.largeEdges == "Clamp":
            value = min(max(value, 0), self.texDimensions[field] - 1)
        if self.is4bit and field == 0:
            # Must start on an even texel (round down)
            value &= ~1
        return value

    def getHigh(self, value, field):
        value = int(math.ceil(value)) - (1 if self.isPointSampled else 0)
        if self.largeEdges == "Clamp":
            value = min(max(value, 0), self.texDimensions[field] - 1)
        if self.is4bit and field == 0:
            # Must end on an odd texel (round up)
            value |= 1
        return value

    def fixRegion(self, sl, sh, tl, th):
        assert sl <= sh and tl <= th
        soffset = int(math.floor(sl / self.texDimensions[0])) * self.texDimensions[0]
        toffset = int(math.floor(tl / self.texDimensions[1])) * self.texDimensions[1]
        sl -= soffset
        sh -= soffset
        tl -= toffset
        th -= toffset
        assert 0 <= sl < self.texDimensions[0] and 0 <= tl < self.texDimensions[1]
        ret = True
        if sh >= 1024 or th >= 1024:
            ret = False
        if sh >= self.texDimensions[0]:
            # Load wraps in S. Load must start a multiple of a TMEM line from
            # the end of the texture, in order for the second load (beginning of
            # image) to start at a whole line.
            texelsPerLine = 64 // texBitSizeInt[self.texFormat]
            if texelsPerLine > self.texDimensions[0]:
                raise PluginError(
                    f"In large texture material {self.materialName}:"
                    + f" large texture must be at least {texelsPerLine} wide."
                )
            sl -= self.texDimensions[0]
            sl = int(math.floor(sl / texelsPerLine)) * texelsPerLine
            sl += self.texDimensions[0]
        if th >= self.texDimensions[1]:
            # Load wraps in T. Load must start a multiple of 2 TMEM lines from
            # the end of the texture, in order for the second load to have the
            # same odd/even line parity as the first (because texels are
            # interleaved in TMEM every other line).
            tl -= self.texDimensions[1]
            tl = int(math.floor(tl / 2.0)) * 2
            tl += self.texDimensions[1]
        tmemUsage = getTmemWordUsage(self.texFormat, sh - sl + 1, th - tl + 1)
        if tmemUsage > self.tmemWordsAvail:
            ret = False
        return ret, sl, sh, tl, th, soffset, toffset

    def initWithFace(self, obj, face):
        uv_data = obj.data.uv_layers["UVMap"].data
        faceUVs = [UVtoSTLarge(obj, loopIndex, uv_data, self.texDimensions) for loopIndex in face.loops]
        if len(faceUVs) == 0:
            return True

        for point in faceUVs:
            self.sl = min(self.sl, self.getLow(point[0], 0))
            self.sh = max(self.sh, self.getHigh(point[0], 0))
            self.tl = min(self.tl, self.getLow(point[1], 1))
            self.th = max(self.th, self.getHigh(point[1], 1))

        ret, self.sl, self.sh, self.tl, self.th, soffset, toffset = self.fixRegion(self.sl, self.sh, self.tl, self.th)
        if not ret:
            if self.sh >= 1024 or self.th >= 1024:
                raise PluginError(
                    f"Large texture material {self.materialName} has a face that needs"
                    + f" to cover texels {self.sl}-{self.sh} x {self.tl}-{self.th}"
                    + f" (image dims are {self.texDimensions}), but image space"
                    + f" only goes up to 1024 so this cannot be represented."
                )
            else:
                raise PluginError(
                    f"Large texture material {self.materialName} has a face that needs"
                    + f" to cover texels {self.sl}-{self.sh} x {self.tl}-{self.th}"
                    + f" ({self.sh-self.sl+1} x {self.th-self.tl+1} texels) "
                    + f"in format {self.texFormat}, which can't fit in TMEM."
                )
        self.faces.append(face)
        self.offsets.append((soffset, toffset))

    def trySubsume(self, other):
        # Could do fancier logic checking across borders, for example if we have
        # one loading 60-68 (size 64) and another 0-8, that could be merged to
        # one load 60-72. But this is likely to be uncommon and won't be generated
        # by the operator.
        new_sl = min(self.sl, other.sl)
        new_sh = max(self.sh, other.sh)
        new_tl = min(self.tl, other.tl)
        new_th = max(self.th, other.th)
        ret, new_sl, new_sh, new_tl, new_th, soffset, toffset = self.fixRegion(new_sl, new_sh, new_tl, new_th)
        if not ret:
            return False
        self.sl, self.sh, self.tl, self.th = new_sl, new_sh, new_tl, new_th
        self.faces.extend(other.faces)
        self.offsets.extend(other.offsets)
        return True


def maybeSaveSingleLargeTextureSetup(
    i: int,
    fMaterial: FMaterial,
    fModel: FModel,
    fImage: FImage,
    gfxOut: GfxList,
    texProp: TextureProperty,
    texDimensions: tuple[int, int],
    tileSettings: TileLoad,
    curImgSet: Union[None, int],
    curTileLines: list[int],
):
    if fMaterial.isTexLarge[i]:
        wrapS = tileSettings.sh >= texDimensions[0]
        wrapT = tileSettings.th >= texDimensions[1]
        assert 0 <= tileSettings.sl < texDimensions[0]
        assert 0 <= tileSettings.tl < texDimensions[1]
        siz = texBitSizeF3D[texProp.tex_format]
        line = getTileLine(fImage, tileSettings.sl, tileSettings.sh, siz, fModel.f3d)
        tmem = fMaterial.largeTexAddr[i]
        print(
            f"Tile: {tileSettings.sl}-{tileSettings.sh} x {tileSettings.tl}-{tileSettings.th} "
            + f"tmem {tmem} line {line}"
        )
        if wrapS or wrapT:
            fmt = texFormatOf[texProp.tex_format]
            texelsPerLine = 64 // texBitSizeInt[texProp.tex_format]
            wid = texDimensions[0]
            is4bit = siz == "G_IM_SIZ_4b"
            if is4bit:
                siz = "G_IM_SIZ_8b"
                wid >>= 1
                assert (tileSettings.sl & 1) == 0
                assert (tileSettings.sh & 1) == 1
            # TL, TH is always * 4 because tile values are 10.2 fixed.
            # SL, SH is * 2 for 4 bit and * 4 otherwise, because actually loading
            # 8 bit pairs of texels. Also written using f3d.G_TEXTURE_IMAGE_FRAC.
            sm = 2 if is4bit else 4
            nocm = ["G_TX_WRAP", "G_TX_NOMIRROR"]
            if curImgSet != i:
                gfxOut.commands.append(DPSetTextureImage(fmt, siz, wid, fImage))

            def loadOneOrTwoS(tmemBase, tidxBase, TL, TH):
                if line != curTileLines[tidxBase]:
                    gfxOut.commands.append(DPSetTile(fmt, siz, line, tmemBase, tidxBase, 0, nocm, 0, 0, nocm, 0, 0))
                    curTileLines[tidxBase] = line
                if wrapS:
                    # Break up at the wrap boundary into two tile loads.
                    # The first load must occupy a whole number of lines.
                    assert (texDimensions[0] - tileSettings.sl) % texelsPerLine == 0
                    sLineOfs = (texDimensions[0] - tileSettings.sl) // texelsPerLine
                    print(f"-- Wrap at S={texDimensions[0]}, offset {sLineOfs}")
                    gfxOut.commands.append(
                        DPLoadTile(tidxBase, tileSettings.sl * sm, TL * 4, (texDimensions[0] - 1) * sm, TH * 4)
                    )
                    gfxOut.commands.append(
                        DPSetTile(fmt, siz, line, tmemBase + sLineOfs, tidxBase - 1, 0, nocm, 0, 0, nocm, 0, 0)
                    )
                    curTileLines[tidxBase - 1] = -1
                    gfxOut.commands.append(
                        DPLoadTile(tidxBase - 1, 0, TL * 4, (tileSettings.sh - texDimensions[0]) * sm, TH * 4)
                    )
                else:
                    gfxOut.commands.append(
                        DPLoadTile(tidxBase, tileSettings.sl * sm, TL * 4, tileSettings.sh * sm, TH * 4)
                    )

            if wrapT:
                # Break up at the wrap boundary into two loads.
                # The first load must be even in size (even number of texture rows).
                assert (texDimensions[1] - tileSettings.tl) % 2 == 0
                tLineOfs = line * (texDimensions[1] - tileSettings.tl)
                print(f"-- Wrap at T={texDimensions[1]}, offset {tLineOfs}")
                loadOneOrTwoS(tmem, 7, tileSettings.tl, texDimensions[1] - 1)
                loadOneOrTwoS(tmem + tLineOfs, 5, 0, tileSettings.th - texDimensions[1])
            else:
                loadOneOrTwoS(tmem, 7, tileSettings.tl, tileSettings.th)
            if fMaterial.isTexLarge[i ^ 1]:
                # May reuse any of the above tiles for the other large texture.
                gfxOut.commands.append(DPTileSync())
        else:
            saveTextureLoadOnly(
                fImage,
                gfxOut,
                texProp,
                tileSettings,
                7 - i,
                tmem,
                fModel.f3d,
                curImgSet == i,
                line == curTileLines[7 - i],
            )
            curTileLines[7 - i] = line
        curImgSet = i
        saveTextureTile(
            fImage,
            fMaterial,
            gfxOut,
            texProp,
            tileSettings,
            i,
            tmem,
            fMaterial.texPaletteIndex[i],
            fModel.f3d,
            line == curTileLines[i],
        )
        curTileLines[i] = line
    return curImgSet


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
            triGroup.triList,
            triGroup.vertexList,
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
                None,
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

    currentGroupIndex = saveTriangleStrip(triConverter, faces, None, obj.data, True)

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
        self.stOffset: tuple(int, int) | None = None
        self.color: mathutils.Vector | None = color
        self.normal: mathutils.Vector | None = normal

    def __eq__(self, other):
        if not isinstance(other, F3DVert):
            return False
        return (
            self.position == other.position
            and self.uv == other.uv
            and self.stOffset == other.stOffset
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

        exportVertexColors = isLightingDisabled(material)
        uv_data = triConverterInfo.obj.data.uv_layers["UVMap"].data
        self.convertInfo = LoopConvertInfo(uv_data, triConverterInfo.obj, exportVertexColors)
        self.texDimensions = texDimensions
        self.isPointSampled = isTexturePointSampled(material)
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
                        bufferVert.f3dVert.stOffset,
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
                        bufferVert.f3dVert.stOffset,
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


def UVtoSTLarge(obj, loopIndex, uv_data, texDimensions):
    uv = uv_data[loopIndex].uv.copy()
    uv[1] = 1 - uv[1]
    loopUV = uv.freeze()

    # Represent the -0.5 texel offset in the UVs themselves in clamping mode
    # if desired, rather than here at export
    pixelOffset = 0
    return [
        convertFloatToFixed16(loopUV[0] * texDimensions[0] - pixelOffset) / 32,
        convertFloatToFixed16(loopUV[1] * texDimensions[1] - pixelOffset) / 32,
    ]


def convertVertexData(
    mesh,
    loopPos,
    loopUV,
    stOffset,
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
    pixelOffset = stOffset if stOffset is not None else pixelOffset

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

    # Get texture info, needed for othermode; also check some texture props
    err0, info0 = getTexInfoFromMat(0, f3dMat)
    err1, info1 = getTexInfoFromMat(1, f3dMat)
    if err0 is not None:
        raise PluginError(f"In {material.name} tex0: {err0}")
    if err1 is not None:
        raise PluginError(f"In {material.name} tex1: {err1}")
    (useTex0, isTex0Ref, isTex0CI, tex0Fmt, pal0Fmt, imageDims0, tex0Tmem) = info0
    (useTex1, isTex1Ref, isTex1CI, tex1Fmt, pal1Fmt, imageDims1, tex1Tmem) = info1
    tex0Name, pal0, pal0Len, im0Use, tex0Flipbook = getTexInfoAdvanced(
        0, material, fMaterial, fModel, useTex0, isTex0Ref, isTex0CI, tex0Fmt, pal0Fmt
    )
    tex1Name, pal1, pal1Len, im1Use, tex1Flipbook = getTexInfoAdvanced(
        1, material, fMaterial, fModel, useTex1, isTex1Ref, isTex1CI, tex1Fmt, pal1Fmt
    )

    isCI = (useTex0 and isTex0CI) or (useTex1 and isTex1CI)

    if useTex0 and useTex1:
        if isTex0CI != isTex1CI:
            raise PluginError(
                "In material "
                + material.name
                + ": N64 does not support CI + non-CI texture. "
                + "Must be both CI or neither CI."
            )
        if (
            isTex0Ref
            and isTex1Ref
            and f3dMat.tex0.tex_reference == f3dMat.tex1.tex_reference
            and f3dMat.tex0.tex_reference_size != f3dMat.tex1.tex_reference_size
        ):
            raise PluginError(
                "In material " + material.name + ": Two textures with the same reference must have the same size."
            )
        if isCI:
            if pal0Fmt != pal1Fmt:
                raise PluginError(
                    "In material "
                    + material.name
                    + ": Both CI textures must use the same palette format (usually RGBA16)."
                )
            if (
                isTex0Ref
                and isTex1Ref
                and f3dMat.tex0.pal_reference == f3dMat.tex1.pal_reference
                and f3dMat.tex0.pal_reference_size != f3dMat.tex1.pal_reference_size
            ):
                raise PluginError(
                    "In material "
                    + material.name
                    + ": Two textures with the same palette reference must have the same palette size."
                )

    palFormat = pal0Fmt if useTex0 else pal1Fmt
    g_tt = "G_TT_NONE" if not isCI else ("G_TT_" + palFormat)

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
        fMaterial, f3dMat.rdp_settings, g_tt, defaults, fModel.f3d._HW_VERSION_1, fModel.matWriteMethod
    )
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

    # Determine how to arrange / load palette entries into upper half of tmem
    tex0PaletteIndex = 0
    tex1PaletteIndex = 0
    loadPal0 = False
    loadPal1 = False
    pal0Addr = 0
    pal1Addr = 0
    pal0Use = im0Use
    pal1Use = im1Use
    if isCI:
        assert useTex0 or useTex1
        if not useTex1:
            loadPal0 = True
        elif not useTex0:
            loadPal1 = True
        elif not convertTextureData:
            if tex0Fmt == "CI8" or tex1Fmt == "CI8":
                raise PluginError(
                    "In material "
                    + material.name
                    + ": When using export as PNGs mode, can't have multitexture with one or more CI8 textures."
                    + " Only single CI texture or two CI4 textures."
                )
            loadPal0 = loadPal1 = True
            tex1PaletteIndex = 1
            pal1Addr = 16
        else:  # Two CI textures, normal mode
            if tex0Fmt == "CI8" and tex1Fmt == "CI8":
                if (pal0 is None) != (pal1 is None):
                    raise PluginError(
                        "In material "
                        + material.name
                        + ": can't have two CI8 textures where only one is a non-flipbook reference; "
                        + "no way to assign the palette."
                    )
                loadPal0 = True
                if pal0 is None:
                    if f3dMat.tex0.pal_reference != f3dMat.tex1.pal_reference:
                        raise PluginError(
                            "In material "
                            + material.name
                            + ": can't have two CI8 textures with different palette references."
                        )
                else:
                    pal0 = mergePalettes(pal0, pal1)
                    pal0Len = len(pal0)
                    if pal0Len > 256:
                        raise PluginError(
                            "In material "
                            + material.name
                            + ": the two CI textures together contain a total of "
                            + str(pal0Len)
                            + " colors, which can't fit in a CI8 palette (256)."
                        )
                    # im0Use remains what it was; the CIs in im0 are the same as they
                    # would be if im0 was alone. But im1 and pal0 depend on both.
                    im1Use = pal0Use = im0Use + im1Use
            elif tex0Fmt != tex1Fmt:  # One CI8, one CI4
                ci8Pal, ci4Pal = (pal0, pal1) if tex0Fmt == "CI8" else (pal1, pal0)
                ci8PalLen, ci4PalLen = (pal0Len, pal1Len) if tex0Fmt == "CI8" else (pal1Len, pal0Len)
                if pal0 is None or pal1 is None:
                    if ci8PalLen > 256 - 16:
                        raise PluginError(
                            "In material "
                            + material.name
                            + ": the CI8 texture has over 240 colors, which can't fit together with the CI4 palette."
                        )
                    loadPal0 = loadPal1 = True
                    if tex0Fmt == "CI8":
                        tex1PaletteIndex = 15
                        pal1Addr = 240
                    else:
                        tex0PaletteIndex = 15
                        pal0Addr = 240
                else:
                    # CI4 indices in palette 0, CI8 indices start from palette 0
                    loadPal0 = True
                    pal0 = mergePalettes(ci4Pal, ci8Pal)
                    pal0Len = len(pal0)
                    if pal0Len > 256:
                        raise PluginError(
                            "In material "
                            + material.name
                            + ": the two CI textures together contain a total of "
                            + str(pal0Len)
                            + " colors, which can't fit in a CI8 palette (256)."
                            + " The CI8 texture must contain up to 240 unique colors,"
                            + " plus the same up to 16 colors used in the CI4 texture."
                        )
                    # The use for the CI4 texture remains what it was; its CIs are the
                    # same as if it was alone. But both the palette and the CI8 CIs are affected.
                    pal0Use = im0Use + im1Use
                    if tex0Fmt == "CI8":
                        im0Use = pal0Use
                    else:
                        im1Use = pal0Use
            else:  # both CI4 textures
                if pal0 is None and pal1 is None and f3dMat.tex0.pal_reference == f3dMat.tex1.pal_reference:
                    loadPal0 = True
                elif pal0 is None or pal1 is None:
                    loadPal0 = loadPal1 = True
                    tex1PaletteIndex = 1
                    pal1Addr = 16
                else:
                    loadPal0 = True
                    tempPal = mergePalettes(pal0, pal1)
                    tempPalLen = len(tempPal)
                    assert tempPalLen <= 32
                    if tempPalLen <= 16:
                        # Share palette 0
                        pal0 = tempPal
                        pal0Len = tempPalLen
                        # im0Use remains what it was; the CIs in im0 are the same as they
                        # would be if im0 was alone. But im1 and pal0 depend on both.
                        im1Use = pal0Use = im0Use + im1Use
                    else:
                        # Load one palette across 0-1. Put the longer in slot 0
                        if pal0Len >= pal1Len:
                            while len(pal0) < 16:
                                pal0.append(0)
                            pal0.extend(pal1)
                            pal0Len = len(pal0)
                            tex1PaletteIndex = 1
                        else:
                            while len(pal1) < 16:
                                pal1.append(0)
                            pal0 = pal1 + pal0
                            pal0Len = len(pal0)
                            tex0PaletteIndex = 1
                        # The up-to-32 entries in pal0 depend on both images. But the
                        # CIs in both im0 and im1 are the same as if there was no shared palette.
                        pal0Use = im0Use + im1Use
    fMaterial.texPaletteIndex = [tex0PaletteIndex, tex1PaletteIndex]
    pal0Name, pal1Name = tex0Name, tex1Name
    if isCI and useTex0 and useTex1 and not loadPal1:
        if tex0Flipbook is not None or tex1Flipbook is not None:
            raise PluginError("TODO: getSharedPaletteName is not correct for flipbooks")
        pal0Name = getSharedPaletteName(f3dMat)
        pal1 = pal0
    writePal0 = loadPal0 and ((not isTex0Ref) or (tex0Flipbook is not None))
    writePal1 = loadPal1 and ((not isTex1Ref) or (tex1Flipbook is not None))

    # Assign TMEM addresses
    sameTextures = (
        useTex0
        and useTex1
        and (
            (not isTex0Ref and not isTex1Ref and f3dMat.tex0.tex == f3dMat.tex1.tex)
            or (isTex0Ref and isTex1Ref and f3dMat.tex0.tex_reference == f3dMat.tex1.tex_reference)
        )
    )
    useLargeTextures = material.mat_ver > 3 and f3dMat.use_large_textures
    tmemSize = 256 if isCI else 512
    doTex0Load = doTex0Tile = doTex1Load = doTex1Tile = True
    tex1Addr = None  # must be set whenever tex 1 used (and loaded or tiled)
    tmemOccupied = texDimensions = None  # must be set on all codepaths
    if sameTextures:
        assert tex0Tmem == tex1Tmem
        tmemOccupied = tex0Tmem
        doTex1Load = False
        tex1Addr = 0
        texDimensions = imageDims0
        fMaterial.largeTexFmt = tex0Fmt
    elif not useLargeTextures or tex0Tmem + tex1Tmem <= tmemSize:
        tex1Addr = tex0Tmem
        tmemOccupied = tex0Tmem + tex1Tmem
        if not useTex0 and not useTex1:
            texDimensions = [32, 32]
            fMaterial.largeTexFmt = "RGBA16"
        elif not useTex1 or f3dMat.uv_basis == "TEXEL0":
            texDimensions = imageDims0
            fMaterial.largeTexFmt = tex0Fmt
        else:
            texDimensions = imageDims1
            fMaterial.largeTexFmt = tex1Fmt
    else:  # useLargeTextures
        if useTex0 and useTex1:
            tmemOccupied = tmemSize
            # TODO: Could change this in the future to do the face tile assigments
            # first, to see how large a tile the large texture(s) needed, instead
            # of arbitrarily assigning half of TMEM to each of the two textures.
            if tex0Tmem <= tmemSize // 2:
                # Tex 0 normal, tex 1 large
                texDimensions = imageDims1
                fMaterial.largeTexFmt = tex1Fmt
                fMaterial.isTexLarge[1] = True
                fMaterial.largeTexAddr[1] = tex0Tmem
                fMaterial.largeTexWords = tmemSize - tex0Tmem
                doTex1Load = doTex1Tile = False
            elif tex1Tmem <= tmemSize // 2:
                # Tex 0 large, tex 1 normal
                texDimensions = imageDims0
                fMaterial.largeTexFmt = tex0Fmt
                fMaterial.isTexLarge[0] = True
                fMaterial.largeTexAddr[0] = 0
                fMaterial.largeTexWords = tmemSize - tex1Tmem
                doTex0Load = doTex0Tile = False
                tex1Addr = tmemSize - tex1Tmem
            else:
                # Both textures large
                raise PluginError(
                    'Error in "' + material.name + '": Multitexture with two large textures is not currently supported.'
                )
                # Limited cases of 2x large textures could be supported in the
                # future. However, these cases are either of questionable
                # utility or have substantial restrictions. Most cases could be
                # premixed into one texture, or would run out of UV space for
                # tiling (1024x1024 in the space of whichever texture had
                # smaller pixels), or one of the textures could be non-large.
                if f3dMat.uv_basis == "TEXEL0":
                    texDimensions = imageDims0
                    fMaterial.largeTexFmt = tex0Fmt
                else:
                    texDimensions = imageDims1
                    fMaterial.largeTexFmt = tex1Fmt
                fMaterial.isTexLarge[0] = True
                fMaterial.isTexLarge[1] = True
                fMaterial.largeTexAddr[0] = 0
                fMaterial.largeTexAddr[1] = tmemSize // 2
                fMaterial.largeTexWords = tmemSize // 2
                doTex0Load = doTex0Tile = doTex1Load = doTex1Tile = False
        elif useTex0:
            texDimensions = imageDims0
            fMaterial.largeTexFmt = tex0Fmt
            fMaterial.isTexLarge[0] = True
            fMaterial.largeTexAddr[0] = 0
            fMaterial.largeTexWords = tmemSize
            doTex0Load = doTex0Tile = False
            tmemOccupied = tmemSize
        elif useTex1:
            tex1Addr = 0
            texDimensions = imageDims1
            fMaterial.largeTexFmt = tex1Fmt
            fMaterial.isTexLarge[1] = True
            fMaterial.largeTexAddr[1] = 0
            fMaterial.largeTexWords = tmemSize
            doTex1Load = doTex1Tile = False
            tmemOccupied = tmemSize
    if tmemOccupied > tmemSize:
        if sameTextures and useLargeTextures:
            raise PluginError(
                'Error in "'
                + material.name
                + '": Using the same texture for Tex0 and Tex1 is not compatible with large textures.'
            )
        elif not bpy.context.scene.ignoreTextureRestrictions:
            raise PluginError(
                'Error in "'
                + material.name
                + '": Textures are too big. Max TMEM size is 4k '
                + "bytes, ex. 2 32x32 RGBA 16 bit textures.\nNote that texture width will be internally padded to 64 bit boundaries."
            )

    # Get texture and palette definitions
    fImage0 = fImage1 = fPalette0 = fPalette1 = None
    if useTex0:
        imageKey0, fImage0 = saveOrGetTextureDefinition(
            fMaterial, fModel, f3dMat.tex0, im0Use, tex0Name, fMaterial.isTexLarge[0]
        )
        fMaterial.imageKey[0] = imageKey0
    if loadPal0:
        paletteKey0, fPalette0 = saveOrGetPaletteDefinition(fMaterial, fModel, f3dMat.tex0, pal0Use, pal0Name, pal0Len)
    if useTex1:
        imageKey1, fImage1 = saveOrGetTextureDefinition(
            fMaterial, fModel, f3dMat.tex1, im1Use, tex1Name, fMaterial.isTexLarge[1]
        )
        fMaterial.imageKey[1] = imageKey1
    if loadPal1:
        paletteKey1, fPalette1 = saveOrGetPaletteDefinition(fMaterial, fModel, f3dMat.tex1, pal1Use, pal1Name, pal1Len)

    # Write DL entries to load textures and palettes
    loadGfx = fMaterial.material
    if loadPal0:
        savePaletteLoad(loadGfx, fPalette0, pal0Fmt, pal0Addr, pal0Len, 5, fModel.f3d)
    if useTex0 and doTex0Load:
        saveTextureLoadOnly(fImage0, loadGfx, f3dMat.tex0, None, 7, 0, fModel.f3d)
    if useTex0 and doTex0Tile:
        saveTextureTile(fImage0, fMaterial, loadGfx, f3dMat.tex0, None, 0, 0, tex0PaletteIndex, fModel.f3d)
    if loadPal1:
        savePaletteLoad(loadGfx, fPalette1, pal1Fmt, pal1Addr, pal1Len, 4, fModel.f3d)
    if useTex1 and doTex1Load:
        saveTextureLoadOnly(fImage1, loadGfx, f3dMat.tex1, None, 6, tex1Addr, fModel.f3d)
    if useTex1 and doTex1Tile:
        saveTextureTile(fImage1, fMaterial, loadGfx, f3dMat.tex1, None, 1, tex1Addr, tex1PaletteIndex, fModel.f3d)

    # Write texture and palette data, unless exporting textures as PNGs.
    if convertTextureData:
        if writePal0:
            writePaletteData(fPalette0, pal0)
        if useTex0:
            if isTex0Ref:
                if isCI:
                    fModel.writeTexRefCITextures(tex0Flipbook, fMaterial, im0Use, pal0, tex0Fmt, pal0Fmt)
                else:
                    fModel.writeTexRefNonCITextures(tex0Flipbook, tex0Fmt)
            else:
                if isCI:
                    writeCITextureData(f3dMat.tex0.tex, fImage0, pal0, pal0Fmt, tex0Fmt)
                else:
                    writeNonCITextureData(f3dMat.tex0.tex, fImage0, tex0Fmt)
        if writePal1:
            writePaletteData(fPalette1, pal1)
        if useTex1:
            if isTex1Ref:
                if isCI:
                    fModel.writeTexRefCITextures(tex1Flipbook, fMaterial, im1Use, pal1, tex1Fmt, pal1Fmt)
                else:
                    fModel.writeTexRefNonCITextures(tex1Flipbook, tex1Fmt)
            else:
                if isCI:
                    writeCITextureData(f3dMat.tex1.tex, fImage1, pal1, pal1Fmt, tex1Fmt)
                else:
                    writeNonCITextureData(f3dMat.tex1.tex, fImage1, tex1Fmt)

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


# Functions for texture and palette definitions


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
    return f"{tex0Name}_x_{tex1Name}_{texFormat}"


def checkDuplicateTextureName(parent: Union[FModel, FTexRect], name):
    names = []
    for info, texture in parent.textures.items():
        names.append(texture.name)
    while name in names:
        name = name + "_copy"
    return name


def saveOrGetPaletteDefinition(
    fMaterial: FMaterial,
    parent: Union[FModel, FTexRect],
    texProp: TextureProperty,
    images: list[bpy.types.Image],
    imageName: str,
    palLen: int,
) -> tuple[FPaletteKey, FImage]:

    texFmt = texProp.tex_format
    palFmt = texProp.ci_format
    palFormat = texFormatOf[palFmt]
    paletteKey = FPaletteKey(palFmt, images)

    # If palette already loaded, return that data.
    fPalette = parent.getTextureAndHandleShared(paletteKey)
    if fPalette is not None:
        # print(f"Palette already exists")
        return paletteKey, fPalette

    if texProp.use_tex_reference:
        fPalette = FImage(texProp.pal_reference, None, None, 1, palLen, None)
        return paletteKey, fPalette

    paletteName = checkDuplicateTextureName(parent, toAlnum(imageName) + "_pal_" + palFmt.lower())
    paletteFilename = getNameFromPath(imageName, True) + "." + getTextureSuffixFromFormat(texFmt) + ".pal"

    fPalette = FImage(
        paletteName,
        palFormat,
        "G_IM_SIZ_16b",
        1,
        palLen,
        paletteFilename,
    )

    parent.addTexture(paletteKey, fPalette, fMaterial)
    return paletteKey, fPalette


def saveOrGetTextureDefinition(
    fMaterial: FMaterial,
    parent: Union[FModel, FTexRect],
    texProp: TextureProperty,
    images: list[bpy.types.Image],
    imageName: str,
    isLarge: bool,
) -> tuple[FImageKey, FImage]:

    image = texProp.tex
    texFmt = texProp.tex_format
    texFormat = texFormatOf[texFmt]
    bitSize = texBitSizeF3D[texFmt]
    imageKey = getImageKey(texProp, images)

    # If image already loaded, return that data.
    fImage = parent.getTextureAndHandleShared(imageKey)
    if fImage is not None:
        # print(f"Image already exists")
        return imageKey, fImage

    if texProp.use_tex_reference:
        width, height = texProp.tex_reference_size
        fImage = FImage(texProp.tex_reference, None, None, width, height, None)
        return imageKey, fImage

    name = image.name if image.filepath == "" else image.filepath
    filename = getNameFromPath(name, True) + "." + getTextureSuffixFromFormat(texFmt) + ".inc.c"

    fImage = FImage(
        checkDuplicateTextureName(parent, toAlnum(imageName)),
        texFormat,
        bitSize,
        image.size[0],
        image.size[1],
        filename,
    )
    fImage.isLargeTexture = isLarge

    parent.addTexture(imageKey, fImage, fMaterial)
    return imageKey, fImage


def getTexInfoFromMat(
    index: int,
    f3dMat: F3DMaterialProperty,
):
    texProp = getattr(f3dMat, "tex" + str(index))

    useDict = all_combiner_uses(f3dMat)
    if not useDict["Texture " + str(index)]:
        return None, (False, False, False, "", "", (0, 0), 0)

    return getTexInfoFromProp(texProp)


def getTexInfoFromProp(texProp: TextureProperty):
    if not texProp.tex_set:
        return None, (False, False, False, "", "", (0, 0), 0)

    tex = texProp.tex
    isTexRef = texProp.use_tex_reference
    texFormat = texProp.tex_format
    isCITexture = texFormat[:2] == "CI"
    palFormat = texProp.ci_format if isCITexture else ""

    if tex is not None and (tex.size[0] == 0 or tex.size[1] == 0):
        return f"Image {tex.name} has 0 size; may have been deleted/moved.", None

    if not isTexRef:
        if tex is None:
            return f"No texture is selected.", None
        elif len(tex.pixels) == 0:
            return f"Image {tex.name} is missing on disk.", None

    if isTexRef:
        width, height = texProp.tex_reference_size
    else:
        width, height = tex.size

    tmemSize = getTmemWordUsage(texFormat, width, height)

    if width > 1024 or height > 1024:
        return f"Image size (even large textures) limited to 1024 in each dimension.", None

    if texBitSizeInt[texFormat] == 4 and (width & 1) != 0:
        return f"A 4-bit image must have a width which is even.", None

    info = (True, isTexRef, isCITexture, texFormat, palFormat, (width, height), tmemSize)
    return None, info


def getTexInfoAdvanced(
    index: int,
    material: bpy.types.Material,
    fMaterial: FMaterial,
    fModel: FModel,
    useTex: bool,
    isTexRef: bool,
    isCITexture: bool,
    texFormat: str,
    palFormat: str,
):
    if not useTex:
        return "", None, 0, [], None
    
    f3dMat = material.f3d_mat
    texProp = getattr(f3dMat, "tex" + str(index))

    texName = getTextureName(texProp, fModel.name, None)

    pal = None
    palLen = 0
    if isCITexture:
        imUse, flipbook, pal, palName = fModel.processTexRefCITextures(fMaterial, material, index)
        if isTexRef:
            if flipbook is not None:
                palLen = len(pal)
                texName = palName
            else:
                palLen = texProp.pal_reference_size
        else:
            assert flipbook is None
            pal = getColorsUsedInImage(texProp.tex, palFormat)
            palLen = len(pal)
        if palLen > (16 if texFormat == "CI4" else 256):
            raise PluginError(
                f"Error in {material.name}: {texName}"
                + (" (all flipbook textures)" if flipbook is not None else "")
                + f" uses too many unique colors to fit in format {texFormat}."
            )
    else:
        imUse, flipbook = fModel.processTexRefNonCITextures(fMaterial, material, index)

    return texName, pal, palLen, imUse, flipbook


# Functions for writing texture and palette DLs


def getTileSizeSettings(texProp: TextureProperty, tileSettings: Union[None, TileLoad], f3d: F3D):
    if tileSettings is not None:
        SL = tileSettings.sl
        TL = tileSettings.tl
        SH = tileSettings.sh
        TH = tileSettings.th
    else:
        SL = texProp.S.low
        TL = texProp.T.low
        SH = texProp.S.high
        TH = texProp.T.high
    sl = int(SL * (2**f3d.G_TEXTURE_IMAGE_FRAC))
    tl = int(TL * (2**f3d.G_TEXTURE_IMAGE_FRAC))
    sh = int(SH * (2**f3d.G_TEXTURE_IMAGE_FRAC))
    th = int(TH * (2**f3d.G_TEXTURE_IMAGE_FRAC))
    return SL, TL, SH, TH, sl, tl, sh, th


def getTileLine(fImage: FImage, SL: int, SH: int, siz: str, f3d: F3D):
    width = int(SH - SL + 1) if fImage.isLargeTexture else int(fImage.width)
    if siz == "G_IM_SIZ_4b":
        line = (((width + 1) >> 1) + 7) >> 3
    else:
        # Note that _LINE_BYTES and _TILE_BYTES variables are the same.
        line = int((width * f3d.G_IM_SIZ_VARS[siz + "_LINE_BYTES"]) + 7) >> 3
    return line


def saveTextureLoadOnly(
    fImage: FImage,
    gfxOut: GfxList,
    texProp: TextureProperty,
    tileSettings: Union[None, TileLoad],
    loadtile: int,
    tmem: int,
    f3d: F3D,
    omitSetTextureImage=False,
    omitSetTile=False,
):
    fmt = texFormatOf[texProp.tex_format]
    siz = texBitSizeF3D[texProp.tex_format]
    nocm = ["G_TX_WRAP", "G_TX_NOMIRROR"]
    SL, TL, SH, TH, sl, tl, sh, th = getTileSizeSettings(texProp, tileSettings, f3d)

    # LoadTile will pad rows to 64 bit word alignment, while
    # LoadBlock assumes this is already done.
    useLoadBlock = not fImage.isLargeTexture and isPowerOf2(fImage.width)
    line = 0 if useLoadBlock else getTileLine(fImage, SL, SH, siz, f3d)
    wid = 1 if useLoadBlock else fImage.width

    if siz == "G_IM_SIZ_4b":
        if useLoadBlock:
            dxs = (((fImage.width) * (fImage.height) + 3) >> 2) - 1
            dxt = f3d.CALC_DXT_4b(fImage.width)
            siz = "G_IM_SIZ_16b"
            loadCommand = DPLoadBlock(loadtile, 0, 0, dxs, dxt)
        else:
            sl2 = int(SL * (2 ** (f3d.G_TEXTURE_IMAGE_FRAC - 1)))
            sh2 = int(SH * (2 ** (f3d.G_TEXTURE_IMAGE_FRAC - 1)))
            siz = "G_IM_SIZ_8b"
            wid >>= 1
            loadCommand = DPLoadTile(loadtile, sl2, tl, sh2, th)
    else:
        if useLoadBlock:
            dxs = (
                ((fImage.width) * (fImage.height) + f3d.G_IM_SIZ_VARS[siz + "_INCR"])
                >> f3d.G_IM_SIZ_VARS[siz + "_SHIFT"]
            ) - 1
            dxt = f3d.CALC_DXT(fImage.width, f3d.G_IM_SIZ_VARS[siz + "_BYTES"])
            siz += "_LOAD_BLOCK"
            loadCommand = DPLoadBlock(loadtile, 0, 0, dxs, dxt)
        else:
            loadCommand = DPLoadTile(loadtile, sl, tl, sh, th)

    if not omitSetTextureImage:
        gfxOut.commands.append(DPSetTextureImage(fmt, siz, wid, fImage))
    if not omitSetTile:
        gfxOut.commands.append(DPSetTile(fmt, siz, line, tmem, loadtile, 0, nocm, 0, 0, nocm, 0, 0))
    gfxOut.commands.append(loadCommand)


def saveTextureTile(
    fImage: FImage,
    fMaterial: FMaterial,
    gfxOut: GfxList,
    texProp: TextureProperty,
    tileSettings,
    rendertile: int,
    tmem: int,
    pal: int,
    f3d: F3D,
    omitSetTile=False,
):
    if tileSettings is not None:
        clamp_S = True
        clamp_T = True
        mirror_S = False
        mirror_T = False
        mask_S = 0
        mask_T = 0
        shift_S = 0
        shift_T = 0
    else:
        clamp_S = texProp.S.clamp
        clamp_T = texProp.T.clamp
        mirror_S = texProp.S.mirror
        mirror_T = texProp.T.mirror
        mask_S = texProp.S.mask
        mask_T = texProp.T.mask
        shift_S = texProp.S.shift
        shift_T = texProp.T.shift
    cms = [("G_TX_CLAMP" if clamp_S else "G_TX_WRAP"), ("G_TX_MIRROR" if mirror_S else "G_TX_NOMIRROR")]
    cmt = [("G_TX_CLAMP" if clamp_T else "G_TX_WRAP"), ("G_TX_MIRROR" if mirror_T else "G_TX_NOMIRROR")]
    masks = mask_S
    maskt = mask_T
    shifts = shift_S if shift_S >= 0 else (shift_S + 16)
    shiftt = shift_T if shift_T >= 0 else (shift_T + 16)
    fmt = texFormatOf[texProp.tex_format]
    siz = texBitSizeF3D[texProp.tex_format]
    SL, _, SH, _, sl, tl, sh, th = getTileSizeSettings(texProp, tileSettings, f3d)
    line = getTileLine(fImage, SL, SH, siz, f3d)

    tileCommand = DPSetTile(fmt, siz, line, tmem, rendertile, pal, cmt, maskt, shiftt, cms, masks, shifts)
    tileSizeCommand = DPSetTileSize(rendertile, sl, tl, sh, th)
    tileSizeCommand.tags |= GfxTag.TileScroll0 if rendertile == 0 else GfxTag.TileScroll1
    tileSizeCommand.fMaterial = fMaterial
    if not omitSetTile:
        gfxOut.commands.append(tileCommand)
    gfxOut.commands.append(tileSizeCommand)

    # hasattr check for FTexRect
    if hasattr(fMaterial, "tileSizeCommands"):
        fMaterial.tileSizeCommands[rendertile] = tileSizeCommand


# palAddr is the address within the second half of tmem (0-255), normally 16*palette num
# palLen is the number of colors
def savePaletteLoad(
    gfxOut: GfxList,
    fPalette: FImage,
    palFormat: str,
    palAddr: int,
    palLen: int,
    loadtile: int,
    f3d: F3D,
):
    assert 0 <= palAddr < 256 and (palAddr & 0xF) == 0
    palFmt = texFormatOf[palFormat]
    nocm = ["G_TX_WRAP", "G_TX_NOMIRROR"]

    if not f3d._HW_VERSION_1:
        gfxOut.commands.extend(
            [
                DPSetTextureImage(palFmt, "G_IM_SIZ_16b", 1, fPalette),
                DPSetTile("0", "0", 0, 256 + palAddr, loadtile, 0, nocm, 0, 0, nocm, 0, 0),
                DPLoadTLUTCmd(loadtile, palLen - 1),
            ]
        )
    else:
        gfxOut.commands.extend(
            [
                _DPLoadTextureBlock(
                    fPalette,
                    256 + palAddr,
                    palFmt,
                    "G_IM_SIZ_16b",
                    4 * palLen,
                    1,
                    0,
                    nocm,
                    nocm,
                    0,
                    0,
                    0,
                    0,
                )
            ]
        )


# Functions for converting and writing texture and palette data


def extractConvertCIPixel(image, pixels, i, j, palFormat):
    color = [1, 1, 1, 1]
    for field in range(image.channels):
        color[field] = pixels[(j * image.size[0] + i) * image.channels + field]
    if palFormat == "RGBA16":
        pixelColor = getRGBA16Tuple(color)
    elif palFormat == "IA16":
        pixelColor = getIA16Tuple(color)
    else:
        raise PluginError("Internal error, palette format is " + palFormat)
    return pixelColor


def getColorsUsedInImage(image, palFormat):
    palette = []
    # N64 is -Y, Blender is +Y
    pixels = image.pixels[:]
    for j in reversed(range(image.size[1])):
        for i in range(image.size[0]):
            pixelColor = extractConvertCIPixel(image, pixels, i, j, palFormat)
            if pixelColor not in palette:
                palette.append(pixelColor)
    return palette


def mergePalettes(pal0, pal1):
    palette = [c for c in pal0]
    for c in pal1:
        if c not in palette:
            palette.append(c)
    return palette


def getColorIndicesOfTexture(image, palette, palFormat):
    texture = []
    # N64 is -Y, Blender is +Y
    pixels = image.pixels[:]
    for j in reversed(range(image.size[1])):
        for i in range(image.size[0]):
            pixelColor = extractConvertCIPixel(image, pixels, i, j, palFormat)
            if pixelColor not in palette:
                raise PluginError(f"Bug: {image.name} palette len {len(palette)} missing CI")
            texture.append(palette.index(pixelColor))
    return texture


def compactNibbleArray(texture, width, height):
    nibbleData = bytearray(0)
    dataSize = int(width * height / 2)

    nibbleData = [((texture[i * 2] & 0xF) << 4) | (texture[i * 2 + 1] & 0xF) for i in range(dataSize)]

    if (width * height) % 2 == 1:
        nibbleData.append((texture[-1] & 0xF) << 4)

    return bytearray(nibbleData)


def writePaletteData(fPalette: FImage, palette: list[int]):
    if fPalette.converted:
        return
    for color in palette:
        fPalette.data.extend(color.to_bytes(2, "big"))
    fPalette.converted = True


def writeCITextureData(
    image: bpy.types.Image,
    fImage: FImage,
    palette: list[int],
    palFmt: str,
    texFmt: str,
):
    if fImage.converted:
        return

    texture = getColorIndicesOfTexture(image, palette, palFmt)

    if texFmt == "CI4":
        fImage.data = compactNibbleArray(texture, image.size[0], image.size[1])
    else:
        fImage.data = bytearray(texture)
    fImage.converted = True


def writeNonCITextureData(image: bpy.types.Image, fImage: FImage, texFmt: str):
    if fImage.converted:
        return
    fmt = texFormatOf[texFmt]
    bitSize = texBitSizeF3D[texFmt]

    pixels = image.pixels[:]
    if fmt == "G_IM_FMT_RGBA":
        if bitSize == "G_IM_SIZ_16b":
            fImage.data = bytearray(
                [
                    byteVal
                    for doubleByte in [
                        (
                            (
                                ((int(round(pixels[(j * image.size[0] + i) * image.channels + 0] * 0x1F)) & 0x1F) << 3)
                                | (
                                    (int(round(pixels[(j * image.size[0] + i) * image.channels + 1] * 0x1F)) & 0x1F)
                                    >> 2
                                )
                            ),
                            (
                                ((int(round(pixels[(j * image.size[0] + i) * image.channels + 1] * 0x1F)) & 0x03) << 6)
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
                                    (j * image.size[0] + i) * image.channels : (j * image.size[0] + i) * image.channels
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
                                    (j * image.size[0] + i) * image.channels : (j * image.size[0] + i) * image.channels
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

    fImage.converted = True


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


def saveOtherModeHDefinition(fMaterial, settings, tlut, defaults, isHWv1, matWriteMethod):
    if matWriteMethod == GfxMatWriteMethod.WriteAll:
        saveOtherModeHDefinitionAll(fMaterial, settings, tlut, defaults, isHWv1)
    elif matWriteMethod == GfxMatWriteMethod.WriteDifferingAndRevert:
        saveOtherModeHDefinitionIndividual(fMaterial, settings, tlut, defaults, isHWv1)
    else:
        raise PluginError("Unhandled material write method: " + str(matWriteMethod))


def saveOtherModeHDefinitionAll(fMaterial, settings, tlut, defaults, isHWv1):
    cmd = SPSetOtherMode("G_SETOTHERMODE_H", 4, 20, [])
    cmd.flagList.append(settings.g_mdsft_alpha_dither)
    if not isHWv1:
        cmd.flagList.append(settings.g_mdsft_rgb_dither)
        cmd.flagList.append(settings.g_mdsft_combkey)
    cmd.flagList.append(settings.g_mdsft_textconv)
    cmd.flagList.append(settings.g_mdsft_text_filt)
    cmd.flagList.append(tlut)
    cmd.flagList.append(settings.g_mdsft_textlod)
    cmd.flagList.append(settings.g_mdsft_textdetail)
    cmd.flagList.append(settings.g_mdsft_textpersp)
    cmd.flagList.append(settings.g_mdsft_cycletype)
    if isHWv1:
        cmd.flagList.append(settings.g_mdsft_color_dither)
    cmd.flagList.append(settings.g_mdsft_pipeline)

    fMaterial.material.commands.append(cmd)


def saveOtherModeHDefinitionIndividual(fMaterial, settings, tlut, defaults, isHWv1):
    saveModeSetting(fMaterial, settings.g_mdsft_alpha_dither, defaults.g_mdsft_alpha_dither, DPSetAlphaDither)

    if not isHWv1:
        saveModeSetting(fMaterial, settings.g_mdsft_rgb_dither, defaults.g_mdsft_rgb_dither, DPSetColorDither)

        saveModeSetting(fMaterial, settings.g_mdsft_combkey, defaults.g_mdsft_combkey, DPSetCombineKey)

    saveModeSetting(fMaterial, settings.g_mdsft_textconv, defaults.g_mdsft_textconv, DPSetTextureConvert)

    saveModeSetting(fMaterial, settings.g_mdsft_text_filt, defaults.g_mdsft_text_filt, DPSetTextureFilter)

    saveModeSetting(fMaterial, tlut, "G_TT_NONE", DPSetTextureLUT)

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
