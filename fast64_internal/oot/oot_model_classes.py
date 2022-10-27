import bpy
from ..f3d.f3d_writer import VertexGroupInfo, TriangleConverterInfo
from ..f3d.f3d_parser import F3DContext
from ..f3d.f3d_material import createF3DMat
from ..utility import CData, hexOrDecInt

from ..f3d.f3d_gbi import (
    FModel,
    GfxMatWriteMethod,
    SPDisplayList,
    GfxList,
    GfxListTag,
    DLFormat,
    SPMatrix,
    GfxFormatter,
    MTX_SIZE,
)


class OOTModel(FModel):
    def __init__(self, f3dType, isHWv1, name, DLFormat, drawLayerOverride):
        self.drawLayerOverride = drawLayerOverride
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

    def onMaterialCommandsBuilt(self, gfxList, revertList, material, drawLayer):
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
            print("POINTER")
            if segment >= 0x08 and segment <= 0x0D:
                print("SETTING " + str(segment))
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
        F3DContext.clearMaterial(self)

    def postMaterialChanged(self):
        clearOOTMaterialDrawLayerProperty(self.materialContext.ootMaterial.opaque)
        clearOOTMaterialDrawLayerProperty(self.materialContext.ootMaterial.transparent)


def clearOOTMaterialDrawLayerProperty(matDrawLayerProp):
    for i in range(0x08, 0x0E):
        setattr(matDrawLayerProp, "segment" + format(i, "X"), False)


class OOTDynamicTransformProperty(bpy.types.PropertyGroup):
    billboard: bpy.props.BoolProperty(name="Billboard")
