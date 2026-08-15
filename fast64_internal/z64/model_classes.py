import bpy
import os
from pathlib import Path
import re
from bpy.types import MeshLoop, MeshLoopTriangle
import mathutils

from enum import Enum
from typing import Union, Optional, NamedTuple, Generic, TypeVar
from collections import defaultdict
from dataclasses import dataclass, field
from ..f3d.f3d_parser import F3DContext, F3DTextureReference, getImportData

from ..f3d.f3d_material import TextureProperty, createF3DMat, texFormatOf, texBitSizeF3D
from ..utility import (
    PluginError,
    CData,
    hexOrDecInt,
    create_or_get_world,
    indent,
    getBoneIndexFromGroupIndex,
    getRgbNormalSettings,
)
from ..f3d.flipbook import TextureFlipbook, usesFlipbook, ootFlipbookReferenceIsValid

from ..f3d.f3d_writer import (
    VertexGroupInfo,
    TriangleConverterInfo,
    TriangleConverter,
    BufferVertex,
    F3DVert,
    getF3DVert,
)
from ..f3d.f3d_texture_writer import (
    getColorsUsedInImage,
    mergePalettes,
    writeCITextureData,
    writeNonCITextureData,
    getTextureNamesFromImage,
)

from ..f3d.f3d_gbi import (
    FModel,
    FMaterial,
    FImage,
    FImageKey,
    GfxMatWriteMethod,
    SPDisplayList,
    GfxList,
    GfxListTag,
    Vtx,
    VtxList,
    FTriGroup,
    FMesh,
    DLFormat,
    SPMatrix,
    GfxFormatter,
    DPSetTile,
    F3D,
    MTX_SIZE,
    VTX_SIZE,
)

from .utility import is_hackeroot


# read included asset data
def ootGetIncludedAssetData(basePaths: list[str], currentPaths: list[str], data: str) -> str:
    includeData = ""
    searchedPaths = currentPaths[:]

    print("Included paths:")

    # search assets
    for includeMatch in re.finditer(r"\#include\s*\"(assets/objects/(.*?)\.h)\"", data):
        h_p = None
        for basePath in basePaths:
            candidate_h_p = Path(basePath) / includeMatch.group(1)
            if candidate_h_p.exists():
                h_p = candidate_h_p
                break
        if h_p is None:
            print("Could not find included file:", includeMatch.group(1))
            continue
        print("", str(h_p))
        includeData += getImportData([str(h_p)]) + "\n"
        for path_p in h_p.parent.glob("*.c"):
            path = str(path_p)
            if path in searchedPaths:
                continue
            searchedPaths.append(path)
            subIncludeData = getImportData([path]) + "\n"
            includeData += subIncludeData
            print(" ", path)

            for subIncludeMatch in re.finditer(r"\#include\s*\"(((?![/\"]).)*\.[ch])\"", subIncludeData):
                sub_inc_p = Path(path).parent / subIncludeMatch.group(1)
                subPath = str(sub_inc_p)
                if subPath in searchedPaths:
                    continue
                searchedPaths.append(subPath)
                print("   ", subPath)
                includeData += getImportData([subPath]) + "\n"

    print("More included paths:")

    # search same directory c includes, both in current path and in included object files
    # these are usually fast64 exported files
    for includeMatch in re.finditer(r"\#include\s*\"(((?![/\"]).)*)\.c\"", data):
        sameDirPaths = [
            os.path.join(os.path.dirname(currentPath), includeMatch.group(1) + ".c") for currentPath in currentPaths
        ]
        sameDirPathsToSearch = []
        for sameDirPath in sameDirPaths:
            if sameDirPath not in searchedPaths:
                sameDirPathsToSearch.append(sameDirPath)

        for sameDirPath in sameDirPathsToSearch:
            print(sameDirPath)

        includeData += getImportData(sameDirPathsToSearch) + "\n"
    return includeData


def ootGetActorDataPaths(basePath: str, overlayName: str) -> list[str]:
    actorFilePath = os.path.join(basePath, f"src/overlays/actors/{overlayName}/z_{overlayName[4:].lower()}.c")
    actorFileDataPath = f"{actorFilePath[:-2]}_data.c"  # some bosses store texture arrays here

    return [actorFileDataPath, actorFilePath]


# read actor data
def ootGetActorData(basePath: str, overlayName: str) -> str:
    actorData = getImportData(ootGetActorDataPaths(basePath, overlayName))
    return actorData


def ootGetLinkData(basePath: str) -> str:
    linkFilePath = os.path.join(basePath, f"src/code/z_player_lib.c")
    actorData = getImportData([linkFilePath])

    return actorData


# custom `SPDisplayList` so we can customize the C output
@dataclass(unsafe_hash=True)
class DynamicMaterialDL(SPDisplayList):
    is_animated_material_sdc: bool

    def __post_init__(self):
        self.default_formatting = False

    def to_c(self, static=True):
        assert static
        if (
            is_hackeroot()
            and bpy.context.scene.fast64.oot.hackeroot_settings.export_ifdefs
            and self.is_animated_material_sdc
        ):
            return (
                "#if ENABLE_ANIMATED_MATERIALS\n" + indent + f"gsSPDisplayList({self.displayList.name}),\n" + "#endif\n"
            )
        else:
            return indent + f"gsSPDisplayList({self.displayList.name}),\n"


