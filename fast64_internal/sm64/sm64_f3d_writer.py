import shutil, copy, bpy, re, os
from io import BytesIO
from math import ceil, log, radians
from mathutils import Matrix, Vector
from bpy.utils import register_class, unregister_class
from bpy.types import PropertyGroup, UILayout, World
from bpy.props import StringProperty, BoolProperty, CollectionProperty, IntProperty

from ..panels import SM64_Panel
from ..f3d.f3d_writer import exportF3DCommon
from ..f3d.f3d_texture_writer import TexInfo
from ..f3d.f3d_material import (
    TextureProperty,
    tmemUsageUI,
    all_combiner_uses,
    ui_procAnim,
    update_world_default_rendermode,
)
from .sm64_texscroll import modifyTexScrollFiles, modifyTexScrollHeadersGroup
from .sm64_utility import export_rom_checks, starSelectWarning, string_int_prop
from .sm64_level_parser import parseLevelAtPointer
from .sm64_rom_tweaks import ExtendBank0x04
from typing import Tuple, Union, Iterable

from ..f3d.f3d_bleed import BleedGraphics

from ..f3d.f3d_gbi import (
    get_F3D_GBI,
    GbiMacro,
    GfxTag,
    FMaterial,
    FModel,
    GfxFormatter,
    GfxMatWriteMethod,
    ScrollMethod,
    DLFormat,
    SPDisplayList,
    GfxList,
    GfxListTag,
    FTexRect,
    DPPipeSync,
    DPSetCycleType,
    DPSetTexturePersp,
    DPSetAlphaCompare,
    DPSetBlendColor,
    DPSetRenderMode,
    SPScisTextureRectangle,
    SPTexture,
    SPEndDisplayList,
    TextureExportSettings,
    FSetTileSizeScrollField,
    FImageKey,
    vertexScrollTemplate,
    get_tile_scroll_code,
    GFX_SIZE,
)

from ..utility import (
    CScrollData,
    PluginError,
    copyPropertyGroup,
    multilineLabel,
    raisePluginError,
    prop_split,
    draw_and_check_tab,
    encodeSegmentedAddr,
    applyRotation,
    toAlnum,
    checkIfPathExists,
    upgrade_old_prop,
    writeIfNotFound,
    overwriteData,
    getExportDir,
    writeMaterialFiles,
    writeMaterialHeaders,
    get64bitAlignedAddr,
    writeInsertableFile,
    getPathAndLevel,
    applyBasicTweaks,
    tempName,
    getAddressFromRAMAddress,
    bytesToHex,
    customExportWarning,
    decompFolderMessage,
    makeWriteInfoBox,
    writeBoxExportType,
    enumExportHeaderType,
    create_or_get_world,
)
from ..operators import OperatorBase

from .sm64_constants import (
    level_enums,
    enumLevelNames,
    level_pointers,
    defaultExtendSegment4,
    bank0Segment,
    insertableBinaryTypes,
)


enumHUDExportLocation = [
    ("HUD", "HUD", "Exports to src/game/hud.c"),
    ("Menu", "Menu", "Exports to src/game/ingame_menu.c"),
]

# filepath, function to insert before
enumHUDPaths = {
    "HUD": ("src/game/hud.c", "void render_hud(void)"),
    "Menu": ("src/game/ingame_menu.c", "s16 render_menus_and_dialogs()"),
}


class SM64Model(FModel):
    def __init__(self, name, DLFormat, matWriteMethod):
        FModel.__init__(self, name, DLFormat, matWriteMethod)
        self.no_light_direction = bpy.context.scene.fast64.sm64.matstack_fix
        self.draw_layers = create_or_get_world(bpy.context.scene).fast64.sm64.draw_layers
        if self.draw_layers.repeated_indices:
            raise PluginError(
                f"World draw layers have repeated indexes: " + self.draw_layers.repeated_indices_str.replace("\n", " ")
            )

    def getDrawLayerV3(self, obj):
        return int(obj.draw_layer_static)

    def getRenderMode(self, drawLayer):
        return self.draw_layers.layers_by_prop[drawLayer].preset


class SM64GfxFormatter(GfxFormatter):
    def __init__(self, scrollMethod: ScrollMethod):
        self.functionNodeDraw = False
        GfxFormatter.__init__(self, scrollMethod, 8, "segmented_to_virtual")

    def processGfxScrollCommand(self, commandIndex: int, command: GbiMacro, gfxListName: str) -> Tuple[str, str]:
        tags: GfxTag = command.tags
        fMaterial: FMaterial = command.fMaterial

        if not tags:
            return "", ""
        elif tags & (GfxTag.TileScroll0 | GfxTag.TileScroll1):
            textureIndex = 0 if tags & GfxTag.TileScroll0 else 1
            return get_tile_scroll_code(fMaterial.texture_DL.name, fMaterial.scrollData, textureIndex, commandIndex)
        else:
            return "", ""

    def vertexScrollToC(self, fMaterial: FMaterial, vtxListName: str, vtxCount: int) -> CScrollData:
        data = CScrollData()
        fScrollData = fMaterial.scrollData
        if fScrollData is None:
            return data

        data.source = vertexScrollTemplate(
            fScrollData,
            vtxListName,
            vtxCount,
            "absi",
            "signum_positive",
            "coss",
            "random_float",
            "random_sign",
            "segmented_to_virtual",
        )

        scrollDataFields = fScrollData.fields[0]
        if not ((scrollDataFields[0].animType == "None") and (scrollDataFields[1].animType == "None")):
            funcName = f"scroll_{vtxListName}"
            data.header = f"extern void {funcName}();\n"
            data.functionCalls.append(funcName)
        return data


