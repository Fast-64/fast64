import shutil, copy, bpy, os
from bpy.utils import register_class, unregister_class
from typing import Dict, List, Any

from .oot_utility import *
from .oot_constants import *
from ..f3d.f3d_writer import *
from ..f3d.f3d_material import *
from ..f3d.f3d_parser import *


def usesFlipbook(material: bpy.types.Material, flipbookProperty: Any, index: int) -> bool:
    texProp = getattr(material.f3d_mat, "tex" + str(index))
    # return all_combiner_uses(material)["Texture " + str(index)] and texProp.use_tex_reference and
    if all_combiner_uses(material.f3d_mat)["Texture " + str(index)] and texProp.use_tex_reference:
        match = re.search(f"0x0([0-9A-F])000000", texProp.tex_reference)
        return match is not None
    else:
        return False


# read included asset data
def ootGetIncludedAssetData(basePath: str, data: str) -> str:
    includeData = ""
    for includeMatch in re.finditer(r"\#include\s*\"(assets/objects/(.*?))\"", data):
        includeData += getImportData([os.path.join(basePath, includeMatch.group(1))]) + "\n"
    for includeMatch in re.finditer(r"\#include\s*\"(assets/misc/(.*?))\"", data):
        includeData += getImportData([os.path.join(basePath, includeMatch.group(1))]) + "\n"
    return includeData


# read actor data
def ootGetActorData(basePath: str, overlayName: str) -> str:
    actorFilePath = os.path.join(basePath, f"src/overlays/actors/{overlayName}/z_{overlayName[4:].lower()}.c")
    actorFileDataPath = f"{actorFilePath[:-2]}_data.c"  # some bosses store texture arrays here
    actorData = getImportData([actorFileDataPath, actorFilePath])

    return actorData


def ootGetLinkData(basePath: str) -> str:
    linkFilePath = os.path.join(basePath, f"src/code/z_player_lib.c")
    actorData = getImportData([linkFilePath])

    return actorData


def flipbook_to_c(flipbook, isStatic):
    newArrayData = "void* " if not isStatic else "static void* "
    newArrayData += f"{flipbook.name}[] = {{ "
    for textureName in flipbook.textureNames:
        newArrayData += textureName + ", "
    newArrayData += " };"
    return newArrayData


class OOTModel(FModel):
    def __init__(self, f3dType, isHWv1, name, DLFormat, drawLayerOverride):
        self.drawLayerOverride = drawLayerOverride
        self.flipbooks = []  # OOTTextureFlipbook
        FModel.__init__(self, f3dType, isHWv1, name, DLFormat, GfxMatWriteMethod.WriteAll)

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

        # save flipbook textures
        for i in range(2):
            flipbookProp = getattr(material.ootMaterial, "flipbook" + str(i))
            texProp = getattr(material.f3d_mat, "tex" + str(i))
            if usesFlipbook(material, flipbookProp, i):
                flipbook = OOTTextureFlipbook(flipbookProp.name, flipbookProp.exportMode, [])
                for flipbookTexture in flipbookProp.textures:
                    name = (
                        flipbookTexture.name
                        if flipbookProp.exportMode == "Individual"
                        else self.name + "_" + flipbookTexture.image.name + "_" + texProp.tex_format.lower()
                    )
                    if texProp.tex_format[:2] == "CI":
                        fImage, fPalette = saveOrGetPaletteDefinition(
                            fMaterial, self, flipbookTexture.image, name, texProp.tex_format, texProp.ci_format, True
                        )
                    else:
                        fImage = saveOrGetTextureDefinition(
                            fMaterial,
                            self,
                            flipbookTexture.image,
                            name,
                            texProp.tex_format,
                            True,
                        )
                    newName = fImage.name
                    flipbook.textureNames.append(newName)
                self.flipbooks.append(flipbook)

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


class OOTTextureFlipbook:
    def __init__(self, name: str, exportMode: str, textureNames: List[str]):
        self.name = name
        self.exportMode = exportMode
        self.textureNames = textureNames


class OOTF3DContext(F3DContext):
    def __init__(self, f3d, limbList, basePath):
        self.limbList = limbList
        self.dlList = []  # in the order they are rendered
        self.isBillboard = False
        self.flipbooks = {}  # {(segment, draw layer) : OOTTextureFlipbook}

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
    def setCurrentTransform(self, name):
        if name[:4].lower() == "0x0d":
            self.currentTransformName = self.getLimbName(self.dlList[int(int(name[4:], 16) / MTX_SIZE)].limbIndex)
        else:
            try:
                pointer = hexOrDecInt(name)
            except:
                self.currentTransformName = name
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
            return name
        else:
            segment = pointer >> 24
            if segment >= 0x08 and segment <= 0x0D:
                setattr(self.materialContext.ootMaterial.opaque, "segment" + format(segment, "1X"), True)
                setattr(self.materialContext.ootMaterial.transparent, "segment" + format(segment, "1X"), True)
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

    def clearMaterial(self):
        self.isBillboard = False
        clearOOTMaterialDrawLayerProperty(self.materialContext.ootMaterial.opaque)
        clearOOTMaterialDrawLayerProperty(self.materialContext.ootMaterial.transparent)
        clearOOTFlipbookProperty(self.materialContext.ootMaterial.flipbook0)
        clearOOTFlipbookProperty(self.materialContext.ootMaterial.flipbook1)
        F3DContext.clearMaterial(self)

    def postMaterialChanged(self):
        clearOOTMaterialDrawLayerProperty(self.materialContext.ootMaterial.opaque)
        clearOOTMaterialDrawLayerProperty(self.materialContext.ootMaterial.transparent)

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
        clearOOTFlipbookProperty(getattr(material.ootMaterial, "flipbook" + str(index)))
        match = re.search(f"(0x0[0-9a-fA-F])000000", name)
        if match:
            segment = int(match.group(1), 16)
            flipbookKey = (segment, material.f3d_mat.draw_layer.oot)
            if flipbookKey in self.flipbooks:
                flipbook = self.flipbooks[flipbookKey]

                flipbookProp = getattr(material.ootMaterial, "flipbook" + str(index))
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
                            f'Could not find texture "{textureName}", so it can not be used in a flipbook texture.'
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
        clearOOTFlipbookProperty(getattr(material.ootMaterial, "flipbook" + str(index)))
        super().handleTextureValue(material, image, index)


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