@dataclass
class SkinVertex:
    index: int
    uv: list[int]
    normal: list[int]
    alpha: int

    # region properties
    @property
    def s(self):
        return self.uv[0]

    @s.setter
    def s(self, val) -> None:
        self.uv[0] = val

    @property
    def t(self):
        return self.uv[1]

    @t.setter
    def t(self, val) -> None:
        self.uv[1] = val

    @property
    def normX(self):
        return (self.normal[0] + 128) % 256 - 128

    @normX.setter
    def normX(self, val) -> None:
        self.normal[0] = val

    @property
    def normY(self):
        return (self.normal[1] + 128) % 256 - 128

    @normY.setter
    def normY(self, val) -> None:
        self.normal[1] = val

    @property
    def normZ(self):
        return (self.normal[2] + 128) % 256 - 128

    @normZ.setter
    def normZ(self, val) -> None:
        self.normal[2] = val

    # endregion

    def to_c(self) -> str:
        return f"{{ {self.index}, {self.s}, {self.t}, {self.normX}, {self.normY}, {self.normZ}, {self.alpha} }}"


@dataclass
class SkinTransformation:
    """Represents a vertex position multiplied by the inverse binding matrix of a limb"""

    limbIndex: int
    x: int
    y: int
    z: int
    scale: int

    def to_c(self) -> str:
        return f"{{ {self.limbIndex}, {self.x}, {self.y}, {self.z}, {self.scale} }}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SkinTransformation):
            return False
        return (
            self.limbIndex == other.limbIndex
            and self.x == other.x
            and self.y == other.y
            and self.z == other.z
            and self.scale == other.scale
        )


@dataclass
class SkinLimbModif:
    skinVertices: list[SkinVertex]
    limbTransformations: list[SkinTransformation]

    @property
    def vtxCount(self) -> int:
        return len(self.skinVertices)

    @property
    def transformCount(self) -> int:
        return len(self.limbTransformations)

    @property
    def unk_4(self) -> int:
        """The index of the SkinTransformation in limbTransformations with the greatest scale"""
        index = self.limbTransformations.index(max(self.limbTransformations, key=lambda transform: transform.scale))
        return index

    def addVertex(self, other: "SkinLimbModif") -> None:
        for skinVertex in other.skinVertices:
            if skinVertex not in self.skinVertices:
                self.skinVertices.append(skinVertex)
            self.skinVertices.sort(key=lambda vertex: vertex.index)

    def to_c(self, vertexName: str, transformName: str) -> str:
        data = f"{{ {self.vtxCount}, {self.transformCount}, {self.unk_4}, {vertexName}, {transformName} }},\n"
        return data

    def __eq__(self, other) -> bool:
        # Since this is only used for merging SkinLimbModifs, we only care if the SkinTransforms are the same
        if not isinstance(other, SkinLimbModif):
            return False
        return sorted(self.limbTransformations, key=lambda transformation: transformation.limbIndex) == sorted(
            other.limbTransformations, key=lambda transformation: transformation.limbIndex
        )


GT = TypeVar("GT", int, str)


@dataclass(frozen=True)
class VertexWeight(Generic[GT]):
    group: GT
    weight: float


VertexTransform = NamedTuple("Transform", [("limbIndex", int), ("pos", mathutils.Vector), ("weight", float)])
IntTransform = NamedTuple("Transform", [("limbIndex", int), ("pos", tuple[int, int, int]), ("weight", int)])


class OOTVtx(Vtx):
    """subclass of Vtx that supports OoT style smooth skinning"""

    def __init__(
        self,
        position: list[int],
        uv: list[int],
        colorOrNormal: list[int],
        packedNormal: int = 0,
        transforms: list[IntTransform] | None = None,
    ) -> None:
        super().__init__(position, uv, colorOrNormal, packedNormal)
        self.transforms = transforms or []

    @property
    def normal(self) -> list[int]:
        return self.colorOrNormal[:3]

    @property
    def alpha(self) -> int:
        return self.colorOrNormal[3]

    @alpha.setter
    def alpha(self, val) -> None:
        self.colorOrNormal[3] = val

    @property
    def groups(self) -> list[tuple[int, int]]:
        return [(transform.limbIndex, transform.weight) for transform in self.transforms]


class OOTVtxList(VtxList):
    """Subclass of VtxList extended to support SkinLimbModifs"""

    def __init__(
        self,
        name: str,
        vertices: list[OOTVtx] | None = None,
        modifs: list[SkinLimbModif] | None = None,
    ) -> None:
        super().__init__(name)
        self.vertices = vertices or []
        self.modifs = modifs or []

    def vtxToModifs(self) -> list[SkinLimbModif]:
        if len(self.modifs) > 0:
            return self.modifs

        skinLimbModifs: list[SkinLimbModif] = []

        for index, vtx in enumerate(self.vertices):
            skinTransforms: list[SkinTransformation] = []

            for transform in vtx.transforms:
                skinTransforms.append(
                    SkinTransformation(
                        transform.limbIndex, transform.pos[0], transform.pos[1], transform.pos[2], transform.weight
                    )
                )
            # To match the order in the extracted files. May matter when setting unk_4
            skinTransforms.sort(key=lambda transform: transform.limbIndex)
            skinVertex = SkinVertex(index, vtx.uv, vtx.normal, vtx.alpha)
            modif = SkinLimbModif([skinVertex], skinTransforms)

            if modif not in skinLimbModifs:
                skinLimbModifs.append(modif)
            else:
                for skinLimbModif in skinLimbModifs:
                    if skinLimbModif == modif:
                        skinLimbModif.addVertex(modif)

        self.modifs = skinLimbModifs
        return skinLimbModifs

    def to_c(self) -> CData:
        if len(self.modifs) > 0:
            return CData()
        else:
            return super().to_c()