def exportTexRectToC(dirPath, texProp, texDir, savePNG, name, exportToProject, projectExportData):
    fTexRect = exportTexRectCommon(texProp, name, not savePNG)

    if name is None or name == "":
        raise PluginError("Name cannot be empty.")

    exportData = fTexRect.to_c(savePNG, texDir, SM64GfxFormatter(ScrollMethod.Vertex))
    staticData = exportData.staticData
    dynamicData = exportData.dynamicData

    declaration = staticData.header
    code = modifyDLForHUD(dynamicData.source)
    data = staticData.source

    if exportToProject:
        seg2CPath = os.path.join(dirPath, "bin/segment2.c")
        seg2HPath = os.path.join(dirPath, "src/game/segment2.h")
        seg2TexDir = os.path.join(dirPath, "textures/segment2")
        hudPath = os.path.join(dirPath, projectExportData[0])

        checkIfPathExists(seg2CPath)
        checkIfPathExists(seg2HPath)
        checkIfPathExists(seg2TexDir)
        checkIfPathExists(hudPath)

        fTexRect.save_textures(seg2TexDir, not savePNG)

        textures = []
        for _, fImage in fTexRect.textures.items():
            textures.append(fImage)

        # Append/Overwrite texture definition to segment2.c
        overwriteData("const\s*u8\s*", textures[0].name, data, seg2CPath, None, False)

        # Append texture declaration to segment2.h
        writeIfNotFound(seg2HPath, declaration, "#endif")

        # Write/Overwrite function to hud.c
        overwriteData("void\s*", fTexRect.name, code, hudPath, projectExportData[1], True)

    else:
        singleFileData = ""
        singleFileData += "// Copy this function to src/game/hud.c or src/game/ingame_menu.c.\n"
        singleFileData += "// Call the function in render_hud() or render_menus_and_dialogs() respectively.\n"
        singleFileData += code
        singleFileData += "// Copy this declaration to src/game/segment2.h.\n"
        singleFileData += declaration
        singleFileData += "// Copy this texture data to bin/segment2.c\n"
        singleFileData += (
            "// If texture data is being included from an inc.c, make sure to copy the png to textures/segment2.\n"
        )
        singleFileData += data
        singleFilePath = os.path.join(dirPath, fTexRect.name + ".c")
        singleFile = open(singleFilePath, "w", newline="\n")
        singleFile.write(singleFileData)
        singleFile.close()

    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def modifyDLForHUD(data):
    # Use sm64 master dl pointer
    data = re.sub("glistp", "gDisplayListHead", data)

    # Add positional arguments to drawing, along with negative pos handling
    negativePosHandling = (
        "\ts32 xl = MAX(0, x);\n"
        + "\ts32 yl = MAX(0, y);\n"
        + "\ts32 xh = MAX(0, x + width - 1);\n"
        + "\ts32 yh = MAX(0, y + height - 1);\n"
        + "\ts = (x < 0) ? s - x : s;\n"
        + "\tt = (y < 0) ? t - y : t;\n"
    )

    data = re.sub(
        "Gfx\* gDisplayListHead\) \{\n",
        "s32 x, s32 y, s32 width, s32 height, s32 s, s32 t) {\n" + negativePosHandling,
        data,
    )

    # Remove display list end command and return value
    data = re.sub("\tgSPEndDisplayList\(gDisplayListHead\+\+\)\;\n\treturn gDisplayListHead;\n", "", data)
    data = "void" + data[4:]

    # Apply positional arguments to SPScisTextureRectangle
    matchResult = re.search(
        "gSPScisTextureRectangle\(gDisplayListHead\+\+\,"
        + " (((?!\,).)*)\, (((?!\,).)*)\, (((?!\,).)*)\, (((?!\,).)*)\, (((?!\,).)*)\, (((?!\,).)*)\, (((?!\,).)*)\,",
        data,
    )
    if matchResult:
        # data = data[:matchResult.start(0)] + \
        # 	'gSPScisTextureRectangle(gDisplayListHead++, (x << 2) + ' + \
        # 	matchResult.group(1) + ', (y << 2) + ' + \
        # 	matchResult.group(3) + ', (x << 2) + ' + \
        # 	matchResult.group(5) + ', (y << 2) + ' + \
        # 	matchResult.group(7) + ',' + data[matchResult.end(0):]
        data = (
            data[: matchResult.start(0)]
            + "gSPScisTextureRectangle(gDisplayListHead++, "
            + "xl << 2, yl << 2, xh << 2, yh << 2, "
            + matchResult.group(11)
            + ", s << 5, t << 5, "
            + data[matchResult.end(0) :]
        )

    # Make sure to convert segmented texture pointer to virtual
    # matchResult = re.search('gDPSetTextureImage\(gDisplayListHead\+\+\,' +\
    # 	'(((?!\,).)*)\, (((?!\,).)*)\, (((?!\,).)*)\, (((?!\,).)*)\)', data)
    # if matchResult:
    # 	data = data[:matchResult.start(7)] + 'segmented_to_virtual(&' + \
    # 		matchResult.group(7) + ")" +data[matchResult.end(7):]

    return data


def exportTexRectCommon(texProp, name, convertTextureData):
    tex = texProp.tex
    if tex is None:
        raise PluginError("No texture is selected.")

    texProp.S.low = 0
    texProp.S.high = texProp.tex.size[0] - 1
    texProp.S.mask = ceil(log(texProp.tex.size[0], 2) - 0.001)
    texProp.S.shift = 0

    texProp.T.low = 0
    texProp.T.high = texProp.tex.size[1] - 1
    texProp.T.mask = ceil(log(texProp.tex.size[1], 2) - 0.001)
    texProp.T.shift = 0

    fTexRect = FTexRect(toAlnum(name), GfxMatWriteMethod.WriteDifferingAndRevert)
    fMaterial = FMaterial(toAlnum(name) + "_mat", DLFormat.Dynamic)

    # dl_hud_img_begin
    fTexRect.draw.commands.extend(
        [
            DPPipeSync(),
            DPSetCycleType("G_CYC_COPY"),
            DPSetTexturePersp("G_TP_NONE"),
            DPSetAlphaCompare("G_AC_THRESHOLD"),
            DPSetBlendColor(0xFF, 0xFF, 0xFF, 0xFF),
            DPSetRenderMode(["G_RM_AA_XLU_SURF", "G_RM_AA_XLU_SURF2"], None),
        ]
    )

    drawEndCommands = GfxList("temp", GfxListTag.Draw, DLFormat.Dynamic)

    ti = TexInfo()
    if not ti.fromProp(texProp, 0):
        raise PluginError(f"In {name}: {texProp.errorMsg}.")
    if not ti.useTex:
        raise PluginError(f"In {name}: texture disabled.")
    if ti.isTexCI:
        raise PluginError(f"In {name}: CI textures not compatible with exportTexRectCommon (because copy mode).")
    if ti.tmemSize > 512:
        raise PluginError(f"In {name}: texture is too big (> 4 KiB).")
    if ti.texFormat != "RGBA16":
        raise PluginError(f"In {name}: texture format must be RGBA16 (because copy mode).")
    ti.imDependencies = [tex]
    ti.writeAll(fTexRect.draw, fMaterial, fTexRect, convertTextureData)

    fTexRect.draw.commands.append(
        SPScisTextureRectangle(0, 0, (texDimensions[0] - 1) << 2, (texDimensions[1] - 1) << 2, 0, 0, 0)
    )

    fTexRect.draw.commands.extend(drawEndCommands.commands)

    # dl_hud_img_end
    fTexRect.draw.commands.extend(
        [
            DPPipeSync(),
            DPSetCycleType("G_CYC_1CYCLE"),
            SPTexture(0xFFFF, 0xFFFF, 0, "G_TX_RENDERTILE", "G_OFF"),
            DPSetTexturePersp("G_TP_PERSP"),
            DPSetAlphaCompare("G_AC_NONE"),
            DPSetRenderMode(["G_RM_AA_ZB_OPA_SURF", "G_RM_AA_ZB_OPA_SURF2"], None),
            SPEndDisplayList(),
        ]
    )

    return fTexRect


