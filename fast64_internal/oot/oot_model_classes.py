import bpy, os, re, mathutils
from typing import Union
from ..f3d.f3d_parser import F3DContext, F3DTextureReference, getImportData
from ..f3d.f3d_material import TextureProperty, createF3DMat
from ..utility import PluginError, CData, hexOrDecInt
from ..f3d.flipbook import TextureFlipbook, FlipbookProperty, usesFlipbook, ootFlipbookReferenceIsValid

from ..f3d.f3d_writer import (
    VertexGroupInfo,
    TriangleConverterInfo,
    FSharedPalette,
    DPLoadTLUTCmd,
    DPSetTextureLUT,
    DPSetTile,
    FImageKey,
    saveOrGetTextureDefinition,
    saveOrGetPaletteAndImageDefinition,
    getTextureNameTexRef,
    saveOrGetPaletteOnlyDefinition,
    texFormatOf,
)

from ..f3d.f3d_gbi import (
    FModel,
    FMaterial,
    FImage,
    GfxMatWriteMethod,
    SPDisplayList,
    GfxList,
    GfxListTag,
    DLFormat,
    SPMatrix,
    GfxFormatter,
    MTX_SIZE,
)


# read included asset data
def ootGetIncludedAssetData(basePath: str, currentPaths: list[str], data: str) -> str:
    includeData = ""
    searchedPaths = currentPaths[:]

    print("Included paths:")

    # search assets
    for includeMatch in re.finditer(r"\#include\s*\"(assets/objects/(.*?))\.h\"", data):
        path = os.path.join(basePath, includeMatch.group(1) + ".c")
        if path in searchedPaths:
            continue
        searchedPaths.append(path)
        subIncludeData = getImportData([path]) + "\n"
        includeData += subIncludeData
        print(path)

        for subIncludeMatch in re.finditer(r"\#include\s*\"(((?![/\"]).)*)\.c\"", subIncludeData):
            subPath = os.path.join(os.path.dirname(path), subIncludeMatch.group(1) + ".c")
            if subPath in searchedPaths:
                continue
            searchedPaths.append(subPath)
            print(subPath)
            includeData += getImportData([subPath]) + "\n"

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