class SkinAnimData(FMesh):
    """subclass of FMesh for exporting SkinAnimatedLimbData"""

    def __init__(self, name: str, DLFormat: DLFormat) -> None:
        super().__init__(name, DLFormat)
        self.namePrefix = name.partition("mesh")[0]
        self.name = self.namePrefix + "SkinAnimatedLimbData"
        self.vtxList: OOTVtxList = OOTVtxList("(Vtx*)0x08000000")

    @property
    def limbModifications(self) -> list[SkinLimbModif]:
        return self.vtxList.vtxToModifs()

    @property
    def totalVtxCount(self) -> int:
        vtxCount = 0
        for modif in self.limbModifications:
            vtxCount += modif.vtxCount
        return vtxCount

    @property
    def limbModifCount(self) -> int:
        return len(self.limbModifications)

    @property
    def dlist(self) -> str:
        return self.draw.name

    def tri_group_new(self, fMaterial) -> FTriGroup:
        triGroup = super().tri_group_new(fMaterial)
        triGroup.vertexList = self.vtxList
        return triGroup

    def to_c(self, f3d: F3D, gfxFormatter: GfxFormatter) -> tuple[CData, CData]:
        staticData = CData()
        transformData = CData()
        vertexData = CData()
        modifData = CData()

        modifName = f"{self.namePrefix}SkinLimbModif"
        modifData.header += f"extern SkinLimbModif {modifName}[{self.limbModifCount}];\n"
        modifData.source += f"SkinLimbModif {modifName}[{self.limbModifCount}] = {{\n"

        for index, modif in enumerate(self.limbModifications):
            transformName = f"{self.namePrefix}SkinTransformation_{index:003}"
            vertexName = f"{self.namePrefix}SkinVertex_{index:003}"
            modifData.source += f"\t{modif.to_c(vertexName, transformName)}"

            transformData.header += "extern SkinTransformation " + f"{transformName}[{modif.transformCount}];\n"
            transformData.source += "SkinTransformation " + f"{transformName}[{modif.transformCount}] = {{\n"
            for transform in modif.limbTransformations:
                transformData.source += f"\t{transform.to_c()},\n"
            transformData.source += "};\n\n"

            vertexData.header += f"extern SkinVertex {vertexName}[{modif.vtxCount}];\n"
            vertexData.source += f"SkinVertex {vertexName}[{modif.vtxCount}] = {{\n"
            for vertex in modif.skinVertices:
                vertexData.source += f"\t{vertex.to_c()},\n"
            vertexData.source += "};\n\n"

        staticData.append(transformData)
        staticData.append(vertexData)
        staticData.append(modifData)
        staticData.source += "};\n\n"

        staticData.header += f"extern SkinAnimatedLimbData {self.name};\n"
        staticData.source += (
            f"SkinAnimatedLimbData {self.name} = {{\n"
            + f"\t{self.totalVtxCount}, {self.limbModifCount},\n"
            + f"\t{modifName}, {self.draw.name}\n"
            + "};\n\n"
        )

        for triGroup in self.triangleGroups:
            staticData.append(triGroup.to_c(f3d, gfxFormatter))

        draw_layer = "Opaque" if "Opaque" in self.name else "Transparent" if "Transparent" in self.name else "Overlay"
        dynamicData = gfxFormatter.drawToC(f3d, self.draw, layer=draw_layer)

        for cmd_list in self.draw_overrides:
            dynamicData.append(cmd_list.to_c(f3d))

        return staticData, dynamicData


class OOTVert(F3DVert):
    """Subclass of F3DVert that can store multiple vertex groups and their weights; for OoT style smooth skinning"""

    def __init__(
        self,
        position: mathutils.Vector,
        uv: mathutils.Vector,
        rgb: mathutils.Vector | None,
        normal: mathutils.Vector | None,
        alpha: float,
        transforms: list[VertexTransform] | None = None,
        skinVert: bool = False,
    ) -> None:
        super().__init__(position, uv, rgb, normal, alpha)
        self.transforms = transforms or []
        self.skinVert = skinVert

    @property
    def unk_4(self) -> int:
        """The index of the transform in transforms with the greatest weight"""
        transform = sorted(self.transforms, key=lambda transform: transform[2], reverse=True)[0]
        index = self.transforms.index(transform)
        return index

    @property
    def groups(self) -> list[VertexWeight]:
        return [VertexWeight(transform.limbIndex, transform.weight) for transform in self.transforms]

    def addTransform(self, limbIndex: int, pos: mathutils.Vector, weight: float):
        self.transforms.append(VertexTransform(limbIndex, pos, weight))
        self.transforms.sort(key=lambda transform: transform.limbIndex)

    def toVtx(
        self, mesh, texDimensions, transformMatrix: mathutils.Matrix, isPointSampled: bool, tex_scale=(1, 1)
    ) -> OOTVtx:
        position = self.convertPosition(transformMatrix)
        uv = self.convertUV(texDimensions, isPointSampled, tex_scale)
        colorOrNormal, packedNormal = self.convertNormalRGB(transformMatrix)
        intTransforms: list[IntTransform] = []
        for transform in self.transforms:
            intTransforms.append(
                IntTransform(
                    transform.limbIndex,
                    (round(transform.pos[0]), round(transform.pos[1]), round(transform.pos[2])),
                    round(transform.weight * 100),
                )
            )
        return OOTVtx(position, uv, colorOrNormal, packedNormal, intTransforms)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OOTVert):
            return NotImplemented

        return (
            self.position == other.position
            and self.uv == other.uv
            and self.stOffset == other.stOffset
            and self.rgb == other.rgb
            and self.normal == other.normal
            and self.alpha == other.alpha
            and self.transforms == other.transforms
        )


