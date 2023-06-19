from typing import Union, Optional
from dataclasses import dataclass, field
import bpy
from math import ceil, floor

from .f3d_enums import *
from .f3d_constants import *
from .f3d_material import (
    all_combiner_uses,
    getTmemWordUsage,
    texBitSizeF3D,
    texFormatOf,
    TextureProperty,
    F3DMaterialProperty,
    isTexturePointSampled,
)
from .f3d_gbi import *
from .f3d_gbi import _DPLoadTextureBlock

from ..utility import *


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
        value = int(floor(value))
        if self.largeEdges == "Clamp":
            value = min(max(value, 0), self.texDimensions[field] - 1)
        if self.is4bit and field == 0:
            # Must start on an even texel (round down)
            value &= ~1
        return value

    def getHigh(self, value, field):
        value = int(ceil(value)) - (1 if self.isPointSampled else 0)
        if self.largeEdges == "Clamp":
            value = min(max(value, 0), self.texDimensions[field] - 1)
        if self.is4bit and field == 0:
            # Must end on an odd texel (round up)
            value |= 1
        return value

    def fixRegion(self, sl, sh, tl, th):
        assert sl <= sh and tl <= th
        soffset = int(floor(sl / self.texDimensions[0])) * self.texDimensions[0]
        toffset = int(floor(tl / self.texDimensions[1])) * self.texDimensions[1]
        sl -= soffset
        sh -= soffset
        tl -= toffset
        th -= toffset
        assert 0 <= sl < self.texDimensions[0] and 0 <= tl < self.texDimensions[1]
        ret = True
        if sh >= 1024 or th >= 1024:
            ret = False
        if sh >= self.texDimensions[0]:
            # Load wraps in S. Load must start a multiple of a TMEM word from
            # the end of the texture, in order for the second load (beginning of
            # image) to start at a whole word.
            texelsPerWord = 64 // texBitSizeInt[self.texFormat]
            if texelsPerWord > self.texDimensions[0]:
                raise PluginError(
                    f"In large texture material {self.materialName}:"
                    + f" large texture must be at least {texelsPerWord} wide."
                )
            sl -= self.texDimensions[0]
            sl = int(floor(sl / texelsPerWord)) * texelsPerWord
            sl += self.texDimensions[0]
        if th >= self.texDimensions[1]:
            # Load wraps in T. Load must start a multiple of 2 texture rows from
            # the end of the texture, in order for the second load to have the
            # same odd/even row parity as the first (because texels are
            # interleaved in TMEM every other row).
            tl -= self.texDimensions[1]
            tl = int(floor(tl / 2.0)) * 2
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
        """
        Attempts to enlarge the self TileLoad to cover both itself and the other
        TileLoad. If this succeeds, self is modified and True is returned. If it
        fails (because it would be too large or the other constraints from
        fixRegion would be violated), self is not modified and False is returned.
        A large texture mesh is built by, for each triangle, trying to subsume
        it into each of the existing loads. If it succeeds on one of them, it
        moves on to the next triangle. If it fails on all of them, a new load is
        created for that triangle and added to the list.
        """
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
    curImgSet: Optional[int],
    curTileLines: list[int],
):
    """
    Checks whether a particular texture is large and if so, writes the loads for
    that large texture. "maybe" is to bring the if statement into the function
    instead of checking whether the texture is large before calling it.
    """
    if fMaterial.isTexLarge[i]:
        wrapS = tileSettings.sh >= texDimensions[0]
        wrapT = tileSettings.th >= texDimensions[1]
        assert 0 <= tileSettings.sl < texDimensions[0]
        assert 0 <= tileSettings.tl < texDimensions[1]
        siz = texBitSizeF3D[texProp.tex_format]
        line = getTileLine(fImage, tileSettings.sl, tileSettings.sh, siz, fModel.f3d)
        tmem = fMaterial.largeTexAddr[i]
        if wrapS or wrapT:
            fmt = texFormatOf[texProp.tex_format]
            texelsPerWord = 64 // texBitSizeInt[texProp.tex_format]
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
                    assert (texDimensions[0] - tileSettings.sl) % texelsPerWord == 0
                    sLineOfs = (texDimensions[0] - tileSettings.sl) // texelsPerWord
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


# Functions for texture and palette definitions