def sm64ExportF3DtoC(
    basePath,
    obj,
    DLFormat,
    transformMatrix,
    texDir,
    savePNG,
    texSeparate,
    includeChildren,
    name,
    levelName,
    groupName,
    customExport,
    headerType,
):
    dirPath, texDir = getExportDir(customExport, basePath, headerType, levelName, texDir, name)

    inline = bpy.context.scene.exportInlineF3D
    fModel = SM64Model(
        name,
        DLFormat,
        GfxMatWriteMethod.WriteDifferingAndRevert if not inline else GfxMatWriteMethod.WriteAll,
    )
    fMeshes = exportF3DCommon(obj, fModel, transformMatrix, includeChildren, name, DLFormat, not savePNG)

    if inline:
        bleed_gfx = BleedGraphics()
        bleed_gfx.bleed_fModel(fModel, fMeshes)

    modelDirPath = os.path.join(dirPath, toAlnum(name))

    if not os.path.exists(modelDirPath):
        os.mkdir(modelDirPath)

    if headerType == "Actor":
        scrollName = "actor_dl_" + name
    elif headerType == "Level":
        scrollName = levelName + "_level_dl_" + name
    elif headerType == "Custom":
        scrollName = "dl_" + name

    gfxFormatter = SM64GfxFormatter(ScrollMethod.Vertex)
    exportData = fModel.to_c(TextureExportSettings(texSeparate, savePNG, texDir, modelDirPath), gfxFormatter)
    staticData = exportData.staticData
    dynamicData = exportData.dynamicData
    texC = exportData.textureData

    scrollData = fModel.to_c_scroll(scrollName, gfxFormatter)
    modifyTexScrollFiles(basePath, modelDirPath, scrollData)

    if DLFormat == DLFormat.Static:
        staticData.append(dynamicData)
    else:
        geoString = writeMaterialFiles(
            basePath,
            modelDirPath,
            '#include "actors/' + toAlnum(name) + '/header.h"',
            '#include "actors/' + toAlnum(name) + '/material.inc.h"',
            dynamicData.header,
            dynamicData.source,
            "",
            customExport,
        )

    if texSeparate:
        texCFile = open(os.path.join(modelDirPath, "texture.inc.c"), "w", newline="\n")
        texCFile.write(texC.source)
        texCFile.close()

    modelPath = os.path.join(modelDirPath, "model.inc.c")
    outFile = open(modelPath, "w", newline="\n")
    outFile.write(staticData.source)
    outFile.close()

    headerPath = os.path.join(modelDirPath, "header.h")
    cDefFile = open(headerPath, "w", newline="\n")
    cDefFile.write(staticData.header)
    cDefFile.close()

    fileStatus = None
    if not customExport:
        if headerType == "Actor":
            # Write to group files
            if groupName == "" or groupName is None:
                raise PluginError("Actor header type chosen but group name not provided.")

            groupPathC = os.path.join(dirPath, groupName + ".c")
            groupPathH = os.path.join(dirPath, groupName + ".h")

            writeIfNotFound(groupPathC, '\n#include "' + toAlnum(name) + '/model.inc.c"', "")
            writeIfNotFound(groupPathH, '\n#include "' + toAlnum(name) + '/header.h"', "\n#endif")

            if DLFormat != DLFormat.Static:  # Change this
                writeMaterialHeaders(
                    basePath,
                    '#include "actors/' + toAlnum(name) + '/material.inc.c"',
                    '#include "actors/' + toAlnum(name) + '/material.inc.h"',
                )

            texscrollIncludeC = '#include "actors/' + name + '/texscroll.inc.c"'
            texscrollIncludeH = '#include "actors/' + name + '/texscroll.inc.h"'
            texscrollGroup = groupName
            texscrollGroupInclude = '#include "actors/' + groupName + '.h"'

        elif headerType == "Level":
            groupPathC = os.path.join(dirPath, "leveldata.c")
            groupPathH = os.path.join(dirPath, "header.h")

            writeIfNotFound(groupPathC, '\n#include "levels/' + levelName + "/" + toAlnum(name) + '/model.inc.c"', "")
            writeIfNotFound(
                groupPathH, '\n#include "levels/' + levelName + "/" + toAlnum(name) + '/header.h"', "\n#endif"
            )

            if DLFormat != DLFormat.Static:  # Change this
                writeMaterialHeaders(
                    basePath,
                    '#include "levels/' + levelName + "/" + toAlnum(name) + '/material.inc.c"',
                    '#include "levels/' + levelName + "/" + toAlnum(name) + '/material.inc.h"',
                )

            texscrollIncludeC = '#include "levels/' + levelName + "/" + name + '/texscroll.inc.c"'
            texscrollIncludeH = '#include "levels/' + levelName + "/" + name + '/texscroll.inc.h"'
            texscrollGroup = levelName
            texscrollGroupInclude = '#include "levels/' + levelName + '/header.h"'

        fileStatus = modifyTexScrollHeadersGroup(
            basePath,
            texscrollIncludeC,
            texscrollIncludeH,
            texscrollGroup,
            scrollData.topLevelScrollFunc,
            texscrollGroupInclude,
            scrollData.hasScrolling(),
        )

    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    return fileStatus