@dataclass
class SkinAnimatedLimbData:
    dlName: str = ""
    vertexData: list[OOTVert] = field(default_factory=list)
    baseAddr: str | None = None


class OOTTriangleConverter(TriangleConverter):
    def getBufferVert(self, loop: MeshLoop, face: MeshLoopTriangle, groupIndex: int | None) -> BufferVertex:
        vertexGroupInfo: OOTVertexGroupInfo = self.triConverterInfo.vertexGroupInfo
        mesh: bpy.types.Mesh = self.triConverterInfo.mesh
        groups = vertexGroupInfo.weights[loop.vertex_index]
        transforms: list[VertexTransform] = []
        unk_4 = sorted(groups, key=lambda group: group.weight, reverse=True)[0].group
        normMat = self.triConverterInfo.getTransformMatrix(unk_4).inverted().transposed()
        normal = loop.normal.copy().freeze()

        for group in groups:
            index = group.group
            weight = group.weight
            position: mathutils.Vector = mesh.vertices[loop.vertex_index].co.copy().freeze()
            mat = self.triConverterInfo.getTransformMatrix(index)
            boneIndex = getBoneIndexFromGroupIndex(self.triConverterInfo.obj, self.triConverterInfo.armature, index)
            limbIndex = vertexGroupInfo.boneIndexToLimbIndex[boneIndex]
            transforms.append(VertexTransform(limbIndex, mat @ position, weight))

        vert = getF3DVert(loop, face, self.convertInfo, mesh, OOTVert)
        vert.transforms = transforms

        if self.currentGroupIndex == -1:
            vert.normal = (normMat @ normal).normalized()
            vert.skinVert = True

        bufferVert = BufferVertex(vert, groupIndex, face.material_index)

        return bufferVert


