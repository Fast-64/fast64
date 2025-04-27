from typing import Union, Optional, Callable, Any, TYPE_CHECKING
import bmesh, bpy, mathutils, re, math, traceback
from mathutils import Vector
from bpy.utils import register_class, unregister_class
from .f3d_gbi import *
from .f3d_material import (
    createF3DMat,
    update_preset_manual,
    all_combiner_uses,
    ootEnumDrawLayers,
    TextureProperty,
    F3DMaterialProperty,
    update_node_values_of_material,
    F3DMaterialHash,
)
from .f3d_writer import BufferVertex, F3DVert
from ..utility import *
import ast
from .f3d_material_helpers import F3DMaterial_UpdateLock

if TYPE_CHECKING:
    from .f3d_material import RDPSettings


colorCombinationCommands = [
    0x03,  # load lighting data
    0xB6,  # clear geometry params
    0xB7,  # set geometry params
    0xBB,  # set texture scaling factor
    0xF3,  # set texture size
    0xF5,  # set texture properties
    0xF7,  # set fill color
    0xF8,  # set fog color
    0xFB,  # set env color
    0xFC,  # set color combination
    0xFD,  # load texture
]

drawCommands = [0x04, 0xBF]  # load vertex data  # draw triangle


def getAxisVector(enumValue):
    sign = -1 if enumValue[0] == "-" else 1
    axis = enumValue[0] if sign == 1 else enumValue[1]
    return (sign if axis == "X" else 0, sign if axis == "Y" else 0, sign if axis == "Z" else 0)


def getExportRotation(forwardAxisEnum, convertTransformMatrix):
    if "Z" in forwardAxisEnum:
        print("Z axis reserved for verticals.")
        return None
    elif forwardAxisEnum == "X":
        rightAxisEnum = "-Y"
    elif forwardAxisEnum == "-Y":
        rightAxisEnum = "-X"
    elif forwardAxisEnum == "-X":
        rightAxisEnum = "Y"
    else:
        rightAxisEnum = "X"

    forwardAxis = getAxisVector(forwardAxisEnum)
    rightAxis = getAxisVector(rightAxisEnum)

    upAxis = (0, 0, 1)

    # Z assumed to be up
    columns = [rightAxis, forwardAxis, upAxis]
    localToBlenderRotation = mathutils.Matrix(
        [[col[0] for col in columns], [col[1] for col in columns], [col[2] for col in columns]]
    ).to_quaternion()

    return convertTransformMatrix.to_quaternion() @ localToBlenderRotation


def F3DtoBlenderObject(romfile, startAddress, scene, newname, transformMatrix, segmentData, shadeSmooth):
    mesh = bpy.data.meshes.new(newname + "-mesh")
    obj = bpy.data.objects.new(newname, mesh)
    scene.collection.objects.link(obj)
    createBlankMaterial(obj)

    bMesh = bmesh.new()
    bMesh.from_mesh(mesh)

    parseF3DBinary(romfile, startAddress, scene, bMesh, obj, transformMatrix, newname, segmentData, [None] * 16 * 16)

    # bmesh.ops.rotate(bMesh, cent = [0,0,0],
    # 	matrix = blenderToSM64Rotation,
    # 	verts = bMesh.verts)
    bMesh.to_mesh(mesh)
    bMesh.free()
    mesh.update()

    if shadeSmooth:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.ops.object.shade_smooth()

    return obj


def cmdToPositiveInt(cmd):
    return cmd if cmd >= 0 else 256 + cmd


def parseF3DBinary(romfile, startAddress, scene, bMesh, obj, transformMatrix, groupName, segmentData, vertexBuffer):
    f3d = F3D("F3D")
    currentAddress = startAddress
    romfile.seek(currentAddress)
    command = romfile.read(8)

    faceSeq = bMesh.faces
    vertSeq = bMesh.verts
    uv_layer = bMesh.loops.layers.uv.verify()
    deform_layer = bMesh.verts.layers.deform.verify()
    vertexGroup = getOrMakeVertexGroup(obj, groupName)
    groupIndex = vertexGroup.index

    textureSize = [32, 32]

    currentTextureAddr = -1
    jumps = [startAddress]

    # Used for remove_double op at end
    vertList = []

    while len(jumps) > 0:
        # FD, FC, B7 (tex, shader, geomode)
        # print(format(command[0], '#04x') + ' at ' + hex(currentAddress))
        if command[0] == cmdToPositiveInt(f3d.G_TRI1):
            try:
                newVerts = interpretDrawTriangle(
                    command, vertexBuffer, faceSeq, vertSeq, uv_layer, deform_layer, groupIndex
                )
                vertList.extend(newVerts)
            except TypeError:
                print("Ignoring triangle from unloaded vertices.")

        elif command[0] == cmdToPositiveInt(f3d.G_VTX):
            interpretLoadVertices(romfile, vertexBuffer, transformMatrix, command, segmentData)

        # Note: size can usually be indicated in LoadTile / LoadBlock.
        elif command[0] == cmdToPositiveInt(f3d.G_SETTILESIZE):
            textureSize = interpretSetTileSize(int.from_bytes(command[4:8], "big"))

        elif command[0] == cmdToPositiveInt(f3d.G_DL):
            if command[1] == 0:
                jumps.append(currentAddress)
            currentAddress = decodeSegmentedAddr(command[4:8], segmentData=segmentData)
            romfile.seek(currentAddress)
            command = romfile.read(8)
            continue

        elif command[0] == cmdToPositiveInt(f3d.G_ENDDL):
            currentAddress = jumps.pop()

        elif command[0] == cmdToPositiveInt(f3d.G_SETGEOMETRYMODE):
            pass
        elif command[0] == cmdToPositiveInt(f3d.G_SETCOMBINE):
            pass

        elif command[0] == cmdToPositiveInt(f3d.G_SETTIMG):
            currentTextureAddr = interpretSetTImage(command, segmentData)

        elif command[0] == cmdToPositiveInt(f3d.G_LOADBLOCK):
            # for now only 16bit RGBA is supported.
            interpretLoadBlock(command, romfile, currentTextureAddr, textureSize, "RGBA", 16)

        elif command[0] == cmdToPositiveInt(f3d.G_SETTILE):
            interpretSetTile(int.from_bytes(command[4:8], "big"), None)

        else:
            pass
            # print(format(command[0], '#04x') + ' at ' + hex(currentAddress))

        currentAddress += 8
        romfile.seek(currentAddress)
        command = romfile.read(8)

    bmesh.ops.remove_doubles(bMesh, verts=vertList, dist=0.0001)
    return vertexBuffer


def getPosition(vertexBuffer, index):
    xStart = index * 16 + 0
    yStart = index * 16 + 2
    zStart = index * 16 + 4

    xBytes = vertexBuffer[xStart : xStart + 2]
    yBytes = vertexBuffer[yStart : yStart + 2]
    zBytes = vertexBuffer[zStart : zStart + 2]

    x = int.from_bytes(xBytes, "big", signed=True) / bpy.context.scene.fast64.sm64.blender_to_sm64_scale
    y = int.from_bytes(yBytes, "big", signed=True) / bpy.context.scene.fast64.sm64.blender_to_sm64_scale
    z = int.from_bytes(zBytes, "big", signed=True) / bpy.context.scene.fast64.sm64.blender_to_sm64_scale

    return (x, y, z)


def getNormalorColor(vertexBuffer, index, isNormal=True):
    xByte = bytes([vertexBuffer[index * 16 + 12]])
    yByte = bytes([vertexBuffer[index * 16 + 13]])
    zByte = bytes([vertexBuffer[index * 16 + 14]])
    wByte = bytes([vertexBuffer[index * 16 + 15]])

    if isNormal:
        x = int.from_bytes(xByte, "big", signed=True)
        y = int.from_bytes(yByte, "big", signed=True)
        z = int.from_bytes(zByte, "big", signed=True)
        return (x, y, z)

    else:  # vertex color
        r = int.from_bytes(xByte, "big") / 255
        g = int.from_bytes(yByte, "big") / 255
        b = int.from_bytes(zByte, "big") / 255
        a = int.from_bytes(wByte, "big") / 255
        return (r, g, b, a)


def getUV(vertexBuffer, index, textureDimensions=[32, 32]):
    uStart = index * 16 + 8
    vStart = index * 16 + 10

    uBytes = vertexBuffer[uStart : uStart + 2]
    vBytes = vertexBuffer[vStart : vStart + 2]

    u = int.from_bytes(uBytes, "big", signed=True) / 32
    v = int.from_bytes(vBytes, "big", signed=True) / 32

    # We don't know texture size, so assume 32x32.
    u /= textureDimensions[0]
    v /= textureDimensions[1]
    v = 1 - v

    return (u, v)


def interpretSetTile(data, texture):
    clampMirrorFlags = bitMask(data, 18, 2)


def interpretSetTileSize(data):
    hVal = bitMask(data, 0, 12)
    wVal = bitMask(data, 12, 12)

    height = hVal >> 2 + 1
    width = wVal >> 2 + 1

    return (width, height)


def interpretLoadVertices(romfile, vertexBuffer, transformMatrix, command, segmentData=None):
    command = int.from_bytes(command, "big", signed=True)

    numVerts = bitMask(command, 52, 4) + 1
    startIndex = bitMask(command, 48, 4)
    dataLength = bitMask(command, 32, 16)
    segmentedAddr = bitMask(command, 0, 32)

    dataStartAddr = decodeSegmentedAddr(segmentedAddr.to_bytes(4, "big"), segmentData=segmentData)

    romfile.seek(dataStartAddr)
    data = romfile.read(dataLength)

    for i in range(numVerts):
        vert = Vector(readVectorFromShorts(data, i * 16))
        vert = transformMatrix @ vert
        transformedVert = bytearray(6)
        writeVectorToShorts(transformedVert, 0, vert)

        start = (startIndex + i) * 16
        vertexBuffer[start : start + 6] = transformedVert
        vertexBuffer[start + 6 : start + 16] = data[i * 16 + 6 : i * 16 + 16]


# Note the divided by 0x0A, which is due to the way BF command stores indices.
# Without this the triangles are drawn incorrectly.
def interpretDrawTriangle(command, vertexBuffer, faceSeq, vertSeq, uv_layer, deform_layer, groupIndex):
    verts = [None, None, None]

    index0 = int(command[5] / 0x0A)
    index1 = int(command[6] / 0x0A)
    index2 = int(command[7] / 0x0A)

    vert0 = Vector(getPosition(vertexBuffer, index0))
    vert1 = Vector(getPosition(vertexBuffer, index1))
    vert2 = Vector(getPosition(vertexBuffer, index2))

    verts[0] = vertSeq.new(vert0)
    verts[1] = vertSeq.new(vert1)
    verts[2] = vertSeq.new(vert2)

    tri = faceSeq.new(verts)

    # Assign vertex group
    for vert in tri.verts:
        vert[deform_layer][groupIndex] = 1

    loopIndex = 0
    for loop in tri.loops:
        loop[uv_layer].uv = Vector(getUV(vertexBuffer, int(command[5 + loopIndex] / 0x0A)))
        loopIndex += 1

    return verts


def interpretSetTImage(command, levelData):
    segmentedAddr = command[4:8]
    return decodeSegmentedAddr(segmentedAddr, levelData)


def interpretLoadBlock(command, romfile, textureStart, textureSize, colorFormat, colorDepth):
    numTexels = ((int.from_bytes(command[6:8], "big")) >> 12) + 1

    # This is currently broken.
    # createNewTextureMaterial(romfile, textureStart, textureSize, numTexels, colorFormat, colorDepth, obj)


def printvbuf(vertexBuffer):
    for i in range(0, int(len(vertexBuffer) / 16)):
        print(getPosition(vertexBuffer, i))
        print(getNormalorColor(vertexBuffer, i))
        print(getUV(vertexBuffer, i))


def createBlankMaterial(obj):
    material = createF3DMat(obj)
    update_preset_manual(material, bpy.context)


def createNewTextureMaterial(romfile, textureStart, textureSize, texelCount, colorFormat, colorDepth, obj):
    newMat = bpy.data.materials.new("f3d_material")
    newTex = bpy.data.textures.new("f3d_texture", "IMAGE")
    newImg = bpy.data.images.new("f3d_texture", *textureSize, True, True)

    newTex.image = newImg
    newSlot = newMat.texture_slots.add()
    newSlot.texture = newTex

    obj.data.materials.append(newMat)

    romfile.seek(textureStart)
    texelSize = int(colorDepth / 8)
    dataLength = texelCount * texelSize
    textureData = romfile.read(dataLength)

    if colorDepth != 16:
        print("Warning: Only 16bit RGBA supported, input was " + str(colorDepth) + "bit " + colorFormat)
    else:
        print(str(texelSize) + " " + str(colorDepth))
        for n in range(0, dataLength, texelSize):
            oldPixel = textureData[n : n + texelSize]
            newImg.pixels[n : n + 4] = read16bitRGBA(int.from_bytes(oldPixel, "big"))