def exportF3DtoBinary(romfile, exportRange, transformMatrix, obj, segmentData, includeChildren):
    fModel = SM64Model(obj.name, DLFormat, GfxMatWriteMethod.WriteDifferingAndRevert)
    fMeshes = exportF3DCommon(obj, fModel, transformMatrix, includeChildren, obj.name, DLFormat.Static, True)
    fMesh = fMeshes[fModel.getDrawLayerV3(obj)]
    fModel.freePalettes()

    addrRange = fModel.set_addr(exportRange[0])
    if addrRange[1] > exportRange[1]:
        raise PluginError(
            "Size too big: Data ends at " + hex(addrRange[1]) + ", which is larger than the specified range."
        )
    fModel.save_binary(romfile, segmentData)
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    segPointerData = encodeSegmentedAddr(fMesh.draw.startAddress, segmentData)

    return fMesh.draw.startAddress, addrRange, segPointerData


def exportF3DtoBinaryBank0(romfile, exportRange, transformMatrix, obj, RAMAddr, includeChildren):
    fModel = SM64Model(obj.name, DLFormat, GfxMatWriteMethod.WriteDifferingAndRevert)
    fMeshes = exportF3DCommon(obj, fModel, transformMatrix, includeChildren, obj.name, DLFormat.Static, True)
    fMesh = fMeshes[fModel.getDrawLayerV3(obj)]
    segmentData = copy.copy(bank0Segment)

    data, startRAM = getBinaryBank0F3DData(fModel, RAMAddr, exportRange)

    startAddress = get64bitAlignedAddr(exportRange[0])
    romfile.seek(startAddress)
    romfile.write(data)

    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    segPointerData = encodeSegmentedAddr(fMesh.draw.startAddress, segmentData)

    return (fMesh.draw.startAddress, (startAddress, startAddress + len(data)), segPointerData)


def exportF3DtoInsertableBinary(filepath, transformMatrix, obj, includeChildren):
    fModel = SM64Model(obj.name, DLFormat, GfxMatWriteMethod.WriteDifferingAndRevert)
    fMeshes = exportF3DCommon(obj, fModel, transformMatrix, includeChildren, obj.name, DLFormat.Static, True)
    fMesh = fMeshes[fModel.getDrawLayerV3(obj)]

    data, startRAM = getBinaryBank0F3DData(fModel, 0, [0, 0xFFFFFF])
    # must happen after getBinaryBank0F3DData
    address_ptrs = fModel.get_ptr_addresses(get_F3D_GBI())

    writeInsertableFile(filepath, insertableBinaryTypes["Display List"], address_ptrs, fMesh.draw.startAddress, data)


def getBinaryBank0F3DData(fModel, RAMAddr, exportRange):
    fModel.freePalettes()
    segmentData = copy.copy(bank0Segment)

    addrRange = fModel.set_addr(RAMAddr)
    if addrRange[1] - RAMAddr > exportRange[1] - exportRange[0]:
        raise PluginError(
            "Size too big: Data ends at " + hex(addrRange[1]) + ", which is larger than the specified range."
        )

    bytesIO = BytesIO()
    # actualRAMAddr = get64bitAlignedAddr(RAMAddr)
    bytesIO.seek(RAMAddr)
    fModel.save_binary(bytesIO, segmentData)
    data = bytesIO.getvalue()[RAMAddr:]
    bytesIO.close()
    return data, RAMAddr