def getTextureNamesFromBasename(baseName: str, texOrPalFormat: str, parent: Union[FModel, FTexRect], isPalette: bool):
    suffix = getTextureSuffixFromFormat(texOrPalFormat)
    imageName = parent.name + "_" + baseName + "_"
    if isPalette:
        imageName += "pal_"
    imageName += suffix
    imageName = checkDuplicateTextureName(parent, toAlnum(imageName))
    filename = baseName + (f"" if (baseName.endswith(suffix)) else f".{suffix}") + (".pal" if isPalette else ".inc.c")
    return imageName, filename


def getImageName(image: bpy.types.Image):
    if image is None:
        raise PluginError("No image set in material!")
    elif image.filepath == "":
        return image.name
    else:
        return getNameFromPath(image.filepath, True)


def getTextureNamesFromImage(image: bpy.types.Image, texFormat: str, parent: Union[FModel, FTexRect]):
    return getTextureNamesFromBasename(getImageName(image), texFormat, parent, False)


def getTextureNamesFromProp(texProp: TextureProperty, parent: Union[FModel, FTexRect]):
    if texProp.use_tex_reference:
        raise PluginError("Internal error, invalid use of getTextureNamesFromProp")
    return getTextureNamesFromImage(texProp.tex, texProp.tex_format, parent)


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
    isPalRef: bool,
    images: list[bpy.types.Image],
    palBaseName: str,
    palLen: int,
) -> tuple[FPaletteKey, FImage]:
    texFmt = texProp.tex_format
    palFmt = texProp.ci_format
    palFormat = texFormatOf[palFmt]
    paletteKey = FPaletteKey(palFmt, images)

    if isPalRef:
        fPalette = FImage(texProp.pal_reference, None, None, 1, palLen, None)
        return paletteKey, fPalette

    # If palette already loaded, return that data.
    fPalette = parent.getTextureAndHandleShared(paletteKey)
    if fPalette is not None:
        # print(f"Palette already exists")
        return paletteKey, fPalette

    paletteName, filename = getTextureNamesFromBasename(palBaseName, palFmt, parent, True)
    fPalette = FImage(paletteName, palFormat, "G_IM_SIZ_16b", 1, palLen, filename)

    parent.addTexture(paletteKey, fPalette, fMaterial)
    return paletteKey, fPalette


def saveOrGetTextureDefinition(
    fMaterial: FMaterial,
    parent: Union[FModel, FTexRect],
    texProp: TextureProperty,
    images: list[bpy.types.Image],
    isLarge: bool,
) -> tuple[FImageKey, FImage]:
    image = texProp.tex
    texFmt = texProp.tex_format
    texFormat = texFormatOf[texFmt]
    bitSize = texBitSizeF3D[texFmt]
    imageKey = getImageKey(texProp, images)

    if texProp.use_tex_reference:
        width, height = texProp.tex_reference_size
        fImage = FImage(texProp.tex_reference, None, None, width, height, None)
        return imageKey, fImage

    # If image already loaded, return that data.
    fImage = parent.getTextureAndHandleShared(imageKey)
    if fImage is not None:
        # print(f"Image already exists")
        return imageKey, fImage

    imageName, filename = getTextureNamesFromProp(texProp, parent)
    fImage = FImage(imageName, texFormat, bitSize, image.size[0], image.size[1], filename)
    fImage.isLargeTexture = isLarge

    parent.addTexture(imageKey, fImage, fMaterial)
    return imageKey, fImage