def math_eval(s, f3d):
    if isinstance(s, int):
        return s

    s = s.strip()
    node = ast.parse(s, mode="eval")

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        elif isinstance(node, ast.Str):
            return node.s
        elif isinstance(node, ast.Name):
            if hasattr(f3d, node.id):
                return getattr(f3d, node.id)
            else:
                return node.id
        elif isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.USub):
                return -1 * _eval(node.operand)
            elif isinstance(node.op, ast.Invert):
                return ~_eval(node.operand)
            else:
                raise Exception("Unsupported type {}".format(node.op))
        elif isinstance(node, ast.BinOp):
            return binOps[type(node.op)](_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.Call):
            args = list(map(_eval, node.args))
            funcName = _eval(node.func)
            return funcName(*args)
        else:
            raise Exception("Unsupported type {}".format(node))

    return _eval(node.body)


def bytesToNormal(normal):
    return [int.from_bytes([round(value)], "big", signed=True) / 128 if value > 0 else value / 128 for value in normal]


def getTileFormat(value, f3d):
    data = math_eval(value, f3d)
    return ["G_IM_FMT_RGBA", "G_IM_FMT_YUV", "G_IM_FMT_CI", "G_IM_FMT_IA", "G_IM_FMT_I"][data]


def getTileSize(value, f3d):
    data = math_eval(value, f3d)
    return ["G_IM_SIZ_4b", "G_IM_SIZ_8b", "G_IM_SIZ_16b", "G_IM_SIZ_32b", "G_IM_SIZ_32b", "G_IM_SIZ_DD"][data]


def getTileClampMirror(value, f3d):
    data = math_eval(value, f3d)
    return [(data & f3d.G_TX_CLAMP) != 0, (data & f3d.G_TX_MIRROR) != 0]


def getTileMask(value, f3d):
    data = math_eval(value, f3d)
    return data


def getTileShift(value, f3d):
    data = math_eval(value, f3d)
    if data > 10:
        return data - 16
    else:
        return data


def renderModeMask(rendermode, cycle, blendOnly):
    nonBlend = (((1 << 13) - 1) << 3) if not blendOnly else 0
    if cycle == 1:
        return rendermode & (3 << 30 | 3 << 26 | 3 << 22 | 3 << 18 | nonBlend)
    else:
        return rendermode & (3 << 28 | 3 << 24 | 3 << 20 | 3 << 16 | nonBlend)


def convertF3DUV(value, maxSize):
    try:
        valueBytes = int.to_bytes(round(value), 2, "big", signed=True)
    except OverflowError:
        valueBytes = int.to_bytes(round(value), 2, "big", signed=False)

    return ((int.from_bytes(valueBytes, "big", signed=True) / 32) + 0.5) / (maxSize if maxSize > 0 else 1)


class F3DTextureReference:
    def __init__(self, name, width):
        self.name = name
        self.width = width


class F3DParsedCommands:
    def __init__(self, name: str, commands: "list[ParsedMacro]", index: int):
        self.name = name
        self.commands = commands
        self.index = index

    def currentCommand(self):
        return self.commands[self.index]