class OOTModel(FModel):
    def __init__(self, name, DLFormat, drawLayerOverride, draw_config: Optional[str] = None):
        self.drawLayerOverride = drawLayerOverride
        self.flipbooks: list[TextureFlipbook] = []
        self.draw_config = draw_config

        FModel.__init__(self, name, DLFormat, GfxMatWriteMethod.WriteAll)

    # Since dynamic textures are handled by scene draw config, flipbooks should only belong to scene model.
    # Thus we have this function.
    def getFlipbookOwner(self):
        if self.parentModel is not None:
            model = self.parentModel
        else:
            model = self
        return model

    def getDrawLayerV3(self, obj):
        return obj.ootDrawLayer

    def getRenderMode(self, drawLayer):
        if self.drawLayerOverride:
            drawLayerUsed = self.drawLayerOverride
        else:
            drawLayerUsed = drawLayer
        defaultRenderModes = create_or_get_world(bpy.context.scene).ootDefaultRenderModes
        cycle1 = getattr(defaultRenderModes, drawLayerUsed.lower() + "Cycle1")
        cycle2 = getattr(defaultRenderModes, drawLayerUsed.lower() + "Cycle2")
        return (cycle1, cycle2)

    def addFlipbookWithRepeatCheck(self, flipbook: TextureFlipbook):
        model = self.getFlipbookOwner()

        def raiseErr(subMsg):
            raise PluginError(
                f"There are two flipbooks {subMsg} trying to write to the same texture array "
                + f"named: {flipbook.name}.\nMake sure that this flipbook name is unique, or "
                + "that repeated uses of this name use the same textures in the same order/format."
            )

        for existingFlipbook in model.flipbooks:
            if existingFlipbook.name == flipbook.name:
                if len(existingFlipbook.textureNames) != len(flipbook.textureNames):
                    raiseErr(
                        f"of different lengths ({len(existingFlipbook.textureNames)} "
                        + f"vs. {len(flipbook.textureNames)})"
                    )
                for i in range(len(flipbook.textureNames)):
                    if existingFlipbook.textureNames[i] != flipbook.textureNames[i]:
                        raiseErr(
                            f"with differing elements (elem {i} = "
                            + f"{existingFlipbook.textureNames[i]} vs. "
                            + f"{flipbook.textureNames[i]})"
                        )
        model.flipbooks.append(flipbook)

    def validateImages(self, material: bpy.types.Material, index: int):
        flipbookProp = getattr(material.flipbookGroup, f"flipbook{index}")
        texProp = getattr(material.f3d_mat, f"tex{index}")
        allImages = []
        refSize = (texProp.tex_reference_size[0], texProp.tex_reference_size[1])
        for flipbookTexture in flipbookProp.textures:
            if flipbookTexture.image is None:
                raise PluginError(f"Flipbook for {material.name} has a texture array item that has not been set.")
            imSize = (flipbookTexture.image.size[0], flipbookTexture.image.size[1])
            if imSize != refSize:
                raise PluginError(
                    f"In {material.name}: texture reference size is {refSize}, "
                    + f"but flipbook image {flipbookTexture.image.filepath} size is {imSize}."
                )
            if flipbookTexture.image not in allImages:
                allImages.append(flipbookTexture.image)
        return allImages

    def processTexRefCITextures(self, fMaterial: FMaterial, material: bpy.types.Material, index: int) -> FImage:
        # print("Processing flipbook...")
        model = self.getFlipbookOwner()
        flipbookProp = getattr(material.flipbookGroup, f"flipbook{index}")
        texProp = getattr(material.f3d_mat, f"tex{index}")
        if not usesFlipbook(material, flipbookProp, index, True, ootFlipbookReferenceIsValid):
            return super().processTexRefCITextures(fMaterial, material, index)
        if len(flipbookProp.textures) == 0:
            raise PluginError(f"{str(material)} cannot have a flipbook material with no flipbook textures.")

        flipbook = TextureFlipbook(flipbookProp.name, flipbookProp.exportMode, [], [])

        pal = []
        allImages = self.validateImages(material, index)
        for flipbookTexture in flipbookProp.textures:
            # print(f"Texture: {str(flipbookTexture.image)}")
            imageName, filename = getTextureNamesFromImage(
                flipbookTexture.image, texProp.tex_format, texProp.ci_format, model
            )
            if flipbookProp.exportMode == "Individual":
                imageName = flipbookTexture.name

            # We don't know yet if this already exists, cause we need the full set
            # of images which contribute to the palette, which we don't get until
            # writeTexRefCITextures (in case the other texture in multitexture contributes).
            # So these get created but may get dropped later.
            fImage_temp = FImage(
                imageName,
                texFormatOf[texProp.tex_format],
                texBitSizeF3D[texProp.tex_format],
                flipbookTexture.image.size[0],
                flipbookTexture.image.size[1],
                filename,
            )

            pal = mergePalettes(pal, getColorsUsedInImage(flipbookTexture.image, texProp.ci_format))

            flipbook.textureNames.append(fImage_temp.name)
            flipbook.images.append((flipbookTexture.image, fImage_temp))

        # print(f"Palette length: {len(pal)}") # Checked in moreSetupFromModel
        return allImages, flipbook, pal

    def writeTexRefCITextures(
        self,
        flipbook: Union[TextureFlipbook, None],
        fMaterial: FMaterial,
        imagesSharingPalette: list[bpy.types.Image],
        pal: list[int],
        texFmt: str,
        palFmt: str,
    ):
        if flipbook is None:
            return super().writeTexRefCITextures(None, fMaterial, imagesSharingPalette, pal, texFmt, palFmt)
        model = self.getFlipbookOwner()
        for i in range(len(flipbook.images)):
            image, fImage_temp = flipbook.images[i]
            imageKey = FImageKey(image, texFmt, palFmt, imagesSharingPalette)
            fImage = model.getTextureAndHandleShared(imageKey)
            if fImage is not None:
                flipbook.textureNames[i] = fImage.name
                flipbook.images[i] = (image, fImage)
            else:
                fImage = fImage_temp
                model.addTexture(imageKey, fImage, fMaterial)
            writeCITextureData(image, fImage, pal, palFmt, texFmt)
        # Have to delay this until here because texture names may have changed
        model.addFlipbookWithRepeatCheck(flipbook)

    def processTexRefNonCITextures(self, fMaterial: FMaterial, material: bpy.types.Material, index: int):
        model = self.getFlipbookOwner()
        flipbookProp = getattr(material.flipbookGroup, f"flipbook{index}")
        texProp = getattr(material.f3d_mat, f"tex{index}")
        if not usesFlipbook(material, flipbookProp, index, True, ootFlipbookReferenceIsValid):
            return super().processTexRefNonCITextures(fMaterial, material, index)
        if len(flipbookProp.textures) == 0:
            raise PluginError(f"{str(material)} cannot have a flipbook material with no flipbook textures.")

        flipbook = TextureFlipbook(flipbookProp.name, flipbookProp.exportMode, [], [])
        allImages = self.validateImages(material, index)
        for flipbookTexture in flipbookProp.textures:
            # print(f"Texture: {str(flipbookTexture.image)}")
            # Can't use saveOrGetTextureDefinition because the way it gets the
            # image key and the name from the texture property won't work here.
            imageKey = FImageKey(flipbookTexture.image, texProp.tex_format, texProp.ci_format, [flipbookTexture.image])
            fImage = model.getTextureAndHandleShared(imageKey)
            if fImage is None:
                imageName, filename = getTextureNamesFromImage(flipbookTexture.image, texProp.tex_format, None, model)
                if flipbookProp.exportMode == "Individual":
                    imageName = flipbookTexture.name
                fImage = FImage(
                    imageName,
                    texFormatOf[texProp.tex_format],
                    texBitSizeF3D[texProp.tex_format],
                    flipbookTexture.image.size[0],
                    flipbookTexture.image.size[1],
                    filename,
                )
                model.addTexture(imageKey, fImage, fMaterial)

            flipbook.textureNames.append(fImage.name)
            flipbook.images.append((flipbookTexture.image, fImage))

        self.addFlipbookWithRepeatCheck(flipbook)
        return allImages, flipbook

    def writeTexRefNonCITextures(self, flipbook: Union[TextureFlipbook, None], texFmt: str):
        if flipbook is None:
            return super().writeTexRefNonCITextures(flipbook, texFmt)
        for image, fImage in flipbook.images:
            writeNonCITextureData(image, fImage, texFmt)

    def onMaterialCommandsBuilt(self, fMaterial, material, drawLayer):
        super().onMaterialCommandsBuilt(fMaterial, material, drawLayer)
        # handle dynamic material calls
        gfxList = fMaterial.material
        matDrawLayer = getattr(material.ootMaterial, drawLayer.lower())

        for i in range(8, 14):
            if getattr(matDrawLayer, f"segment{i:X}"):
                is_animated_material = False

                if self.draw_config is not None and "mat_anim" in self.draw_config:
                    is_animated_material = True

                gfxList.commands.append(
                    DynamicMaterialDL(
                        GfxList(f"0x0{i:X}000000", GfxListTag.Material, DLFormat.Static), is_animated_material
                    )
                )

        for i in range(0, 2):
            p = f"customCall{i}"
            if getattr(matDrawLayer, p):
                gfxList.commands.append(
                    SPDisplayList(GfxList(getattr(matDrawLayer, f"{p}_seg"), GfxListTag.Material, DLFormat.Static))
                )

    def onAddMesh(self, fMesh, contextObj):
        if contextObj is not None and hasattr(contextObj, "ootDynamicTransform"):
            if contextObj.ootDynamicTransform.billboard:
                fMesh.draw.commands.append(SPMatrix("0x01000000", "G_MTX_MODELVIEW | G_MTX_NOPUSH | G_MTX_MUL"))