@dataclass
class TexInfo:
    # Main parameters
    useTex: bool = False
    isTexRef: bool = False
    isTexCI: bool = False
    texFormat: str = ""
    palFormat: str = ""
    imageDims: tuple[int, int] = (0, 0)
    tmemSize: int = 0
    errorMsg: str = ""

    # Parameters from moreSetupFromModel
    pal: Optional[list[int]] = None
    palLen: int = 0
    imDependencies: Optional[list[bpy.types.Image]] = None
    flipbook: Optional["TextureFlipbook"] = None
    isPalRef: bool = False

    # Parameters computed by MultitexManager.writeAll
    texAddr: int = 0
    palAddr: int = 0
    palIndex: int = 0
    palDependencies: list[bpy.types.Image] = field(default_factory=list)
    palBaseName: str = ""
    loadPal: bool = False
    doTexLoad: bool = True
    doTexTile: bool = True

    # Internal parameters--copies of passed parameters
    texProp: Optional[TextureProperty] = None
    indexInMat: int = -1

    def fromMat(self, index: int, f3dMat: F3DMaterialProperty) -> bool:
        useDict = all_combiner_uses(f3dMat)
        if not useDict["Texture " + str(index)]:
            return True

        texProp = getattr(f3dMat, "tex" + str(index))
        return self.fromProp(texProp, index)

    def fromProp(self, texProp: TextureProperty, index: int) -> bool:
        self.indexInMat = index
        self.texProp = texProp
        if not texProp.tex_set:
            return True

        self.useTex = True
        tex = texProp.tex
        self.isTexRef = texProp.use_tex_reference
        self.texFormat = texProp.tex_format
        self.isTexCI = self.texFormat[:2] == "CI"
        self.palFormat = texProp.ci_format if self.isTexCI else ""

        if tex is not None and (tex.size[0] == 0 or tex.size[1] == 0):
            self.errorMsg = f"Image {tex.name} has 0 size; may have been deleted/moved."
            return False

        if not self.isTexRef:
            if tex is None:
                self.errorMsg = f"No texture is selected."
                return False
            elif len(tex.pixels) == 0:
                self.errorMsg = f"Image {tex.name} is missing on disk."
                return False

        if self.isTexRef:
            width, height = texProp.tex_reference_size
        else:
            width, height = tex.size
        self.imageDims = (width, height)

        self.tmemSize = getTmemWordUsage(self.texFormat, width, height)

        if width > 1024 or height > 1024:
            self.errorMsg = f"Image size (even large textures) limited to 1024 in each dimension."
            return False

        if texBitSizeInt[self.texFormat] == 4 and (width & 1) != 0:
            self.errorMsg = f"A 4-bit image must have a width which is even."
            return False

        return True

    def moreSetupFromModel(
        self,
        material: bpy.types.Material,
        fMaterial: FMaterial,
        fModel: FModel,
    ) -> None:
        if not self.useTex:
            return

        if self.isTexCI:
            self.imDependencies, self.flipbook, self.pal = fModel.processTexRefCITextures(
                fMaterial, material, self.indexInMat
            )
            if self.isTexRef:
                if self.flipbook is not None:
                    self.palLen = len(self.pal)
                else:
                    self.palLen = self.texProp.pal_reference_size
            else:
                assert self.flipbook is None
                self.pal = getColorsUsedInImage(self.texProp.tex, self.palFormat)
                self.palLen = len(self.pal)
            if self.palLen > (16 if self.texFormat == "CI4" else 256):
                raise PluginError(
                    f"Error in {material.name}: texture {self.indexInMat}"
                    + (" (all flipbook textures)" if self.flipbook is not None else "")
                    + f" uses too many unique colors to fit in format {self.texFormat}."
                )
        else:
            self.imDependencies, self.flipbook = fModel.processTexRefNonCITextures(fMaterial, material, self.indexInMat)

        self.isPalRef = self.isTexRef and self.flipbook is None
        self.palDependencies = self.imDependencies

    def getPaletteName(self):
        if not self.useTex or self.isPalRef:
            return None
        if self.flipbook is not None:
            return self.flipbook.name
        return getImageName(self.texProp.tex)

    def writeAll(
        self,
        fMaterial: FMaterial,
        fModel: Union[FModel, FTexRect],
        convertTextureData: bool,
    ):
        if not self.useTex:
            return
        assert (
            self.imDependencies is not None
        )  # Must be set manually if didn't use moreSetupFromModel, e.g. ti.imDependencies = [tex]

        # Get definitions
        imageKey, fImage = saveOrGetTextureDefinition(
            fMaterial, fModel, self.texProp, self.imDependencies, fMaterial.isTexLarge[self.indexInMat]
        )
        fMaterial.imageKey[self.indexInMat] = imageKey
        if self.loadPal:
            _, fPalette = saveOrGetPaletteDefinition(
                fMaterial, fModel, self.texProp, self.isPalRef, self.palDependencies, self.palBaseName, self.palLen
            )

        # Write loads
        loadGfx = fMaterial.texture_DL
        f3d = fModel.f3d
        if self.loadPal:
            savePaletteLoad(loadGfx, fPalette, self.palFormat, self.palAddr, self.palLen, 5 - self.indexInMat, f3d)
        if self.doTexLoad:
            saveTextureLoadOnly(fImage, loadGfx, self.texProp, None, 7 - self.indexInMat, self.texAddr, f3d)
        if self.doTexTile:
            saveTextureTile(
                fImage, fMaterial, loadGfx, self.texProp, None, self.indexInMat, self.texAddr, self.palIndex, f3d
            )

        # Write texture data
        if convertTextureData:
            if self.loadPal and not self.isPalRef:
                writePaletteData(fPalette, self.pal)
            if self.isTexRef:
                if self.isTexCI:
                    fModel.writeTexRefCITextures(
                        self.flipbook, fMaterial, self.imDependencies, self.pal, self.texFormat, self.palFormat
                    )
                else:
                    fModel.writeTexRefNonCITextures(self.flipbook, self.texFormat)
            else:
                if self.isTexCI:
                    writeCITextureData(self.texProp.tex, fImage, self.pal, self.palFormat, self.texFormat)
                else:
                    writeNonCITextureData(self.texProp.tex, fImage, self.texFormat)