class F3DContext:
    def __init__(self, f3d: F3D, basePath: str, materialContext: bpy.types.Material):
        self.f3d: F3D = f3d
        self.basePath: str = basePath
        self.materialContext: bpy.types.Material = materialContext
        self.materialContext.f3d_update_flag = True  # Don't want visual updates while parsing
        # If this is not disabled, then tex_scale will auto-update on manual node update.
        self.materialContext.f3d_mat.scale_autoprop = False
        self.draw_layer_prop: str | None = None
        self.initContext()

    # This is separate as we want to call __init__ in clearGeometry, but don't want same behaviour for child classes
    def initContext(self):
        self.vertexBuffer: list[None | BufferVertex] = [None] * self.f3d.vert_load_size
        self.clearMaterial()
        mat: F3DMaterialProperty = self.mat()
        mat.set_combiner = False

        self.materials: list[bpy.types.Material] = []  # current material list
        self.materialDict: dict[F3DMaterialHash, bpy.types.Material] = {}  # cached materials for all imports
        self.triMatIndices: list[int] = []  # material indices per triangle
        self.materialChanged: bool = True  # indicates if the material changed since the last triangle
        self.lastMaterialIndex: bool = None

        self.vertexData: dict[str, list[F3DVert]] = {}  # c name : parsed data
        self.textureData: dict[str, bpy.types.Image] = {}  # c name : blender texture

        self.tlutAppliedTextures: str = []  # c name
        self.currentTextureName: str | None = None
        self.imagesDontApplyTlut: set[bpy.types.Image] = set()  # image

        # Determines if images in CI formats loaded from png files,
        # should have the TLUT set by the dlist applied on top of them (False),
        # or if the image file should just be loaded as is with no further change (True)
        # OoT64 and SM64 stores CI images as pngs in actual colors (with the TLUT accounted for),
        # So for now this can be always True.
        # In the future this could be an option if for example pngs for CI images were grayscale to represent the palette index.
        self.ciImageFilesStoredAsFullColor: bool = True  # determines whether to apply tlut to file or import as is

        # This macro has all the tile setting properties, so we reuse it
        self.tileSettings: list[DPSetTile] = [
            DPSetTile("G_IM_FMT_RGBA", "G_IM_SIZ_16b", 5, 0, i, 0, [False, False], 0, 0, [False, False], 0, 0)
            for i in range(8)
        ]
        self.tileSizes: list[DPSetTileSize] = [DPSetTileSize(i, 0, 0, 32, 32) for i in range(8)]

        # When a tile is loaded, store dict of tmem : texture name
        self.tmemDict: dict[int, str] = {}

        # This should be modified before parsing f3d
        self.matrixData: dict[str, mathutils.Matrix] = {}  # bone name : matrix
        self.currentTransformName: str | None = None
        self.limbToBoneName: dict[str, str] = {}  # limb name (c variable) : bone name (blender vertex group)

        # data for Mesh.from_pydata, list of BufferVertex tuples
        # use BufferVertex to also form uvs / normals / colors
        self.verts: list[F3DVert] = []
        self.limbGroups: dict[str, list[int]] = {}  # dict of groupName : vertex indices

        self.lights: Lights = Lights("lights_context", self.f3d)

        # Here these are ints, but when parsing the values will be normalized.
        self.lights.l = [
            Light([0, 0, 0], [0x49, 0x49, 0x49]),
            Light([0, 0, 0], [0x49, 0x49, 0x49]),
            Light([0, 0, 0], [0x49, 0x49, 0x49]),
            Light([0, 0, 0], [0x49, 0x49, 0x49]),
            Light([0, 0, 0], [0x49, 0x49, 0x49]),
            Light([0, 0, 0], [0x49, 0x49, 0x49]),
            Light([0, 0, 0], [0x49, 0x49, 0x49]),
        ]
        self.lights.a = Ambient([0, 0, 0])
        self.numLights: int = 0
        self.lightData: dict[Light, bpy.types.Object] = {}  # Light : blender light object

    """
    Restarts context, but keeps cached materials/textures.
    Warning: calls initContext, make sure to save/restore preserved fields
    """

    def clearGeometry(self):
        savedMaterialDict = self.materialDict
        savedTextureData = self.textureData
        savedTlutAppliedTextures = self.tlutAppliedTextures
        savedImagesDontApplyTlut = self.imagesDontApplyTlut
        savedLightData = self.lightData
        savedMatrixData = self.matrixData
        savedLimbToBoneName = self.limbToBoneName

        self.initContext()

        self.materialDict = savedMaterialDict
        self.textureData = savedTextureData
        self.tlutAppliedTextures = savedTlutAppliedTextures
        self.imagesDontApplyTlut = savedImagesDontApplyTlut
        self.lightData = savedLightData
        self.matrixData = savedMatrixData
        self.limbToBoneName = savedLimbToBoneName

    def clearMaterial(self):
        mat = self.mat()

        mat.set_prim = False
        mat.set_lights = False
        mat.set_env = False
        mat.set_blend = False
        mat.set_key = False
        mat.set_k0_5 = False

        for i in range(1, 8):
            setattr(mat, "f3d_light" + str(i), None)
        mat.tex0.tex = None
        mat.tex1.tex = None
        mat.tex0.tex_set = False
        mat.tex1.tex_set = False
        mat.tex0.autoprop = False
        mat.tex1.autoprop = False

        mat.tex0.tex_format = "RGBA16"
        mat.tex1.tex_format = "RGBA16"

        self.tmemDict = {}

        self.tileSettings = [
            DPSetTile("G_IM_FMT_RGBA", "G_IM_SIZ_16b", 5, 0, i, 0, [False, False], 0, 0, [False, False], 0, 0)
            for i in range(8)
        ]

        self.tileSizes = [DPSetTileSize(i, 0, 0, 32, 32) for i in range(8)]

        self.lights = Lights("lights_context", self.f3d)
        self.lights.l = [
            Light([0, 0, 0], [0x49, 0x49, 0x49]),
            Light([0, 0, 0], [0x49, 0x49, 0x49]),
            Light([0, 0, 0], [0x49, 0x49, 0x49]),
            Light([0, 0, 0], [0x49, 0x49, 0x49]),
            Light([0, 0, 0], [0x49, 0x49, 0x49]),
            Light([0, 0, 0], [0x49, 0x49, 0x49]),
            Light([0, 0, 0], [0x49, 0x49, 0x49]),
        ]
        self.lights.a = Ambient([0, 0, 0])
        self.numLights = 0

        mat.presetName = "Custom"

    def mat(self) -> F3DMaterialProperty:
        return self.materialContext.f3d_mat

    def vertexFormatPatterns(self, data):
        # position, uv, color/normal
        return [
            # decomp format
            "\{\s*\{\s*"
            + "\{([^,\}]*),([^,\}]*),([^,\}]*)\}\s*,"
            + "([^,\}]*),\s*"
            + "\{([^,\}]*),([^,\}]*)\}\s*,\s*"
            + "\{([^,\}]*),([^,\}]*),([^,\}]*),([^,\}]*)\}\s*"
            + "\}\s*\}",
            # nusys format
            "\{\s*"
            + "([^,\}]*),([^,\}]*),([^,\}]*),"
            + "([^,\}]*),"
            + "([^,\}]*),([^,\}]*),"
            + "([^,\}]*),([^,\}]*),([^,\}]*),([^,\}]*)\s*"
            + "\}",
        ]

    def addMatrix(self, name, matrix):
        self.matrixData[name] = matrix
        self.limbToBoneName[name] = name

    # For game specific instance, override this to be able to identify which verts belong to which bone.
    def setCurrentTransform(self, name, flagList="G_MTX_NOPUSH | G_MTX_LOAD | G_MTX_MODELVIEW"):
        flags = [value.strip() for value in flagList.split("|")]
        if "G_MTX_MUL" in flags:
            tempName = name + "_x_" + str(self.currentTransformName)
            self.addMatrix(tempName, self.matrixData[name] @ self.matrixData[self.currentTransformName])
            self.limbToBoneName[tempName] = tempName
            self.currentTransformName = tempName
        else:
            self.currentTransformName = name

    def getTransformedVertex(self, index: int):
        bufferVert = self.vertexBuffer[index]

        # NOTE: The groupIndex here does NOT correspond to a vertex group, but to the name of the limb (c variable)
        matrixName = bufferVert.groupIndex
        if matrixName in self.matrixData:
            transform = self.matrixData[matrixName]
        else:
            print(self.matrixData)
            raise PluginError("Transform matrix not specified for " + matrixName)

        mat = self.mat()
        f3dVert = bufferVert.f3dVert
        position = transform @ Vector(f3dVert.position)
        if mat.tex0.tex is not None:
            texDimensions = mat.tex0.tex.size
        elif mat.tex0.use_tex_reference:
            texDimensions = mat.tex0.tex_reference_size
        elif mat.tex1.tex is not None:
            texDimensions = mat.tex1.tex.size
        elif mat.tex1.use_tex_reference:
            texDimensions = mat.tex1.tex_reference_size
        else:
            texDimensions = [32, 32]

        uv = [convertF3DUV(f3dVert.uv[i], texDimensions[i]) for i in range(2)]
        uv[1] = 1 - uv[1]

        has_rgb, has_normal, has_packed_normals = getRgbNormalSettings(self.mat())
        rgb = Vector([v / 0xFF for v in f3dVert.rgb]) if has_rgb else Vector([1.0, 1.0, 1.0])
        alpha = f3dVert.alpha / 0xFF
        normal = Vector([0.0, 0.0, 0.0])  # Zero normal makes normals_split_custom_set use auto
        if has_normal:
            if has_packed_normals:
                normal = f3dVert.normal
            else:
                normal = Vector([v - 0x100 if v >= 0x80 else v for v in f3dVert.rgb]).normalized()
            normal = (transform.inverted().transposed() @ normal).normalized()

        # NOTE: The groupIndex here does NOT correspond to a vertex group, but to the name of the limb (c variable)
        return BufferVertex(F3DVert(position, uv, rgb, normal, alpha), bufferVert.groupIndex, bufferVert.materialIndex)

    def addVertices(self, num, start, vertexDataName, vertexDataOffset):
        vertexData = self.vertexData[vertexDataName]

        # TODO: material index not important?
        count = math_eval(num, self.f3d)
        start = math_eval(start, self.f3d)

        if start + count > len(self.vertexBuffer):
            raise PluginError(
                "Vertex buffer of size "
                + str(len(self.vertexBuffer))
                + " too small, attempting load into "
                + str(start)
                + ", "
                + str(start + count)
            )
        if vertexDataOffset + count > len(vertexData):
            raise PluginError(
                f"Attempted to read vertex data out of bounds.\n"
                f"{vertexDataName} is of size {len(vertexData)}, "
                f"attemped read from ({vertexDataOffset}, {vertexDataOffset + count})"
            )
        for i in range(count):
            self.vertexBuffer[start + i] = BufferVertex(vertexData[vertexDataOffset + i], self.currentTransformName, 0)

    def addTriangle(self, indices, dlData):
        if self.materialChanged:
            region = None

            tileSettings = self.tileSettings[0]
            tileSizeSettings = self.tileSizes[0]
            if tileSettings.tmem in self.tmemDict:
                textureName = self.tmemDict[tileSettings.tmem]
                self.loadTexture(dlData, textureName, region, tileSettings, False)
                self.applyTileToMaterial(0, tileSettings, tileSizeSettings, dlData)

            tileSettings = self.tileSettings[1]
            tileSizeSettings = self.tileSizes[1]
            if tileSettings.tmem in self.tmemDict:
                textureName = self.tmemDict[tileSettings.tmem]
                self.loadTexture(dlData, textureName, region, tileSettings, False)
                self.applyTileToMaterial(1, tileSettings, tileSizeSettings, dlData)

            self.applyLights()

            self.lastMaterialIndex = self.getMaterialIndex()
            self.materialChanged = False

        verts = [self.getTransformedVertex(math_eval(index, self.f3d)) for index in indices]
        # if verts[0].groupIndex != verts[1].groupIndex or\
        # 	verts[0].groupIndex != verts[2].groupIndex or\
        # 	verts[2].groupIndex != verts[1].groupIndex:
        # 	return
        for i in range(len(verts)):
            vert = verts[i]

            # NOTE: The groupIndex here does NOT correspond to a vertex group, but to the name of the limb (c variable)
            if vert.groupIndex not in self.limbGroups:
                self.limbGroups[vert.groupIndex] = []
            self.limbGroups[vert.groupIndex].append(len(self.verts) + i)
        self.verts.extend([vert.f3dVert for vert in verts])

        for i in range(int(len(indices) / 3)):
            self.triMatIndices.append(self.lastMaterialIndex)

    # Add items to this tuple in child classes
    def getMaterialKey(self, material: bpy.types.Material):
        return material.f3d_mat.key()

    def getMaterialIndex(self):
        key = self.getMaterialKey(self.materialContext)
        if key in self.materialDict:
            material = self.materialDict[key]
            if material in self.materials:
                return self.materials.index(material)
            else:
                self.materials.append(material)
                return len(self.materials) - 1

        self.addMaterial()
        return len(self.materials) - 1

    def getImageName(self, image):
        for name, otherImage in self.textureData.items():
            if image == otherImage:
                return name
        return None

    # override this to handle applying tlut to other texture
    # ex. in oot, apply to flipbook textures
    def handleApplyTLUT(
        self,
        material: bpy.types.Material,
        texProp: TextureProperty,
        tlut: bpy.types.Image,
        index: int,
    ):
        self.applyTLUT(texProp.tex, tlut)
        self.tlutAppliedTextures.append(texProp.tex)

    # we only want to apply tlut to an existing image under specific conditions.
    # however we always want to record the changing tlut for texture references.
    def applyTLUTToIndex(self, index):
        mat = self.mat()
        texProp = getattr(mat, "tex" + str(index))
        combinerUses = all_combiner_uses(mat)

        if texProp.tex_format[:2] == "CI":
            # Only handles TLUT at 256
            tlutName = self.tmemDict[256]
            if 256 in self.tmemDict and tlutName is not None:
                tlut = self.textureData[tlutName]
                # print(f"TLUT: {tlutName}, {isinstance(tlut, F3DTextureReference)}")
                if isinstance(tlut, F3DTextureReference) or texProp.use_tex_reference:
                    if not texProp.use_tex_reference:
                        texProp.use_tex_reference = True
                        imageName = self.getImageName(texProp.tex)
                        if imageName is not None:
                            texProp.tex_reference = imageName
                        else:
                            print("Cannot find name of texture " + str(texProp.tex))

                    if isinstance(tlut, F3DTextureReference):
                        texProp.pal_reference = tlut.name
                        texProp.pal_reference_size = tlut.width
                    else:
                        texProp.pal_reference = tlutName
                        texProp.pal_reference_size = min(tlut.size[0] * tlut.size[1], 256)

                if (
                    not isinstance(tlut, F3DTextureReference)
                    and combinerUses["Texture " + str(index)]
                    and (texProp.tex is not None)
                    and texProp.tex_set
                    and (texProp.tex not in self.tlutAppliedTextures or texProp.use_tex_reference)
                    and (
                        texProp.tex not in self.imagesDontApplyTlut or not self.ciImageFilesStoredAsFullColor
                    )  # oot currently stores CI textures in full color pngs
                ):
                    # print(f"Apply tlut {tlutName} ({str(tlut)}) to {self.getImageName(texProp.tex)}")
                    # print(f"Size: {str(tlut.size[0])} x {str(tlut.size[1])}, Data: {str(len(tlut.pixels))}")
                    self.handleApplyTLUT(self.materialContext, texProp, tlut, index)
            else:
                print("Ignoring TLUT.")

    def addMaterial(self):
        self.applyTLUTToIndex(0)
        self.applyTLUTToIndex(1)

        materialCopy = self.materialContext.copy()

        # disable flag so that we can lock it, then unlock after update
        materialCopy.f3d_update_flag = False

        with F3DMaterial_UpdateLock(materialCopy) as material:
            assert material is not None
            update_node_values_of_material(material, bpy.context)
            material.f3d_mat.presetName = "Custom"

        self.materials.append(materialCopy)
        self.materialDict[self.getMaterialKey(materialCopy)] = materialCopy

    def getSizeMacro(self, size: str, suffix: str):
        if hasattr(self.f3d, size):
            return getattr(self.f3d, size + suffix)
        else:
            return getattr(self.f3d, self.f3d.IM_SIZ[size] + suffix)

    def getImagePathFromInclude(self, path):
        if self.basePath is None:
            raise PluginError("Cannot load texture from " + path + " without any provided base path.")

        imagePathRelative = path[:-5] + "png"
        imagePath = os.path.join(self.basePath, imagePathRelative)

        # handle custom imports, where relative paths don't make sense
        if not os.path.exists(imagePath):
            imagePath = os.path.join(self.basePath, os.path.basename(imagePathRelative))
        return imagePath

    def getVTXPathFromInclude(self, path):
        if self.basePath is None:
            raise PluginError("Cannot load VTX from " + path + " without any provided base path.")

        vtxPath = os.path.join(self.basePath, path)
        # handle custom imports, where relative paths don't make sense
        if not os.path.exists(vtxPath):
            vtxPath = os.path.join(self.basePath, os.path.basename(path))
        return vtxPath

    def setGeoFlags(self, command: "ParsedMacro", value: bool):
        mat = self.mat()
        bitFlags = math_eval(command.params[0], self.f3d)

        rdp_settings: "RDPSettings" = mat.rdp_settings

        if bitFlags & self.f3d.G_ZBUFFER:
            rdp_settings.g_zbuffer = value
        if bitFlags & self.f3d.G_SHADE:
            rdp_settings.g_shade = value
        if bitFlags & self.f3d.G_CULL_FRONT:
            rdp_settings.g_cull_front = value
        if bitFlags & self.f3d.G_CULL_BACK:
            rdp_settings.g_cull_back = value
        if self.f3d.F3DEX_GBI_3:
            if bitFlags & self.f3d.G_AMBOCCLUSION:
                rdp_settings.g_ambocclusion = value
            if bitFlags & self.f3d.G_ATTROFFSET_Z_ENABLE:
                rdp_settings.g_attroffset_z_enable = value
            if bitFlags & self.f3d.G_ATTROFFSET_ST_ENABLE:
                rdp_settings.g_attroffset_st_enable = value
            if bitFlags & self.f3d.G_PACKED_NORMALS:
                rdp_settings.g_packed_normals = value
            if bitFlags & self.f3d.G_LIGHTTOALPHA:
                rdp_settings.g_lighttoalpha = value
            if bitFlags & self.f3d.G_LIGHTING_SPECULAR:
                rdp_settings.g_lighting_specular = value
            if bitFlags & self.f3d.G_FRESNEL_COLOR:
                rdp_settings.g_fresnel_color = value
            if bitFlags & self.f3d.G_FRESNEL_ALPHA:
                rdp_settings.g_fresnel_alpha = value
        if bitFlags & self.f3d.G_FOG:
            rdp_settings.g_fog = value
        if bitFlags & self.f3d.G_LIGHTING:
            rdp_settings.g_lighting = value
        if bitFlags & self.f3d.G_TEXTURE_GEN:
            rdp_settings.g_tex_gen = value
        if bitFlags & self.f3d.G_TEXTURE_GEN_LINEAR:
            rdp_settings.g_tex_gen_linear = value
        if bitFlags & self.f3d.G_LOD:
            rdp_settings.g_lod = value
        if bitFlags & self.f3d.G_SHADING_SMOOTH:
            rdp_settings.g_shade_smooth = value
        if bitFlags & self.f3d.G_CLIPPING:
            rdp_settings.g_clipping = value

    def loadGeoFlags(self, command: "ParsedMacro"):
        mat = self.mat()

        bitFlags = math_eval(command.params[0], self.f3d)

        rdp_settings: "RDPSettings" = mat.rdp_settings

        rdp_settings.g_zbuffer = bitFlags & self.f3d.G_ZBUFFER != 0
        rdp_settings.g_shade = bitFlags & self.f3d.G_SHADE != 0
        rdp_settings.g_cull_front = bitFlags & self.f3d.G_CULL_FRONT != 0
        rdp_settings.g_cull_back = bitFlags & self.f3d.G_CULL_BACK != 0
        if self.f3d.F3DEX_GBI_3:
            rdp_settings.g_ambocclusion = bitFlags & self.f3d.G_AMBOCCLUSION != 0
            rdp_settings.g_attroffset_z_enable = bitFlags & self.f3d.G_ATTROFFSET_Z_ENABLE != 0
            rdp_settings.g_attroffset_st_enable = bitFlags & self.f3d.G_ATTROFFSET_ST_ENABLE != 0
            rdp_settings.g_packed_normals = bitFlags & self.f3d.G_PACKED_NORMALS != 0
            rdp_settings.g_lighttoalpha = bitFlags & self.f3d.G_LIGHTTOALPHA != 0
            rdp_settings.g_lighting_specular = bitFlags & self.f3d.G_LIGHTING_SPECULAR != 0
            rdp_settings.g_fresnel_color = bitFlags & self.f3d.G_FRESNEL_COLOR != 0
            rdp_settings.g_fresnel_alpha = bitFlags & self.f3d.G_FRESNEL_ALPHA != 0
        else:
            rdp_settings.g_ambocclusion = False
            rdp_settings.g_attroffset_z_enable = False
            rdp_settings.g_attroffset_st_enable = False
            rdp_settings.g_packed_normals = False
            rdp_settings.g_lighttoalpha = False
            rdp_settings.g_lighting_specular = False
            rdp_settings.g_fresnel_color = False
            rdp_settings.g_fresnel_alpha = False
        rdp_settings.g_fog = bitFlags & self.f3d.G_FOG != 0
        rdp_settings.g_lighting = bitFlags & self.f3d.G_LIGHTING != 0
        rdp_settings.g_tex_gen = bitFlags & self.f3d.G_TEXTURE_GEN != 0
        rdp_settings.g_tex_gen_linear = bitFlags & self.f3d.G_TEXTURE_GEN_LINEAR != 0
        rdp_settings.g_lod = bitFlags & self.f3d.G_LOD != 0
        rdp_settings.g_shade_smooth = bitFlags & self.f3d.G_SHADING_SMOOTH != 0
        rdp_settings.g_clipping = bitFlags & self.f3d.G_CLIPPING != 0

    def setCombineLerp(self, lerp0, lerp1):
        mat = self.mat()

        if len(lerp0) < 8 or len(lerp1) < 8:
            print("Incorrect combiner param count: " + str(lerp0) + " " + str(lerp1))
            return

        lerp0 = [value.strip() for value in lerp0]
        lerp1 = [value.strip() for value in lerp1]

        # Padding since index can go up to 31
        combinerAList = ["COMBINED", "TEXEL0", "TEXEL1", "PRIMITIVE", "SHADE", "ENVIRONMENT", "1", "NOISE"] + ["0"] * 24
        combinerBList = ["COMBINED", "TEXEL0", "TEXEL1", "PRIMITIVE", "SHADE", "ENVIRONMENT", "CENTER", "K4"] + [
            "0"
        ] * 24
        combinerCList = [
            "COMBINED",
            "TEXEL0",
            "TEXEL1",
            "PRIMITIVE",
            "SHADE",
            "ENVIRONMENT",
            "SCALE",
            "COMBINED_ALPHA",
            "TEXEL0_ALPHA",
            "TEXEL1_ALPHA",
            "PRIMITIVE_ALPHA",
            "SHADE_ALPHA",
            "ENV_ALPHA",
            "LOD_FRACTION",
            "PRIM_LOD_FRAC",
            "K5",
        ] + ["0"] * 16
        combinerDList = ["COMBINED", "TEXEL0", "TEXEL1", "PRIMITIVE", "SHADE", "ENVIRONMENT", "1", "0"] + ["0"] * 24

        combinerAAlphaList = ["COMBINED", "TEXEL0", "TEXEL1", "PRIMITIVE", "SHADE", "ENVIRONMENT", "1", "0"]
        combinerBAlphaList = ["COMBINED", "TEXEL0", "TEXEL1", "PRIMITIVE", "SHADE", "ENVIRONMENT", "1", "0"]
        combinerCAlphaList = [
            "LOD_FRACTION",
            "TEXEL0",
            "TEXEL1",
            "PRIMITIVE",
            "SHADE",
            "ENVIRONMENT",
            "PRIM_LOD_FRAC",
            "0",
        ]
        combinerDAlphaList = ["COMBINED", "TEXEL0", "TEXEL1", "PRIMITIVE", "SHADE", "ENVIRONMENT", "1", "0"]

        for i in range(0, 4):
            lerp0[i] = math_eval("G_CCMUX_" + lerp0[i], self.f3d)
            lerp1[i] = math_eval("G_CCMUX_" + lerp1[i], self.f3d)

        for i in range(4, 8):
            lerp0[i] = math_eval("G_ACMUX_" + lerp0[i], self.f3d)
            lerp1[i] = math_eval("G_ACMUX_" + lerp1[i], self.f3d)

        mat.set_combiner = True
        mat.combiner1.A = combinerAList[lerp0[0]]
        mat.combiner1.B = combinerBList[lerp0[1]]
        mat.combiner1.C = combinerCList[lerp0[2]]
        mat.combiner1.D = combinerDList[lerp0[3]]
        mat.combiner1.A_alpha = combinerAAlphaList[lerp0[4]]
        mat.combiner1.B_alpha = combinerBAlphaList[lerp0[5]]
        mat.combiner1.C_alpha = combinerCAlphaList[lerp0[6]]
        mat.combiner1.D_alpha = combinerDAlphaList[lerp0[7]]

        mat.combiner2.A = combinerAList[lerp1[0]]
        mat.combiner2.B = combinerBList[lerp1[1]]
        mat.combiner2.C = combinerCList[lerp1[2]]
        mat.combiner2.D = combinerDList[lerp1[3]]
        mat.combiner2.A_alpha = combinerAAlphaList[lerp1[4]]
        mat.combiner2.B_alpha = combinerBAlphaList[lerp1[5]]
        mat.combiner2.C_alpha = combinerCAlphaList[lerp1[6]]
        mat.combiner2.D_alpha = combinerDAlphaList[lerp1[7]]

    def setCombineMode(self, command: "ParsedMacro"):
        if not hasattr(self.f3d, command.params[0]) or not hasattr(self.f3d, command.params[1]):
            print("Unhandled combiner mode: " + command.params[0] + ", " + command.params[1])
            return
        lerp0 = getattr(self.f3d, command.params[0])
        lerp1 = getattr(self.f3d, command.params[1])

        self.setCombineLerp(lerp0, lerp1)

    def setTLUTMode(self, flags):
        mat = self.mat()
        if not isinstance(flags, int):
            flags = math_eval(flags, self.f3d)
        tlut_mode = flags & (0b11 << self.f3d.G_MDSFT_TEXTLUT)
        for index in range(2):
            texProp = getattr(mat, "tex" + str(index))
            if tlut_mode == self.f3d.G_TT_IA16:
                texProp.ci_format = "IA16"
            elif tlut_mode == self.f3d.G_TT_RGBA16:
                texProp.ci_format = "RGBA16"
            else:  # self.f3d.G_TT_NONE or the unsupported value of 1
                # Othermode is set to disable palette/CI; make sure the texture format is not CI
                if texProp.tex_format[:2] == "CI":
                    texProp.tex_format = texProp.tex_format[1:]  # Cut off the C, so CI4->I4 and CI8->I8

    def setOtherModeFlags(self, command: "ParsedMacro"):
        mode = math_eval(command.params[0], self.f3d)
        if mode == self.f3d.G_SETOTHERMODE_H:
            self.setOtherModeFlagsH(command)
        else:
            self.setOtherModeFlagsL(command)

    def setFlagsAttrs(self, command: "ParsedMacro", database: "dict[str, Union[list[str], Callable[[Any],None]]]"):
        mat = self.mat()
        flags = math_eval(command.params[3], self.f3d)
        shift = math_eval(command.params[1], self.f3d)
        mask = math_eval(command.params[2], self.f3d)

        for field, fieldData in database.items():
            fieldShift = getattr(self.f3d, field)
            if shift <= fieldShift < shift + mask:
                if isinstance(fieldData, list):
                    value = (flags >> fieldShift) & (roundUpToPowerOf2(len(fieldData)) - 1)
                    setattr(mat.rdp_settings, field.lower(), fieldData[value])
                elif callable(fieldData):
                    fieldData(flags)
                else:
                    raise PluginError(f"Internal error in setFlagsAttrs, type(fieldData) == {type(fieldData)}")

    def setOtherModeFlagsH(self, command: "ParsedMacro"):
        otherModeH = {
            "G_MDSFT_ALPHADITHER": ["G_AD_PATTERN", "G_AD_NOTPATTERN", "G_AD_NOISE", "G_AD_DISABLE"],
            "G_MDSFT_RGBDITHER": ["G_CD_MAGICSQ", "G_CD_BAYER", "G_CD_NOISE", "G_CD_DISABLE"],
            "G_MDSFT_COMBKEY": ["G_CK_NONE", "G_CK_KEY"],
            "G_MDSFT_TEXTCONV": [
                "G_TC_CONV",
                "G_TC_CONV",
                "G_TC_CONV",
                "G_TC_CONV",
                "G_TC_CONV",
                "G_TC_FILTCONV",
                "G_TC_FILT",
            ],
            "G_MDSFT_TEXTFILT": ["G_TF_POINT", "G_TF_POINT", "G_TF_BILERP", "G_TF_AVERAGE"],
            "G_MDSFT_TEXTLUT": self.setTLUTMode,
            "G_MDSFT_TEXTLOD": ["G_TL_TILE", "G_TL_LOD"],
            "G_MDSFT_TEXTDETAIL": ["G_TD_CLAMP", "G_TD_SHARPEN", "G_TD_DETAIL"],
            "G_MDSFT_TEXTPERSP": ["G_TP_NONE", "G_TP_PERSP"],
            "G_MDSFT_CYCLETYPE": ["G_CYC_1CYCLE", "G_CYC_2CYCLE", "G_CYC_COPY", "G_CYC_FILL"],
            "G_MDSFT_COLORDITHER": ["G_CD_DISABLE", "G_CD_ENABLE"],
            "G_MDSFT_PIPELINE": ["G_PM_NPRIMITIVE", "G_PM_1PRIMITIVE"],
        }
        self.setFlagsAttrs(command, otherModeH)

    # This only handles commonly used render mode presets (with macros),
    # and no render modes at all with raw bit data.
    def setOtherModeFlagsL(self, command: "ParsedMacro"):
        otherModeL = {
            "G_MDSFT_ALPHACOMPARE": ["G_AC_NONE", "G_AC_THRESHOLD", "G_AC_THRESHOLD", "G_AC_DITHER"],
            "G_MDSFT_ZSRCSEL": ["G_ZS_PIXEL", "G_ZS_PRIM"],
            "G_MDSFT_RENDERMODE": self.setRenderMode,
        }
        self.setFlagsAttrs(command, otherModeL)

    def setRenderMode(self, flags):
        mat = self.mat()
        rendermode1 = renderModeMask(flags, 1, False)
        rendermode2 = renderModeMask(flags, 2, False)

        blend1 = renderModeMask(flags, 1, True)

        rendermodeName1 = None
        rendermodeName2 = None

        # print("Render mode: " + hex(rendermode1) + ", " + hex(rendermode2))
        for name, value in vars(self.f3d).items():
            if name[:5] == "G_RM_":
                # print(name + " " + hex(value))

                if name in ["G_RM_FOG_SHADE_A", "G_RM_FOG_PRIM_A", "G_RM_PASS"]:
                    if blend1 == value:
                        rendermodeName1 = name
                else:
                    if rendermode1 == value:
                        rendermodeName1 = name
                    if rendermode2 == value:
                        rendermodeName2 = name
            if rendermodeName1 is not None and rendermodeName2 is not None:
                break

        rdp_settings: "RDPSettings" = mat.rdp_settings

        if rendermodeName1 is not None and rendermodeName2 is not None:
            rdp_settings.rendermode_advanced_enabled = False
            rdp_settings.rendermode_preset_cycle_1 = rendermodeName1
            rdp_settings.rendermode_preset_cycle_2 = rendermodeName2
        else:
            rdp_settings.rendermode_advanced_enabled = True

        rdp_settings.aa_en = rendermode1 & self.f3d.AA_EN != 0
        rdp_settings.z_cmp = rendermode1 & self.f3d.Z_CMP != 0
        rdp_settings.z_upd = rendermode1 & self.f3d.Z_UPD != 0
        rdp_settings.im_rd = rendermode1 & self.f3d.IM_RD != 0
        rdp_settings.clr_on_cvg = rendermode1 & self.f3d.CLR_ON_CVG != 0
        rdp_settings.cvg_dst = self.f3d.cvgDstDict[rendermode1 & self.f3d.CVG_DST_SAVE]
        rdp_settings.zmode = self.f3d.zmodeDict[rendermode1 & self.f3d.ZMODE_DEC]
        rdp_settings.cvg_x_alpha = rendermode1 & self.f3d.CVG_X_ALPHA != 0
        rdp_settings.alpha_cvg_sel = rendermode1 & self.f3d.ALPHA_CVG_SEL != 0
        rdp_settings.force_bl = rendermode1 & self.f3d.FORCE_BL != 0

        rdp_settings.blend_p1 = self.f3d.blendColorDict[rendermode1 >> 30 & 3]
        rdp_settings.blend_a1 = self.f3d.blendAlphaDict[rendermode1 >> 26 & 3]
        rdp_settings.blend_m1 = self.f3d.blendColorDict[rendermode1 >> 22 & 3]
        rdp_settings.blend_b1 = self.f3d.blendMixDict[rendermode1 >> 18 & 3]

        rdp_settings.blend_p2 = self.f3d.blendColorDict[rendermode2 >> 28 & 3]
        rdp_settings.blend_a2 = self.f3d.blendAlphaDict[rendermode2 >> 24 & 3]
        rdp_settings.blend_m2 = self.f3d.blendColorDict[rendermode2 >> 20 & 3]
        rdp_settings.blend_b2 = self.f3d.blendMixDict[rendermode2 >> 16 & 3]

    def gammaInverseParam(self, color: "list[str]"):
        return [gammaInverseValue(math_eval(value, self.f3d) / 255) for value in color[:3]] + [
            math_eval(color[3], self.f3d) / 255
        ]

    def getLightIndex(self, lightIndexString):
        return math_eval(lightIndexString, self.f3d) if "LIGHT_" not in lightIndexString else int(lightIndexString[-1:])

    def getLightCount(self, lightCountString):
        return (
            math_eval(lightCountString, self.f3d)
            if "NUMLIGHTS_" not in lightCountString
            else int(lightCountString[-1:])
        )

    def getLightObj(self, light: Light):
        if light not in self.lightData:
            lightName = "Light"
            bLight = bpy.data.lights.new(lightName, "SUN")
            lightObj = bpy.data.objects.new(lightName, bLight)

            lightObj.rotation_euler = (
                mathutils.Euler((0, 0, math.pi)).to_quaternion()
                @ (mathutils.Euler((math.pi / 2, 0, 0)).to_quaternion() @ Vector(light.normal)).rotation_difference(
                    Vector((0, 0, 1))
                )
            ).to_euler()
            # lightObj.rotation_euler[0] *= 1
            bLight.color = light.color

            bpy.context.scene.collection.objects.link(lightObj)
            self.lightData[light] = lightObj
        return self.lightData[light]

    def applyLights(self):
        mat = self.mat()
        allCombinerUses = all_combiner_uses(mat)
        if allCombinerUses["Shade"] and mat.rdp_settings.g_lighting and mat.set_lights:
            mat.use_default_lighting = False
            mat.ambient_light_color = tuple(self.lights.a.color[:]) + ((1,) if len(self.lights.a.color) == 3 else ())

            for i in range(self.numLights):
                lightObj = self.getLightObj(self.lights.l[i])
                setattr(mat, "f3d_light" + str(i + 1), lightObj.data)

    def setLightColor(self, data, command):
        self.mat().set_lights = True
        lightIndex = self.getLightIndex(command.params[0])
        colorData = math_eval(command.params[1], self.f3d)
        color = Vector(
            [((colorData >> 24) & 0xFF) / 0xFF, ((colorData >> 16) & 0xFF) / 0xFF, ((colorData >> 8) & 0xFF) / 0xFF]
        )

        if lightIndex != self.numLights + 1:
            self.lights.l[lightIndex - 1].color = color
        else:
            self.lights.a.color = color

        # This is an assumption.
        if self.numLights < lightIndex - 1:
            self.numLights = lightIndex - 1

    # Assumes that any SPLight references a Lights0-9n struct instead of specific Light structs.
    def setLight(self, data, command):
        mat = self.mat()
        mat.set_lights = True

        lightReference = command.params[0]
        lightIndex = self.getLightIndex(command.params[1])

        match = re.search("([A-Za-z0-9\_]*)\.(l(\[([0-9])\])?)?(a)?", lightReference)
        if match is None:
            print(
                "Could not handle parsing of light reference: "
                + lightReference
                + ". Currently only handling Lights0-9n structs (not Light)"
            )
            return

        lightsName = match.group(1)
        lights = self.createLights(data, lightsName)

        if match.group(2) is not None:
            if match.group(3) is not None:
                lightIndex = math_eval(match.group(4), self.f3d)
            else:
                lightIndex = 0

            # This is done as an assumption, to handle models that have numLights set beforehand
            if self.numLights < lightIndex + 1:
                self.numLights = lightIndex + 1
            self.lights.l[lightIndex] = lights.l[lightIndex]
        else:
            self.lights.a = lights.a

    def setLights(self, data, command):
        mat = self.mat()
        self.mat().set_lights = True

        numLights = self.getLightCount(command.name[13])
        self.numLights = numLights

        lightsName = command.params[0]
        self.lights = self.createLights(data, lightsName)

    def createLights(self, data, lightsName):
        numLights, lightValues = parseLightsData(data, lightsName, self)
        ambientColor = Vector(gammaInverse([value / 255 for value in lightValues[0:3]]))

        lightList = []

        for i in range(numLights):
            color = Vector(gammaInverse([value / 255 for value in lightValues[3 + 6 * i : 3 + 6 * i + 3]]))
            direction = Vector(bytesToNormal(lightValues[3 + 6 * i + 3 : 3 + 6 * i + 6]))
            lightList.append(Light(color, direction))

        while len(lightList) < 7:
            lightList.append(Light(Vector([0, 0, 0]), Vector([0x49, 0x49, 0x49])))

        # normally a and l are Ambient and Light objects,
        # but here they will be a color and blender light object array.
        lights = Lights(lightsName, self.f3d)
        lights.a = Ambient(ambientColor)
        lights.l = lightList

        return lights

    def getTileIndex(self, value):
        if value == "G_TX_RENDERTILE":
            return self.f3d.G_TX_RENDERTILE
        elif value == "G_TX_LOADTILE":
            return self.f3d.G_TX_LOADTILE
        else:
            return math_eval(value, self.f3d)

    def getTileSettings(self, value):
        return self.tileSettings[self.getTileIndex(value)]

    def getTileSizeSettings(self, value):
        return self.tileSizes[self.getTileIndex(value)]

    def setTileSize(self, params: "list[str | int]"):
        tileSizeSettings = self.getTileSizeSettings(params[0])
        tileSettings = self.getTileSettings(params[0])

        dimensions = [0, 0, 0, 0]
        for i in range(1, 5):
            # match = None
            # if not isinstance(params[i], int):
            # 	match = re.search("\(([0-9]+)\s*\-\s*1\s*\)\s*<<\s*G\_TEXTURE\_IMAGE\_FRAC", params[i])
            # if match is not None:
            # 	dimensions[i - 1] = (math_eval(match.group(1), self.f3d) - 1) << self.f3d.G_TEXTURE_IMAGE_FRAC
            # else:
            # 	dimensions[i - 1] = math_eval(params[i], self.f3d)
            dimensions[i - 1] = math_eval(params[i], self.f3d)

        tileSizeSettings.uls = dimensions[0]
        tileSizeSettings.ult = dimensions[1]
        tileSizeSettings.lrs = dimensions[2]
        tileSizeSettings.lrt = dimensions[3]

    def setTile(self, params: "list[str | int]", dlData: str):
        tileIndex = self.getTileIndex(params[4])
        tileSettings = self.getTileSettings(params[4])
        tileSettings.fmt = getTileFormat(params[0], self.f3d)
        tileSettings.siz = getTileSize(params[1], self.f3d)
        tileSettings.line = math_eval(params[2], self.f3d)
        tileSettings.tmem = math_eval(params[3], self.f3d)
        tileSettings.palette = math_eval(params[5], self.f3d)
        tileSettings.cmt = getTileClampMirror(params[6], self.f3d)
        tileSettings.maskt = getTileMask(params[7], self.f3d)
        tileSettings.shiftt = getTileShift(params[8], self.f3d)
        tileSettings.cms = getTileClampMirror(params[9], self.f3d)
        tileSettings.masks = getTileMask(params[10], self.f3d)
        tileSettings.shifts = getTileShift(params[11], self.f3d)

        tileSizeSettings = self.getTileSizeSettings(params[4])

    def loadTile(self, params):
        tileSettings = self.getTileSettings(params[0])
        """
        TODO: Region parsing too hard?
        region = [
        	math_eval(params[1], self.f3d) / 4,
        	math_eval(params[2], self.f3d) / 4,
        	math_eval(params[3], self.f3d) / 4,
        	math_eval(params[4], self.f3d) / 4
        ]
        """
        region = None

        # Defer texture parsing until next set tile.
        self.tmemDict[tileSettings.tmem] = self.currentTextureName
        self.materialChanged = True

    def loadMultiBlock(self, params: "list[str | int]", dlData: str, is4bit: bool):
        width = math_eval(params[5], self.f3d)
        height = math_eval(params[6], self.f3d)
        siz = params[4]
        assert isinstance(siz, str)
        line = ((width * self.getSizeMacro(siz, "_LINE_BYTES")) + 7) >> 3 if not is4bit else ((width >> 1) + 7) >> 3
        tmem = params[1]
        tile = params[2]
        loadBlockSiz = self.getSizeMacro(siz, "_LOAD_BLOCK") if not is4bit else self.f3d.G_IM_SIZ_16b
        self.currentTextureName = params[0]
        self.setTile(
            [
                params[3],
                loadBlockSiz,
                0,
                tmem,
                "G_TX_LOADTILE",
                0,
                params[9],
                params[11],
                params[13],
                params[8],
                params[10],
                params[12],
            ],
            dlData,
        )
        # TODO: Region is ignored for now
        self.loadTile(["G_TX_LOADTILE", 0, 0, 0, 0])
        self.setTile(
            [
                params[3],
                params[4],
                line,
                tmem,
                tile,
                0,
                params[9],
                params[11],
                params[13],
                params[8],
                params[10],
                params[12],
            ],
            dlData,
        )
        self.setTileSize(
            [tile, 0, 0, (width - 1) << self.f3d.G_TEXTURE_IMAGE_FRAC, (height - 1) << self.f3d.G_TEXTURE_IMAGE_FRAC]
        )

    def loadTLUTPal(self, name: str, dlData: str, count: int):
        # TODO: Doesn't handle loading palettes into not tmem 256
        self.currentTextureName = name
        self.setTile([0, 0, 0, 256, "G_TX_LOADTILE", 0, 0, 0, 0, 0, 0, 0], dlData)
        self.loadTLUT(["G_TX_LOADTILE", count], dlData)

    # override this in a child context to handle texture references.
    # keep material parameter for use by parent.
    # ex. In OOT, you can call self.loadTexture() here based on texture arrays.
    def handleTextureReference(
        self,
        name: str,
        image: F3DTextureReference,
        material: bpy.types.Material,
        index: int,
        tileSettings: DPSetTile,
        data: str,
    ):
        texProp = getattr(material.f3d_mat, "tex" + str(index))
        texProp.tex = None
        texProp.use_tex_reference = True
        texProp.tex_reference = name
        size = texProp.tex_reference_size

    # add to this by overriding in a parent context, to handle clearing settings related to previous texture references.
    def handleTextureValue(self, material: bpy.types.Material, image: bpy.types.Image, index: int):
        texProp = getattr(material.f3d_mat, "tex" + str(index))
        texProp.tex = image
        texProp.use_tex_reference = False
        size = texProp.tex.size

    def applyTileToMaterial(self, index, tileSettings, tileSizeSettings, dlData: str):
        mat = self.mat()

        texProp = getattr(mat, "tex" + str(index))

        name = self.tmemDict[tileSettings.tmem]
        image = self.textureData[name]
        if isinstance(image, F3DTextureReference):
            self.handleTextureReference(name, image, self.materialContext, index, tileSettings, dlData)
        else:
            self.handleTextureValue(self.materialContext, image, index)
        texProp.tex_set = True

        if texProp.use_tex_reference:
            # WARNING: Inferring texture size from tile size.
            texProp.tex_reference_size = [
                int(round(tileSizeSettings.lrs / (2**self.f3d.G_TEXTURE_IMAGE_FRAC) + 1)),
                int(round(tileSizeSettings.lrt / (2**self.f3d.G_TEXTURE_IMAGE_FRAC) + 1)),
            ]

        texProp.tex_format = tileSettings.fmt[8:].replace("_", "") + tileSettings.siz[8:-1].replace("_", "")

        texProp.S.clamp = tileSettings.cms[0]
        texProp.S.mirror = tileSettings.cms[1]
        texProp.S.mask = tileSettings.masks
        texProp.S.shift = tileSettings.shifts

        texProp.T.clamp = tileSettings.cmt[0]
        texProp.T.mirror = tileSettings.cmt[1]
        texProp.T.mask = tileSettings.maskt
        texProp.T.shift = tileSettings.shiftt

        texProp.S.low = round(tileSizeSettings.uls / (2**self.f3d.G_TEXTURE_IMAGE_FRAC), 3)
        texProp.T.low = round(tileSizeSettings.ult / (2**self.f3d.G_TEXTURE_IMAGE_FRAC), 3)
        texProp.S.high = round(tileSizeSettings.lrs / (2**self.f3d.G_TEXTURE_IMAGE_FRAC), 3)
        texProp.T.high = round(tileSizeSettings.lrt / (2**self.f3d.G_TEXTURE_IMAGE_FRAC), 3)

    def loadTexture(self, data, name, region, tileSettings, isLUT):
        textureName = name

        if textureName in self.textureData:
            return self.textureData[textureName]

        """region ignored?"""
        if isLUT:
            siz = "G_IM_SIZ_16b"
            width = 16
        else:
            siz = tileSettings.siz
            if siz == "G_IM_SIZ_4b":
                width = (tileSettings.line * 8) * 2
            else:
                width = ceil((tileSettings.line * 8) / self.f3d.G_IM_SIZ_VARS[siz + "_LINE_BYTES"])

        # TODO: Textures are sometimes loaded in with different dimensions than for rendering.
        # This means width is incorrect?
        image, loadedFromImageFile = parseTextureData(
            data, textureName, self, tileSettings.fmt, siz, width, isLUT, self.f3d
        )
        if loadedFromImageFile:
            self.imagesDontApplyTlut.add(image)

        self.textureData[textureName] = image
        return self.textureData[textureName]

    def loadTLUT(self, params, dlData):
        tileSettings = self.getTileSettings(params[0])
        name = self.currentTextureName
        textureName = name
        self.tmemDict[tileSettings.tmem] = textureName

        tlut = self.loadTexture(dlData, textureName, [0, 0, 16, 16], tileSettings, True)
        self.materialChanged = True

    def applyTLUT(self, image, tlut):
        invalidIndicesDetected = False
        for i in range(int(len(image.pixels) / 4)):
            lutIndex = int(round(image.pixels[4 * i] * 255))
            newValues = tlut.pixels[4 * lutIndex : 4 * (lutIndex + 1)]
            if len(newValues) < 4:
                # print("Invalid LUT Index " + str(lutIndex))
                invalidIndicesDetected = True
            else:
                image.pixels[4 * i : 4 * (i + 1)] = newValues

        if invalidIndicesDetected:
            print("Invalid LUT Indices detected.")

    def getVertexDataStart(self, vertexDataParam: str, f3d: F3D):
        matchResult = re.search(r"\&?([A-Za-z0-9\_]*)\s*(\[([^\]]*)\])?\s*(\+(.*))?", vertexDataParam)
        if matchResult is None:
            raise PluginError("SPVertex param " + vertexDataParam + " is malformed.")

        offset = 0
        if matchResult.group(3):
            offset += math_eval(matchResult.group(3), f3d)
        if matchResult.group(5):
            offset += math_eval(matchResult.group(5), f3d)

        return matchResult.group(1), offset

    def processCommands(self, dlData: str, dlName: str, dlCommands: "list[ParsedMacro]"):
        callStack = [F3DParsedCommands(dlName, dlCommands, 0)]
        while len(callStack) > 0:
            currentCommandList = callStack[-1]
            command = currentCommandList.currentCommand()

            if currentCommandList.index >= len(currentCommandList.commands):
                raise PluginError("Cannot handle unterminated static display lists: " + currentCommandList.name)
            elif len(callStack) > 2**16:
                raise PluginError("DL call stack larger than 2**16, assuming infinite loop: " + currentCommandList.name)

            # print(command.name + " " + str(command.params))
            if command.name == "gsSPVertex":
                vertexDataName, vertexDataOffset = self.getVertexDataStart(command.params[0], self.f3d)
                parseVertexData(dlData, vertexDataName, self)
                self.addVertices(command.params[1], command.params[2], vertexDataName, vertexDataOffset)
            elif command.name == "gsSPMatrix":
                self.setCurrentTransform(command.params[0], command.params[1])
            elif command.name == "gsSPPopMatrix":
                print("gsSPPopMatrix not handled.")
            elif command.name == "gsSP1Triangle":
                self.addTriangle(command.params[0:3], dlData)
            elif command.name == "gsSP2Triangles":
                self.addTriangle(command.params[0:3] + command.params[4:7], dlData)
            elif command.name == "gsSPDisplayList" or command.name.startswith("gsSPBranch"):
                newDLName = self.processDLName(command.params[0])
                if newDLName is not None:
                    newDLCommands = parseDLData(dlData, newDLName)
                    # Use -1 index so that it will be incremented to 0 at end of loop
                    parsedCommands = F3DParsedCommands(newDLName, newDLCommands, -1)
                    if command.name == "gsSPDisplayList":
                        callStack.append(parsedCommands)
                    elif command.name.startswith("gsSPBranch"):  # TODO: Handle BranchZ?
                        callStack = callStack[:-1]
                        callStack.append(parsedCommands)
            elif command.name == "gsSPEndDisplayList":
                callStack = callStack[:-1]

            # Should we parse commands into f3d_gbi classes?
            # No, because some parsing involves reading C files, which is separate.

            # Assumes macros use variable names instead of values
            mat = self.mat()
            try:
                # Material Specific Commands
                materialNotChanged = False

                rdp_settings: "RDPSettings" = mat.rdp_settings

                if command.name == "gsSPClipRatio":
                    rdp_settings.clip_ratio = math_eval(command.params[0], self.f3d)
                elif command.name == "gsSPNumLights":
                    self.numLights = self.getLightCount(command.params[0])
                elif command.name == "gsSPLight":
                    self.setLight(dlData, command)
                elif command.name == "gsSPLightColor":
                    self.setLightColor(dlData, command)
                elif command.name[:13] == "gsSPSetLights":
                    self.setLights(dlData, command)
                elif command.name == "gsSPAmbOcclusionAmb":
                    mat.ao_ambient = float_from_u16_str(command.params[0])
                    mat.set_ao = True
                elif command.name == "gsSPAmbOcclusionDir":
                    mat.ao_directional = float_from_u16_str(command.params[0])
                    mat.set_ao = True
                elif command.name == "gsSPAmbOcclusionPoint":
                    mat.ao_point = float_from_u16_str(command.params[0])
                    mat.set_ao = True
                elif command.name == "gsSPAmbOcclusionAmbDir":
                    mat.ao_ambient = float_from_u16_str(command.params[0])
                    mat.ao_directional = float_from_u16_str(command.params[1])
                    mat.set_ao = True
                elif command.name == "gsSPAmbOcclusionDirPoint":
                    mat.ao_directional = float_from_u16_str(command.params[0])
                    mat.ao_point = float_from_u16_str(command.params[1])
                    mat.set_ao = True
                elif command.name == "gsSPAmbOcclusion":
                    mat.ao_ambient = float_from_u16_str(command.params[0])
                    mat.ao_directional = float_from_u16_str(command.params[1])
                    mat.ao_point = float_from_u16_str(command.params[2])
                    mat.set_ao = True
                elif command.name == "gsSPFresnel":
                    scale = int_from_s16_str(command.params[0])
                    offset = int_from_s16_str(command.params[1])
                    dotMax = ((0x7F - offset) << 15) // scale
                    dotMin = ((0x00 - offset) << 15) // scale
                    mat.fresnel_hi = dotMax / float(0x7FFF)
                    mat.fresnel_lo = dotMin / float(0x7FFF)
                    mat.set_fresnel = True
                elif command.name == "gsSPAttrOffsetST":
                    mat.attroffs_st = [
                        int_from_s16_str(command.params[0]) / 32,
                        int_from_s16_str(command.params[1]) / 32,
                    ]
                    mat.set_attroffs_st = True
                elif command.name == "gsSPAttrOffsetZ":
                    mat.attroffs_z = int_from_s16_str(command.params[0])
                    mat.set_attroffs_z = True
                elif command.name == "gsSPFogFactor":
                    pass
                elif command.name == "gsSPFogPosition":
                    mat.fog_position = [math_eval(command.params[0], self.f3d), math_eval(command.params[1], self.f3d)]
                    mat.set_fog = True
                elif command.name == "gsSPTexture" or command.name == "gsSPTextureL":
                    # scale_autoprop should always be false (set in init)
                    # This prevents issues with material caching where updating nodes on a material causes its key to change
                    if command.params[0] == 0xFFFF and command.params[1] == 0xFFFF:
                        mat.tex_scale = (1, 1)
                    else:
                        mat.tex_scale = [
                            math_eval(command.params[0], self.f3d) / (2**16),
                            math_eval(command.params[1], self.f3d) / (2**16),
                        ]
                    # command.params[2] is "lod level", and for clarity we store this is the number of mipmapped textures (which is +1)
                    rdp_settings.num_textures_mipmapped = 1 + math_eval(command.params[2], self.f3d)
                elif command.name == "gsSPSetGeometryMode":
                    self.setGeoFlags(command, True)
                elif command.name == "gsSPClearGeometryMode":
                    self.setGeoFlags(command, False)
                elif command.name == "gsSPLoadGeometryMode":
                    self.loadGeoFlags(command)
                elif command.name == "gsSPSetOtherMode":
                    self.setOtherModeFlags(command)
                elif command.name == "gsDPPipelineMode":
                    rdp_settings.g_mdsft_pipeline = command.params[0]
                elif command.name == "gsDPSetCycleType":
                    rdp_settings.g_mdsft_cycletype = command.params[0]
                elif command.name == "gsDPSetTexturePersp":
                    rdp_settings.g_mdsft_textpersp = command.params[0]
                elif command.name == "gsDPSetTextureDetail":
                    rdp_settings.g_mdsft_textdetail = command.params[0]
                elif command.name == "gsDPSetTextureLOD":
                    rdp_settings.g_mdsft_textlod = command.params[0]
                elif command.name == "gsDPSetTextureLUT":
                    self.setTLUTMode(command.params[0])
                elif command.name == "gsDPSetTextureFilter":
                    rdp_settings.g_mdsft_text_filt = command.params[0]
                elif command.name == "gsDPSetTextureConvert":
                    rdp_settings.g_mdsft_textconv = command.params[0]
                elif command.name == "gsDPSetCombineKey":
                    rdp_settings.g_mdsft_combkey = command.params[0]
                elif command.name == "gsDPSetColorDither":
                    rdp_settings.g_mdsft_color_dither = command.params[0]
                elif command.name == "gsDPSetAlphaDither":
                    rdp_settings.g_mdsft_alpha_dither = command.params[0]
                elif command.name == "gsDPSetAlphaCompare":
                    rdp_settings.g_mdsft_alpha_compare = command.params[0]
                elif command.name == "gsDPSetDepthSource":
                    rdp_settings.g_mdsft_zsrcsel = command.params[0]
                elif command.name == "gsDPSetRenderMode":
                    flags = math_eval(command.params[0] + " | " + command.params[1], self.f3d)
                    self.setRenderMode(flags)
                elif command.name == "gsDPSetTextureImage":
                    # Are other params necessary?
                    # The params are set in SetTile commands.
                    self.currentTextureName = command.params[3]
                elif command.name == "gsDPSetCombineMode":
                    self.setCombineMode(command)
                elif command.name == "gsDPSetCombineLERP":
                    self.setCombineLerp(command.params[0:8], command.params[8:16])
                elif command.name == "gsDPSetEnvColor":
                    mat.env_color = self.gammaInverseParam(command.params)
                    mat.set_env = True
                elif command.name == "gsDPSetBlendColor":
                    mat.blend_color = self.gammaInverseParam(command.params)
                    mat.set_blend = True
                elif command.name == "gsDPSetFogColor":
                    mat.fog_color = self.gammaInverseParam(command.params)
                    mat.set_fog = True
                elif command.name == "gsDPSetFillColor":
                    pass
                elif command.name == "gsDPSetPrimDepth":
                    pass
                elif command.name == "gsDPSetPrimColor":
                    mat.prim_lod_min = math_eval(command.params[0], self.f3d) / 255
                    mat.prim_lod_frac = math_eval(command.params[1], self.f3d) / 255
                    mat.prim_color = self.gammaInverseParam(command.params[2:6])
                    mat.set_prim = True
                elif command.name == "gsDPSetOtherMode":
                    print("gsDPSetOtherMode not handled.")
                elif command.name == "DPSetConvert":
                    mat.set_k0_5 = True
                    for i in range(6):
                        setattr(mat, "k" + str(i), gammaInverseValue(math_eval(command.params[i], self.f3d) / 255))
                elif command.name == "DPSetKeyR":
                    mat.set_key = True
                elif command.name == "DPSetKeyGB":
                    mat.set_key = True
                else:
                    materialNotChanged = True

                if not materialNotChanged:
                    self.materialChanged = True

                # Texture Commands
                # Assume file texture load
                # SetTextureImage -> Load command -> Set Tile (0 or 1)

                if command.name == "gsDPSetTileSize":
                    self.setTileSize(command.params)
                elif command.name == "gsDPLoadTile":
                    self.loadTile(command.params)
                elif command.name == "gsDPSetTile":
                    self.setTile(command.params, dlData)
                elif command.name == "gsDPLoadBlock":
                    self.loadTile(command.params)
                elif command.name == "gsDPLoadTLUTCmd":
                    self.loadTLUT(command.params, dlData)

                # This all ignores S/T high/low values
                # This is pretty bad/confusing
                elif command.name.startswith("gsDPLoadTextureBlock"):
                    is4bit = "4b" in command.name
                    if is4bit:
                        self.loadMultiBlock(
                            [command.params[0]]
                            + [0, "G_TX_RENDERTILE"]
                            + [command.params[1], "G_IM_SIZ_4b"]
                            + command.params[2:],
                            dlData,
                            True,
                        )
                    else:
                        self.loadMultiBlock(
                            [command.params[0]] + [0, "G_TX_RENDERTILE"] + command.params[1:], dlData, False
                        )
                elif command.name.startswith("gsDPLoadMultiBlock"):
                    is4bit = "4b" in command.name
                    if is4bit:
                        self.loadMultiBlock(command.params[:4] + ["G_IM_SIZ_4b"] + command.params[4:], dlData, True)
                    else:
                        self.loadMultiBlock(command.params, dlData, False)
                elif command.name.startswith("gsDPLoadTextureTile"):
                    is4bit = "4b" in command.name
                    if is4bit:
                        self.loadMultiBlock(
                            [command.params[0]]
                            + [0, "G_TX_RENDERTILE"]
                            + [command.params[1], "G_IM_SIZ_4b"]
                            + command.params[2:4]
                            + command.params[9:],
                            "4b",  # FIXME extra argument?
                            dlData,
                            True,
                        )
                    else:
                        self.loadMultiBlock(
                            [command.params[0]] + [0, "G_TX_RENDERTILE"] + command.params[1:5] + command.params[9:],
                            "4b",  # FIXME extra argument?
                            dlData,
                            False,
                        )
                elif command.name.startswith("gsDPLoadMultiTile"):
                    is4bit = "4b" in command.name
                    if is4bit:
                        self.loadMultiBlock(
                            command.params[:4] + ["G_IM_SIZ_4b"] + command.params[4:6] + command.params[10:],
                            dlData,
                            True,
                        )
                    else:
                        self.loadMultiBlock(command.params[:7] + command.params[11:], dlData, False)

                # TODO: Only handles palettes at tmem = 256
                elif command.name == "gsDPLoadTLUT_pal16":
                    self.loadTLUTPal(command.params[1], dlData, 15)
                elif command.name == "gsDPLoadTLUT_pal256":
                    self.loadTLUTPal(command.params[0], dlData, 255)
                else:
                    pass

            except TypeError as e:
                print(traceback.format_exc())
                # raise Exception(e)
                # print(e)

            # Don't use currentCommandList because some commands may change that
            if len(callStack) > 0:
                callStack[-1].index += 1

    # override this to handle game specific DL calls.
    # return None to indicate DL call should be skipped.
    def processDLName(self, name: str) -> Optional[str]:
        return name

    def deleteMaterialContext(self):
        if self.materialContext is not None:
            bpy.data.materials.remove(self.materialContext)
        else:
            raise PluginError("Attempting to delete material context that is None.")

    # if deleteMaterialContext is False, then manually call self.deleteMaterialContext() later.
    def createMesh(self, obj, removeDoubles, importNormals, callDeleteMaterialContext: bool):
        mesh = obj.data
        if len(self.verts) % 3 != 0:
            print(len(self.verts))
            raise PluginError("Number of verts in mesh not divisible by 3, currently " + str(len(self.verts)))

        triangleCount = int(len(self.verts) / 3)
        verts = [f3dVert.position for f3dVert in self.verts]
        faces = [[3 * i + j for j in range(3)] for i in range(triangleCount)]
        print("Vertices: " + str(len(self.verts)) + ", Triangles: " + str(triangleCount))

        mesh.from_pydata(vertices=verts, edges=[], faces=faces)
        uv_layer_name = mesh.uv_layers.new().name
        # if self.materialContext.f3d_mat.rdp_settings.g_lighting:
        # else:

        if importNormals:
            # Changed in Blender 4.1: "Meshes now always use custom normals if they exist." (and use_auto_smooth was removed)
            if bpy.app.version < (4, 1, 0):
                mesh.use_auto_smooth = True
            mesh.normals_split_custom_set([f3dVert.normal for f3dVert in self.verts])

        for groupName, indices in self.limbGroups.items():
            group = obj.vertex_groups.new(name=self.limbToBoneName[groupName])
            group.add(indices, 1, "REPLACE")

        for i in range(len(mesh.polygons)):
            mesh.polygons[i].material_index = self.triMatIndices[i]

        # Workaround for an issue in Blender 3.5 where putting this above the `if importNormals` block
        # causes wrong uvs/normals and sometimes crashes.
        uv_layer = mesh.uv_layers[uv_layer_name].data

        for i in range(len(mesh.loops)):
            # This should be okay, since we aren't trying to optimize vertices
            # There will be one loop for every vertex
            uv_layer[i].uv = self.verts[i].uv

        color_layer = mesh.vertex_colors.new(name="Col").data
        for i in range(len(mesh.loops)):
            color_layer[i].color = self.verts[i].rgb.to_4d()

        alpha_layer = mesh.vertex_colors.new(name="Alpha").data
        for i in range(len(mesh.loops)):
            alpha_layer[i].color = [self.verts[i].alpha] * 3 + [1]

        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        for material in self.materials:
            obj.data.materials.append(material)
        if not importNormals:
            bpy.ops.object.shade_smooth()
        if removeDoubles:
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.remove_doubles()
            bpy.ops.object.mode_set(mode="OBJECT")

        obj.location = bpy.context.scene.cursor.location

        i = 0
        for key, lightObj in self.lightData.items():
            lightObj.location = bpy.context.scene.cursor.location + Vector((i, 0, 0))
            i += 1

        self.clearGeometry()

        if callDeleteMaterialContext:
            self.deleteMaterialContext()