class SM64_ExportDL(bpy.types.Operator):
    # set bl_ properties
    bl_idname = "object.sm64_export_dl"
    bl_label = "Export Display List"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        romfileOutput = None
        tempROM = None
        try:
            if context.mode != "OBJECT":
                raise PluginError("Operator can only be used in object mode.")
            allObjs = context.selected_objects
            if len(allObjs) == 0:
                raise PluginError("No objects selected.")
            obj = context.selected_objects[0]
            if obj.type != "MESH":
                raise PluginError("Object is not a mesh.")

            scaleValue = context.scene.fast64.sm64.blender_to_sm64_scale
            finalTransform = Matrix.Diagonal(Vector((scaleValue, scaleValue, scaleValue))).to_4x4()

        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        try:
            applyRotation([obj], radians(90), "X")
            if context.scene.fast64.sm64.export_type == "C":
                exportPath, levelName = getPathAndLevel(
                    context.scene.DLCustomExport,
                    context.scene.DLExportPath,
                    context.scene.DLLevelName,
                    context.scene.DLLevelOption,
                )
                if not context.scene.DLCustomExport:
                    applyBasicTweaks(exportPath)
                fileStatus = sm64ExportF3DtoC(
                    exportPath,
                    obj,
                    DLFormat.Static if context.scene.DLExportisStatic else DLFormat.Dynamic,
                    finalTransform,
                    bpy.context.scene.DLTexDir,
                    bpy.context.scene.saveTextures,
                    bpy.context.scene.DLSeparateTextureDef,
                    bpy.context.scene.DLincludeChildren,
                    bpy.context.scene.DLName,
                    levelName,
                    context.scene.DLGroupName,
                    context.scene.DLCustomExport,
                    context.scene.DLExportHeaderType,
                )

                starSelectWarning(self, fileStatus)
                self.report({"INFO"}, "Success!")

            elif context.scene.fast64.sm64.export_type == "Insertable Binary":
                exportF3DtoInsertableBinary(
                    bpy.path.abspath(context.scene.DLInsertableBinaryPath),
                    finalTransform,
                    obj,
                    bpy.context.scene.DLincludeChildren,
                )
                self.report({"INFO"}, "Success! DL at " + context.scene.DLInsertableBinaryPath + ".")
            else:
                export_rom_checks(bpy.path.abspath(context.scene.fast64.sm64.export_rom))
                tempROM = tempName(context.scene.fast64.sm64.output_rom)
                romfileExport = open(bpy.path.abspath(context.scene.fast64.sm64.export_rom), "rb")
                shutil.copy(bpy.path.abspath(context.scene.fast64.sm64.export_rom), bpy.path.abspath(tempROM))
                romfileExport.close()
                romfileOutput = open(bpy.path.abspath(tempROM), "rb+")

                levelParsed = parseLevelAtPointer(romfileOutput, level_pointers[context.scene.levelDLExport])
                segmentData = levelParsed.segmentData
                if context.scene.fast64.sm64.extend_bank_4:
                    ExtendBank0x04(romfileOutput, segmentData, defaultExtendSegment4)

                if context.scene.DLUseBank0:
                    startAddress, addrRange, segPointerData = exportF3DtoBinaryBank0(
                        romfileOutput,
                        [int(context.scene.DLExportStart, 16), int(context.scene.DLExportEnd, 16)],
                        finalTransform,
                        obj,
                        getAddressFromRAMAddress(int(context.scene.DLRAMAddr, 16)),
                        bpy.context.scene.DLincludeChildren,
                    )
                else:
                    startAddress, addrRange, segPointerData = exportF3DtoBinary(
                        romfileOutput,
                        [int(context.scene.DLExportStart, 16), int(context.scene.DLExportEnd, 16)],
                        finalTransform,
                        obj,
                        segmentData,
                        bpy.context.scene.DLincludeChildren,
                    )

                if context.scene.overwriteGeoPtr:
                    romfileOutput.seek(int(context.scene.DLExportGeoPtr, 16))
                    romfileOutput.write(segPointerData)

                romfileOutput.close()
                if os.path.exists(bpy.path.abspath(context.scene.fast64.sm64.output_rom)):
                    os.remove(bpy.path.abspath(context.scene.fast64.sm64.output_rom))
                os.rename(bpy.path.abspath(tempROM), bpy.path.abspath(context.scene.fast64.sm64.output_rom))

                if context.scene.DLUseBank0:
                    self.report(
                        {"INFO"},
                        "Success! DL at ("
                        + hex(addrRange[0])
                        + ", "
                        + hex(addrRange[1])
                        + "), "
                        + "to write to RAM address "
                        + hex(startAddress + 0x80000000),
                    )
                else:
                    self.report(
                        {"INFO"},
                        "Success! DL at ("
                        + hex(addrRange[0])
                        + ", "
                        + hex(addrRange[1])
                        + ") (Seg. "
                        + bytesToHex(segPointerData)
                        + ").",
                    )

            applyRotation([obj], radians(-90), "X")
            return {"FINISHED"}  # must return a set

        except Exception as e:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            applyRotation([obj], radians(-90), "X")
            if context.scene.fast64.sm64.export_type == "Binary":
                if romfileOutput is not None:
                    romfileOutput.close()
                if tempROM is not None and os.path.exists(bpy.path.abspath(tempROM)):
                    os.remove(bpy.path.abspath(tempROM))
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


class SM64_ExportDLPanel(SM64_Panel):
    bl_idname = "SM64_PT_export_dl"
    bl_label = "SM64 DL Exporter"
    goal = "Displaylist"

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        propsDLE = col.operator(SM64_ExportDL.bl_idname)

        if context.scene.fast64.sm64.export_type == "C":
            col.prop(context.scene, "DLExportisStatic")

            col.prop(context.scene, "DLCustomExport")
            if context.scene.DLCustomExport:
                col.prop(context.scene, "DLExportPath")
                prop_split(col, context.scene, "DLName", "Name")
                if context.scene.saveTextures:
                    prop_split(col, context.scene, "DLTexDir", "Texture Include Path")
                    col.prop(context.scene, "DLSeparateTextureDef")
                customExportWarning(col)
            else:
                prop_split(col, context.scene, "DLExportHeaderType", "Export Type")
                prop_split(col, context.scene, "DLName", "Name")
                if context.scene.DLExportHeaderType == "Actor":
                    prop_split(col, context.scene, "DLGroupName", "Group Name")
                elif context.scene.DLExportHeaderType == "Level":
                    prop_split(col, context.scene, "DLLevelOption", "Level")
                    if context.scene.DLLevelOption == "Custom":
                        prop_split(col, context.scene, "DLLevelName", "Level Name")
                if context.scene.saveTextures:
                    col.prop(context.scene, "DLSeparateTextureDef")

                decompFolderMessage(col)
                writeBox = makeWriteInfoBox(col)
                writeBoxExportType(
                    writeBox,
                    context.scene.DLExportHeaderType,
                    context.scene.DLName,
                    context.scene.DLLevelName,
                    context.scene.DLLevelOption,
                )

        elif context.scene.fast64.sm64.export_type == "Insertable Binary":
            col.prop(context.scene, "DLInsertableBinaryPath")
        else:
            prop_split(col, context.scene, "DLExportStart", "Start Address")
            prop_split(col, context.scene, "DLExportEnd", "End Address")
            col.prop(context.scene, "DLUseBank0")
            if context.scene.DLUseBank0:
                prop_split(col, context.scene, "DLRAMAddr", "RAM Address")
            else:
                col.prop(context.scene, "levelDLExport")
            col.prop(context.scene, "overwriteGeoPtr")
            if context.scene.overwriteGeoPtr:
                prop_split(col, context.scene, "DLExportGeoPtr", "Geolayout Pointer")
        col.prop(context.scene, "DLincludeChildren")


class ExportTexRectDraw(bpy.types.Operator):
    # set bl_ properties
    bl_idname = "object.f3d_texrect_draw"
    bl_label = "Export F3D Texture Rectangle"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        try:
            if context.scene.texrect.tex is None:
                raise PluginError("No texture selected.")
            else:
                if context.scene.TexRectCustomExport:
                    exportPath = context.scene.TexRectExportPath
                else:
                    if context.scene.fast64.sm64.decomp_path == "":
                        raise PluginError("Decomp path has not been set in File Settings.")
                    exportPath = context.scene.fast64.sm64.decomp_path
                if not context.scene.TexRectCustomExport:
                    applyBasicTweaks(exportPath)
                exportTexRectToC(
                    bpy.path.abspath(exportPath),
                    context.scene.texrect,
                    "textures/segment2",
                    context.scene.saveTextures,
                    context.scene.TexRectName,
                    not context.scene.TexRectCustomExport,
                    enumHUDPaths[context.scene.TexRectExportType],
                )

                self.report({"INFO"}, "Success!")
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}
        return {"FINISHED"}  # must return a set