class MultitexManager:
    def __init__(
        self,
        material: bpy.types.Material,
        fMaterial: FMaterial,
        fModel: FModel,
    ):
        f3dMat = material.f3d_mat
        self.ti0, self.ti1 = TexInfo(), TexInfo()
        if not self.ti0.fromMat(0, f3dMat):
            raise PluginError(f"In {material.name} tex0: {self.ti0.errorMsg}")
        if not self.ti1.fromMat(1, f3dMat):
            raise PluginError(f"In {material.name} tex1: {self.ti1.errorMsg}")
        self.ti0.moreSetupFromModel(material, fMaterial, fModel)
        self.ti1.moreSetupFromModel(material, fMaterial, fModel)

        self.isCI = self.ti0.isTexCI or self.ti1.isTexCI

        if self.ti0.useTex and self.ti1.useTex:
            if self.ti0.isTexCI != self.ti1.isTexCI:
                raise PluginError(
                    "In material "
                    + material.name
                    + ": N64 does not support CI + non-CI texture. "
                    + "Must be both CI or neither CI."
                )
            if (
                self.ti0.isTexRef
                and self.ti1.isTexRef
                and self.ti0.texProp.tex_reference == self.ti1.texProp.tex_reference
                and self.ti0.texProp.tex_reference_size != self.ti1.texProp.tex_reference_size
            ):
                raise PluginError(
                    "In material " + material.name + ": Two textures with the same reference must have the same size."
                )
            if self.isCI:
                if self.ti0.palFormat != self.ti1.palFormat:
                    raise PluginError(
                        "In material "
                        + material.name
                        + ": Both CI textures must use the same palette format (usually RGBA16)."
                    )
                if (
                    self.ti0.isTexRef
                    and self.ti1.isTexRef
                    and self.ti0.texProp.pal_reference == self.ti1.texProp.pal_reference
                    and self.ti0.texProp.pal_reference_size != self.ti1.texProp.pal_reference_size
                ):
                    raise PluginError(
                        "In material "
                        + material.name
                        + ": Two textures with the same palette reference must have the same palette size."
                    )

        self.palFormat = self.ti0.palFormat if self.ti0.useTex else self.ti1.palFormat

    def getTT(self) -> str:
        return "G_TT_NONE" if not self.isCI else ("G_TT_" + self.palFormat)

    def writeAll(
        self, material: bpy.types.Material, fMaterial: FMaterial, fModel: FModel, convertTextureData: bool
    ) -> None:
        f3dMat = material.f3d_mat
        # Determine how to arrange / load palette entries into upper half of tmem
        if self.isCI:
            assert self.ti0.useTex or self.ti1.useTex
            if not self.ti1.useTex:
                self.ti0.loadPal = True
            elif not self.ti0.useTex:
                self.ti1.loadPal = True
            elif not convertTextureData:
                if self.ti0.texFormat == "CI8" or self.ti1.texFormat == "CI8":
                    raise PluginError(
                        "In material "
                        + material.name
                        + ": When using export as PNGs mode, can't have multitexture with one or more CI8 textures."
                        + " Only single CI texture or two CI4 textures."
                    )
                self.ti0.loadPal = self.ti1.loadPal = True
                self.ti1.palIndex = 1
                self.ti1.palAddr = 16
            else:  # Two CI textures, normal mode
                if self.ti0.texFormat == "CI8" and self.ti1.texFormat == "CI8":
                    if (self.ti0.pal is None) != (self.ti1.pal is None):
                        raise PluginError(
                            "In material "
                            + material.name
                            + ": can't have two CI8 textures where only one is a non-flipbook reference; "
                            + "no way to assign the palette."
                        )
                    self.ti0.loadPal = True
                    if self.ti0.pal is None:
                        if self.ti0.texProp.pal_reference != self.ti1.texProp.pal_reference:
                            raise PluginError(
                                "In material "
                                + material.name
                                + ": can't have two CI8 textures with different palette references."
                            )
                    else:
                        self.ti0.pal = mergePalettes(self.ti0.pal, self.ti1.pal)
                        self.ti0.palLen = len(self.ti0.pal)
                        if self.ti0.palLen > 256:
                            raise PluginError(
                                "In material "
                                + material.name
                                + ": the two CI textures together contain a total of "
                                + str(self.ti0.palLen)
                                + " colors, which can't fit in a CI8 palette (256)."
                            )
                        # self.ti0.imDependencies remains what it was; the CIs in im0 are the same as they
                        # would be if im0 was alone. But im1 and self.ti0.pal depend on both.
                        self.ti1.imDependencies = self.ti0.palDependencies = (
                            self.ti0.imDependencies + self.ti1.imDependencies
                        )
                elif self.ti0.texFormat != self.ti1.texFormat:  # One CI8, one CI4
                    ci8Pal, ci4Pal = (
                        (self.ti0.pal, self.ti1.pal) if self.ti0.texFormat == "CI8" else (self.ti1.pal, self.ti0.pal)
                    )
                    ci8PalLen, ci4PalLen = (
                        (self.ti0.palLen, self.ti1.palLen)
                        if self.ti0.texFormat == "CI8"
                        else (self.ti1.palLen, self.ti0.palLen)
                    )
                    if self.ti0.pal is None or self.ti1.pal is None:
                        if ci8PalLen > 256 - 16:
                            raise PluginError(
                                "In material "
                                + material.name
                                + ": the CI8 texture has over 240 colors, which can't fit together with the CI4 palette."
                            )
                        self.ti0.loadPal = self.ti1.loadPal = True
                        if self.ti0.texFormat == "CI8":
                            self.ti1.palIndex = 15
                            self.ti1.palAddr = 240
                        else:
                            self.ti0.palIndex = 15
                            self.ti0.palAddr = 240
                    else:
                        # CI4 indices in palette 0, CI8 indices start from palette 0
                        self.ti0.loadPal = True
                        self.ti0.pal = mergePalettes(ci4Pal, ci8Pal)
                        self.ti0.palLen = len(self.ti0.pal)
                        if self.ti0.palLen > 256:
                            raise PluginError(
                                "In material "
                                + material.name
                                + ": the two CI textures together contain a total of "
                                + str(self.ti0.palLen)
                                + " colors, which can't fit in a CI8 palette (256)."
                                + " The CI8 texture must contain up to 240 unique colors,"
                                + " plus the same up to 16 colors used in the CI4 texture."
                            )
                        # The use for the CI4 texture remains what it was; its CIs are the
                        # same as if it was alone. But both the palette and the CI8 CIs are affected.
                        self.ti0.palDependencies = self.ti0.imDependencies + self.ti1.imDependencies
                        if self.ti0.texFormat == "CI8":
                            self.ti0.imDependencies = self.ti0.palDependencies
                        else:
                            self.ti1.imDependencies = self.ti0.palDependencies
                else:  # both CI4 textures
                    if (
                        self.ti0.pal is None
                        and self.ti1.pal is None
                        and self.ti0.texProp.pal_reference == self.ti1.texProp.pal_reference
                    ):
                        self.ti0.loadPal = True
                    elif self.ti0.pal is None or self.ti1.pal is None:
                        self.ti0.loadPal = self.ti1.loadPal = True
                        self.ti1.palIndex = 1
                        self.ti1.palAddr = 16
                    else:
                        self.ti0.loadPal = True
                        tempPal = mergePalettes(self.ti0.pal, self.ti1.pal)
                        tempPalLen = len(tempPal)
                        assert tempPalLen <= 32
                        if tempPalLen <= 16:
                            # Share palette 0
                            self.ti0.pal = tempPal
                            self.ti0.palLen = tempPalLen
                            # self.ti0.imDependencies remains what it was; the CIs in im0 are the same as they
                            # would be if im0 was alone. But im1 and self.ti0.pal depend on both.
                            self.ti1.imDependencies = self.ti0.palDependencies = (
                                self.ti0.imDependencies + self.ti1.imDependencies
                            )
                        else:
                            # Load one palette across 0-1. Put the longer in slot 0
                            if self.ti0.palLen >= self.ti1.palLen:
                                while len(self.ti0.pal) < 16:
                                    self.ti0.pal.append(0)
                                self.ti0.pal.extend(self.ti1.pal)
                                self.ti0.palLen = len(self.ti0.pal)
                                self.ti1.palIndex = 1
                            else:
                                while len(self.ti1.pal) < 16:
                                    self.ti1.pal.append(0)
                                self.ti0.pal = self.ti1.pal + self.ti0.pal
                                self.ti0.palLen = len(self.ti0.pal)
                                self.ti0.palIndex = 1
                            # The up-to-32 entries in self.ti0.pal depend on both images. But the
                            # CIs in both im0 and im1 are the same as if there was no shared palette.
                            self.ti0.palDependencies = self.ti0.imDependencies + self.ti1.imDependencies
        fMaterial.texPaletteIndex = [self.ti0.palIndex, self.ti1.palIndex]
        self.ti0.palBaseName = self.ti0.getPaletteName()
        self.ti1.palBaseName = self.ti1.getPaletteName()
        if self.isCI and self.ti0.useTex and self.ti1.useTex and not self.ti1.loadPal:
            self.ti0.palBaseName = self.ti0.palBaseName + "_x_" + self.ti1.palBaseName
            self.ti1.pal = self.ti0.pal

        # Assign TMEM addresses
        sameTextures = (
            self.ti0.useTex
            and self.ti1.useTex
            and (
                (not self.ti0.isTexRef and not self.ti1.isTexRef and self.ti0.texProp.tex == self.ti1.texProp.tex)
                or (
                    self.ti0.isTexRef
                    and self.ti1.isTexRef
                    and self.ti0.texProp.tex_reference == self.ti1.texProp.tex_reference
                )
            )
        )
        useLargeTextures = material.mat_ver > 3 and f3dMat.use_large_textures
        tmemSize = 256 if self.isCI else 512
        self.ti1.texAddr = None  # must be set whenever tex 1 used (and loaded or tiled)
        tmemOccupied = self.texDimensions = None  # must be set on all codepaths
        if sameTextures:
            assert self.ti0.tmemSize == self.ti1.tmemSize
            tmemOccupied = self.ti0.tmemSize
            self.ti1.doTexLoad = False
            self.ti1.texAddr = 0
            self.texDimensions = self.ti0.imageDims
            fMaterial.largeTexFmt = self.ti0.texFormat
        elif not useLargeTextures or self.ti0.tmemSize + self.ti1.tmemSize <= tmemSize:
            self.ti1.texAddr = self.ti0.tmemSize
            tmemOccupied = self.ti0.tmemSize + self.ti1.tmemSize
            if not self.ti0.useTex and not self.ti1.useTex:
                self.texDimensions = [32, 32]
                fMaterial.largeTexFmt = "RGBA16"
            elif not self.ti1.useTex or f3dMat.uv_basis == "TEXEL0":
                self.texDimensions = self.ti0.imageDims
                fMaterial.largeTexFmt = self.ti0.texFormat
            else:
                self.texDimensions = self.ti1.imageDims
                fMaterial.largeTexFmt = self.ti1.texFormat
        else:  # useLargeTextures
            if self.ti0.useTex and self.ti1.useTex:
                tmemOccupied = tmemSize
                # TODO: Could change this in the future to do the face tile assigments
                # first, to see how large a tile the large texture(s) needed, instead
                # of arbitrarily assigning half of TMEM to each of the two textures.
                if self.ti0.tmemSize <= tmemSize // 2:
                    # Tex 0 normal, tex 1 large
                    self.texDimensions = self.ti1.imageDims
                    fMaterial.largeTexFmt = self.ti1.texFormat
                    fMaterial.isTexLarge[1] = True
                    fMaterial.largeTexAddr[1] = self.ti0.tmemSize
                    fMaterial.largeTexWords = tmemSize - self.ti0.tmemSize
                    self.ti1.doTexLoad = self.ti1.doTexTile = False
                elif self.ti1.tmemSize <= tmemSize // 2:
                    # Tex 0 large, tex 1 normal
                    self.texDimensions = self.ti0.imageDims
                    fMaterial.largeTexFmt = self.ti0.texFormat
                    fMaterial.isTexLarge[0] = True
                    fMaterial.largeTexAddr[0] = 0
                    fMaterial.largeTexWords = tmemSize - self.ti1.tmemSize
                    self.ti0.doTexLoad = self.ti0.doTexTile = False
                    self.ti1.texAddr = tmemSize - self.ti1.tmemSize
                else:
                    # Both textures large
                    raise PluginError(
                        'Error in "'
                        + material.name
                        + '": Multitexture with two large textures is not currently supported.'
                    )
                    # Limited cases of 2x large textures could be supported in the
                    # future. However, these cases are either of questionable
                    # utility or have substantial restrictions. Most cases could be
                    # premixed into one texture, or would run out of UV space for
                    # tiling (1024x1024 in the space of whichever texture had
                    # smaller pixels), or one of the textures could be non-large.
                    if f3dMat.uv_basis == "TEXEL0":
                        self.texDimensions = self.ti0.imageDims
                        fMaterial.largeTexFmt = self.ti0.texFormat
                    else:
                        self.texDimensions = self.ti1.imageDims
                        fMaterial.largeTexFmt = self.ti1.texFormat
                    fMaterial.isTexLarge[0] = True
                    fMaterial.isTexLarge[1] = True
                    fMaterial.largeTexAddr[0] = 0
                    fMaterial.largeTexAddr[1] = tmemSize // 2
                    fMaterial.largeTexWords = tmemSize // 2
                    self.ti0.doTexLoad = self.ti0.doTexTile = self.ti1.doTexLoad = self.ti1.doTexTile = False
            elif self.ti0.useTex:
                self.texDimensions = self.ti0.imageDims
                fMaterial.largeTexFmt = self.ti0.texFormat
                fMaterial.isTexLarge[0] = True
                fMaterial.largeTexAddr[0] = 0
                fMaterial.largeTexWords = tmemSize
                self.ti0.doTexLoad = self.ti0.doTexTile = False
                tmemOccupied = tmemSize
            elif self.ti1.useTex:
                self.ti1.texAddr = 0
                self.texDimensions = self.ti1.imageDims
                fMaterial.largeTexFmt = self.ti1.texFormat
                fMaterial.isTexLarge[1] = True
                fMaterial.largeTexAddr[1] = 0
                fMaterial.largeTexWords = tmemSize
                self.ti1.doTexLoad = self.ti1.doTexTile = False
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

        self.ti0.writeAll(fMaterial, fModel, convertTextureData)
        self.ti1.writeAll(fMaterial, fModel, convertTextureData)

    def getTexDimensions(self):
        return self.texDimensions