class ParsedMacro:
    def __init__(self, name: str, params: "list[str]"):
        self.name = name
        self.params = params


# Static DLs only


# limbName = c variable name (for parsing text)
# boneName = blender bone name (for assigning vertex groups)
# we distinguish these because there is no guarantee of bone order in blender,
# so we usually rely on alphabetical naming.
# This means changing the c variable names.
def parseF3D(
    dlData: str,
    dlName: str,
    transformMatrix: mathutils.Matrix,
    limbName: str,
    boneName: str,
    drawLayer: str,
    f3dContext: F3DContext,
    callClearMaterial: bool,
):
    f3dContext.matrixData[limbName] = transformMatrix
    f3dContext.setCurrentTransform(limbName)
    f3dContext.limbToBoneName[limbName] = boneName
    if f3dContext.draw_layer_prop is not None:
        setattr(f3dContext.mat().draw_layer, f3dContext.draw_layer_prop, drawLayer)

    # vertexGroup = getOrMakeVertexGroup(obj, boneName)
    # groupIndex = vertexGroup.index

    processedDLName = f3dContext.processDLName(dlName)
    if processedDLName is not None:
        dlCommands = parseDLData(dlData, processedDLName)
        f3dContext.processCommands(dlData, processedDLName, dlCommands)

    if callClearMaterial:
        f3dContext.clearMaterial()