class OOTGfxFormatter(GfxFormatter):
    def __init__(self, scrollMethod):
        GfxFormatter.__init__(self, scrollMethod, 64, None)


class OOTTriangleConverterInfo(TriangleConverterInfo):
    def __init__(self, obj, armature, f3d, transformMatrix, infoDict):
        TriangleConverterInfo.__init__(self, obj, armature, f3d, transformMatrix, infoDict)

    def getMatrixAddrFromGroup(self, groupIndex):
        return format((0x0D << 24) + MTX_SIZE * self.vertexGroupInfo.vertexGroupToMatrixIndex[groupIndex], "#010x")


# StrEnum is Python 3.11+
class LimbType(str, Enum):
    INVALID = "Invalid"
    STANDARD = "Standard"
    LOD = "Lod"
    SKIN = "Skin"


class LimbSkinType(str, Enum):
    # Contains no mesh data, segment is NULL
    EMPTY = "0"
    # Contains the smooth skinned mesh data, segment is SkinAnimatedLimbData
    SKIN_LIMB_TYPE_ANIMATED = "SKIN_LIMB_TYPE_ANIMATED"
    # Is a limb responsible for smooth skinned deformation, segment is NULL
    SKINNED = "5"
    # Functions like a StandardLimb, segment is DisplayList
    SKIN_LIMB_TYPE_NORMAL = "SKIN_LIMB_TYPE_NORMAL"


@dataclass(frozen=True)
class SkinLimbGroup:
    name: str
    vertices: list[int] = field(default_factory=list)  # vertex indices
    weights: list[float] = field(default_factory=list)  # vertex group weights out of 1.0
    type: LimbSkinType = LimbSkinType.EMPTY


class OOTVertexGroupInfo(VertexGroupInfo):
    def __init__(self):
        self.vertexGroupToMatrixIndex: dict[int | None, int] = {}
        self.weights: dict[int, list[VertexWeight[int]]] = {}  # vertex index to list of (group index, weight)
        self.skinnedVertexGroups: dict[str, SkinLimbGroup] = {}  # boneName to SkinLimbGroup
        self.boneIndexToLimbIndex: dict[int, int] = {}
        VertexGroupInfo.__init__(self)


# class OOTBox:
# 	def __init__(self):
# 		self.minBounds = [-2**8, -2**8]
# 		self.maxBounds = [2**8 - 1, 2**8 - 1]