class UnlinkTexRect(bpy.types.Operator):
    bl_idname = "image.texrect_unlink"
    bl_label = "Unlink TexRect Image"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        context.scene.texrect.tex = None
        return {"FINISHED"}  # must return a set


class ExportTexRectDrawPanel(SM64_Panel):
    bl_idname = "TEXTURE_PT_export_texrect"
    bl_label = "SM64 UI Image Exporter"
    goal = "UI Image"
    decomp_only = True

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        propsTexRectE = col.operator(ExportTexRectDraw.bl_idname)

        textureProp = context.scene.texrect
        tex = textureProp.tex
        col.label(text="This is for decomp only.")
        col.template_ID(textureProp, "tex", new="image.new", open="image.open", unlink="image.texrect_unlink")
        # col.prop(textureProp, 'tex')

        tmemUsageUI(col, textureProp)
        if tex is not None and tex.size[0] > 0 and tex.size[1] > 0:
            col.prop(textureProp, "tex_format", text="Format")
            if textureProp.tex_format[:2] == "CI":
                col.prop(textureProp, "ci_format", text="CI Format")
            col.prop(textureProp.S, "clamp", text="Clamp S")
            col.prop(textureProp.T, "clamp", text="Clamp T")
            col.prop(textureProp.S, "mirror", text="Mirror S")
            col.prop(textureProp.T, "mirror", text="Mirror T")

        prop_split(col, context.scene, "TexRectName", "Name")
        col.prop(context.scene, "TexRectCustomExport")
        if context.scene.TexRectCustomExport:
            col.prop(context.scene, "TexRectExportPath")
            customExportWarning(col)
        else:
            prop_split(col, context.scene, "TexRectExportType", "Export Type")
            if not context.scene.TexRectCustomExport:
                decompFolderMessage(col)
                writeBox = makeWriteInfoBox(col)
                writeBox.label(text="bin/segment2.c")
                writeBox.label(text="src/game/segment2.h")
                writeBox.label(text="textures/segment2")
            infoBox = col.box()
            infoBox.label(text="After export, call your hud's draw function in ")
            infoBox.label(text=enumHUDPaths[context.scene.TexRectExportType][0] + ": ")
            infoBox.label(text=enumHUDPaths[context.scene.TexRectExportType][1] + ".")


class SM64_DrawLayersPanel(bpy.types.Panel):
    bl_label = "SM64 Draw Layers"
    bl_idname = "WORLD_PT_SM64_Draw_Layers_Panel"
    bl_parent_id = "WORLD_PT_RDP_Default_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "world"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "SM64" and context.scene.world is not None

    def draw(self, context):
        col = self.layout.column()
        draw_layer_props = context.scene.world.fast64.sm64.draw_layers
        if draw_and_check_tab(col, draw_layer_props, "tab"):
            draw_layer_props.draw_props(col)


class SM64_MaterialPanel(bpy.types.Panel):
    bl_label = "SM64 Material"
    bl_idname = "MATERIAL_PT_SM64_Material_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.material is not None and context.material.is_f3d and context.scene.gameEditorMode == "SM64"

    def draw(self, context):
        layout = self.layout
        material = context.material
        col = layout.column()

        if material.mat_ver > 3:
            f3dMat = material.f3d_mat
        else:
            f3dMat = material
        useDict = all_combiner_uses(f3dMat)

        if useDict["Texture"]:
            ui_procAnim(material, col, useDict["Texture 0"], useDict["Texture 1"], "SM64 UV Texture Scroll", False)


class SM64_DrawLayerOps(OperatorBase):
    bl_idname = "scene.sm64_draw_layer_ops"
    bl_label = ""
    bl_description = "Move, remove, clear or add draw layers to the world"
    bl_options = {"UNDO"}

    index: IntProperty()
    op_name: StringProperty()

    def execute_operator(self, context):
        layer_props: SM64_DrawLayersProperties = context.scene.world.fast64.sm64.draw_layers
        if layer_props.lock:
            raise PluginError("Draw layer operators are locked by default, unlock them by disabling the lock icon")
        layers = layer_props.layers
        if self.op_name == "ADD":
            layers.add()
            added_layer = layers[-1]
            copyPropertyGroup(layers[self.index], added_layer)
            layers.move(len(layers) - 1, self.index + 1)
        elif self.op_name == "REMOVE":  # Upgrade all materials once this runs
            layer_props.layers.remove(self.index)


class SM64_DrawLayerProperties(PropertyGroup):
    name: StringProperty(name="Name", default="Custom")
    enum: StringProperty(name="Enum", default="LAYER_CUSTOM")
    str_index: StringProperty(name="Index", default="0x08", update=update_world_default_rendermode)
    cycle_1: StringProperty(name="", default="G_RM_AA_ZB_OPA_SURF", update=update_world_default_rendermode)
    cycle_2: StringProperty(name="", default="G_RM_AA_ZB_OPA_SURF2", update=update_world_default_rendermode)

    @property
    def preset(self):
        return [self.cycle_1, self.cycle_2]

    @property
    def index(self):
        return int(self.str_index, 0)

    def to_dict(self):
        return {"enum": self.enum, "index": self.str_index, "preset": self.preset}

    def from_dict(self, data: dict):
        self.enum = data.get("enum", "LAYER_CUSTOM")
        self.str_index = data.get("index", "0x08")
        self.cycle_1, self.cycle_2 = data.get("preset", ["G_RM_AA_ZB_OPA_SURF", "G_RM_AA_ZB_OPA_SURF2"])

    def draw_props(self, layout: UILayout):
        col = layout.column()
        prop_split(col, self, "name", "Name")

        row = col.row()
        row.prop(self, "enum")
        string_int_prop(row, self, "str_index", "Index", split=False)

        split = col.split(factor=0.18)
        split.label(text="Render Mode:")
        row = split.row()
        row.prop(self, "cycle_1")
        row.prop(self, "cycle_2")