def parseDLData(dlData: str, dlName: str):
    matchResult = re.search(r"Gfx\s*" + re.escape(dlName) + r"\s*\[\s*\w*\s*\]\s*=\s*\{([^\}]*)\}", dlData)
    if matchResult is None:
        raise PluginError("Cannot find display list named " + dlName)

    dlCommandData = matchResult.group(1)

    # recursive regex not available in re
    # dlCommands = [(match.group(1), [param.strip() for param in match.group(2).split(",")]) for match in \
    # 	re.findall('(gs[A-Za-z0-9\_]*)\(((?>[^()]|(?R))*)\)', dlCommandData, re.DOTALL)]

    dlCommands = parseMacroList(dlCommandData)
    return dlCommands


def parseVertexData(dlData: str, vertexDataName: str, f3dContext: F3DContext):
    if vertexDataName in f3dContext.vertexData:
        return f3dContext.vertexData[vertexDataName]

    matchResult = re.search(
        r"Vtx\s*" + re.escape(vertexDataName) + r"\s*\[\s*[0-9x]*\s*\]\s*=\s*\{([^;]*);", dlData, re.DOTALL
    )
    if matchResult is None:
        raise PluginError("Cannot find vertex list named " + vertexDataName)
    data = matchResult.group(1)

    pathMatch = re.search(r'\#include\s*"([^"]*)"', data)
    if pathMatch is not None:
        path = pathMatch.group(1)
        if bpy.context.scene.gameEditorMode == "OOT":
            path = f"{bpy.context.scene.fast64.oot.get_extracted_path()}/{path}"
        data = readFile(f3dContext.getVTXPathFromInclude(path))

    f3d = f3dContext.f3d
    patterns = f3dContext.vertexFormatPatterns(data)
    vertexData = []
    for pattern in patterns:
        # For this step, store rgb/normal as rgb and packed normal as normal.
        for match in re.finditer(pattern, data, re.DOTALL):
            values = [math_eval(g, f3d) for g in match.groups()]
            if len(values) == 9:
                # A format without the flag / packed normal
                values = values[0:3] + [0] + values[3:9]
            vertexData.append(
                F3DVert(
                    Vector(values[0:3]),
                    Vector(values[4:6]),
                    Vector(values[6:9]),
                    unpackNormal(values[3]),
                    values[9],
                )
            )
        if len(vertexData) > 0:
            break
    f3dContext.vertexData[vertexDataName] = vertexData

    return f3dContext.vertexData[vertexDataName]