class OOTModel(FModel):
    def __init__(self, f3dType, isHWv1, name, DLFormat, drawLayerOverride):
        self.drawLayerOverride = drawLayerOverride
        self.flipbooks: list[TextureFlipbook] = []

        # key: first flipbook image
        # value: list of flipbook textures in order
        self.processedFlipbooks: dict[bpy.types.Image, list[bpy.types.Image]] = {}
        FModel.__init__(self, f3dType, isHWv1, name, DLFormat, GfxMatWriteMethod.WriteAll)

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
        defaultRenderModes = bpy.context.scene.world.ootDefaultRenderModes
        cycle1 = getattr(defaultRenderModes, drawLayerUsed.lower() + "Cycle1")
        cycle2 = getattr(defaultRenderModes, drawLayerUsed.lower() + "Cycle2")
        return [cycle1, cycle2]

    def getTextureSuffixFromFormat(self, texFmt):
        if texFmt == "RGBA16":
            return "rgb5a1"
        else:
            return texFmt.lower()

    def addFlipbookWithRepeatCheck(self, flipbook: TextureFlipbook):
        model = self.getFlipbookOwner()
        for existingFlipbook in model.flipbooks:
            if existingFlipbook.name == flipbook.name:
                if len(existingFlipbook.textureNames) != len(flipbook.textureNames):
                    raise PluginError(
                        f"There are two flipbooks with differing elements trying to write to the same texture array name: {flipbook.name}."
                        + f"\nMake sure that this flipbook name is unique, or that repeated uses of this name use the same textures is the same order/format."
                    )
                for i in range(len(flipbook.textureNames)):
                    if existingFlipbook.textureNames[i] != flipbook.textureNames[i]:
                        raise PluginError(
                            f"There are two flipbooks with differing elements trying to write to the same texture array name: {flipbook.name}."
                            + f"\nMake sure that this flipbook name is unique, or that repeated uses of this name use the same textures is the same order/format."
                        )
        model.flipbooks.append(flipbook)

    def validateCIFlipbook(
        self, existingFPalette: FImage, alreadyExists: bool, fPalette: FImage, flipbookImage: bpy.types.Image
    ) -> Union[FImage, bool]:
        if existingFPalette is None:
            if alreadyExists:
                if fPalette:
                    return fPalette
                else:
                    raise PluginError("FPalette not found.")
            else:
                return False
        else:
            if (
                alreadyExists  # texture already processed for this export
                and fPalette is not None  # texture is not a repeat within flipbook
                and existingFPalette != False  # a previous texture used an existing palette
                and fPalette != existingFPalette  # the palettes do not match
            ):
                raise PluginError(
                    f"Cannot reuse a CI texture across multiple flipbooks: {str(flipbookImage)}. "
                    + f"Flipbook textures should only be reused if they are in the same grouping/order, including LOD skeletons."
                )
            elif (
                not alreadyExists  # current texture has not been processed yet
                and existingFPalette is not None
                and existingFPalette != False  # a previous texture used an existing palette
            ):
                raise PluginError(
                    f"Flipbook textures before this were part of a different palette: {str(flipbookImage)}. "
                    + f"Flipbook textures should only be reused if they are in the same grouping/order, including LOD skeletons."
                )
            return existingFPalette

    def processTexRefCITextures(self, fMaterial: FMaterial, material: bpy.types.Material, index: int) -> FImage:
        # print("Processing flipbook...")
        model = self.getFlipbookOwner()
        flipbookProp = getattr(material.flipbookGroup, f"flipbook{index}")
        texProp = getattr(material.f3d_mat, f"tex{index}")
        if not usesFlipbook(material, flipbookProp, index, True, ootFlipbookReferenceIsValid):
            return FModel.processTexRefCITextures(fMaterial, material, index)

        if len(flipbookProp.textures) == 0:
            raise PluginError(f"{str(material)} cannot have a flipbook material with no flipbook textures.")
        flipbook = TextureFlipbook(flipbookProp.name, flipbookProp.exportMode, [])
        sharedPalette = FSharedPalette(model.name + "_" + flipbookProp.textures[0].image.name + "_pal")
        existingFPalette = None
        fImages = []
        for flipbookTexture in flipbookProp.textures:
            if flipbookTexture.image is None:
                raise PluginError(f"Flipbook for {fMaterial.name} has a texture array item that has not been set.")
            # print(f"Texture: {str(flipbookTexture.image)}")
            name = (
                flipbookTexture.name
                if flipbookProp.exportMode == "Individual"
                else model.name + "_" + flipbookTexture.image.name + "_" + texProp.tex_format.lower()
            )

            texName = getTextureNameTexRef(texProp, model.name)
            # fPalette should be None here, since sharedPalette is not None
            fImage, fPalette, alreadyExists = saveOrGetPaletteAndImageDefinition(
                fMaterial,
                model,
                flipbookTexture.image,
                name,
                texProp.tex_format,
                texProp.ci_format,
                True,
                sharedPalette,
                FImageKey(
                    flipbookTexture.image,
                    texProp.tex_format,
                    texProp.ci_format,
                    [flipbookTexture.image for flipbookTexture in flipbookProp.textures],
                ),
            )
            existingFPalette = model.validateCIFlipbook(
                existingFPalette, alreadyExists, fPalette, flipbookTexture.image
            )
            fImages.append(fImage)

            # do this here to check for modified names due to repeats
            flipbook.textureNames.append(fImage.name)

        model.addFlipbookWithRepeatCheck(flipbook)

        # print(f"Palette length for {sharedPalette.name}: {len(sharedPalette.palette)}")
        firstImage = flipbookProp.textures[0].image
        model.processedFlipbooks[firstImage] = [flipbookTex.image for flipbookTex in flipbookProp.textures]

        if existingFPalette == False:

            palFormat = texProp.ci_format
            fPalette, paletteKey = saveOrGetPaletteOnlyDefinition(
                fMaterial,
                model,
                [tex.image for tex in flipbookProp.textures],
                sharedPalette.name,
                texProp.tex_format,
                palFormat,
                True,
                sharedPalette.palette,
            )

            # using the first image for the key, apply paletteKey to all images
            # while this is not ideal, its better to us an image for the key as
            # names are modified when duplicates are found
            for fImage in fImages:
                fImage.paletteKey = paletteKey
        else:
            fPalette = existingFPalette

        return fPalette

    def processTexRefNonCITextures(self, fMaterial: FMaterial, material: bpy.types.Material, index: int):
        model = self.getFlipbookOwner()
        flipbookProp = getattr(material.flipbookGroup, f"flipbook{index}")
        texProp = getattr(material.f3d_mat, f"tex{index}")
        if not usesFlipbook(material, flipbookProp, index, True, ootFlipbookReferenceIsValid):
            return FModel.processTexRefNonCITextures(self, fMaterial, material, index)
        if len(flipbookProp.textures) == 0:
            raise PluginError(f"{str(material)} cannot have a flipbook material with no flipbook textures.")

        flipbook = TextureFlipbook(flipbookProp.name, flipbookProp.exportMode, [])
        for flipbookTexture in flipbookProp.textures:
            if flipbookTexture.image is None:
                raise PluginError(f"Flipbook for {fMaterial.name} has a texture array item that has not been set.")
            # print(f"Texture: {str(flipbookTexture.image)}")
            name = (
                flipbookTexture.name
                if flipbookProp.exportMode == "Individual"
                else model.name + "_" + flipbookTexture.image.name + "_" + texProp.tex_format.lower()
            )
            fImage = saveOrGetTextureDefinition(
                fMaterial,
                model,
                flipbookTexture.image,
                name,
                texProp.tex_format,
                True,
            )

            # do this here to check for modified names due to repeats
            flipbook.textureNames.append(fImage.name)
        self.addFlipbookWithRepeatCheck(flipbook)

    def onMaterialCommandsBuilt(self, fMaterial, material, drawLayer):
        # handle dynamic material calls
        gfxList = fMaterial.material
        matDrawLayer = getattr(material.ootMaterial, drawLayer.lower())
        for i in range(8, 14):
            if getattr(matDrawLayer, "segment" + format(i, "X")):
                gfxList.commands.append(
                    SPDisplayList(GfxList("0x" + format(i, "X") + "000000", GfxListTag.Material, DLFormat.Static))
                )
        for i in range(0, 2):
            p = "customCall" + str(i)
            if getattr(matDrawLayer, p):
                gfxList.commands.append(
                    SPDisplayList(GfxList(getattr(matDrawLayer, p + "_seg"), GfxListTag.Material, DLFormat.Static))
                )

    def onAddMesh(self, fMesh, contextObj):
        if contextObj is not None and hasattr(contextObj, "ootDynamicTransform"):
            if contextObj.ootDynamicTransform.billboard:
                fMesh.draw.commands.append(SPMatrix("0x01000000", "G_MTX_MODELVIEW | G_MTX_NOPUSH | G_MTX_MUL"))