class OOTF3DContext(F3DContext):
    def __init__(self, f3d, limbList, basePath):
        self.limbList = limbList
        self.dlList = []  # in the order they are rendered
        self.isBillboard = False
        self.flipbooks = {}  # {(segment, draw layer) : TextureFlipbook}

        # the new assets system extracts CI textures as PNGs with the TLUT already applied
        # so we need to avoid reading TLUTs as the files don't exist outside the build folder
        self.ignore_tlut = False

        materialContext = createF3DMat(None, preset="oot_shaded_solid")
        # materialContext.f3d_mat.rdp_settings.g_mdsft_cycletype = "G_CYC_1CYCLE"
        F3DContext.__init__(self, f3d, basePath, materialContext)
        self.draw_layer_prop = "oot"
        self.vertOverride = OOTVert
        self.initContext()

    def initContext(self):
        super().initContext()
        # nested dict of groupName{weight : [vertex index] }
        self.ootLimbGroups: defaultdict[str, dict[float, list[int]]] = defaultdict(lambda: defaultdict(list))

        # For handling SkinLimbs
        self.skinAnimatedLimbData: SkinAnimatedLimbData | None = None
        self.skinLimbType: list[LimbSkinType | None] = []
        self.isSkinDL: bool = False

    def getLimbName(self, index):
        return self.limbList[index]

    def getBoneName(self, index):
        return "bone" + format(index, "03") + "_" + self.getLimbName(index)

    def vertexFormatPatterns(self, data):
        # position, uv, color/normal
        if "VTX" in data:
            return ["VTX\s*\(([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*)\)"]
        else:
            return F3DContext.vertexFormatPatterns(self, data)

    # For game specific instance, override this to be able to identify which verts belong to which bone.
    def setCurrentTransform(self, name, flagList="G_MTX_NOPUSH | G_MTX_LOAD | G_MTX_MODELVIEW"):
        if name[:4].lower() == "0x0d":
            # This code is for skeletons
            index = int(int(name[4:], 16) / MTX_SIZE)
            if index < len(self.dlList):
                transformName = self.getLimbName(self.dlList[index].limbIndex)

            # This code is for jabu jabu level, requires not adding to self.dlList?
            else:
                transformName = name
                self.matrixData[name] = mathutils.Matrix.Identity(4)
                print(f"Matrix {name} has not been processed from dlList, substituting identity matrix.")

            F3DContext.setCurrentTransform(self, transformName, flagList)

        else:
            try:
                pointer = hexOrDecInt(name)
            except:
                F3DContext.setCurrentTransform(self, name, flagList)
            else:
                if pointer >> 24 == 0x01:
                    self.isBillboard = True
                else:
                    print("Unhandled matrix: " + name)

    def processDLName(self, name):
        # Commands loaded to 0x0C are material related only.
        try:
            pointer = hexOrDecInt(name)
        except:
            if name == "gEmptyDL":
                return None
            return name
        else:
            segment = pointer >> 24
            if segment >= 0x08 and segment <= 0x0D:
                setattr(self.materialContext.ootMaterial.opaque, "segment" + format(segment, "1X"), True)
                setattr(self.materialContext.ootMaterial.transparent, "segment" + format(segment, "1X"), True)
                self.materialChanged = True
            return None
        return name

    def processTextureName(self, textureName):
        try:
            pointer = hexOrDecInt(textureName)
        except:
            return textureName
        else:
            return textureName
            # if (pointer >> 24) == 0x08:
            # 	print("Unhandled OOT pointer: " + textureName)

    def getMaterialKey(self, material: bpy.types.Material):
        return (material.ootMaterial.key(), super().getMaterialKey(material))

    def clearGeometry(self):
        self.dlList = []
        self.isBillboard = False
        # self.initContext()
        super().clearGeometry()

    def transformPosition(self, vert: OOTVert) -> mathutils.Vector:
        position = mathutils.Vector((0.0, 0.0, 0.0))
        for transform in vert.transforms:
            position += self.matrixData[self.limbList[transform.limbIndex]] @ transform.pos * (transform.weight)

        return position

    def getVertexTransforms(
        self, bufferVert: BufferVertex, has_normal: bool, has_packed_normals: bool
    ) -> tuple[mathutils.Vector, mathutils.Vector]:
        vert = bufferVert.f3dVert
        if not isinstance(vert, OOTVert):
            raise PluginError("vert must be of type OOTVert")

        if len(self.limbList) == 0:
            return super().getVertexTransforms(bufferVert, has_normal, has_packed_normals)

        if len(vert.transforms) == 0:
            if isinstance(bufferVert.groupIndex, int):
                groupIndex = bufferVert.groupIndex
            else:
                groupIndex = list(self.matrixData).index(bufferVert.groupIndex)
            vert.addTransform(groupIndex, vert.position, 1.0)

        position = self.transformPosition(vert)
        limbIndex = vert.transforms[vert.unk_4].limbIndex
        transform = self.matrixData[self.getLimbName(limbIndex)]
        normal = self.transformNormal(has_normal, has_packed_normals, vert, transform)
        return position, normal

    def getTransformedVertex(self, index: int) -> BufferVertex:
        bufferVert = self.vertexBuffer[index]

        if bufferVert is None:
            raise PluginError("Vertex Buffer is empty.")

        vert = bufferVert.f3dVert
        if not isinstance(vert, OOTVert):
            raise PluginError("vert must be of type OOTVert")

        mat = self.mat()
        has_rgb, has_normal, has_packed_normals = getRgbNormalSettings(mat)
        has_packed_normals = has_packed_normals and not vert.skinVert

        position, normal = self.getVertexTransforms(bufferVert, has_normal, has_packed_normals)
        uv, rgb, alpha = self.convertVertexValues(mat, has_rgb, vert)
        transformedVert = OOTVert(position, uv, rgb, normal, alpha, transforms=vert.transforms)

        return BufferVertex(transformedVert, bufferVert.groupIndex, bufferVert.materialIndex)

    def updateBuffer(self, count, start, vertexData, vertexDataOffset):
        for i in range(count):
            vert: OOTVert = vertexData[vertexDataOffset + i]
            self.vertexBuffer[start + i] = BufferVertex(vert, self.currentTransformName, 0)

    def processLimbGroups(self, verts: list[BufferVertex]) -> None:
        for idx, bufferVert in enumerate(verts):
            vert = bufferVert.f3dVert
            assert isinstance(vert, OOTVert)

            for vertexWeight in vert.groups:
                weight = vertexWeight.weight
                group = vertexWeight.group
                if isinstance(group, int):
                    boneName = self.limbToBoneName[self.limbList[group]]
                else:
                    boneName = self.limbToBoneName[group]
                self.ootLimbGroups[boneName][weight].append(len(self.verts) + idx)

        self.verts.extend([vert.f3dVert for vert in verts])

    def createVertexGroups(self, obj):
        for limbGroup, weights in self.ootLimbGroups.items():
            if isinstance(limbGroup, str):
                groupName = limbGroup
            else:
                groupName = self.getBoneName(limbGroup)
            if not obj.vertex_groups.get(groupName):
                group = obj.vertex_groups.new(name=groupName)
            else:
                group = obj.vertex_groups.get(groupName)
            for weight, indices in weights.items():
                group.add(indices, weight, "REPLACE")

    def clearMaterial(self):
        self.isBillboard = False

        # Don't clear ootMaterial, some skeletons (Link) require dynamic material calls to be preserved between limbs
        clearOOTFlipbookProperty(self.materialContext.flipbookGroup.flipbook0)
        clearOOTFlipbookProperty(self.materialContext.flipbookGroup.flipbook1)
        F3DContext.clearMaterial(self)

    def postMaterialChanged(self):
        pass

    def handleTextureReference(
        self,
        name: str,
        image: F3DTextureReference,
        material: bpy.types.Material,
        index: int,
        tileSettings: DPSetTile,
        data: str,
    ):
        # check for texture arrays.
        clearOOTFlipbookProperty(getattr(material.flipbookGroup, "flipbook" + str(index)))
        match = re.search(f"(0x0[0-9a-fA-F])000000", name)
        if match:
            segment = int(match.group(1), 16)
            flipbookKey = (segment, material.f3d_mat.draw_layer.oot)
            if flipbookKey in self.flipbooks:
                flipbook = self.flipbooks[flipbookKey]

                flipbookProp = getattr(material.flipbookGroup, "flipbook" + str(index))
                flipbookProp.enable = True
                flipbookProp.exportMode = flipbook.exportMode
                if flipbookProp.exportMode == "Array":
                    flipbookProp.name = flipbook.name

                if len(flipbook.textureNames) == 0:
                    raise PluginError(
                        f'Texture array "{flipbookProp.name}" pointed at segment {hex(segment)} is a zero element array, which is invalid.'
                    )
                for textureName in flipbook.textureNames:
                    image = self.loadTexture(data, textureName, None, tileSettings, False)
                    if not isinstance(image, bpy.types.Image):
                        raise PluginError(
                            f'Could not find texture "{textureName}", so it can not be used in a flipbook texture.\n'
                            f"For OOT scenes this may be because the scene's draw config references textures not stored in its scene/room files.\n"
                            f"In this case, draw configs that use flipbook textures should only be used for one scene.\n"
                        )
                    flipbookProp.textures.add()
                    flipbookProp.textures[-1].image = image

                    if flipbookProp.exportMode == "Individual":
                        flipbookProp.textures[-1].name = textureName

                texProp = getattr(material.f3d_mat, "tex" + str(index))
                texProp.tex = flipbookProp.textures[0].image  # for visual purposes only, will be ignored
                texProp.use_tex_reference = True
                texProp.tex_reference = name
            else:
                super().handleTextureReference(name, image, material, index, tileSettings, data)
        else:
            super().handleTextureReference(name, image, material, index, tileSettings, data)

    def handleTextureValue(self, material: bpy.types.Material, image: bpy.types.Image, index: int):
        clearOOTFlipbookProperty(getattr(material.flipbookGroup, "flipbook" + str(index)))
        super().handleTextureValue(material, image, index)

    def handleApplyTLUT(
        self,
        material: bpy.types.Material,
        texProp: TextureProperty,
        tlut: bpy.types.Image,
        index: int,
    ):
        flipbook = getattr(material.flipbookGroup, "flipbook" + str(index))
        if usesFlipbook(material, flipbook, index, True, ootFlipbookReferenceIsValid):
            # Don't apply TLUT to texProp.tex, as it is the same texture as the first flipbook texture.
            # Make sure to check if tlut is already applied (ex. LOD skeleton uses same flipbook textures)
            # applyTLUTToIndex() doesn't check for this if texProp.use_tex_reference.
            for flipbookTexture in flipbook.textures:
                if flipbookTexture.image not in self.tlutAppliedTextures:
                    self.applyTLUT(flipbookTexture.image, tlut)
                    self.tlutAppliedTextures.append(flipbookTexture.image)
        else:
            super().handleApplyTLUT(material, texProp, tlut, index)

    def applyTLUTToIndex(self, index):
        if not self.ignore_tlut:
            super().applyTLUTToIndex(index)

    def loadTLUTPal(self, name: str, dlData: str, count: int):
        if not self.ignore_tlut:
            super().loadTLUTPal(name, dlData, count)

    def getVertexSegmentData(self, segment: str, count: str, start: str, vertOverride: type[F3DVert] = F3DVert) -> None:
        if not self.isSkinDL:
            super().getVertexSegmentData(segment, count, start, vertOverride)
        if self.skinAnimatedLimbData.baseAddr is None:
            self.skinAnimatedLimbData.baseAddr = int(segment, 16)

        offset = (int(segment, 16) - self.skinAnimatedLimbData.baseAddr) // VTX_SIZE
        end = offset + int(count) + int(start)
        self.vertexData[segment] = self.skinAnimatedLimbData.vertexData[offset:end]


def clearOOTFlipbookProperty(flipbookProp):
    flipbookProp.enable = False
    flipbookProp.name = "sFlipbookTextures"
    flipbookProp.exportMode = "Array"
    flipbookProp.textures.clear()