def parseLightsData(lightsData, lightsName, f3dContext):
    # if lightsName in f3dContext.lightData:
    # 	return f3dContext.lightData[lightsName]

    matchResult = re.search(
        r"Lights([0-9n])\s*" + re.escape(lightsName) + r"\s*=\s*gdSPDefLights[0-9]\s*\(([^\)]*)\)\s*;\s*",
        lightsData,
        re.DOTALL,
    )
    if matchResult is None:
        raise PluginError("Cannot find lights data named " + lightsName)
    data = matchResult.group(2)

    values = [math_eval(value.strip(), f3dContext.f3d) for value in data.split(",")]
    if values[-1] == "":
        values = values[:-1]

    lightCount = matchResult.group(1)
    if lightCount == "n":
        lightCount = "7"
    return int(lightCount), values

    # return f3dContext.lightData[lightsName]


def RGBA16toRGBA32(value):
    return [((value >> 11) & 31) / 31, ((value >> 6) & 31) / 31, ((value >> 1) & 31) / 31, value & 1]


def IA16toRGBA32(value):
    return [((value >> 8) & 255) / 255, ((value >> 8) & 255) / 255, ((value >> 8) & 255) / 255, (value & 255) / 255]


def IA8toRGBA32(value):
    return [((value >> 4) & 15) / 15, ((value >> 4) & 15) / 15, ((value >> 4) & 15) / 15, (value & 15) / 15]