# Functions for writing texture and palette DLs


def getTileSizeSettings(texProp: TextureProperty, tileSettings: Optional[TileLoad], f3d: F3D):
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


def canUseLoadBlock(fImage: FImage, tex_format: str, f3d: F3D):
    if fImage.isLargeTexture:
        return False
    width, height = fImage.width, fImage.height
    texelsPerWord = 64 // texBitSizeInt[tex_format]
    if width % texelsPerWord != 0:
        return False
    wordsperrow = width // texelsPerWord
    dxt = ((1 << f3d.G_TX_DXT_FRAC) + wordsperrow - 1) // wordsperrow
    error = (dxt * wordsperrow) - (1 << f3d.G_TX_DXT_FRAC)
    assert error >= 0
    if error == 0:
        return True
    rowsWhenCorruptionHappens = (dxt + error - 1) // error
    return height < rowsWhenCorruptionHappens


def saveTextureLoadOnly(
    fImage: FImage,
    gfxOut: GfxList,
    texProp: TextureProperty,
    tileSettings: Optional[TileLoad],
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
    useLoadBlock = canUseLoadBlock(fImage, texProp.tex_format, f3d)
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

    scrollInfo = getattr(fMaterial.scrollData, f"tile_scroll_tex{rendertile}")
    if scrollInfo.s or scrollInfo.t:
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
        raise PluginError("Internal error, writeNonCITextureData called for CI image.")

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