class SM64_DrawLayersProperties(PropertyGroup):
    internal_defaults_set: BoolProperty()
    tab: BoolProperty(name="Draw Layers")
    lock: BoolProperty(
        name="",
        default=True,
        description="(This feature is for advanced users, use at your own risk)\n"
        "Disable the lock to remove or add new draw layers.",
    )
    layers: CollectionProperty(type=SM64_DrawLayerProperties)

    @property
    def repeated_indices(self) -> dict:
        indices, repeated_indices = {}, {}
        for layer in self.layers:
            if layer.index in indices:
                repeated_indices[layer.index] = indices[layer.index]
                indices[layer.index].append(layer)
            else:
                indices[layer.index] = [layer]
        return repeated_indices

    @property
    def repeated_indices_str(self) -> str:
        return "\n".join(
            f"{index}: [{', '.join([layer.name for layer in layers])}]"
            for index, layers in self.repeated_indices.items()
        )

    @property
    def layers_by_enum(self):
        return {layer.enum: layer for layer in self.layers}

    @property
    def layers_by_prop(self):
        return {str(layer.index): layer for layer in self.layers}

    @property
    def layers_by_index(self):
        return {layer.index: layer for layer in self.layers}

    def from_dict(self, data: dict):
        self.layers.clear()
        for name, layer in data.items():
            self.layers.add()
            self.layers[-1].from_dict(layer)
            self.layers[-1].name = name

    def to_dict(self):
        layers = {}
        layer: SM64_DrawLayerProperties
        for layer in self.layers:
            layers[layer.name] = layer.to_dict()
        return layers

    def to_enum(self):
        return [
            (
                str(layer.index),
                f"{name} ({layer.str_index})",
                f"{layer.enum} ({layer.str_index})\n{layer.cycle_1}, {layer.cycle_2}",
                layer.index,
            )
            for name, layer in self.layers.items()
        ]

    def populate(self, world: World | None = None):
        """If a world is passed in, try to upgrade properties from it"""
        if self.internal_defaults_set:
            return
        default_draw_layer_info = {
            "Background": {
                "enum": "LAYER_FORCE",
                "index": "0x00",
                "preset": ["G_RM_ZB_OPA_SURF", "G_RM_ZB_OPA_SURF2"],
            },
            "Opaque": {
                "enum": "LAYER_OPAQUE",
                "index": "0x01",
                "preset": ["G_RM_AA_ZB_OPA_SURF", "G_RM_AA_ZB_OPA_SURF2"],
            },
            "Opaque Decal": {
                "enum": "LAYER_OPAQUE_DECAL",
                "index": "0x02",
                "preset": ["G_RM_AA_ZB_OPA_DECAL", "G_RM_AA_ZB_OPA_DECAL2"],
            },
            "Opaque Intersecting": {
                "enum": "LAYER_OPAQUE_INTER",
                "index": "0x03",
                "preset": ["G_RM_AA_ZB_OPA_INTER", "G_RM_AA_ZB_OPA_INTER2"],
            },
            "Cutout": {
                "enum": "LAYER_ALPHA",
                "index": "0x04",
                "preset": ["G_RM_AA_ZB_TEX_EDGE", "G_RM_AA_ZB_TEX_EDGE2"],
            },
            "Transparent": {
                "enum": "LAYER_TRANSPARENT",
                "index": "0x05",
                "preset": ["G_RM_AA_ZB_XLU_SURF", "G_RM_AA_ZB_XLU_SURF2"],
            },
            "Transparent Decal": {
                "enum": "LAYER_TRANSPARENT_DECAL",
                "index": "0x06",
                "preset": ["G_RM_AA_ZB_XLU_DECAL", "G_RM_AA_ZB_XLU_DECAL2"],
            },
            "Transparent Intersecting": {
                "enum": "LAYER_TRANSPARENT_INTER",
                "index": "0x07",
                "preset": ["G_RM_AA_ZB_XLU_INTER", "G_RM_AA_ZB_XLU_INTER2"],
            },
        }
        self.from_dict(default_draw_layer_info)

        if world is not None:
            for i, layer in self.layers_by_index.items():
                upgrade_old_prop(layer, "cycle_1", world, f"draw_layer_{i}_cycle_1")
                upgrade_old_prop(layer, "cycle_2", world, f"draw_layer_{i}_cycle_2")
        self.internal_defaults_set = True

    @staticmethod
    def upgrade_changed_props():
        for world in bpy.data.worlds:
            world.fast64.sm64.draw_layers.populate(world)

    def draw_props(self, layout: UILayout):
        col = layout.column()
        multilineLabel(
            col,
            "(This feature is for advanced users, use at your own risk)\n"
            "Disable the lock to remove or add new draw layers.",
            icon="ERROR",
        )
        col.row().prop(self, "lock", icon="LOCKED" if self.lock else "UNLOCKED")
        if not self.lock:
            col.separator()
            multilineLabel(
                col,
                "These won´t modify your repo's draw layers automatically!\n"
                "Tip: Use repo settings and custom presets to streamline your\n"
                "custom draw layer.",
                icon="INFO",
            )
        layers_col = col.column()
        layers_col.enabled = not self.lock

        if self.repeated_indices:
            col.separator()
            error_box = layers_col.box()
            error_box.alert = True
            multilineLabel(error_box, text=f"Repeated indices:\n{self.repeated_indices_str}", icon="ERROR")
            col.separator()

        draw_layer: SM64_DrawLayerProperties
        # Enumerate, then sort by index
        for i, draw_layer in sorted(enumerate(self.layers), key=lambda layer: layer[1].index):
            layer_box = layers_col.box().column()
            if draw_layer.index in self.repeated_indices:
                bad_layers = self.repeated_indices[draw_layer.index]
                bad_layers.remove(draw_layer)
                layer_box.alert = True
                layer_box.box().label(
                    text=f"Duplicate index at {', '.join(layer.name for layer in bad_layers)}", icon="ERROR"
                )
            row = layer_box.row()
            SM64_DrawLayerOps.draw_props(row, "ADD", op_name="ADD", index=i)
            SM64_DrawLayerOps.draw_props(row, "REMOVE", op_name="REMOVE", index=i)
            draw_layer.draw_props(layer_box)