def IA4toRGBA32(value):
    return [((value >> 1) & 7) / 7, ((value >> 1) & 7) / 7, ((value >> 1) & 7) / 7, value & 1]


def I8toRGBA32(value):
    return [value / 255, value / 255, value / 255, 1]


def I4toRGBA32(value):
    return [value / 15, value / 15, value / 15, 1]


def CI8toRGBA32(value):
    return [value / 255, value / 255, value / 255, 1]


def CI4toRGBA32(value):
    return [value / 255, value / 255, value / 255, 1]


def parseTextureData(dlData, textureName, f3dContext, imageFormat, imageSize, width, isLUT, f3d):
    matchResult = re.search(
        r"([A-Za-z0-9\_]+)\s*" + re.escape(textureName) + r"\s*\[\s*[0-9a-fA-Fx]*\s*\]\s*=\s*\{([^\}]*)\s*\}\s*;\s*",
        dlData,
        re.DOTALL,
    )
    if matchResult is None:
        print("Cannot find texture named " + textureName)
        return F3DTextureReference(textureName, width), False
    data = matchResult.group(2)
    valueSize = matchResult.group(1)

    loadedFromImageFile = False

    pathMatch = re.search(r'\#include\s*"(.*?)"', data, re.DOTALL)
    if pathMatch is not None:
        path = pathMatch.group(1)
        if bpy.context.scene.gameEditorMode == "OOT":
            path = f"{bpy.context.scene.fast64.oot.get_extracted_path()}/{path}"
        originalImage = bpy.data.images.load(f3dContext.getImagePathFromInclude(path))
        image = originalImage.copy()
        image.pack()
        image.filepath = ""
        bpy.data.images.remove(originalImage)

        # Blender UV origin is bottom right, while N64 is top right, so we must flip LUT since we read it as data
        if isLUT:
            flippedValues = image.pixels[:]
            width, height = image.size
            for j in range(height):
                image.pixels[width * j * 4 : width * (j + 1) * 4] = flippedValues[
                    width * (height - (j + 1)) * 4 : width * (height - j) * 4
                ]

        loadedFromImageFile = True
    else:
        values = [value.strip() for value in data.split(",") if value.strip() != ""]
        newValues = []
        for value in values:
            intValue = math_eval(value, f3d)
            if valueSize == "u8" or valueSize == "s8" or valueSize == "char" or valueSize == "Texture":
                size = 1
            elif valueSize == "u16" or valueSize == "s16" or valueSize == "short":
                size = 2
            elif valueSize == "u32" or valueSize == "s32" or valueSize == "int":
                size = 4
            else:
                size = 8
            newValues.extend(int.to_bytes(intValue, size, "big")[:])
        values = newValues

        if width == 0:
            width = 16
        height = int(ceil(len(values) / (width * int(imageSize[9:-1]) / 8)))
        # print("Texture: " + str(len(values)) + ", width = " + str(width) + ", height = " + str(height))
        image = bpy.data.images.new(textureName, width, height, alpha=True)
        if imageFormat == "G_IM_FMT_RGBA":
            if imageSize == "G_IM_SIZ_16b":
                for i in range(int(len(values) / 2)):
                    image.pixels[4 * i : 4 * (i + 1)] = RGBA16toRGBA32(
                        int.from_bytes(values[2 * i : 2 * (i + 1)], "big")
                    )
            elif imageSize == "G_IM_SIZ_32b":
                image.pixels[:] = values
            else:
                print("Unhandled size for RGBA: " + str(imageSize))
        elif imageFormat == "G_IM_FMT_IA":
            if imageSize == "G_IM_SIZ_4b":
                for i in range(len(values)):
                    image.pixels[8 * i : 8 * i + 4] = IA4toRGBA32((values[i] >> 4) & 15)
                    image.pixels[8 * i + 4 : 8 * i + 8] = IA4toRGBA32(values[i] & 15)
            elif imageSize == "G_IM_SIZ_8b":
                for i in range(len(values)):
                    image.pixels[4 * i : 4 * (i + 1)] = IA8toRGBA32(values[i])
            elif imageSize == "G_IM_SIZ_16b":
                for i in range(int(len(values) / 2)):
                    image.pixels[4 * i : 4 * (i + 1)] = IA16toRGBA32(int.from_bytes(values[2 * i : 2 * (i + 1)], "big"))
            else:
                print("Unhandled size for IA: " + str(imageSize))
        elif imageFormat == "G_IM_FMT_I":
            if imageSize == "G_IM_SIZ_4b":
                for i in range(len(values)):
                    image.pixels[8 * i : 8 * i + 4] = I4toRGBA32((values[i] >> 4) & 15)
                    image.pixels[8 * i + 4 : 8 * i + 8] = I4toRGBA32(values[i] & 15)
            elif imageSize == "G_IM_SIZ_8b":
                for i in range(len(values)):
                    image.pixels[4 * i : 4 * (i + 1)] = I8toRGBA32(values[i])
            else:
                print("Unhandled size for I: " + str(imageSize))
        elif imageFormat == "G_IM_FMT_CI":
            if imageSize == "G_IM_SIZ_4b":
                for i in range(len(values)):
                    image.pixels[8 * i : 8 * i + 4] = CI4toRGBA32((values[i] >> 4) & 15)
                    image.pixels[8 * i + 4 : 8 * i + 8] = CI4toRGBA32(values[i] & 15)
            elif imageSize == "G_IM_SIZ_8b":
                for i in range(len(values)):
                    image.pixels[4 * i : 4 * (i + 1)] = CI8toRGBA32(values[i])
            else:
                print("Unhandled size for CI: " + str(imageSize))

        # Blender UV origin is bottom right, while N64 is top right, so we must flip non LUT
        if not isLUT:
            flippedValues = image.pixels[:]
            for j in range(height):
                image.pixels[width * j * 4 : width * (j + 1) * 4] = flippedValues[
                    width * (height - (j + 1)) * 4 : width * (height - j) * 4
                ]

    return image, loadedFromImageFile