class OOTDynamicMaterialDrawLayer:
    def __init__(self, opaque, transparent):
        self.opaque = opaque
        self.transparent = transparent


class OOTGfxFormatter(GfxFormatter):
    def __init__(self, scrollMethod):
        GfxFormatter.__init__(self, scrollMethod, 64)

    # This code is not functional, only used for an example
    def drawToC(self, f3d, gfxList):
        return gfxList.to_c(f3d)

    # This code is not functional, only used for an example
    def tileScrollMaterialToC(self, f3d, fMaterial):
        materialGfx = fMaterial.material
        scrollDataFields = fMaterial.scrollData.fields

        # Set tile scrolling
        for texIndex in range(2):  # for each texture
            for axisIndex in range(2):  # for each axis
                scrollField = scrollDataFields[texIndex][axisIndex]
                if scrollField.animType != "None":
                    if scrollField.animType == "Linear":
                        if axisIndex == 0:
                            fMaterial.tileSizeCommands[texIndex].uls = (
                                str(fMaterial.tileSizeCommands[0].uls) + " + s * " + str(scrollField.speed)
                            )
                        else:
                            fMaterial.tileSizeCommands[texIndex].ult = (
                                str(fMaterial.tileSizeCommands[0].ult) + " + s * " + str(scrollField.speed)
                            )

        # Build commands
        data = CData()
        data.header = "Gfx* " + fMaterial.material.name + "(Gfx* glistp, int s, int t);\n"
        data.source = "Gfx* " + materialGfx.name + "(Gfx* glistp, int s, int t) {\n"
        for command in materialGfx.commands:
            data.source += "\t" + command.to_c(False) + ";\n"
        data.source += "\treturn glistp;\n}" + "\n\n"

        if fMaterial.revert is not None:
            data.append(fMaterial.revert.to_c(f3d))
        return data


class OOTTriangleConverterInfo(TriangleConverterInfo):
    def __init__(self, obj, armature, f3d, transformMatrix, infoDict):
        TriangleConverterInfo.__init__(self, obj, armature, f3d, transformMatrix, infoDict)

    def getMatrixAddrFromGroup(self, groupIndex):
        return format((0x0D << 24) + MTX_SIZE * self.vertexGroupInfo.vertexGroupToMatrixIndex[groupIndex], "#010x")


class OOTVertexGroupInfo(VertexGroupInfo):
    def __init__(self):
        self.vertexGroupToMatrixIndex = {}
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

        materialContext = createF3DMat(None, preset="oot_shaded_solid")
        # materialContext.f3d_mat.rdp_settings.g_mdsft_cycletype = "G_CYC_1CYCLE"
        F3DContext.__init__(self, f3d, basePath, materialContext)

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
        return (material.ootMaterial.key(), material.f3d_mat.key())

    def clearGeometry(self):
        self.dlList = []
        self.isBillboard = False
        super().clearGeometry()

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


def clearOOTFlipbookProperty(flipbookProp):
    flipbookProp.enable = False
    flipbookProp.name = "sFlipbookTextures"
    flipbookProp.exportMode = "Array"
    flipbookProp.textures.clear()


def clearOOTMaterialDrawLayerProperty(matDrawLayerProp):
    for i in range(0x08, 0x0E):
        setattr(matDrawLayerProp, "segment" + format(i, "X"), False)


class OOTDynamicTransformProperty(bpy.types.PropertyGroup):
    billboard: bpy.props.BoolProperty(name="Billboard")