def populate_draw_layers(scene):
    if scene.world is not None:
        scene.world.fast64.sm64.draw_layers.populate()


sm64_dl_writer_classes = (
    SM64_DrawLayerOps,
    SM64_DrawLayerProperties,
    SM64_DrawLayersProperties,
    SM64_ExportDL,
    ExportTexRectDraw,
    UnlinkTexRect,
)

sm64_dl_writer_panel_classes = (
    SM64_MaterialPanel,
    SM64_DrawLayersPanel,
    SM64_ExportDLPanel,
    ExportTexRectDrawPanel,
)


def sm64_dl_writer_panel_register():
    for cls in sm64_dl_writer_panel_classes:
        register_class(cls)


def sm64_dl_writer_panel_unregister():
    for cls in sm64_dl_writer_panel_classes:
        unregister_class(cls)


def sm64_dl_writer_register():
    for cls in sm64_dl_writer_classes:
        register_class(cls)

    bpy.types.Scene.DLExportStart = bpy.props.StringProperty(name="Start", default="11D8930")
    bpy.types.Scene.DLExportEnd = bpy.props.StringProperty(name="End", default="11FFF00")
    bpy.types.Scene.levelDLExport = bpy.props.EnumProperty(items=level_enums, name="Level", default="WF")
    bpy.types.Scene.DLExportGeoPtr = bpy.props.StringProperty(name="Geolayout Pointer", default="132AA8")
    bpy.types.Scene.overwriteGeoPtr = bpy.props.BoolProperty(name="Overwrite geolayout pointer", default=False)
    bpy.types.Scene.DLExportPath = bpy.props.StringProperty(name="Directory", subtype="FILE_PATH")
    bpy.types.Scene.DLExportisStatic = bpy.props.BoolProperty(name="Static DL", default=True)
    bpy.types.Scene.DLDefinePath = bpy.props.StringProperty(name="Definitions Filepath", subtype="FILE_PATH")
    bpy.types.Scene.DLUseBank0 = bpy.props.BoolProperty(name="Use Bank 0")
    bpy.types.Scene.DLRAMAddr = bpy.props.StringProperty(name="RAM Address", default="80000000")
    bpy.types.Scene.DLTexDir = bpy.props.StringProperty(name="Include Path", default="levels/bob")
    bpy.types.Scene.DLSeparateTextureDef = bpy.props.BoolProperty(name="Save texture.inc.c separately")
    bpy.types.Scene.DLincludeChildren = bpy.props.BoolProperty(name="Include Children")
    bpy.types.Scene.DLInsertableBinaryPath = bpy.props.StringProperty(name="Filepath", subtype="FILE_PATH")
    bpy.types.Scene.DLName = bpy.props.StringProperty(name="Name", default="mario")
    bpy.types.Scene.DLCustomExport = bpy.props.BoolProperty(name="Custom Export Path")
    bpy.types.Scene.DLExportHeaderType = bpy.props.EnumProperty(
        items=enumExportHeaderType, name="Header Export", default="Actor"
    )
    bpy.types.Scene.DLGroupName = bpy.props.StringProperty(name="Group Name", default="group0")
    bpy.types.Scene.DLLevelName = bpy.props.StringProperty(name="Level", default="bob")
    bpy.types.Scene.DLLevelOption = bpy.props.EnumProperty(items=enumLevelNames, name="Level", default="bob")

    bpy.types.Scene.texrect = bpy.props.PointerProperty(type=TextureProperty)
    bpy.types.Scene.texrectImageTexture = bpy.props.PointerProperty(type=bpy.types.ImageTexture)
    bpy.types.Scene.TexRectExportPath = bpy.props.StringProperty(name="Export Path", subtype="FILE_PATH")
    bpy.types.Scene.TexRectTexDir = bpy.props.StringProperty(name="Include Path", default="textures/segment2")
    bpy.types.Scene.TexRectName = bpy.props.StringProperty(name="Name", default="render_hud_image")
    bpy.types.Scene.TexRectCustomExport = bpy.props.BoolProperty(name="Custom Export Path")
    bpy.types.Scene.TexRectExportType = bpy.props.EnumProperty(name="Export Type", items=enumHUDExportLocation)

    bpy.app.handlers.depsgraph_update_post.append(populate_draw_layers)


def sm64_dl_writer_unregister():
    for cls in reversed(sm64_dl_writer_classes):
        unregister_class(cls)

    del bpy.types.Scene.levelDLExport
    del bpy.types.Scene.DLExportStart
    del bpy.types.Scene.DLExportEnd
    del bpy.types.Scene.DLExportGeoPtr
    del bpy.types.Scene.overwriteGeoPtr
    del bpy.types.Scene.DLExportPath
    del bpy.types.Scene.DLExportisStatic
    del bpy.types.Scene.DLDefinePath
    del bpy.types.Scene.DLUseBank0
    del bpy.types.Scene.DLRAMAddr
    del bpy.types.Scene.DLTexDir
    del bpy.types.Scene.DLSeparateTextureDef
    del bpy.types.Scene.DLincludeChildren
    del bpy.types.Scene.DLInsertableBinaryPath
    del bpy.types.Scene.DLName
    del bpy.types.Scene.DLCustomExport
    del bpy.types.Scene.DLExportHeaderType
    del bpy.types.Scene.DLGroupName
    del bpy.types.Scene.DLLevelName
    del bpy.types.Scene.DLLevelOption

    del bpy.types.Scene.texrect
    del bpy.types.Scene.TexRectExportPath
    del bpy.types.Scene.TexRectTexDir
    del bpy.types.Scene.TexRectName
    del bpy.types.Scene.texrectImageTexture
    del bpy.types.Scene.TexRectCustomExport
    del bpy.types.Scene.TexRectExportType

    if populate_draw_layers in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(populate_draw_layers)