def parseMacroList(data: str):
    end = 0
    start = 0
    isCommand = True
    commands: "list[ParsedMacro]" = []
    parenthesesCount = 0

    command = None
    while end < len(data) - 1:
        end += 1
        if data[end] == "(":
            parenthesesCount += 1
        elif data[end] == ")":
            parenthesesCount -= 1

        if isCommand and parenthesesCount > 0:
            command = data[start:end].strip()
            if command[0] == ",":
                command = command[1:].strip()
            isCommand = False
            start = end + 1

        elif not isCommand and parenthesesCount == 0:
            assert command is not None  # due to isCommand
            params = parseMacroArgs(data[start:end])
            commands.append(ParsedMacro(command, params))
            isCommand = True
            start = end + 1

    return commands


def parseMacroArgs(data: str):
    start = 0
    params: "list[str]" = []
    parenthesesCount = 0

    for end in range(len(data)):
        if data[end] == "(":
            parenthesesCount += 1
        elif data[end] == ")":
            parenthesesCount -= 1

        if (data[end] == "," or end == len(data) - 1) and parenthesesCount == 0:
            if end == len(data) - 1:
                end += 1
            param = "".join(data[start:end].split())
            params.append(param)
            start = end + 1

    return params


def getImportData(filepaths):
    data = ""
    for path in filepaths:
        if os.path.exists(path):
            data += readFile(path)

    return data


def parseMatrices(sceneData: str, f3dContext: F3DContext, importScale: float = 1):
    for match in re.finditer(rf"Mtx\s*([a-zA-Z0-9\_]+)\s*=\s*\{{(.*?)\}}\s*;", sceneData, flags=re.DOTALL):
        name = "&" + match.group(1)
        values = [hexOrDecInt(value.strip()) for value in match.group(2).split(",") if value.strip() != ""]
        trueValues = []
        for n in range(8):
            valueInt = int.from_bytes(values[n].to_bytes(4, "big", signed=True), "big", signed=False)
            valueFrac = int.from_bytes(values[n + 8].to_bytes(4, "big", signed=True), "big", signed=False)
            int1 = values[n] >> 16
            int2 = int.from_bytes((valueInt & (2**16 - 1)).to_bytes(2, "big", signed=False), "big", signed=True)
            frac1 = valueFrac >> 16
            frac2 = valueFrac & (2**16 - 1)
            trueValues.append(int1 + (frac1 / (2**16)))
            trueValues.append(int2 + (frac2 / (2**16)))

        matrix = mathutils.Matrix()
        for i in range(4):
            for j in range(4):
                matrix[j][i] = trueValues[i * 4 + j]

        f3dContext.addMatrix(name, mathutils.Matrix.Scale(importScale, 4) @ matrix)


def importMeshC(
    data: str,
    name: str,
    scale: float,
    removeDoubles: bool,
    importNormals: bool,
    drawLayer: str,
    f3dContext: F3DContext,
    callClearMaterial: bool = True,
) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name + "_mesh", mesh)
    bpy.context.collection.objects.link(obj)

    transformMatrix = mathutils.Matrix.Scale(1 / scale, 4)

    parseF3D(data, name, transformMatrix, name, name, drawLayer, f3dContext, True)
    f3dContext.createMesh(obj, removeDoubles, importNormals, callClearMaterial)

    applyRotation([obj], math.radians(-90), "X")
    return obj


class F3D_ImportDL(bpy.types.Operator):
    # set bl_ properties
    bl_idname = "object.f3d_import_dl"
    bl_label = "Import DL"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        obj = None
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        try:
            name = context.scene.DLImportName
            importPath = bpy.path.abspath(context.scene.DLImportPath)
            basePath = bpy.path.abspath(context.scene.DLImportBasePath)
            scaleValue = bpy.context.scene.blenderF3DScale

            removeDoubles = context.scene.DLRemoveDoubles
            importNormals = context.scene.DLImportNormals
            drawLayer = context.scene.DLImportDrawLayer

            data = getImportData([importPath])

            importMeshC(
                data,
                name,
                scaleValue,
                removeDoubles,
                importNormals,
                drawLayer,
                F3DContext(get_F3D_GBI(), basePath, createF3DMat(None)),
            )

            self.report({"INFO"}, "Success!")
            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


class F3D_UL_ImportDLPathList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        scene = data
        fileProperty = item
        # draw_item must handle the three layout types... Usually 'DEFAULT' and 'COMPACT' can share the same code.
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            # You should always start your row layout by a label (icon + text), or a non-embossed text field,
            # this will also make the row easily selectable in the list! The later also enables ctrl-click rename.
            # We use icon_value of label, as our given icon is an integer value, not an enum ID.
            # Note "data" names should never be translated!
            if ma:
                layout.prop(fileProperty, "Path", text="", emboss=False, icon_value=icon)
            else:
                layout.label(text="", translate=False, icon_value=icon)
        # 'GRID' layout type should be as compact as possible (typically a single icon!).
        elif self.layout_type in {"GRID"}:
            layout.alignment = "CENTER"
            layout.label(text="", icon_value=icon)


class F3D_ImportDLPanel(bpy.types.Panel):
    bl_idname = "F3D_PT_import_dl"
    bl_label = "F3D Importer"
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

        col.operator(F3D_ImportDL.bl_idname)
        prop_split(col, context.scene, "DLImportName", "Name")
        prop_split(col, context.scene, "DLImportPath", "File")
        prop_split(col, context.scene, "DLImportBasePath", "Base Path")
        prop_split(col, context.scene, "blenderF3DScale", "Scale")
        prop_split(col, context.scene, "DLImportDrawLayer", "Draw Layer")
        col.prop(context.scene, "DLRemoveDoubles")
        col.prop(context.scene, "DLImportNormals")

        box = col.box().column()
        box.label(text="All data must be contained within file.")
        box.label(text="The only exception are pngs converted to inc.c.")

        # col.template_list('F3D_UL_ImportDLPathList', '', context.scene,
        # 	'DLImportOtherFiles', context.scene, 'DLImportOtherFilesIndex')


class ImportFileProperty(bpy.types.PropertyGroup):
    path: bpy.props.StringProperty(name="Path", subtype="FILE_PATH")


f3d_parser_classes = (
    F3D_ImportDL,
    F3D_ImportDLPanel,
    ImportFileProperty,
    F3D_UL_ImportDLPathList,
)


def f3d_parser_register():
    for cls in f3d_parser_classes:
        register_class(cls)

    bpy.types.Scene.DLImportName = bpy.props.StringProperty(name="Name")
    bpy.types.Scene.DLImportPath = bpy.props.StringProperty(name="Directory", subtype="FILE_PATH")
    bpy.types.Scene.DLImportBasePath = bpy.props.StringProperty(name="Directory", subtype="FILE_PATH")
    bpy.types.Scene.DLRemoveDoubles = bpy.props.BoolProperty(name="Remove Doubles", default=True)
    bpy.types.Scene.DLImportNormals = bpy.props.BoolProperty(name="Import Normals", default=True)
    bpy.types.Scene.DLImportDrawLayer = bpy.props.EnumProperty(name="Draw Layer", items=ootEnumDrawLayers)
    bpy.types.Scene.DLImportOtherFiles = bpy.props.CollectionProperty(type=ImportFileProperty)
    bpy.types.Scene.DLImportOtherFilesIndex = bpy.props.IntProperty()


def f3d_parser_unregister():
    for cls in reversed(f3d_parser_classes):
        unregister_class(cls)

    del bpy.types.Scene.DLImportName
    del bpy.types.Scene.DLImportPath
    del bpy.types.Scene.DLRemoveDoubles
    del bpy.types.Scene.DLImportNormals
    del bpy.types.Scene.DLImportDrawLayer
    del bpy.types.Scene.DLImportBasePath
    del bpy.types.Scene.DLImportOtherFiles
    del bpy.types.Scene.DLImportOtherFilesIndex
